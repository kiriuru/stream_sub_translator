(function attachBrowserAsrSessionManager(global) {
  "use strict";

  class BrowserAsrSessionManager {
    constructor(options) {
      this.options = options || {};
      this.state = this.options.state || {};
      this.SpeechRecognitionCtor = this.options.SpeechRecognitionCtor || null;
      this.restartDelayByReasonMs = {
        normal_onend: 350,
        settings_change: 350,
        websocket_reconnect: 350,
        watchdog_stall: 750,
        session_cycle: 350,
      };
      this.initialNoSpeechDelayMs = 350;
      this.maxNoSpeechDelayMs = 5000;
      this.initialNetworkBackoffMs = 1000;
      this.maxNetworkBackoffMs = 30000;
      this.watchdogIntervalMs = 1000;
      this.maxStoppingMs = 2500;
      this.visibleIdleRestartMs = 30000;
      this.hiddenIdleRestartMs = 60000;
      this.stallDegradedAfterMs = 6000;
      this.micSilentDegradedAfterMs = 5000;
      this.recentMicActivityWindowMs = 2000;
      this.minimumReconnectIntervalMs = 500;
      this.maxBrowserSessionAgeMs = 180000;
      this.prepareCycleBeforeMs = 15000;
      this.forceFinalOnInterruption = true;
      this.forceFinalMinChars = 3;
      this.forceFinalMinStableMs = 700;
      this.voiceBelowRecognitionRmsThreshold = 0.025;
      this.voiceBelowRecognitionGraceMs = 8000;
      this.voiceBelowRecognitionMicWindowMs = 2000;
      this.voiceBelowRecognitionMinNoSpeech = 1;
      this.networkPreflightBurstThreshold = 3;
      this.networkPreflightBurstWindowMs = 12000;
      this.networkPreflightTimeoutMs = 4000;
      this.networkPreflightCooldownMs = 30000;
      /** Dedupes noisy recognition.start lines during no-speech / tight onend loops (~max 850/h per key). */
      this.recognitionStartLogMinGapMs = 4200;
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
      Object.assign(this.state, {
        desiredRunning: Boolean(this.state.desiredRunning),
        pendingStart: Boolean(this.state.pendingStart),
        generationId: Number(this.state.generationId || 0),
        sessionId: this.state.sessionId || `browser-worker-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
        providerName: this.state.providerName || this.state.browserMode || "browser_google",
        browserSupervisorState: this.state.browserSupervisorState || "idle",
        recognitionState: this.state.recognitionState || "idle",
        restartTimer: this.state.restartTimer || null,
        reconnectTimer: this.state.reconnectTimer || null,
        watchdogTimerId: this.state.watchdogTimerId || null,
        restartCount: Number(this.state.restartCount || 0),
        noSpeechCount: Number(this.state.noSpeechCount || 0),
        networkErrorCount: Number(this.state.networkErrorCount || 0),
        websocketReady: Boolean(this.state.websocketReady),
        stoppingSinceMs: this.state.stoppingSinceMs || null,
        lastStartAtMs: Number(this.state.lastStartAtMs || 0),
        lastEndAtMs: Number(this.state.lastEndAtMs || 0),
        lastSessionStartedAtMs: Number(this.state.lastSessionStartedAtMs || 0),
        lastSessionEndedAtMs: Number(this.state.lastSessionEndedAtMs || 0),
        lastEventAtMs: Number(this.state.lastEventAtMs || 0),
        lastResultAtMs: Number(this.state.lastResultAtMs || 0),
        lastResultIndex: this.state.lastResultIndex == null ? null : Number(this.state.lastResultIndex || 0),
        browserCyclePending: Boolean(this.state.browserCyclePending),
        browserCycleCount: Number(this.state.browserCycleCount || 0),
        browserMinimumReconnectSuppressedCount: Number(this.state.browserMinimumReconnectSuppressedCount || 0),
        browserForcedFinalOnInterruptionCount: Number(this.state.browserForcedFinalOnInterruptionCount || 0),
        lastErrorKind: this.state.lastErrorKind || null,
        lastError: this.state.lastError || null,
        degradedReason: this.state.degradedReason || null,
        terminalDegradedReason: this.state.terminalDegradedReason || null,
        healthDegradedReason: this.state.healthDegradedReason || null,
        socketDegraded: Boolean(this.state.socketDegraded),
        visibilityDegraded: Boolean(this.state.visibilityDegraded),
        restartBackoffMs: Number(this.state.restartBackoffMs || 0),
        noSpeechBackoffMs: Number(this.state.noSpeechBackoffMs || 0),
        pendingRestartReason: this.state.pendingRestartReason || null,
        lastRestartReason: this.state.lastRestartReason || null,
        recognition: null,
        recognitionGenerationId: 0,
        effectiveContinuousMode: this.state.effectiveContinuousMode || "native_continuous",
        currentClientSegmentId: this.state.currentClientSegmentId || null,
        nextClientSegmentOrdinal: Number(this.state.nextClientSegmentOrdinal || 0),
        currentSegmentLastPartialText: this.state.currentSegmentLastPartialText || "",
        currentSegmentLastFinalText: this.state.currentSegmentLastFinalText || "",
        currentPartialStableSinceMs: Number(this.state.currentPartialStableSinceMs || 0),
        currentSegmentForcedFinalized: Boolean(this.state.currentSegmentForcedFinalized),
        lastForcedFinal: this.state.lastForcedFinal || null,
        duplicatePartialSuppressed: Number(this.state.duplicatePartialSuppressed || 0),
        duplicateFinalSuppressed: Number(this.state.duplicateFinalSuppressed || 0),
        lateForcedFinalSuppressed: Number(this.state.lateForcedFinalSuppressed || 0),
        minimumReconnectIntervalMs: Number(this.state.minimumReconnectIntervalMs || 500),
        normalRestartDelayMs: Number(this.state.normalRestartDelayMs || 350),
        noSpeechRestartDelayMs: Number(this.state.noSpeechRestartDelayMs || 350),
        networkReconnectInitialMs: Number(this.state.networkReconnectInitialMs || 1000),
        networkReconnectMaxMs: Number(this.state.networkReconnectMaxMs || 30000),
        maxBrowserSessionAgeMs: Number(this.state.maxBrowserSessionAgeMs || 180000),
        networkErrorBurstCount: Number(this.state.networkErrorBurstCount || 0),
        networkErrorBurstStartedAtMs: Number(this.state.networkErrorBurstStartedAtMs || 0),
        lastNetworkPreflightAtMs: Number(this.state.lastNetworkPreflightAtMs || 0),
        lastNetworkPreflightOk: this.state.lastNetworkPreflightOk == null ? null : Boolean(this.state.lastNetworkPreflightOk),
        networkPreflightInFlight: Boolean(this.state.networkPreflightInFlight),
        wakeLockActive: Boolean(this.state.wakeLockActive),
        wakeLockSupported: typeof navigator !== "undefined" && Boolean(navigator?.wakeLock?.request),
        prepareCycleBeforeMs: Number(this.state.prepareCycleBeforeMs || 15000),
        forceFinalOnInterruption: this.state.forceFinalOnInterruption !== false,
        forceFinalMinChars: Number(this.state.forceFinalMinChars || 3),
        forceFinalMinStableMs: Number(this.state.forceFinalMinStableMs || 700),
        micTrackReadyState: this.state.micTrackReadyState || null,
        micTrackMuted: Boolean(this.state.micTrackMuted),
        micRms: Number(this.state.micRms || 0),
        micActiveRecentMs: this.state.micActiveRecentMs == null ? null : Number(this.state.micActiveRecentMs || 0),
        lastMicActivityAt: Number(this.state.lastMicActivityAt || 0),
        getUserMediaCount: Number(this.state.getUserMediaCount || 0),
        getUserMediaLastError: this.state.getUserMediaLastError || null,
        micStreamActive: Boolean(this.state.micStreamActive),
        mediaTracksStoppedCount: Number(this.state.mediaTracksStoppedCount || 0),
        mediaTrackLeakGuardCount: Number(this.state.mediaTrackLeakGuardCount || 0),
        workerTranscriptMessageSequence: Number(this.state.workerTranscriptMessageSequence || 0),
      });
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
      const last = Number(this._appendLogThrottleState.get(throttleKey) || 0);
      if (last && now - last < minGapMs) {
        return;
      }
      this._appendLog(message);
      this._appendLogThrottleState.set(throttleKey, now);
    }

    _recognitionStartBurstThrottle(reason) {
      const raw = String(reason || "")
        .trim()
        .toLowerCase()
        .replace(/-/g, "_");
      const burst = raw === "no_speech" || raw === "nospeech" || raw === "normal_onend";
      const gapMs = Math.max(500, Number(this.recognitionStartLogMinGapMs || 4200));
      if (!burst) {
        return { gapMs, key: null };
      }
      return { gapMs, key: `recognition-start:${raw}` };
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

    _isForceFinalizationEnabled() {
      return this.options.isForceFinalizationEnabled?.() !== false;
    }

    _currentVisibilityState() {
      return document.hidden ? "hidden" : "visible";
    }

    _currentSessionAgeMs(nowMs = this._now()) {
      if (!this.state.lastSessionStartedAtMs) {
        return null;
      }
      return Math.max(0, nowMs - Number(this.state.lastSessionStartedAtMs || 0));
    }

    _resetCycleState() {
      this.state.browserCyclePending = false;
    }

    _minimumReconnectGuardDelayMs(delayMs) {
      const minimumIntervalMs = Math.max(0, Number(this.state.minimumReconnectIntervalMs || this.minimumReconnectIntervalMs || 0));
      if (!minimumIntervalMs) {
        return delayMs;
      }
      const anchorMs = Math.max(
        Number(this.state.lastSessionEndedAtMs || 0),
        Number(this.state.lastEndAtMs || 0),
        Number(this.state.lastStartAtMs || 0)
      );
      if (!anchorMs) {
        return delayMs;
      }
      const remainingMs = minimumIntervalMs - Math.max(0, this._now() - anchorMs);
      if (remainingMs <= 0 || remainingMs <= delayMs) {
        return delayMs;
      }
      this.state.browserMinimumReconnectSuppressedCount = Number(this.state.browserMinimumReconnectSuppressedCount || 0) + 1;
      return remainingMs;
    }

    _canForceFinalizeOnInterruption() {
      if (!this.state.forceFinalOnInterruption || !this._isForceFinalizationEnabled()) {
        return false;
      }
      const normalizedText = this._normalizeTranscriptText(this.state.currentPartial);
      if (!normalizedText || normalizedText.length < Math.max(1, Number(this.state.forceFinalMinChars || 0))) {
        return false;
      }
      if (normalizedText === this.state.currentSegmentLastFinalText) {
        return false;
      }
      const stableSinceMs = Number(this.state.currentPartialStableSinceMs || 0);
      if (!stableSinceMs) {
        return false;
      }
      return (this._now() - stableSinceMs) >= Math.max(0, Number(this.state.forceFinalMinStableMs || 0));
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
      let nextReason = null;
      if (this.state.terminalDegradedReason) {
        nextReason = this.state.terminalDegradedReason;
      } else if (this.state.visibilityDegraded) {
        nextReason = "document_hidden";
      } else if (this.state.socketDegraded) {
        nextReason = "websocket_disconnected";
      } else if (this.state.healthDegradedReason) {
        nextReason = this.state.healthDegradedReason;
      }
      this._setDegradedReason(nextReason);
    }

    _setLastError(kind, message) {
      this.state.lastErrorKind = String(kind || "").trim().toLowerCase() || null;
      this.state.lastError = String(message || "").trim() || null;
    }

    _markActivity(label) {
      this.state.lastEventAtMs = this._now();
      if (label === "result") {
        this.state.lastResultAtMs = this.state.lastEventAtMs;
        this.state.noSpeechBackoffMs = 0;
        this.state.restartBackoffMs = 0;
        this._resetNetworkErrorBurst();
      }
    }

    _resetSegmentTracking() {
      this.state.currentClientSegmentId = null;
      this.state.currentSegmentLastPartialText = "";
      this.state.currentSegmentLastFinalText = "";
      this.state.currentPartialStableSinceMs = 0;
      this.state.currentSegmentForcedFinalized = false;
      this.state.lastForcedFinal = null;
      this._clearForceFinalizeTimer();
    }

    _currentGenerationId() {
      return Number(this.state.generationId || 0);
    }

    _ensureClientSegmentId() {
      if (this.state.currentClientSegmentId && !this.state.currentSegmentForcedFinalized) {
        return this.state.currentClientSegmentId;
      }
      this.state.nextClientSegmentOrdinal = Number(this.state.nextClientSegmentOrdinal || 0) + 1;
      const ordinal = this.state.nextClientSegmentOrdinal;
      const sessionId = String(this.state.sessionId || "browser-worker").replace(/[^a-z0-9_-]+/gi, "-");
      this.state.currentClientSegmentId = `${sessionId}-g${this._currentGenerationId()}-s${ordinal}`;
      this.state.currentSegmentLastPartialText = "";
      this.state.currentSegmentLastFinalText = "";
      this.state.currentSegmentForcedFinalized = false;
      return this.state.currentClientSegmentId;
    }

    _consumeCompletedSegment() {
      this.state.currentClientSegmentId = null;
      this.state.currentSegmentLastPartialText = "";
      this.state.currentSegmentLastFinalText = "";
      this.state.currentSegmentForcedFinalized = false;
    }

    _normalizeTranscriptText(value) {
      return String(value || "").trim().replace(/\s+/g, " ");
    }

    _restartDelayForReason(reason) {
      const normalized = String(reason || "").trim().toLowerCase();
      if (normalized === "no_speech") {
        if (!this.state.noSpeechBackoffMs) {
          this.state.noSpeechBackoffMs = Math.max(0, Number(this.state.noSpeechRestartDelayMs || this.initialNoSpeechDelayMs));
        } else {
          this.state.noSpeechBackoffMs = Math.min(
            this.maxNoSpeechDelayMs,
            Math.max(
              Math.max(0, Number(this.state.noSpeechRestartDelayMs || this.initialNoSpeechDelayMs)),
              this.state.noSpeechBackoffMs + 800
            )
          );
        }
        return this.state.noSpeechBackoffMs;
      }
      if (normalized === "network") {
        this.state.restartBackoffMs = this._nextNetworkBackoff();
        return this.state.restartBackoffMs;
      }
      return this.restartDelayByReasonMs[normalized] || this.restartDelayByReasonMs.normal_onend;
    }

    _shouldSuppressDuplicatePartial(text) {
      const normalizedText = this._normalizeTranscriptText(text);
      if (!normalizedText) {
        return true;
      }
      if (normalizedText === this.state.currentSegmentLastPartialText) {
        this.state.duplicatePartialSuppressed = Number(this.state.duplicatePartialSuppressed || 0) + 1;
        this._emitWorkerStatus("duplicate-partial");
        return true;
      }
      return false;
    }

    _shouldSuppressFinal(text, { forcedFinal = false } = {}) {
      const normalizedText = this._normalizeTranscriptText(text);
      if (!normalizedText) {
        return true;
      }
      const lateForcedFinal = this.state.lastForcedFinal;
      if (
        !forcedFinal
        && this.state.currentSegmentForcedFinalized
        && lateForcedFinal
        && Number(lateForcedFinal.generation_id || 0) === this._currentGenerationId()
        && this._normalizeTranscriptText(lateForcedFinal.text) === normalizedText
      ) {
        this.state.lateForcedFinalSuppressed = Number(this.state.lateForcedFinalSuppressed || 0) + 1;
        this._emitWorkerStatus("late-forced-final");
        this._consumeCompletedSegment();
        return true;
      }
      if (normalizedText === this.state.currentSegmentLastFinalText) {
        this.state.duplicateFinalSuppressed = Number(this.state.duplicateFinalSuppressed || 0) + 1;
        this._emitWorkerStatus("duplicate-final");
        return true;
      }
      return false;
    }

    _buildUpdatePayload(payload) {
      const nowMs = this._now();
      this.state.workerTranscriptMessageSequence = Number(this.state.workerTranscriptMessageSequence || 0) + 1;
      return {
        partial: payload.partial || "",
        final: payload.final || "",
        is_final: Boolean(payload.is_final),
        source_lang: payload.source_lang || this.state.sourceLang || "auto",
        client_segment_id: payload.client_segment_id || this.state.currentClientSegmentId || null,
        forced_final: Boolean(payload.forced_final),
        forced_final_reason: payload.forced_final_reason || null,
        asr_result_created_at_ms: payload.asr_result_created_at_ms || nowMs,
        worker_send_started_at_ms: nowMs,
        worker_message_sequence: this.state.workerTranscriptMessageSequence,
      };
    }

    async reloadSettingsFromBackend() {
      if (typeof this.options.loadBackendSettings !== "function") {
        return;
      }
      await this.options.loadBackendSettings();
      this._emitWorkerStatus("settings-reloaded");
    }

    _refreshHealthSignals() {
      const now = this._now();
      const trackReadyState = String(this.state.micTrackReadyState || "").trim().toLowerCase();
      const micActivityAgeMs = this.state.lastMicActivityAt > 0 ? Math.max(0, now - Number(this.state.lastMicActivityAt)) : null;
      const recognitionQuietMs = Math.max(
        0,
        now - Math.max(
          Number(this.state.lastEventAtMs || 0),
          Number(this.state.lastResultAtMs || 0),
          Number(this.state.lastStartAtMs || 0)
        )
      );
      this.state.micActiveRecentMs = micActivityAgeMs;
      if (!this.state.desiredRunning) {
        this._setHealthDegradedReason(null);
        return;
      }
      if (trackReadyState && trackReadyState !== "live") {
        this._setHealthDegradedReason("mic_track_unavailable");
        return;
      }
      if (
        !document.hidden
        && this.state.browserSupervisorState === "running"
        && micActivityAgeMs != null
        && micActivityAgeMs >= this.micSilentDegradedAfterMs
      ) {
        this._setHealthDegradedReason("mic_silent");
        return;
      }
      const micRms = Number(this.state.micRms || 0);
      const voiceLevelGoodRecently =
        micRms >= this.voiceBelowRecognitionRmsThreshold
        || (
          micActivityAgeMs != null
          && micActivityAgeMs <= this.voiceBelowRecognitionMicWindowMs
          && Number(this.state.noSpeechCount || 0) >= this.voiceBelowRecognitionMinNoSpeech
        );
      if (
        !document.hidden
        && this.state.browserSupervisorState === "running"
        && recognitionQuietMs >= this.voiceBelowRecognitionGraceMs
        && voiceLevelGoodRecently
        && Number(this.state.noSpeechCount || 0) >= this.voiceBelowRecognitionMinNoSpeech
      ) {
        this._setHealthDegradedReason("voice_below_recognition_threshold");
        return;
      }
      if (
        !document.hidden
        && this.state.browserSupervisorState === "running"
        && recognitionQuietMs >= this.stallDegradedAfterMs
        && micActivityAgeMs != null
        && micActivityAgeMs <= this.recentMicActivityWindowMs
      ) {
        this._setHealthDegradedReason("web_speech_stalled");
        return;
      }
      this._setHealthDegradedReason(null);
    }

    _buildLastError() {
      const parts = [this.state.lastErrorKind, this.state.lastError].filter(Boolean);
      return parts.length ? parts.join(": ") : null;
    }

    _buildWorkerPayload(type, extra) {
      return {
        type,
        session_id: this.state.sessionId,
        generation_id: Number(this.state.generationId || 0),
        browser_mode: this.state.browserMode || "browser_google",
        provider_name: this.state.providerName || this.state.browserMode || "browser_google",
        desired_running: Boolean(this.state.desiredRunning),
        active_recognition: Boolean(this.state.recognition),
        active_media_stream: Boolean(this.state.mediaStream),
        recognition_state: this.state.recognitionState || "idle",
        browser_supervisor_state: this.state.browserSupervisorState || "idle",
        supervisor_state: this.state.browserSupervisorState || "idle",
        pending_start: Boolean(this.state.pendingStart),
        websocket_ready: Boolean(this.state.websocketReady),
        degraded_reason: this.state.degradedReason || null,
        last_error: this._buildLastError(),
        error_type: this.state.lastErrorKind || null,
        restart_count: Number(this.state.restartCount || 0),
        no_speech_count: Number(this.state.noSpeechCount || 0),
        network_error_count: Number(this.state.networkErrorCount || 0),
        stopping_since_ms: this.state.stoppingSinceMs
          ? Math.max(0, this._now() - Number(this.state.stoppingSinceMs))
          : null,
        recognition_continuous: Boolean(this.state.actualContinuous),
        effective_continuous_mode: this.state.effectiveContinuousMode || "native_continuous",
        client_segment_id: this.state.currentClientSegmentId || null,
        forced_final: Boolean(this.state.currentSegmentForcedFinalized),
        last_result_index: this.state.lastResultIndex,
        last_result_at_ms: Number(this.state.lastResultAtMs || 0) || null,
        last_session_started_at_ms: Number(this.state.lastSessionStartedAtMs || 0) || null,
        last_session_ended_at_ms: Number(this.state.lastSessionEndedAtMs || 0) || null,
        browser_session_age_ms: this._currentSessionAgeMs(),
        browser_cycle_pending: Boolean(this.state.browserCyclePending),
        browser_cycle_count: Number(this.state.browserCycleCount || 0),
        browser_minimum_reconnect_suppressed_count: Number(this.state.browserMinimumReconnectSuppressedCount || 0),
        browser_forced_final_on_interruption_count: Number(this.state.browserForcedFinalOnInterruptionCount || 0),
        duplicate_partial_suppressed: Number(this.state.duplicatePartialSuppressed || 0),
        duplicate_final_suppressed: Number(this.state.duplicateFinalSuppressed || 0),
        late_forced_final_suppressed: Number(this.state.lateForcedFinalSuppressed || 0),
        mic_track_ready_state: this.state.micTrackReadyState || null,
        mic_track_muted: Boolean(this.state.micTrackMuted),
        mic_rms: Number.isFinite(this.state.micRms) ? Number(this.state.micRms) : 0,
        mic_active_recent_ms: this.state.micActiveRecentMs == null ? null : Math.max(0, Number(this.state.micActiveRecentMs || 0)),
        last_mic_activity_at: Number(this.state.lastMicActivityAt || 0) || null,
        get_user_media_count: Number(this.state.getUserMediaCount || 0),
        get_user_media_last_error: this.state.getUserMediaLastError || null,
        mic_stream_active: Boolean(this.state.micStreamActive),
        media_tracks_stopped_count: Number(this.state.mediaTracksStoppedCount || 0),
        media_track_leak_guard_count: Number(this.state.mediaTrackLeakGuardCount || 0),
        visibility_state: this._currentVisibilityState(),
        wake_lock_active: Boolean(this.state.wakeLockActive),
        wake_lock_supported: this._hasWakeLockSupport(),
        network_error_burst_count: Number(this.state.networkErrorBurstCount || 0),
        network_preflight_last_at_ms: Number(this.state.lastNetworkPreflightAtMs || 0) || null,
        network_preflight_last_ok: this.state.lastNetworkPreflightOk == null ? null : Boolean(this.state.lastNetworkPreflightOk),
        last_seen_at_ms: this._now(),
        ...extra,
      };
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
      const recognition = this.state.recognition;
      if (!recognition) {
        this._updateCounters();
        return;
      }
      recognition.lang = this.state.configuredLanguage;
      recognition.interimResults = settings.interimResults !== false;
      recognition.continuous = this.state.actualContinuous;
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
        this._setStatus(this._locale() === "ru" ? `ошибка микрофона: ${message}` : `mic-error: ${message}`);
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
      this._performControlledStart("user-start");
    }

    stop() {
      this._appendLog("stop requested by user");
      this.state.desiredRunning = false;
      this.state.pendingStart = false;
      this.state.generationId = Number(this.state.generationId || 0) + 1;
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
      const protocol = location.protocol === "https:" ? "wss" : "ws";
      const nextSocket = new WebSocket(`${protocol}://${location.host}/ws/asr_worker`);
      this.state.socket = nextSocket;
      this._attachSocketListeners(nextSocket);
    }

    _attachSocketListeners(socket) {
      if (!socket || socket.__sstAttached) {
        return;
      }
      socket.__sstAttached = true;
      socket.addEventListener("open", () => {
        if (this.state.socket !== socket) {
          return;
        }
        this.state.websocketReady = true;
        this.state.socketDegraded = false;
        this._refreshDegradedReason();
        this._appendLog("websocket connected");
        this._updateCounters();
        this._emitWorkerStatus("socket-open");
        this._emitHeartbeat("socket-open");
        if (
          this.state.desiredRunning
          && this.state.browserSupervisorState !== "running"
          && this.state.browserSupervisorState !== "starting"
        ) {
          this._scheduleRestart("websocket_reconnect");
        }
      });
      socket.addEventListener("close", () => {
        if (this.state.socket !== socket) {
          return;
        }
        this.state.websocketReady = false;
        this.state.socketDegraded = Boolean(this.state.desiredRunning);
        this._refreshDegradedReason();
        this._appendLog("websocket closed");
        this._updateCounters();
        this.state.socket = null;
        if (this.state.desiredRunning) {
          this._setStatus("socket-reconnecting");
          this.state.reconnectTimer = window.setTimeout(
            () => this.ensureSocketConnected(),
            this.restartDelayByReasonMs.websocket_reconnect
          );
        }
      });
      socket.addEventListener("error", () => {
        if (this.state.socket !== socket) {
          return;
        }
        this.state.websocketReady = false;
        this.state.socketDegraded = Boolean(this.state.desiredRunning);
        this._refreshDegradedReason();
        this._appendLog("websocket error");
        this._updateCounters();
      });
      socket.addEventListener("message", (event) => {
        if (this.state.socket !== socket) {
          return;
        }
        this._handleSocketMessage(event.data);
      });
    }

    _handleSocketMessage(raw) {
      let message = null;
      try {
        message = JSON.parse(raw);
      } catch (_error) {
        return;
      }
      if (!message || typeof message !== "object") {
        return;
      }
      const type = String(message.type || "").trim().toLowerCase();
      if (type !== "browser_asr_control") {
        return;
      }
      const action = String(message.action || "").trim().toLowerCase();
      if (action === "stop") {
        this.stop();
        return;
      }
      if (action === "reload_settings") {
        this.reloadSettingsFromBackend();
      }
    }

    _hasWakeLockSupport() {
      return typeof navigator !== "undefined" && Boolean(navigator?.wakeLock?.request);
    }

    _clearWakeLockRetryTimer() {
      if (this._wakeLockRetryTimer) {
        window.clearTimeout(this._wakeLockRetryTimer);
        this._wakeLockRetryTimer = null;
      }
    }

    async _acquireWakeLock(reason) {
      if (!this._hasWakeLockSupport()) {
        this.state.wakeLockActive = false;
        return false;
      }
      if (document.hidden) {
        // Browser will reject wake lock on hidden documents; defer until visible.
        this._clearWakeLockRetryTimer();
        this._wakeLockRetryTimer = window.setTimeout(() => this._acquireWakeLock("retry-after-visibility"), 1500);
        return false;
      }
      if (this._wakeLockSentinel && !this._wakeLockSentinel.released) {
        this.state.wakeLockActive = true;
        return true;
      }
      try {
        const sentinel = await navigator.wakeLock.request("screen");
        if (!sentinel) {
          this.state.wakeLockActive = false;
          return false;
        }
        this._wakeLockSentinel = sentinel;
        this.state.wakeLockActive = true;
        if (!this._wakeLockBound) {
          this._wakeLockBound = true;
        }
        sentinel.addEventListener("release", () => {
          if (this._wakeLockSentinel === sentinel) {
            this._wakeLockSentinel = null;
            this.state.wakeLockActive = false;
            if (this.state.desiredRunning) {
              this._clearWakeLockRetryTimer();
              this._wakeLockRetryTimer = window.setTimeout(
                () => this._acquireWakeLock("re-acquire-after-release"),
                500
              );
            }
          }
        });
        this._appendLog(`screen wake lock acquired (${reason || "start"})`);
        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error || "");
        this.state.wakeLockActive = false;
        if (message) {
          this._appendLog(`screen wake lock acquisition failed: ${message}`);
        }
        return false;
      }
    }

    async _releaseWakeLock(reason) {
      this._clearWakeLockRetryTimer();
      const sentinel = this._wakeLockSentinel;
      this._wakeLockSentinel = null;
      this.state.wakeLockActive = false;
      if (!sentinel) {
        return;
      }
      try {
        await sentinel.release();
        this._appendLog(`screen wake lock released (${reason || "stop"})`);
      } catch (_error) {
        // best effort
      }
    }

    _shouldRunNetworkPreflight(nowMs) {
      if (this.state.networkPreflightInFlight) {
        return false;
      }
      if (Number(this.state.networkErrorBurstCount || 0) < this.networkPreflightBurstThreshold) {
        return false;
      }
      const burstStartedAt = Number(this.state.networkErrorBurstStartedAtMs || 0);
      if (!burstStartedAt || (nowMs - burstStartedAt) > this.networkPreflightBurstWindowMs) {
        return false;
      }
      const lastPreflightAt = Number(this.state.lastNetworkPreflightAtMs || 0);
      if (lastPreflightAt && (nowMs - lastPreflightAt) < this.networkPreflightCooldownMs) {
        return false;
      }
      return true;
    }

    async _runNetworkPreflight(reason) {
      this.state.networkPreflightInFlight = true;
      this.state.lastNetworkPreflightAtMs = this._now();
      this._appendLog(`network preflight probe started (${reason || "network-burst"})`);
      this._emitWorkerStatus("network-preflight-start");
      const controller = typeof AbortController === "function" ? new AbortController() : null;
      const timeoutId = controller ? window.setTimeout(() => controller.abort(), this.networkPreflightTimeoutMs) : null;
      let ok = false;
      try {
        const response = await fetch("https://www.google.com/generate_204", {
          method: "GET",
          mode: "no-cors",
          cache: "no-store",
          credentials: "omit",
          referrerPolicy: "no-referrer",
          signal: controller ? controller.signal : undefined,
        });
        ok = Boolean(response);
      } catch (_error) {
        ok = false;
      } finally {
        if (timeoutId) {
          window.clearTimeout(timeoutId);
        }
      }
      this.state.lastNetworkPreflightOk = ok;
      this.state.networkPreflightInFlight = false;
      this._appendLog(`network preflight probe result: ${ok ? "reachable" : "unreachable"}`);
      this._emitWorkerStatus(ok ? "network-preflight-ok" : "network-preflight-failed");
      if (!ok) {
        this.state.desiredRunning = false;
        this.state.pendingStart = false;
        this._clearAllTimers();
        this._setSupervisorState("fatal");
        this._setTerminalDegradedReason("recognition_network_unreachable");
        this._setStatus(
          this._locale() === "ru"
            ? "сеть недоступна для Web Speech"
            : "recognition cloud unreachable"
        );
        this._appendLog(
          this._locale() === "ru"
            ? "Web Speech: сетевой preflight provalil — облако распознавания недоступно. Проверьте VPN/firewall/DNS/прокси и нажмите Start заново."
            : "Web Speech: network preflight failed — recognition cloud unreachable. Check VPN/firewall/DNS/proxy and press Start again."
        );
        await this._releaseWakeLock("network-preflight-failed");
        this._emitWorkerStatus("terminal-network-unreachable");
        return false;
      }
      return true;
    }

    _resetNetworkErrorBurst() {
      this.state.networkErrorBurstCount = 0;
      this.state.networkErrorBurstStartedAtMs = 0;
    }

    _registerNetworkErrorForPreflight() {
      const now = this._now();
      const startedAt = Number(this.state.networkErrorBurstStartedAtMs || 0);
      if (!startedAt || (now - startedAt) > this.networkPreflightBurstWindowMs) {
        this.state.networkErrorBurstStartedAtMs = now;
        this.state.networkErrorBurstCount = 1;
      } else {
        this.state.networkErrorBurstCount = Number(this.state.networkErrorBurstCount || 0) + 1;
      }
      if (this._shouldRunNetworkPreflight(now)) {
        this._runNetworkPreflight("network-burst-threshold");
      }
    }

    async _ensureMicrophonePermission() {
      if (this._permissionPromise) {
        return this._permissionPromise;
      }
      this._appendLog("requesting microphone permission");
      this._permissionPromise = Promise.resolve(this.options.ensureMicrophonePermission?.())
        .then((result) => {
          this._permissionPromise = null;
          this.state.getUserMediaLastError = null;
          this._appendLog("microphone permission granted");
          return result;
        })
        .catch((error) => {
          this._permissionPromise = null;
          this.state.getUserMediaLastError = error instanceof Error ? error.message : String(error || "");
          this._appendLog(`microphone permission failed: ${error instanceof Error ? error.message : error}`);
          throw error;
        });
      return this._permissionPromise;
    }

    async _waitUntilDocumentVisibleForRecognition(options = {}) {
      const visibilityMaxMs = Math.max(0, Number(options.visibilityMaxMs ?? 20000));
      const focusMaxMs = Math.max(0, Number(options.focusMaxMs ?? 6000));
      const waitFocus = Boolean(options.waitWindowFocus ?? false);

      if (document.hidden) {
        this._appendLog("document hidden; waiting for tab visibility before recognition start");
        await new Promise((resolve) => {
          let done = false;
          const cleanup = () => {
            document.removeEventListener("visibilitychange", onVis);
            window.clearTimeout(timer);
          };
          const finish = () => {
            if (done) {
              return;
            }
            done = true;
            cleanup();
            resolve();
          };
          const onVis = () => {
            if (!document.hidden) {
              this._appendLog("tab became visible; continuing recognition start");
              finish();
            }
          };
          document.addEventListener("visibilitychange", onVis);
          const timer = window.setTimeout(() => {
            this._appendLog("visibility wait timed out; continuing recognition start anyway");
            finish();
          }, visibilityMaxMs);
        });
      }

      if (!this.state.desiredRunning) {
        return false;
      }

      if (waitFocus && typeof document.hasFocus === "function" && !document.hasFocus()) {
        this._appendLog("window not focused; waiting briefly before recognition start");
        const startAt = this._now();
        await new Promise((resolve) => {
          const timer = window.setInterval(() => {
            if (!this.state.desiredRunning) {
              window.clearInterval(timer);
              resolve();
              return;
            }
            if (document.hasFocus()) {
              this._appendLog("window focused; continuing recognition start");
              window.clearInterval(timer);
              resolve();
              return;
            }
            if (this._now() - startAt >= focusMaxMs) {
              this._appendLog("focus wait timed out; continuing recognition start anyway");
              window.clearInterval(timer);
              resolve();
            }
          }, 80);
        });
      }

      return Boolean(this.state.desiredRunning);
    }

    _createRecognition(generationId) {
      const recognition = new this.SpeechRecognitionCtor();
      recognition.maxAlternatives = 1;
      this.state.recognitionGenerationId = generationId;
      this.state.recognition = recognition;
      this.applyRecognitionSettings();

      recognition.onstart = () => {
        if (!this._isActiveGeneration(generationId)) {
          return;
        }
        this.state.lastStartAtMs = this._now();
        this.state.lastSessionStartedAtMs = this.state.lastStartAtMs;
        this.state.stoppingSinceMs = null;
        this._setLastError(null, null);
        this.state.noSpeechBackoffMs = 0;
        this.state.restartBackoffMs = 0;
        this._setTerminalDegradedReason(null);
        this.state.pendingRestartReason = null;
        this._resetCycleState();
        this._setRecognitionState("running");
        this._setSupervisorState("running");
        this._setStatus("listening");
        this.state.visibilityDegraded = Boolean(document.hidden && this.state.desiredRunning);
        this._refreshDegradedReason();
        this._markActivity("start");
        this._emitWorkerStatus("recognition-started");
      };

      recognition.onsoundstart = () => {
        if (!this._isActiveGeneration(generationId)) {
          return;
        }
        this.state.onSound = true;
        this._markActivity("sound");
        this._updateCounters();
      };

      recognition.onsoundend = () => {
        if (!this._isActiveGeneration(generationId)) {
          return;
        }
        this.state.onSound = false;
        this._updateCounters();
      };

      recognition.onspeechstart = () => {
        if (!this._isActiveGeneration(generationId)) {
          return;
        }
        this._markActivity("speech");
      };

      recognition.onerror = (event) => {
        if (!this._isActiveGeneration(generationId)) {
          return;
        }
        const errorKind = String(event?.error || "").trim().toLowerCase() || "unknown";
        const errorMessage = String(event?.message || "").trim();
        this._setLastError(errorKind, errorMessage);
        this._markActivity("error");
        if (errorKind === "no-speech") {
          this.state.noSpeechCount = Number(this.state.noSpeechCount || 0) + 1;
          this.state.pendingRestartReason = "no_speech";
          this._setStatus("restarting");
          this._emitWorkerStatus("recognition-error");
          return;
        }
        if (errorKind === "network") {
          this.state.networkErrorCount = Number(this.state.networkErrorCount || 0) + 1;
          this.state.pendingRestartReason = "network";
          this._setSupervisorState("backoff");
          this._setStatus("socket-reconnecting");
          const now = this._now();
          const last = Number(this._lastWebSpeechNetworkHintAtMs || 0);
          if (now - last > 15000) {
            this._lastWebSpeechNetworkHintAtMs = now;
            this._appendLog(
              this._locale() === "ru"
                ? "Web Speech: ошибка network — облако распознавания недоступно (VPN, фаервол, DNS, прокси, блокировщики). Проверьте интернет; смена микрофона в браузере это обычно не лечит."
                : "Web Speech network error: recognition service unreachable (VPN, firewall, DNS, proxy, blockers). Check connectivity; changing the browser microphone usually does not fix this."
            );
          }
          this._registerNetworkErrorForPreflight();
          this._emitWorkerStatus("recognition-error");
          return;
        }
        if (errorKind === "aborted") {
          if (this.state.desiredRunning) {
            this.state.pendingRestartReason = "normal_onend";
          }
          this._emitWorkerStatus("recognition-error");
          return;
        }
        if (["not-allowed", "service-not-allowed", "audio-capture", "language-not-supported"].includes(errorKind)) {
          this.state.desiredRunning = false;
          this.state.pendingStart = false;
          this._clearAllTimers();
          this._setSupervisorState("fatal");
          this._setStatus(this._locale() === "ru" ? `ошибка: ${errorKind}` : `error: ${errorKind}`);
          this._setTerminalDegradedReason(errorKind === "audio-capture" ? "audio_capture_recovery" : "permission_denied");
          this._emitWorkerStatus("terminal-error");
        }
      };

      recognition.onend = () => {
        if (!this._isActiveGeneration(generationId)) {
          return;
        }
        this.state.lastEndAtMs = this._now();
        this.state.lastSessionEndedAtMs = this.state.lastEndAtMs;
        this.state.onSound = false;
        this._setRecognitionState("idle");
        if (!this.state.desiredRunning) {
          this._cleanupRecognitionInstance(generationId);
          this._resetSegmentTracking();
          this._setSupervisorState("idle");
          this._setStatus("stopped");
          this._emitWorkerStatus("recognition-ended");
          return;
        }
        this._cleanupRecognitionInstance(generationId);
        this._emitWorkerStatus("recognition-ended");
        if (this.state.pendingStart) {
          this.state.pendingStart = false;
          const pendingReason = this.state.pendingRestartReason || "normal_onend";
          this.state.pendingRestartReason = null;
          this._scheduleRestart(pendingReason);
          return;
        }
        const restartReason = this.state.pendingRestartReason
          || (this.state.lastErrorKind === "network" ? "network" : null)
          || (this.state.lastErrorKind === "no-speech" ? "no_speech" : null)
          || "normal_onend";
        this.state.pendingRestartReason = null;
        this._scheduleRestart(restartReason);
      };

      recognition.onresult = (event) => {
        if (!this._isActiveGeneration(generationId)) {
          return;
        }
        let interimText = "";
        let finalText = "";
        this.state.lastResultIndex = Number(event.resultIndex || 0);
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
        this.state.restartBackoffMs = 0;
        if (interimText) {
          this._markActivity("result");
          const clientSegmentId = this._ensureClientSegmentId();
          const nowMs = this._now();
          const normalizedInterimText = this._normalizeTranscriptText(interimText);
          if (normalizedInterimText !== this.state.currentSegmentLastPartialText) {
            this.state.currentPartialStableSinceMs = nowMs;
          }
          this.state.currentPartial = interimText;
          this.state.lastPartialAt = nowMs;
          this.options.setPartialText?.(interimText);
          if (!this._shouldSuppressDuplicatePartial(interimText)) {
            this.state.currentSegmentLastPartialText = normalizedInterimText;
            this.state.currentSegmentForcedFinalized = false;
            this._sendUpdate({
              partial: interimText,
              final: "",
              is_final: false,
              source_lang: this.state.sourceLang,
              client_segment_id: clientSegmentId,
              forced_final: false,
            });
          }
          this._scheduleForceFinalize();
          this._setStatus("interim");
        }
        if (finalText) {
          this._markActivity("result");
          const clientSegmentId = this.state.currentClientSegmentId || this._ensureClientSegmentId();
          if (this._shouldSuppressFinal(finalText)) {
            this._clearForceFinalizeTimer();
            this.state.currentPartial = "";
            this.options.setPartialText?.("");
            this._emitWorkerStatus("result");
            this._updateCounters();
            return;
          }
          this._clearForceFinalizeTimer();
          this.state.currentPartial = "";
          this.state.currentPartialStableSinceMs = 0;
          this.state.lastFinalAt = this._now();
          this.state.finalCount = Number(this.state.finalCount || 0) + 1;
          this.state.currentSegmentLastFinalText = this._normalizeTranscriptText(finalText);
          this.options.setFinalText?.(finalText);
          this.options.setPartialText?.("");
          this._sendUpdate({
            partial: "",
            final: finalText,
            is_final: true,
            source_lang: this.state.sourceLang,
            client_segment_id: clientSegmentId,
            forced_final: false,
          });
          this._consumeCompletedSegment();
          this._setStatus("final");
        }
        this._emitWorkerStatus("result");
        this._updateCounters();
      };

      return recognition;
    }

    _performControlledStart(reason) {
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
      this.state.providerName = this.state.browserMode || "browser_google";
      this.state.pendingRestartReason = null;
      this.ensureSocketConnected();
      const recognition = this._createRecognition(generationId);
      const startLogThrottle = this._recognitionStartBurstThrottle(reason);
      try {
        recognition.start();
        if (startLogThrottle.key) {
          this._appendLogThrottled(`recognition.start (${reason})`, startLogThrottle.key, startLogThrottle.gapMs);
        } else {
          this._appendLog(`recognition.start (${reason})`);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error || "start failed");
        if (String(message).toLowerCase().includes("already started")) {
          this._setSupervisorState("running");
          this._setRecognitionState("running");
          this._setStatus("listening");
          return;
        }
        this._setRecognitionState("idle");
        this._setSupervisorState("restarting");
        this._appendLog(`recognition.start failed: ${message}`);
        this._scheduleRestart("network");
      }
    }

    _transitionToStopping(reason) {
      const recognition = this.state.recognition;
      if (reason !== "user-stop") {
        this._forceFinalizeOnInterruption("browser_recognition_interrupted");
      }
      if (!recognition) {
        this._cleanupRecognitionInstance(this.state.recognitionGenerationId);
        this._setRecognitionState("idle");
        this._setSupervisorState(this.state.desiredRunning ? "restarting" : "idle");
        this._setStatus(this.state.desiredRunning ? "restarting" : "stopped");
        if (this.state.desiredRunning) {
          this._scheduleRestart(this.state.pendingRestartReason || "normal_onend");
        }
        return;
      }
      if (this.state.browserSupervisorState !== "stopping") {
        this._setSupervisorState("stopping");
      }
      this._setRecognitionState("stopping");
      this.state.stoppingSinceMs = this._now();
      this._setStatus("stopping");
      try {
        recognition.stop();
        this._appendLog(`recognition.stop (${reason})`);
      } catch (_error) {
        this._cleanupRecognitionInstance(this.state.recognitionGenerationId);
        this._setRecognitionState("idle");
        this._setSupervisorState(this.state.desiredRunning ? "restarting" : "idle");
        if (this.state.desiredRunning) {
          this._scheduleRestart(this.state.pendingRestartReason || "normal_onend");
        }
      }
    }

    _scheduleRestart(reason, options = {}) {
      if (!this.state.desiredRunning) {
        this._setSupervisorState("idle");
        return;
      }
      const normalizedReason = String(reason || "normal_onend").trim().toLowerCase();
      const requestedDelayMs = Math.max(
        0,
        Number(options.backoffMs != null ? options.backoffMs : this._restartDelayForReason(normalizedReason))
      );
      const delayMs = this._minimumReconnectGuardDelayMs(requestedDelayMs);
      this._clearRestartTimer();
      this.state.restartCount = Number(this.state.restartCount || 0) + 1;
      this.state.lastRestartReason = normalizedReason;
      this._setSupervisorState(delayMs > this.restartDelayByReasonMs.normal_onend ? "backoff" : "restarting");
      this._setStatus("restarting");
      const capturedGeneration = Number(this.state.generationId || 0);
      this.state.restartTimer = window.setTimeout(() => {
        if (!this.state.desiredRunning) {
          return;
        }
        if (capturedGeneration !== Number(this.state.generationId || 0)) {
          return;
        }
        if (this.state.browserSupervisorState === "stopping") {
          this.state.pendingStart = true;
          return;
        }
        this._performControlledStart(normalizedReason);
      }, delayMs);
      this._emitWorkerStatus("restart-scheduled");
    }

    _nextNetworkBackoff() {
      if (!this.state.restartBackoffMs) {
        return Math.max(100, Number(this.state.networkReconnectInitialMs || this.initialNetworkBackoffMs));
      }
      return Math.min(
        Math.max(100, Number(this.state.networkReconnectMaxMs || this.maxNetworkBackoffMs)),
        this.state.restartBackoffMs * 2
      );
    }

    _cleanupRecognitionInstance(generationId) {
      if (!this.state.recognition || generationId !== this.state.recognitionGenerationId) {
        return;
      }
      const recognition = this.state.recognition;
      recognition.onstart = null;
      recognition.onend = null;
      recognition.onerror = null;
      recognition.onresult = null;
      recognition.onsoundstart = null;
      recognition.onsoundend = null;
      recognition.onspeechstart = null;
      recognition.onspeechend = null;
      recognition.onaudiostart = null;
      recognition.onaudioend = null;
      this.state.recognition = null;
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
      const sessionAgeMs = this._currentSessionAgeMs(now);
      const prepareAtMs = Math.max(
        0,
        Number(this.state.maxBrowserSessionAgeMs || this.maxBrowserSessionAgeMs)
        - Number(this.state.prepareCycleBeforeMs || this.prepareCycleBeforeMs)
      );
      if (
        this.state.browserSupervisorState === "running"
        && sessionAgeMs != null
        && sessionAgeMs >= prepareAtMs
        && !this.state.browserCyclePending
      ) {
        this.state.browserCyclePending = true;
        this._emitWorkerStatus("cycle-pending");
      }
      if (
        this.state.browserSupervisorState === "running"
        && sessionAgeMs != null
        && sessionAgeMs >= Number(this.state.maxBrowserSessionAgeMs || this.maxBrowserSessionAgeMs)
      ) {
        this.state.browserCycleCount = Number(this.state.browserCycleCount || 0) + 1;
        this.state.pendingStart = true;
        this.state.pendingRestartReason = "session_cycle";
        this._appendLog("browser session age limit reached; controlled cycle requested");
        this._transitionToStopping("session-cycle");
        this._emitWorkerStatus("session-cycle");
        return;
      }
      if (this.state.browserSupervisorState === "stopping" && this.state.stoppingSinceMs) {
        if ((now - Number(this.state.stoppingSinceMs)) >= this.maxStoppingMs) {
          const recognition = this.state.recognition;
          if (recognition) {
            try {
              recognition.abort();
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
      }
      const lastActivityAt = Math.max(
        Number(this.state.lastEventAtMs || 0),
        Number(this.state.lastStartAtMs || 0),
        Number(this.state.lastResultAtMs || 0)
      );
      const idleThresholdMs = document.hidden ? this.hiddenIdleRestartMs : this.visibleIdleRestartMs;
      if (lastActivityAt > 0 && (now - lastActivityAt) >= idleThresholdMs && this.state.browserSupervisorState === "running") {
        this.state.pendingStart = true;
        this.state.pendingRestartReason = "watchdog_stall";
        this._appendLog("watchdog forced rearm");
        this._transitionToStopping("watchdog");
        return;
      }
      this._emitHeartbeat("watchdog");
    }
  }

  global.BrowserAsrSessionManager = BrowserAsrSessionManager;
})(window);
