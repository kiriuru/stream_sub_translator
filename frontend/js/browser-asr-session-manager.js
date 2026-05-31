(function attachBrowserAsrSessionManager(global) {
  "use strict";

  const ASR = global.SstBrowserAsr || {};

  class BrowserAsrSessionManager {
    constructor(options) {
      this.options = options || {};
      this.state = this.options.state || {};
      this.SpeechRecognitionCtor = this.options.SpeechRecognitionCtor || null;
      if (typeof ASR.applyInstanceDefaults === "function") {
        ASR.applyInstanceDefaults(this);
      }
      /** Dedupes noisy recognition.start lines during no-speech / tight onend loops (~max 850/h per key). */
      this.recognitionStartLogMinGapMs = Number(this.recognitionStartLogMinGapMs || 4200);
      this._appendLogThrottleState = null;
      this._watchdogTimer = null;
      this._permissionPromise = null;
      this._socketListenersAttached = false;
      this._wakeLockSentinel = null;
      this._wakeLockBound = false;
      this._wakeLockRetryTimer = null;
      this._initializeState();
    }

    _initializeState() {
      if (typeof ASR.initializeBrowserAsrState === "function") {
        ASR.initializeBrowserAsrState(this.state, this.state);
        return;
      }
      throw new Error("SstBrowserAsr session-state module is required");
    }

    _timingLimits() {
      return {
        restartDelayByReasonMs: this.restartDelayByReasonMs,
        initialNoSpeechDelayMs: this.initialNoSpeechDelayMs,
        maxNoSpeechDelayMs: this.maxNoSpeechDelayMs,
        initialNetworkBackoffMs: this.initialNetworkBackoffMs,
        maxNetworkBackoffMs: this.maxNetworkBackoffMs,
        networkPreflightBurstThreshold: this.networkPreflightBurstThreshold,
        networkPreflightBurstWindowMs: this.networkPreflightBurstWindowMs,
        networkPreflightCooldownMs: this.networkPreflightCooldownMs,
        micSilentDegradedAfterMs: this.micSilentDegradedAfterMs,
        voiceBelowRecognitionRmsThreshold: this.voiceBelowRecognitionRmsThreshold,
        voiceBelowRecognitionGraceMs: this.voiceBelowRecognitionGraceMs,
        voiceBelowRecognitionMicWindowMs: this.voiceBelowRecognitionMicWindowMs,
        voiceBelowRecognitionMinNoSpeech: this.voiceBelowRecognitionMinNoSpeech,
        stallDegradedAfterMs: this.stallDegradedAfterMs,
        recentMicActivityWindowMs: this.recentMicActivityWindowMs,
      };
    }

    _appendLog(message) {
      this.options.appendLog?.(message);
    }

    _appendLogThrottled(message, throttleKey, minGapMs) {
      if (!throttleKey || !minGapMs) {
        this._appendLog(message);
        return;
      }
      const now = this._now();
      if (!this._appendLogThrottleState) {
        this._appendLogThrottleState = new Map();
      }
      if (ASR.shouldThrottleAppendLog?.(this._appendLogThrottleState, throttleKey, minGapMs, now)) {
        return;
      }
      this._appendLog(message);
      ASR.recordThrottledAppendLog?.(this._appendLogThrottleState, throttleKey, now);
    }

    _recognitionStartBurstThrottle(reason) {
      if (typeof ASR.recognitionStartBurstThrottle === "function") {
        return ASR.recognitionStartBurstThrottle(reason, this.recognitionStartLogMinGapMs);
      }
      return { gapMs: 4200, key: null };
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

    _locale() {
      return this.options.locale?.() || "en";
    }

    _getRecognitionSettings() {
      return this.options.getRecognitionSettings?.() || {};
    }

    _webSpeechPolicy() {
      const root = typeof globalThis !== "undefined" ? globalThis : typeof window !== "undefined" ? window : null;
      return root && root.SSTWebSpeechRecognitionPolicy ? root.SSTWebSpeechRecognitionPolicy : null;
    }

    _recognitionOverlapModeDesired() {
      return ASR.recognitionOverlapModeDesired(this._getRecognitionSettings(), this._webSpeechPolicy());
    }

    _recognitionOverlapActive() {
      return ASR.recognitionOverlapActive(this.state);
    }

    _overlapResultAllowed(overlapSlotIndex) {
      return ASR.overlapResultAllowed(this.state, overlapSlotIndex);
    }

    _applyChromeCompatHintsToRecognition(recognition) {
      if (!recognition || !this.state.webSpeechPhraseHintsSuppressed) {
        return;
      }
      const policy = this._webSpeechPolicy();
      if (policy && typeof policy.stripChromeOnDeviceHints === "function") {
        policy.stripChromeOnDeviceHints(recognition);
      }
    }

    _stripWebSpeechExperimentalHints(recognition) {
      const policy = this._webSpeechPolicy();
      if (policy && typeof policy.stripChromeOnDeviceHints === "function") {
        policy.stripChromeOnDeviceHints(recognition);
      }
    }

    _isForceFinalizationEnabled() {
      return this.options.isForceFinalizationEnabled?.() !== false;
    }

    _currentVisibilityState() {
      return document.hidden ? "hidden" : "visible";
    }

    _currentSessionAgeMs(nowMs = this._now()) {
      return ASR.currentSessionAgeMs?.(this.state, nowMs) ?? null;
    }

    _resetCycleState() {
      this.state.browserCyclePending = false;
    }

    _minimumReconnectGuardDelayMs(delayMs) {
      return ASR.minimumReconnectGuardDelayMs?.(
        this.state,
        delayMs,
        this._now(),
        this.minimumReconnectIntervalMs
      ) ?? delayMs;
    }

    _canForceFinalizeOnInterruption() {
      return Boolean(
        ASR.canForceFinalizeOnInterruption?.(this.state, this._isForceFinalizationEnabled())
      );
    }

    _forceFinalizeOnInterruption(reason) {
      if (!this._canForceFinalizeOnInterruption()) {
        return false;
      }
      const finalText = this._normalizeTranscriptText(this.state.currentPartial);
      const clientSegmentId = this.state.currentClientSegmentId || this._ensureClientSegmentId();
      if (this._shouldSuppressFinal(finalText, { forcedFinal: true })) {
        return false;
      }
      this._clearForceFinalizeTimer();
      this.state.missingFinalCount = Number(this.state.missingFinalCount || 0) + 1;
      this.state.forcedCount = Number(this.state.forcedCount || 0) + 1;
      this.state.browserForcedFinalOnInterruptionCount = Number(this.state.browserForcedFinalOnInterruptionCount || 0) + 1;
      this.state.currentSegmentLastFinalText = finalText;
      this.state.currentSegmentForcedFinalized = true;
      this.state.lastForcedFinal = {
        generation_id: this._currentGenerationId(),
        client_segment_id: clientSegmentId,
        text: finalText,
        reason: String(reason || "browser_recognition_interrupted"),
        at_ms: this._now(),
      };
      this.state.currentPartial = "";
      this.state.currentPartialStableSinceMs = 0;
      this.options.setFinalText?.(finalText);
      this.options.setPartialText?.("");
      this._sendUpdate({
        partial: finalText,
        final: finalText,
        is_final: true,
        source_lang: this.state.sourceLang,
        client_segment_id: clientSegmentId,
        forced_final: true,
        forced_final_reason: String(reason || "browser_recognition_interrupted"),
      });
      this._setStatus("forced-finalized");
      this._updateCounters();
      return true;
    }

    _clearForceFinalizeTimer() {
      if (this.state.forceFinalizeTimer) {
        clearTimeout(this.state.forceFinalizeTimer);
        this.state.forceFinalizeTimer = null;
      }
    }

    _clearRestartTimer() {
      if (this.state.restartTimer) {
        clearTimeout(this.state.restartTimer);
        this.state.restartTimer = null;
      }
    }

    _clearReconnectTimer() {
      if (this.state.reconnectTimer) {
        clearTimeout(this.state.reconnectTimer);
        this.state.reconnectTimer = null;
      }
    }

    _clearAllTimers() {
      this._clearForceFinalizeTimer();
      this._clearRestartTimer();
      this._clearReconnectTimer();
    }

    _setSupervisorState(nextState) {
      if (this.state.browserSupervisorState === nextState) {
        return;
      }
      this.state.browserSupervisorState = nextState;
      this._emitWorkerStatus("supervisor-state");
      this._updateCounters();
    }

    _setRecognitionState(nextState) {
      this.state.recognitionState = nextState;
      this._updateCounters();
    }

    _setDegradedReason(reason) {
      const normalized = String(reason || "").trim() || null;
      if (this.state.degradedReason === normalized) {
        return;
      }
      this.state.degradedReason = normalized;
      this._emitWorkerStatus("degraded");
    }

    _setTerminalDegradedReason(reason) {
      this.state.terminalDegradedReason = String(reason || "").trim() || null;
      this._refreshDegradedReason();
    }

    _setHealthDegradedReason(reason) {
      this.state.healthDegradedReason = String(reason || "").trim() || null;
      this._refreshDegradedReason();
    }

    _refreshDegradedReason() {
      this._setDegradedReason(ASR.resolveDegradedReason?.(this.state) || null);
    }

    _setLastError(kind, message) {
      this.state.lastErrorKind = String(kind || "").trim().toLowerCase() || null;
      this.state.lastError = String(message || "").trim() || null;
    }

    _markActivity(label) {
      const nowMs = this._now();
      if (label === "result") {
        ASR.markResultActivity?.(this.state, nowMs);
        ASR.resetNetworkErrorBurst?.(this.state);
        return;
      }
      this.state.lastEventAtMs = nowMs;
    }

    _resetSegmentTracking() {
      ASR.resetSegmentTrackingFields?.(this.state);
      this._clearForceFinalizeTimer();
    }

    _currentGenerationId() {
      return ASR.currentGenerationId?.(this.state) ?? 0;
    }

    _ensureClientSegmentId() {
      return ASR.ensureClientSegmentId?.(this.state) || null;
    }

    _consumeCompletedSegment() {
      ASR.consumeCompletedSegment?.(this.state);
    }

    _normalizeTranscriptText(value) {
      return ASR.normalizeTranscriptText?.(value) ?? "";
    }

    _restartDelayForReason(reason) {
      return ASR.restartDelayForReason?.(this.state, reason, this._timingLimits()) ?? 350;
    }

    _shouldSuppressDuplicatePartial(text) {
      const suppressed = Boolean(ASR.shouldSuppressDuplicatePartial?.(this.state, text));
      if (suppressed) {
        this._emitWorkerStatus("duplicate-partial");
      }
      return suppressed;
    }

    _shouldSuppressFinal(text, options = {}) {
      const beforeLate = Number(this.state.lateForcedFinalSuppressed || 0);
      const beforeDup = Number(this.state.duplicateFinalSuppressed || 0);
      const suppressed = Boolean(ASR.shouldSuppressFinal?.(this.state, text, options));
      if (suppressed) {
        if (Number(this.state.lateForcedFinalSuppressed || 0) > beforeLate) {
          this._emitWorkerStatus("late-forced-final");
        } else if (Number(this.state.duplicateFinalSuppressed || 0) > beforeDup) {
          this._emitWorkerStatus("duplicate-final");
        }
      }
      return suppressed;
    }

    _buildUpdatePayload(payload) {
      return ASR.buildTranscriptUpdatePayload?.(this.state, payload, this._now()) || {};
    }

    async reloadSettingsFromBackend() {
      if (typeof this.options.loadBackendSettings !== "function") {
        return;
      }
      await this.options.loadBackendSettings();
      this._emitWorkerStatus("settings-reloaded");
    }

    _refreshHealthSignals() {
      const reason = ASR.computeHealthDegradedReason?.({
        state: this.state,
        nowMs: this._now(),
        documentHidden: Boolean(document.hidden),
        limits: this._timingLimits(),
      });
      this._setHealthDegradedReason(reason || null);
    }

    _buildLastError() {
      return ASR.buildLastError?.(this.state) || null;
    }

    _buildWorkerPayload(type, extra) {
      return (
        ASR.buildWorkerPayload?.({
          state: this.state,
          type,
          extra,
          nowMs: this._now(),
          visibilityState: this._currentVisibilityState(),
          browserSessionAgeMs: this._currentSessionAgeMs(),
          wakeLockSupported: ASR.hasWakeLockSupport(),
        }) || {}
      );
    }

    _emitWorkerStatus(reason) {
      const socket = this.state.socket;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        return false;
      }
      try {
        socket.send(
          JSON.stringify(
            this._buildWorkerPayload("browser_asr_status", {
              reason: String(reason || "").trim() || null,
            })
          )
        );
        return true;
      } catch (_error) {
        return false;
      }
    }

    _emitHeartbeat(reason) {
      const socket = this.state.socket;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        return;
      }
      try {
        socket.send(
          JSON.stringify(
            this._buildWorkerPayload("browser_asr_heartbeat", {
              reason: String(reason || "").trim() || "heartbeat",
            })
          )
        );
      } catch (_error) {
        // best effort
      }
    }

    _sendUpdate(payload) {
      const socket = this.state.socket;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        this._setStatus("waiting-for-websocket");
        return false;
      }
      try {
        socket.send(JSON.stringify(this._buildWorkerPayload("external_asr_update", this._buildUpdatePayload(payload))));
        this.state.appSendCount = Number(this.state.appSendCount || 0) + 1;
        this._updateCounters();
        return true;
      } catch (_error) {
        return false;
      }
    }

    _scheduleForceFinalize() {
      this._clearForceFinalizeTimer();
      if (!this._isForceFinalizationEnabled() || !this.state.currentPartial) {
        return;
      }
      this.state.forceFinalizeTimer = window.setTimeout(() => {
        if (!this.state.currentPartial || !this.state.desiredRunning) {
          return;
        }
        const finalText = this.state.currentPartial;
        const clientSegmentId = this._ensureClientSegmentId();
        if (this._shouldSuppressFinal(finalText, { forcedFinal: true })) {
          this.state.currentPartial = "";
          this.state.hasOpenSentence = false;
          this.options.setPartialText?.("");
          return;
        }
        this.state.missingFinalCount = Number(this.state.missingFinalCount || 0) + 1;
        this.state.forcedCount = Number(this.state.forcedCount || 0) + 1;
        this._sendUpdate({
          partial: finalText,
          final: finalText,
          is_final: true,
          source_lang: this.state.sourceLang,
          client_segment_id: clientSegmentId,
          forced_final: true,
        });
        this.state.currentSegmentLastFinalText = this._normalizeTranscriptText(finalText);
        this.state.currentSegmentForcedFinalized = true;
        this.state.lastForcedFinal = {
          generation_id: this._currentGenerationId(),
          client_segment_id: clientSegmentId,
          text: finalText,
          at_ms: this._now(),
        };
        this.state.currentPartial = "";
        this.state.hasOpenSentence = false;
        this.options.setFinalText?.(finalText);
        this.options.setPartialText?.("");
        this._setStatus("forced-finalized");
        this._updateCounters();
      }, Number(this.state.forceFinalizationTimeoutMs || 1600));
    }

    applyRecognitionSettings() {
      const settings = this._getRecognitionSettings();
      this.state.configuredLanguage = settings.language || this.state.configuredLanguage || "ru-RU";
      this.state.sourceLang = String(this.state.configuredLanguage.split("-", 1)[0] || "ru").toLowerCase();
      this.state.providerName = String(settings.providerName || this.state.browserMode || "browser_google");
      this.state.actualContinuous = settings.continuous !== false;
      this.state.effectiveContinuousMode = this.state.actualContinuous ? "native_continuous" : "segmented_restart";
      this.state.minimumReconnectIntervalMs = Math.max(100, Number(settings.minimumReconnectIntervalMs || this.state.minimumReconnectIntervalMs || 500));
      this.state.normalRestartDelayMs = Math.max(0, Number(settings.normalRestartDelayMs || this.state.normalRestartDelayMs || 350));
      this.state.noSpeechRestartDelayMs = Math.max(0, Number(settings.noSpeechRestartDelayMs || this.state.noSpeechRestartDelayMs || 350));
      this.state.networkReconnectInitialMs = Math.max(100, Number(settings.networkReconnectInitialMs || this.state.networkReconnectInitialMs || 1000));
      this.state.networkReconnectMaxMs = Math.max(
        this.state.networkReconnectInitialMs,
        Number(settings.networkReconnectMaxMs || this.state.networkReconnectMaxMs || 30000)
      );
      this.state.maxBrowserSessionAgeMs = Math.max(10000, Number(settings.maxBrowserSessionAgeMs || this.state.maxBrowserSessionAgeMs || 180000));
      this.state.prepareCycleBeforeMs = Math.max(0, Number(settings.prepareCycleBeforeMs || this.state.prepareCycleBeforeMs || 15000));
      this.state.forceFinalOnInterruption = settings.forceFinalOnInterruption !== false;
      this.state.forceFinalMinChars = Math.max(1, Number(settings.forceFinalMinChars || this.state.forceFinalMinChars || 3));
      this.state.forceFinalMinStableMs = Math.max(0, Number(settings.forceFinalMinStableMs || this.state.forceFinalMinStableMs || 700));
      this.restartDelayByReasonMs.normal_onend = this.state.normalRestartDelayMs;
      this.restartDelayByReasonMs.settings_change = this.state.normalRestartDelayMs;
      this.restartDelayByReasonMs.websocket_reconnect = this.state.normalRestartDelayMs;
      this.restartDelayByReasonMs.session_cycle = this.state.normalRestartDelayMs;
      this.initialNoSpeechDelayMs = this.state.noSpeechRestartDelayMs;
      this.initialNetworkBackoffMs = this.state.networkReconnectInitialMs;
      this.maxNetworkBackoffMs = this.state.networkReconnectMaxMs;
      this.maxStoppingMs = Math.max(500, Number(settings.stuckStoppingTimeoutMs || this.state.stuckStoppingTimeoutMs || this.maxStoppingMs));
      this.state.stuckStoppingTimeoutMs = this.maxStoppingMs;
      const targets = [];
      if (this._recognitionOverlapActive()) {
        this.state.recognitionOverlapSlots.forEach((slot) => {
          if (slot) {
            targets.push(slot);
          }
        });
      } else if (this.state.recognition) {
        targets.push(this.state.recognition);
      }
      if (!targets.length) {
        this._updateCounters();
        return;
      }
      targets.forEach((recognition) => {
        recognition.lang = this.state.configuredLanguage;
        recognition.interimResults = settings.interimResults !== false;
        recognition.continuous = this.state.actualContinuous;
        this._applyChromeCompatHintsToRecognition(recognition);
      });
      this._updateCounters();
    }

    maybeRestartAfterSettingsChange(reason = "settings_change") {
      if (!this.state.desiredRunning) {
        return;
      }
      this._appendLog("worker settings changed; controlled restart requested");
      this.state.pendingStart = true;
      this.state.pendingRestartReason = String(reason || "settings_change");
      this._transitionToStopping("settings-change");
    }

    async start() {
      if (!this.SpeechRecognitionCtor) {
        this._setStatus("unsupported-browser");
        return;
      }
      this.state.desiredRunning = true;
      this._clearRestartTimer();
      this.ensureSocketConnected();
      this._startWatchdog();
      if (this.state.browserSupervisorState === "fatal") {
        this._appendLog("start ignored: supervisor is in fatal state");
        return;
      }
      if (this.state.browserSupervisorState === "running" || this.state.browserSupervisorState === "starting") {
        this._appendLog(`duplicate start ignored (${this.state.browserSupervisorState})`);
        return;
      }
      if (this.state.browserSupervisorState === "stopping") {
        this.state.pendingStart = true;
        this._appendLog("recognition.start deferred: recognition is stopping");
        this._emitWorkerStatus("start-deferred");
        return;
      }
      if (this.state.browserSupervisorState === "restarting" || this.state.browserSupervisorState === "backoff") {
        this.state.pendingStart = true;
        this._appendLog("start requested while restart/backoff is already scheduled");
        return;
      }
      try {
        await this._ensureMicrophonePermission();
      } catch (error) {
        const message = error instanceof Error ? error.message : "Microphone permission was denied.";
        this._setLastError("not-allowed", message);
        this.state.desiredRunning = false;
        this._setSupervisorState("fatal");
        this._setStatus(
          (global.I18n?.t ? global.I18n.t("browser_asr.mic_error_status", { message }) : `mic-error: ${message}`)
        );
        this._setTerminalDegradedReason("permission_denied");
        this._emitWorkerStatus("microphone-permission-failed");
        return;
      }
      const proceed = await this._waitUntilDocumentVisibleForRecognition();
      if (!proceed || !this.state.desiredRunning) {
        if (!this.state.desiredRunning) {
          this._appendLog("start aborted while waiting for visibility/focus");
        }
        return;
      }
      this.state.pendingStart = false;
      this._setTerminalDegradedReason(null);
      this._resetNetworkErrorBurst();
      this._acquireWakeLock("user-start");
      this.state.webSpeechPhraseHintsSuppressed = false;
      this.state.webSpeechLanguageSoftFallbackUsed = false;
      this._performControlledStart("user-start");
    }

    stop() {
      this._appendLog("stop requested by user");
      this.state.desiredRunning = false;
      this.state.pendingStart = false;
      this.state.generationId = Number(this.state.generationId || 0) + 1;
      this.state.webSpeechPhraseHintsSuppressed = false;
      this.state.webSpeechLanguageSoftFallbackUsed = false;
      this._resetCycleState();
      this._clearAllTimers();
      this.state.currentPartial = "";
      this.state.currentPartialStableSinceMs = 0;
      this.state.hasOpenSentence = false;
      this.state.stoppingSinceMs = this._now();
      this.state.pendingRestartReason = null;
      this.state.noSpeechBackoffMs = 0;
      this.state.restartBackoffMs = 0;
      this._resetSegmentTracking();
      this._resetNetworkErrorBurst();
      this._setTerminalDegradedReason(null);
      this.state.socketDegraded = false;
      this.state.visibilityDegraded = false;
      this._refreshDegradedReason();
      this.options.setPartialText?.("");
      this._transitionToStopping("user-stop");
      this._releaseWakeLock("user-stop");
      this._emitWorkerStatus("user-stop");
    }

    destroy() {
      this.stop();
      this._stopWatchdog();
      this._releaseWakeLock("destroy");
      this._appendLogThrottleState = null;
      const socket = this.state.socket;
      this.state.socket = null;
      this.state.websocketReady = false;
      if (socket && socket.readyState <= WebSocket.OPEN) {
        try {
          socket.close();
        } catch (_error) {
          // best effort
        }
      }
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

    handleVisibilityChange() {
      this.state.visibilityDegraded = Boolean(document.hidden && this.state.desiredRunning);
      this._refreshDegradedReason();
      const supervisor = this.state.browserSupervisorState;
      const startupInFlight =
        supervisor === "starting" || supervisor === "stopping";
      if (
        !document.hidden
        && this.state.desiredRunning
        && supervisor !== "running"
        && !startupInFlight
      ) {
        this._scheduleRestart("websocket_reconnect");
      }
      if (!document.hidden) {
        this._refreshHealthSignals();
        if (this.state.desiredRunning && !this.state.wakeLockActive) {
          this._acquireWakeLock("visibility-visible");
        }
      }
      this._emitWorkerStatus("visibility");
    }

    ensureSocketConnected() {
      const socket = this.state.socket;
      if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        return;
      }
      this._clearReconnectTimer();
      const nextSocket = new WebSocket(ASR.buildAsrWorkerWebSocketUrl());
      this.state.socket = nextSocket;
      ASR.attachSocketListeners(this, nextSocket);
    }

    _handleSocketMessage(raw) {
      const control = ASR.parseBrowserAsrControlMessage(raw);
      if (!control) {
        return;
      }
      if (control.action === "stop") {
        this.stop();
        return;
      }
      if (control.action === "reload_settings") {
        this.reloadSettingsFromBackend();
      }
    }

    _hasWakeLockSupport() {
      return ASR.hasWakeLockSupport();
    }

    async _acquireWakeLock(reason) {
      return ASR.acquireWakeLock(this, reason);
    }

    async _releaseWakeLock(reason) {
      return ASR.releaseWakeLock(this, reason);
    }

    _shouldRunNetworkPreflight(nowMs) {
      return Boolean(ASR.shouldRunNetworkPreflight?.(this.state, nowMs, this._timingLimits()));
    }

    async _runNetworkPreflight(reason) {
      return ASR.runNetworkPreflight(this, reason);
    }

    _resetNetworkErrorBurst() {
      ASR.resetNetworkErrorBurst?.(this.state);
    }

    _registerNetworkErrorForPreflight() {
      ASR.registerNetworkErrorForPreflight(this);
    }

    async _ensureMicrophonePermission() {
      return ASR.ensureMicrophonePermission(this);
    }

    async _waitUntilDocumentVisibleForRecognition(options = {}) {
      return ASR.waitUntilDocumentVisibleForRecognition(this, options);
    }

    _wireRecognitionHandlers(recognition, generationId, overlapSlotIndex) {
      ASR.wireRecognitionHandlers(this, recognition, generationId, overlapSlotIndex);
    }

    _performControlledStart(reason) {
      ASR.performControlledStart(this, reason);
    }

    _transitionToStopping(reason) {
      ASR.transitionToStopping(this, reason);
    }

    _scheduleRestart(reason, options = {}) {
      ASR.scheduleRestart(this, reason, options);
    }

    _nextNetworkBackoff() {
      return ASR.nextNetworkBackoffMs?.(this.state, this.initialNetworkBackoffMs, this.maxNetworkBackoffMs) ?? 1000;
    }

    _cleanupRecognitionInstance(generationId) {
      ASR.cleanupRecognitionInstance(this, generationId);
    }

    _isActiveGeneration(generationId) {
      return generationId === Number(this.state.recognitionGenerationId || 0);
    }

    _startWatchdog() {
      if (this._watchdogTimer) {
        return;
      }
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
      const now = this._now();
      this._refreshHealthSignals();
      const tick = ASR.evaluateWatchdogTick({
        state: this.state,
        nowMs: now,
        limits: {
          maxBrowserSessionAgeMs: this.maxBrowserSessionAgeMs,
          prepareCycleBeforeMs: this.prepareCycleBeforeMs,
          maxStoppingMs: this.maxStoppingMs,
          hiddenIdleRestartMs: this.hiddenIdleRestartMs,
          visibleIdleRestartMs: this.visibleIdleRestartMs,
        },
        documentHidden: document.hidden,
      });
      if (tick.type === "session_cycle") {
        this.state.browserCycleCount = Number(this.state.browserCycleCount || 0) + 1;
        this.state.pendingStart = true;
        this.state.pendingRestartReason = "session_cycle";
        this._appendLog("browser session age limit reached; controlled cycle requested");
        this._transitionToStopping("session-cycle");
        this._emitWorkerStatus("session-cycle");
        return;
      }
      if (tick.type === "cycle_pending") {
        this.state.browserCyclePending = true;
        this._emitWorkerStatus("cycle-pending");
      }
      if (tick.type === "stopping_timeout") {
        if (this._recognitionOverlapActive()) {
          (this.state.recognitionOverlapSlots || []).forEach((recognition) => {
            if (recognition) {
              try {
                recognition.abort();
              } catch (_error) {
                // best effort
              }
            }
          });
        } else if (this.state.recognition) {
          try {
            this.state.recognition.abort();
          } catch (_error) {
            // best effort
          }
        }
        this._cleanupRecognitionInstance(this.state.recognitionGenerationId);
        this._setRecognitionState("idle");
        this.state.stoppingSinceMs = null;
        if (this.state.desiredRunning || this.state.pendingStart) {
          this.state.pendingRestartReason = "watchdog_stall";
          this._scheduleRestart("watchdog_stall");
        } else {
          this._setSupervisorState("idle");
        }
        this._emitWorkerStatus("watchdog-stop");
        return;
      }
      if (tick.type === "idle_rearm") {
        this.state.pendingStart = true;
        this.state.pendingRestartReason = "watchdog_stall";
        this._appendLog("watchdog forced rearm");
        this._transitionToStopping("watchdog");
        return;
      }
      if (tick.type === "heartbeat" || tick.type === "cycle_pending") {
        this._emitHeartbeat("watchdog");
      }
    }
  }

  global.BrowserAsrSessionManager = BrowserAsrSessionManager;
})(window);
