(function attachBrowserAsrSessionManager(global) {
  "use strict";

  class BrowserAsrSessionManager {
    constructor(options) {
      this.options = options || {};
      this.state = this.options.state || {};
      this.SpeechRecognitionCtor = this.options.SpeechRecognitionCtor || null;
      this.socketReconnectDelayMs = 1000;
      this.fastRearmDelayMs = 60;
      this.watchdogIntervalMs = 2000;
      this.visibleWatchdogIdleMs = 30000;
      this.hiddenWatchdogIdleMs = 60000;
      this.minWatchdogRearmGapMs = 12000;
      this._watchdogTimer = null;
    }

    _appendLog(message) {
      this.options.appendLog?.(message);
    }

    _setStatus(status) {
      this.options.setStatus?.(status);
    }

    _updateCounters() {
      this.options.updateCounters?.();
    }

    _now() {
      return Date.now();
    }

    _getRecognitionSettings() {
      return this.options.getRecognitionSettings?.() || {};
    }

    _isForceFinalizationEnabled() {
      return this.options.isForceFinalizationEnabled?.() !== false;
    }

    _clearForceFinalizeTimer() {
      if (this.state.forceFinalizeTimer) {
        clearTimeout(this.state.forceFinalizeTimer);
        this.state.forceFinalizeTimer = null;
      }
    }

    _sendUpdate(payload) {
      const socket = this.state.socket;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        this._setStatus("waiting-for-websocket");
        this._appendLog("partial/final skipped: websocket is not open");
        return false;
      }
      socket.send(
        JSON.stringify({
          type: "external_asr_update",
          partial: payload.partial || "",
          final: payload.final || "",
          is_final: Boolean(payload.is_final),
          source_lang: payload.source_lang || this.state.sourceLang,
        })
      );
      this.state.appSendCount = Number(this.state.appSendCount || 0) + 1;
      this._updateCounters();
      return true;
    }

    _scheduleForceFinalize() {
      this._clearForceFinalizeTimer();
      if (!this._isForceFinalizationEnabled() || !this.state.currentPartial) {
        return;
      }
      this.state.forceFinalizeTimer = window.setTimeout(() => {
        if (!this.state.currentPartial) {
          return;
        }
        this.state.missingFinalCount = Number(this.state.missingFinalCount || 0) + 1;
        this.state.forcedCount = Number(this.state.forcedCount || 0) + 1;
        const finalText = this.state.currentPartial;
        this._sendUpdate({
          partial: finalText,
          final: finalText,
          is_final: true,
          source_lang: this.state.sourceLang,
        });
        this.options.setFinalText?.(finalText);
        this.options.setPartialText?.("");
        this.state.currentPartial = "";
        this.state.hasOpenSentence = false;
        this._updateCounters();
        this._setStatus("forced-finalized");
      }, Number(this.state.forceFinalizationTimeoutMs || 1600));
    }

    _emitWorkerStatus(reason) {
      const socket = this.state.socket;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        return;
      }
      const now = this._now();
      try {
        socket.send(
          JSON.stringify({
            type: "browser_asr_status",
            reason: String(reason || "").trim() || null,
            desired_running: Boolean(this.state.desiredRunning),
            recognition_running: this.state.recognitionState === "running",
            recognition_state: this.state.recognitionState || "idle",
            websocket_ready: Boolean(this.state.websocketReady),
            last_error: this._buildLastError(),
            error_type: String(this.state.lastErrorCode || "").trim().toLowerCase() || null,
            rearm_count: Number(this.state.rearmCount || 0),
            restart_count: Number(this.state.restartCount || 0),
            watchdog_rearm_count: Number(this.state.watchdogRearmCount || 0),
            rearm_delay_ms: Number(this.state.lastRearmDelayMs || 0),
            last_partial_age_ms: this.state.lastPartialAt
              ? Math.max(0, now - Number(this.state.lastPartialAt || 0))
              : null,
            last_final_age_ms: this.state.lastFinalAt
              ? Math.max(0, now - Number(this.state.lastFinalAt || 0))
              : null,
            degraded_reason: this.state.degradedReason || null,
            visibility_state: this._currentVisibilityState(),
          })
        );
      } catch (_error) {
        // best effort
      }
    }

    _buildLastError() {
      const code = String(this.state.lastErrorCode || "").trim();
      const message = String(this.state.lastErrorMessage || "").trim();
      if (code && message) {
        return `${code}: ${message}`;
      }
      return code || message || null;
    }

    _currentVisibilityState() {
      return document.hidden ? "hidden" : "visible";
    }

    _setDegradedReason(reason) {
      const nextReason = String(reason || "").trim() || null;
      if (this.state.degradedReason === nextReason) {
        return;
      }
      this.state.degradedReason = nextReason;
      this._emitWorkerStatus("degraded");
    }

    handleVisibilityChange() {
      this.state.visibilityState = this._currentVisibilityState();
      if (!this.state.desiredRunning) {
        this._setDegradedReason(null);
      } else if (document.hidden) {
        this._setDegradedReason("document_hidden");
      } else if (this.state.degradedReason === "document_hidden") {
        this._setDegradedReason(null);
      }
      this._emitWorkerStatus("visibility");
    }

    applyRecognitionSettings() {
      if (!this.state.recognition) {
        return;
      }
      const settings = this._getRecognitionSettings();
      this.state.recognition.lang = settings.language || "ru-RU";
      this.state.recognition.interimResults = settings.interimResults !== false;
      this.state.recognition.continuous = settings.continuous !== false;
    }

    maybeRestartAfterSettingsChange() {
      if (!this.state.desiredRunning || !this.state.recognition) {
        return;
      }
      this._appendLog("worker settings changed; restarting recognition to apply them immediately");
      this.state.restartRequestedAfterStop = true;
      this._clearForceFinalizeTimer();
      this._clearRestartTimer();
      if (this.state.recognitionState === "stopping") {
        return;
      }
      this.state.recognitionState = "stopping";
      this._updateCounters();
      this._setStatus("restarting");
      try {
        this.state.recognition.stop();
      } catch (_error) {
        this.state.recognitionState = "idle";
        window.setTimeout(() => {
          this.state.restartRequestedAfterStop = false;
          this._tryStartRecognition({ reason: "settings-change-fallback", useBackoff: false });
        }, 120);
      }
    }

    _isTerminalRecognitionError(errorCode, errorMessage) {
      const code = String(errorCode || "").trim().toLowerCase();
      const message = String(errorMessage || "").trim().toLowerCase();
      if (["not-allowed", "service-not-allowed", "language-not-supported"].includes(code)) {
        return true;
      }
      return message.includes("permission") && (message.includes("denied") || message.includes("not allowed"));
    }

    _markActivity(label) {
      this.state.lastAudioActivityAt = this._now();
      this.state.lastRecognitionEventAt = this.state.lastAudioActivityAt;
      this.state.consecutiveStartFailures = 0;
      if (this.state.degradedReason === "watchdog_rearm" || this.state.degradedReason === "repeated_start_failures") {
        this._setDegradedReason(null);
      }
      this._appendLog(`audio activity: ${label}`);
    }

    _clearRestartTimer() {
      if (this.state.restartTimer) {
        clearTimeout(this.state.restartTimer);
        this.state.restartTimer = null;
      }
    }

    _restartDelayMs(useBackoff) {
      if (!useBackoff) {
        return this.fastRearmDelayMs;
      }
      const failures = Math.max(0, Number(this.state.consecutiveStartFailures || 0) - 1);
      return Math.min(5000, 400 + failures * 450);
    }

    _scheduleRecognitionRestart(reason, options) {
      const useBackoff = Boolean(options?.useBackoff);
      this._clearRestartTimer();
      if (!this.state.desiredRunning) {
        this._appendLog(`restart skipped: desiredRunning=false (${reason})`);
        return;
      }
      if (this.state.recognitionState === "starting" || this.state.recognitionState === "running") {
        this._appendLog(`restart skipped: recognition already ${this.state.recognitionState} (${reason})`);
        return;
      }
      if (this._isTerminalRecognitionError(this.state.lastErrorCode, this.state.lastErrorMessage)) {
        this.state.desiredRunning = false;
        this._setDegradedReason("permission_denied");
        this._appendLog(`restart cancelled due to terminal error: ${this.state.lastErrorCode || "permission denied"}`);
        this._setStatus(
          this.options.locale?.() === "ru"
            ? `остановлено: ошибка ${this.state.lastErrorCode || "доступ запрещён"}`
            : `stopped: ${this.state.lastErrorCode || "permission denied"}`
        );
        this._emitWorkerStatus("terminal-error");
        return;
      }
      const delayMs = this._restartDelayMs(useBackoff);
      this.state.restartCount = Number(this.state.restartCount || 0) + 1;
      this.state.lastRearmDelayMs = delayMs;
      if (useBackoff && this.state.consecutiveStartFailures >= 3) {
        this._setDegradedReason("repeated_start_failures");
      } else if (document.hidden) {
        this._setDegradedReason("document_hidden");
      }
      this._appendLog(`restart scheduled in ${delayMs} ms (${reason})`);
      this._setStatus("restarting");
      this._emitWorkerStatus("restart-scheduled");
      this.state.restartTimer = window.setTimeout(() => {
        this._tryStartRecognition({ reason, useBackoff });
      }, delayMs);
    }

    _ensureRecognition() {
      if (!this.SpeechRecognitionCtor) {
        throw new Error(
          this.options.locale?.() === "ru"
            ? "Этот браузер не предоставляет SpeechRecognition / webkitSpeechRecognition."
            : "This browser does not expose SpeechRecognition / webkitSpeechRecognition."
        );
      }
      if (this.state.recognition) {
        this.applyRecognitionSettings();
        return this.state.recognition;
      }
      const recognition = new this.SpeechRecognitionCtor();
      recognition.maxAlternatives = 1;
      recognition.onstart = () => {
        this.state.recognitionState = "running";
        this.state.restartRequestedAfterStop = false;
        this.state.lastErrorCode = "";
        this.state.lastErrorMessage = "";
        this.state.lastRecognitionStartAt = this._now();
        this.state.lastRecognitionEventAt = this.state.lastRecognitionStartAt;
        this._appendLog("recognition.onstart");
        this._setStatus("listening");
        this._setDegradedReason(document.hidden ? "document_hidden" : null);
        this._updateCounters();
        this._emitWorkerStatus("recognition-started");
      };
      recognition.onaudiostart = () => {
        this._appendLog("recognition.onaudiostart");
        this._setStatus("capturing-audio");
      };
      recognition.onaudioend = () => {
        this._appendLog("recognition.onaudioend");
      };
      recognition.onsoundstart = () => {
        this.state.onSound = true;
        this._markActivity("onsoundstart");
        this._appendLog("recognition.onsoundstart");
        this._updateCounters();
      };
      recognition.onsoundend = () => {
        this.state.onSound = false;
        this._appendLog("recognition.onsoundend");
        this._updateCounters();
      };
      recognition.onspeechstart = () => {
        this._markActivity("onspeechstart");
        this._appendLog("recognition.onspeechstart");
      };
      recognition.onspeechend = () => {
        this._appendLog("recognition.onspeechend");
        this._updateCounters();
      };
      recognition.onnomatch = () => {
        this._appendLog("recognition.onnomatch");
      };
      recognition.onerror = (event) => {
        this.state.lastErrorCode = String(event?.error || "").trim().toLowerCase();
        this.state.lastErrorMessage = String(event?.message || "");
        this._appendLog(`recognition.onerror: ${this.state.lastErrorCode || "unknown"} ${this.state.lastErrorMessage}`.trim());
        if (this._isTerminalRecognitionError(this.state.lastErrorCode, this.state.lastErrorMessage)) {
          this._setDegradedReason("permission_denied");
        } else if (this.state.lastErrorCode === "audio-capture") {
          this._setDegradedReason("audio_capture_recovery");
        }
        this._setStatus(
          this.options.locale?.() === "ru"
            ? `ошибка: ${event?.error || "неизвестно"}`
            : `error: ${event?.error || "unknown"}`
        );
        this._emitWorkerStatus("recognition-error");
      };
      recognition.onend = () => {
        const restartAfterStop = this.state.restartRequestedAfterStop;
        this.state.recognitionState = "idle";
        this.state.restartRequestedAfterStop = false;
        this.state.onSound = false;
        this._updateCounters();
        this._appendLog(
          `recognition.onend (desiredRunning=${this.state.desiredRunning}, restartAfterStop=${restartAfterStop}, lastError=${this.state.lastErrorCode || "none"})`
        );
        this._emitWorkerStatus("recognition-ended");
        if (!this.state.desiredRunning) {
          this._setStatus("stopped");
          return;
        }
        if (restartAfterStop) {
          this.state.rearmCount = Number(this.state.rearmCount || 0) + 1;
          window.setTimeout(() => {
            this._tryStartRecognition({ reason: "restart-after-stop", useBackoff: false });
          }, 80);
          return;
        }
        this.state.rearmCount = Number(this.state.rearmCount || 0) + 1;
        this._scheduleRecognitionRestart("onend", { useBackoff: false });
      };
      recognition.onresult = (event) => {
        let interimText = "";
        let finalText = "";
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index];
          const transcript = String(result?.[0]?.transcript || "").trim();
          if (!transcript) {
            continue;
          }
          if (result.isFinal) {
            finalText = `${finalText} ${transcript}`.trim();
          } else {
            interimText = `${interimText} ${transcript}`.trim();
          }
        }
        this.state.lastRecognitionEventAt = this._now();
        if (interimText) {
          this.state.lastPartialAt = this._now();
          this._markActivity("onresult:interim");
          if (!this.state.hasOpenSentence) {
            this.state.approxCount = Number(this.state.approxCount || 0) + 1;
            this.state.hasOpenSentence = true;
          }
          this.state.currentPartial = interimText;
          this.options.setPartialText?.(interimText);
          this._sendUpdate({
            partial: interimText,
            final: "",
            is_final: false,
            source_lang: this.state.sourceLang,
          });
          this._scheduleForceFinalize();
          this._setStatus("interim");
        }
        if (finalText) {
          this._markActivity("onresult:final");
          this._clearForceFinalizeTimer();
          this.state.finalCount = Number(this.state.finalCount || 0) + 1;
          this.state.currentPartial = "";
          this.state.hasOpenSentence = false;
          this.state.lastFinalAt = this._now();
          this.options.setFinalText?.(finalText);
          this.options.setPartialText?.("");
          this._sendUpdate({
            partial: "",
            final: finalText,
            is_final: true,
            source_lang: this.state.sourceLang,
          });
          this._updateCounters();
          this._setStatus("final");
        }
      };
      this.state.recognition = recognition;
      this.applyRecognitionSettings();
      return recognition;
    }

    async _tryStartRecognition(options) {
      if (!this.state.desiredRunning) {
        return;
      }
      if (this.state.recognitionState === "starting" || this.state.recognitionState === "running") {
        this._appendLog(`recognition.start skipped: already ${this.state.recognitionState}`);
        return;
      }
      if (this.state.recognitionState === "stopping") {
        this._appendLog("recognition.start deferred: recognition is stopping");
        return;
      }
      try {
        const recognition = this._ensureRecognition();
        this.ensureSocketConnected();
        this.applyRecognitionSettings();
        this.state.recognitionState = "starting";
        this._appendLog(
          `recognition.start lang=${recognition.lang}, interim=${recognition.interimResults}, continuous=${recognition.continuous}`
        );
        if (options?.reason && options.reason !== "user-start") {
          this._emitWorkerStatus("restart-executed");
        }
        recognition.start();
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : this.options.locale?.() === "ru"
              ? "Не удалось запустить браузерное распознавание."
              : "Could not start browser speech recognition.";
        const normalizedMessage = String(message).toLowerCase();
        if (normalizedMessage.includes("already started")) {
          this.state.recognitionState = "running";
          this._appendLog(`recognition.start skipped: ${message}`);
          this._setStatus("listening");
          return;
        }
        this.state.recognitionState = "idle";
        this.state.consecutiveStartFailures = Number(this.state.consecutiveStartFailures || 0) + 1;
        this._appendLog(`recognition.start failed: ${message}`);
        this._setStatus(message);
        this._scheduleRecognitionRestart(options?.reason || "start failed", { useBackoff: true });
      }
    }

    ensureSocketConnected() {
      const socket = this.state.socket;
      if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        return;
      }
      this._clearReconnectTimer();
      const protocol = location.protocol === "https:" ? "wss" : "ws";
      const nextSocket = new WebSocket(`${protocol}://${location.host}/ws/asr_worker`);
      this.state.socket = nextSocket;
      nextSocket.addEventListener("open", () => {
        this.state.websocketReady = true;
        this._updateCounters();
        this._appendLog("websocket connected");
        this._setStatus(this.state.desiredRunning ? "ready" : "idle");
        if (this.state.degradedReason === "websocket_disconnected") {
          this._setDegradedReason(document.hidden ? "document_hidden" : null);
        }
        this._emitWorkerStatus("socket-open");
        if (this.state.desiredRunning && this.state.recognitionState === "idle") {
          this._scheduleRecognitionRestart("socket-open", { useBackoff: false });
        }
      });
      nextSocket.addEventListener("close", () => {
        this.state.websocketReady = false;
        this._updateCounters();
        this._appendLog("websocket closed");
        if (this.state.desiredRunning) {
          this._setStatus("socket-reconnecting");
          this._setDegradedReason("websocket_disconnected");
          this.state.reconnectTimer = window.setTimeout(() => this.ensureSocketConnected(), this.socketReconnectDelayMs);
        }
      });
      nextSocket.addEventListener("error", () => {
        this.state.websocketReady = false;
        this._updateCounters();
        this._appendLog("websocket error");
        this._setStatus("socket-error");
        if (this.state.desiredRunning) {
          this._setDegradedReason("websocket_disconnected");
        }
      });
    }

    _clearReconnectTimer() {
      if (this.state.reconnectTimer) {
        clearTimeout(this.state.reconnectTimer);
        this.state.reconnectTimer = null;
      }
    }

    async start() {
      if (!this.SpeechRecognitionCtor) {
        this._setStatus("unsupported-browser");
        return;
      }
      this.state.desiredRunning = true;
      this.state.restartRequestedAfterStop = false;
      this.state.lastErrorCode = "";
      this.state.lastErrorMessage = "";
      this.state.consecutiveStartFailures = 0;
      this._clearRestartTimer();
      this.ensureSocketConnected();
      this._emitWorkerStatus("start-requested");
      try {
        await this.options.ensureMicrophonePermission?.();
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : this.options.locale?.() === "ru"
              ? "Доступ к микрофону не был выдан."
              : "Microphone permission was denied.";
        this._appendLog(`microphone permission failed: ${message}`);
        this._setStatus(this.options.locale?.() === "ru" ? `ошибка микрофона: ${message}` : `mic-error: ${message}`);
        this.state.desiredRunning = false;
        this._setDegradedReason("permission_denied");
        this._emitWorkerStatus("microphone-permission-failed");
        return;
      }
      this._startWatchdog();
      await this._tryStartRecognition({ reason: "user-start", useBackoff: false });
    }

    stop() {
      this._appendLog("stop requested by user");
      this.state.desiredRunning = false;
      this.state.restartRequestedAfterStop = false;
      this._clearForceFinalizeTimer();
      this._clearRestartTimer();
      this._stopWatchdog();
      this.state.currentPartial = "";
      this.state.hasOpenSentence = false;
      this.options.setPartialText?.("");
      if (this.state.recognition) {
        this.state.recognitionState = "stopping";
        try {
          this.state.recognition.stop();
        } catch (_error) {
          this.state.recognitionState = "idle";
        }
      }
      this._setDegradedReason(null);
      this._setStatus("stopping");
      this._emitWorkerStatus("user-stop");
    }

    handleForceFinalizationSettingChange() {
      if (!this._isForceFinalizationEnabled()) {
        this._clearForceFinalizeTimer();
        return;
      }
      if (this.state.currentPartial) {
        this._scheduleForceFinalize();
      }
    }

    _startWatchdog() {
      this._stopWatchdog();
      this._watchdogTimer = window.setInterval(() => this._runWatchdog(), this.watchdogIntervalMs);
    }

    _stopWatchdog() {
      if (this._watchdogTimer) {
        clearInterval(this._watchdogTimer);
        this._watchdogTimer = null;
      }
    }

    _runWatchdog() {
      if (!this.state.desiredRunning) {
        return;
      }
      if (this.state.recognitionState === "starting" || this.state.recognitionState === "stopping") {
        return;
      }
      const now = this._now();
      const lastActivityAt = Math.max(
        Number(this.state.lastRecognitionEventAt || 0),
        Number(this.state.lastAudioActivityAt || 0),
        Number(this.state.lastRecognitionStartAt || 0)
      );
      const idleMs = now - lastActivityAt;
      const idleThresholdMs = document.hidden ? this.hiddenWatchdogIdleMs : this.visibleWatchdogIdleMs;
      if (idleMs < idleThresholdMs) {
        return;
      }
      if (now - Number(this.state.lastWatchdogRearmAt || 0) < this.minWatchdogRearmGapMs) {
        return;
      }
      this.state.lastWatchdogRearmAt = now;
      this.state.rearmCount = Number(this.state.rearmCount || 0) + 1;
      this.state.watchdogRearmCount = Number(this.state.watchdogRearmCount || 0) + 1;
      this._appendLog(`watchdog forced rearm after ${idleMs} ms idle`);
      this._setDegradedReason(document.hidden ? "document_hidden" : "watchdog_rearm");
      this._emitWorkerStatus("watchdog-rearm");
      if (this.state.recognition && this.state.recognitionState === "running") {
        this.state.restartRequestedAfterStop = true;
        this.state.recognitionState = "stopping";
        try {
          this.state.recognition.stop();
          return;
        } catch (_error) {
          this.state.recognitionState = "idle";
        }
      }
      this._scheduleRecognitionRestart("watchdog", { useBackoff: false });
    }
  }

  global.BrowserAsrSessionManager = BrowserAsrSessionManager;
})(window);
