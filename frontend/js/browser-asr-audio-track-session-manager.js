(function attachBrowserAsrAudioTrackSessionManager(global) {
  "use strict";

  const BaseSessionManager = global.BrowserAsrSessionManager;
  if (!BaseSessionManager) {
    return;
  }

  class BrowserAsrAudioTrackSessionManager extends BaseSessionManager {
    constructor(options) {
      super(options);
      this.state.browserMode = "browser_google_experimental";
      this.state.experimental = true;
      this.state.startMode = "audio_track";
      this.state.fallbackUsed = false;
      this.state.audioTrackReused = false;
      this.state.audioTrackReopenCount = Number(this.state.audioTrackReopenCount || 0);
      this.state.audioTrackStartAttempts = Number(this.state.audioTrackStartAttempts || 0);
      this.state.audioTrackStartFailures = Number(this.state.audioTrackStartFailures || 0);
      this.state.lastStartError = this.state.lastStartError || "";
      this.state.lastAudioTrackError = this.state.lastAudioTrackError || "";
      this.state.fallbackToDefaultStart = this._fallbackToDefaultStartEnabled();
      this.state.mediaStream = this.state.mediaStream || null;
      this.state.audioTrack = this.state.audioTrack || null;
      this.state.audioTrackOpenedOnce = Boolean(this.state.audioTrackOpenedOnce);
      this.state.pendingAudioTrackRecovery = false;
      this._boundAudioTrack = null;
    }

    _experimentalSettings() {
      return this.options.getExperimentalSettings?.() || {};
    }

    _fallbackToDefaultStartEnabled() {
      return this._experimentalSettings().fallbackToDefaultStart !== false;
    }

    _keepStreamAliveEnabled() {
      return this._experimentalSettings().keepStreamAlive !== false;
    }

    _startWithAudioTrackEnabled() {
      return this._experimentalSettings().startWithAudioTrack !== false;
    }

    _audioTrackConstraints() {
      const settings = this._experimentalSettings();
      const constraints = settings.audioTrackConstraints;
      if (!constraints || typeof constraints !== "object") {
        return {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        };
      }
      return {
        echoCancellation: constraints.echoCancellation === true,
        noiseSuppression: constraints.noiseSuppression === true,
        autoGainControl: constraints.autoGainControl === true,
      };
    }

    _buildErrorMessage(error, fallbackMessage) {
      const message = error instanceof Error ? error.message : String(error || "").trim();
      return message || fallbackMessage;
    }

    _setTrackDiagnostics(track) {
      if (!track) {
        this.state.audioTrackReused = false;
        this.state.micTrackReadyState = "missing";
        this.state.micTrackMuted = false;
        this.state.micStreamActive = false;
        return;
      }
      this.state.lastAudioTrackError = "";
      this.state.audioTrackReused = Boolean(this.state.audioTrackReused);
      this.state.micTrackReadyState = String(track.readyState || "unknown");
      this.state.micTrackMuted = Boolean(track.muted);
      this.state.micStreamActive = Boolean(this.state.mediaStream);
    }

    async _openAudioTrack() {
      if (this.state.browserSupervisorState === "stopping") {
        this.state.mediaTrackLeakGuardCount = Number(this.state.mediaTrackLeakGuardCount || 0) + 1;
        this._appendLog("experimental audio track open skipped while stopping");
        return this.state.audioTrack || null;
      }
      this.state.getUserMediaCount = Number(this.state.getUserMediaCount || 0) + 1;
      this._emitWorkerStatus("audio-track-permission-requested");
      this._appendLog("experimental audio track: requesting microphone permission");
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: this._audioTrackConstraints(),
        });
        const audioTracks = typeof stream.getAudioTracks === "function" ? stream.getAudioTracks() : [];
        const audioTrack = audioTracks[0] || null;
        if (!audioTrack) {
          throw new Error(
            this._locale() === "ru"
              ? "Браузер не вернул audio track."
              : "The browser did not return an audio track."
          );
        }
        if (audioTrack.kind !== "audio") {
          throw new Error(
            this._locale() === "ru"
              ? `Ожидался audio track, получено: ${audioTrack.kind || "unknown"}`
              : `Expected an audio track, got: ${audioTrack.kind || "unknown"}`
          );
        }
        if (audioTrack.readyState !== "live") {
          throw new Error(
            this._locale() === "ru"
              ? `Audio track не live: ${audioTrack.readyState || "unknown"}`
              : `Audio track is not live: ${audioTrack.readyState || "unknown"}`
          );
        }
        this._releaseAudioTrack("replace-track");
        this.state.mediaStream = stream;
        this.state.audioTrack = audioTrack;
        this.state.audioTrackReused = false;
        this.state.getUserMediaLastError = null;
        this.state.micStreamActive = true;
        if (this.state.audioTrackOpenedOnce) {
          this.state.audioTrackReopenCount = Number(this.state.audioTrackReopenCount || 0) + 1;
        }
        this.state.audioTrackOpenedOnce = true;
        this._bindAudioTrackEvents(audioTrack);
        this._setTrackDiagnostics(audioTrack);
        this._appendLog(`experimental audio track opened (${audioTrack.kind}, ${audioTrack.readyState})`);
        this._emitWorkerStatus("audio-track-permission-granted");
        this._emitWorkerStatus("audio-track-opened");
        this._refreshHealthSignals();
        return audioTrack;
      } catch (error) {
        const message = this._buildErrorMessage(
          error,
          this._locale() === "ru"
            ? "Не удалось открыть микрофонный audio track."
            : "Could not open microphone audio track."
        );
        this.state.lastAudioTrackError = message;
        this.state.getUserMediaLastError = message;
        this._setLastError("audio-capture", message);
        this._appendLog(`experimental audio track open failed: ${message}`);
        this._emitWorkerStatus("audio-track-permission-denied");
        throw error instanceof Error ? error : new Error(message);
      }
    }

    async _ensureLiveAudioTrack(options) {
      const allowReuse = options?.allowReuse !== false;
      const audioTrack = this.state.audioTrack;
      if (
        allowReuse
        && audioTrack
        && audioTrack.kind === "audio"
        && audioTrack.readyState === "live"
      ) {
        this.state.audioTrackReused = true;
        this._setTrackDiagnostics(audioTrack);
        this._emitWorkerStatus("audio-track-reused");
        return audioTrack;
      }
      if (!allowReuse && audioTrack) {
        this._releaseAudioTrack("reopen-for-start");
      }
      return this._openAudioTrack();
    }

    _bindAudioTrackEvents(audioTrack) {
      if (!audioTrack || this._boundAudioTrack === audioTrack) {
        return;
      }
      this._boundAudioTrack = audioTrack;
      const updateTrackState = () => {
        if (this.state.audioTrack !== audioTrack) {
          return;
        }
        this._setTrackDiagnostics(audioTrack);
        this._refreshHealthSignals();
        this._emitWorkerStatus("audio-track-state");
      };
      audioTrack.addEventListener("ended", () => {
        if (this.state.audioTrack !== audioTrack) {
          return;
        }
        this.state.lastAudioTrackError = "audio track ended";
        this.state.micTrackReadyState = String(audioTrack.readyState || "ended");
        this._appendLog("experimental audio track ended");
        this._setHealthDegradedReason("mic_track_unavailable");
        this._emitWorkerStatus("audio-track-ended");
        if (this.state.desiredRunning) {
          this._scheduleAudioTrackRecovery();
        }
      });
      audioTrack.addEventListener("mute", () => {
        this._appendLog("experimental audio track muted");
        updateTrackState();
      });
      audioTrack.addEventListener("unmute", () => {
        this.state.lastMicActivityAt = this._now();
        this._appendLog("experimental audio track unmuted");
        updateTrackState();
      });
    }

    _scheduleAudioTrackRecovery() {
      if (this.state.pendingAudioTrackRecovery) {
        return;
      }
      this.state.pendingAudioTrackRecovery = true;
      window.setTimeout(async () => {
        this.state.pendingAudioTrackRecovery = false;
        if (!this.state.desiredRunning) {
          return;
        }
        if (this.state.browserSupervisorState === "stopping") {
          this.state.mediaTrackLeakGuardCount = Number(this.state.mediaTrackLeakGuardCount || 0) + 1;
          return;
        }
        try {
          await this._openAudioTrack();
          this._setHealthDegradedReason(null);
          this._refreshHealthSignals();
          if (this.state.browserSupervisorState === "running") {
            this.state.pendingStart = true;
            this.state.pendingRestartReason = "watchdog_stall";
            this._transitionToStopping("audio-track-recovery");
            return;
          }
          this._scheduleRestart("watchdog_stall");
        } catch (error) {
          const message = this._buildErrorMessage(
            error,
            this._locale() === "ru"
              ? "Audio track recovery failed."
              : "Audio track recovery failed."
          );
          this.state.lastAudioTrackError = message;
          this._setHealthDegradedReason("mic_track_unavailable");
          this._appendLog(`experimental audio track recovery failed: ${message}`);
        }
      }, 100);
    }

    _releaseAudioTrack(reason) {
      const stream = this.state.mediaStream;
      if (stream && typeof stream.getTracks === "function") {
        const tracks = stream.getTracks();
        this.state.mediaTracksStoppedCount = Number(this.state.mediaTracksStoppedCount || 0) + tracks.length;
        tracks.forEach((track) => {
          try {
            track.stop();
          } catch (_error) {
            // best effort
          }
        });
      } else if (this.state.audioTrack) {
        this.state.mediaTracksStoppedCount = Number(this.state.mediaTracksStoppedCount || 0) + 1;
        try {
          this.state.audioTrack.stop();
        } catch (_error) {
          // best effort
        }
      }
      this.state.mediaStream = null;
      this.state.audioTrack = null;
      this.state.audioTrackReused = false;
      this._boundAudioTrack = null;
      this.state.micStreamActive = false;
      this.state.micTrackReadyState = reason === "stop" || reason === "destroy" ? null : "ended";
      this.state.micTrackMuted = false;
      if (reason === "stop" || reason === "destroy") {
        this.state.lastAudioTrackError = "";
      }
    }

    async _ensureMicrophonePermission() {
      return this._ensureLiveAudioTrack({ allowReuse: this._keepStreamAliveEnabled() });
    }

    async _tryDefaultFallbackStart(recognition) {
      const fallbackMessage = this._locale() === "ru"
        ? "Не удалось переключиться на обычный recognition.start()."
        : "Could not fall back to the default recognition.start().";
      this.state.startMode = "fallback_default_start";
      this.state.fallbackUsed = true;
      this._emitWorkerStatus("fallback-default-start-attempt");
      try {
        recognition.start();
        this._appendLog("experimental fallback recognition.start() accepted");
        this._emitWorkerStatus("fallback-default-start-success");
        return true;
      } catch (error) {
        const message = this._buildErrorMessage(error, fallbackMessage);
        this.state.lastStartError = message;
        this._appendLog(`experimental fallback recognition.start() failed: ${message}`);
        this._emitWorkerStatus("fallback-default-start-failed");
        return false;
      }
    }

    async _performControlledStart(reason) {
      if (!this.state.desiredRunning) {
        return;
      }
      if (this.state.browserSupervisorState === "starting" || this.state.browserSupervisorState === "running") {
        return;
      }
      if (this.state.browserSupervisorState === "stopping") {
        this.state.pendingStart = true;
        this._appendLog("recognition.start deferred: recognition is stopping");
        return;
      }

      const generationId = Number(this.state.generationId || 0);
      this._cleanupRecognitionInstance(this.state.recognitionGenerationId);
      this._setSupervisorState("starting");
      this._setRecognitionState("starting");
      this.state.stoppingSinceMs = null;
      this.state.pendingRestartReason = null;
      this.state.fallbackToDefaultStart = this._fallbackToDefaultStartEnabled();
      this.ensureSocketConnected();
      const recognition = this._createRecognition(generationId);

      try {
        let audioTrack = null;
        if (this._startWithAudioTrackEnabled()) {
          audioTrack = await this._ensureLiveAudioTrack({ allowReuse: this._keepStreamAliveEnabled() });
        }
        if (
          !this.state.desiredRunning
          || generationId !== Number(this.state.generationId || 0)
          || this.state.recognition !== recognition
        ) {
          this._cleanupRecognitionInstance(generationId);
          return;
        }
        if (reason && reason !== "user-start") {
          this._emitWorkerStatus("restart-executed");
        }
        const startLogThrottle = this._recognitionStartBurstThrottle(reason);
        const expLogKey = startLogThrottle.key ? `${startLogThrottle.key}:exp` : null;
        if (audioTrack) {
          this.state.startMode = "audio_track";
          this.state.audioTrackStartAttempts = Number(this.state.audioTrackStartAttempts || 0) + 1;
          const line = `experimental recognition.start(audioTrack) lang=${recognition.lang}, interim=${recognition.interimResults}, continuous=${recognition.continuous}`;
          if (expLogKey) {
            this._appendLogThrottled(line, expLogKey, startLogThrottle.gapMs);
          } else {
            this._appendLog(line);
          }
          this._emitWorkerStatus("audio-track-start-attempt");
          try {
            recognition.start(audioTrack);
            this.state.lastStartError = "";
            this.state.fallbackUsed = false;
            this._emitWorkerStatus("audio-track-start-success");
            return;
          } catch (error) {
            const message = this._buildErrorMessage(
              error,
              this._locale() === "ru"
                ? "Не удалось запустить экспериментальное браузерное распознавание."
                : "Could not start experimental Web Speech recognition."
            );
            this.state.lastStartError = message;
            this.state.audioTrackStartFailures = Number(this.state.audioTrackStartFailures || 0) + 1;
            this._appendLog(`experimental audio-track start failed: ${message}`);
            this._emitWorkerStatus("audio-track-start-failed");
            if (!this._fallbackToDefaultStartEnabled() || !(await this._tryDefaultFallbackStart(recognition))) {
              throw error instanceof Error ? error : new Error(message);
            }
            return;
          }
        }
        this.state.startMode = "default_start";
        recognition.start();
        if (expLogKey) {
          this._appendLogThrottled(`experimental recognition.start (${reason})`, expLogKey, startLogThrottle.gapMs);
        } else {
          this._appendLog(`experimental recognition.start (${reason})`);
        }
      } catch (error) {
        const message = this._buildErrorMessage(
          error,
          this._locale() === "ru"
            ? "Не удалось запустить экспериментальное браузерное распознавание."
            : "Could not start experimental Web Speech recognition."
        );
        if (String(message).toLowerCase().includes("already started")) {
          this._setSupervisorState("running");
          this._setRecognitionState("running");
          this._setStatus("listening");
          return;
        }
        this._setRecognitionState("idle");
        this._setSupervisorState("restarting");
        this.state.lastStartError = message;
        this.state.audioTrackStartFailures = Number(this.state.audioTrackStartFailures || 0) + 1;
        this._setLastError("audio-capture", message);
        this._setHealthDegradedReason("mic_track_unavailable");
        this._appendLog(`experimental recognition.start failed: ${message}`);
        this._scheduleRestart("network");
      }
    }

    stop() {
      super.stop();
      this._releaseAudioTrack("stop");
    }

    destroy() {
      super.destroy();
      this._releaseAudioTrack("destroy");
    }
  }

  global.BrowserAsrAudioTrackSessionManager = BrowserAsrAudioTrackSessionManager;
})(window);
