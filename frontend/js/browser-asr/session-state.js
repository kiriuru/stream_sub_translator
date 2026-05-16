/**
 * Browser ASR worker state initialization (pure merge into state object).
 */
(function attachSstBrowserAsrState(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  root.createBrowserAsrStateSeed = function createBrowserAsrStateSeed(existing) {
    const seed = existing && typeof existing === "object" ? existing : {};
    return {
      desiredRunning: Boolean(seed.desiredRunning),
      pendingStart: Boolean(seed.pendingStart),
      generationId: Number(seed.generationId || 0),
      sessionId: seed.sessionId || `browser-worker-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
      providerName: seed.providerName || seed.browserMode || "browser_google",
      browserSupervisorState: seed.browserSupervisorState || "idle",
      recognitionState: seed.recognitionState || "idle",
      restartTimer: seed.restartTimer || null,
      reconnectTimer: seed.reconnectTimer || null,
      watchdogTimerId: seed.watchdogTimerId || null,
      restartCount: Number(seed.restartCount || 0),
      noSpeechCount: Number(seed.noSpeechCount || 0),
      networkErrorCount: Number(seed.networkErrorCount || 0),
      websocketReady: Boolean(seed.websocketReady),
      stoppingSinceMs: seed.stoppingSinceMs || null,
      lastStartAtMs: Number(seed.lastStartAtMs || 0),
      lastEndAtMs: Number(seed.lastEndAtMs || 0),
      lastSessionStartedAtMs: Number(seed.lastSessionStartedAtMs || 0),
      lastSessionEndedAtMs: Number(seed.lastSessionEndedAtMs || 0),
      lastEventAtMs: Number(seed.lastEventAtMs || 0),
      lastResultAtMs: Number(seed.lastResultAtMs || 0),
      lastResultIndex: seed.lastResultIndex == null ? null : Number(seed.lastResultIndex || 0),
      browserCyclePending: Boolean(seed.browserCyclePending),
      browserCycleCount: Number(seed.browserCycleCount || 0),
      browserMinimumReconnectSuppressedCount: Number(seed.browserMinimumReconnectSuppressedCount || 0),
      browserForcedFinalOnInterruptionCount: Number(seed.browserForcedFinalOnInterruptionCount || 0),
      lastErrorKind: seed.lastErrorKind || null,
      lastError: seed.lastError || null,
      degradedReason: seed.degradedReason || null,
      terminalDegradedReason: seed.terminalDegradedReason || null,
      healthDegradedReason: seed.healthDegradedReason || null,
      socketDegraded: Boolean(seed.socketDegraded),
      visibilityDegraded: Boolean(seed.visibilityDegraded),
      restartBackoffMs: Number(seed.restartBackoffMs || 0),
      noSpeechBackoffMs: Number(seed.noSpeechBackoffMs || 0),
      pendingRestartReason: seed.pendingRestartReason || null,
      lastRestartReason: seed.lastRestartReason || null,
      recognition: null,
      recognitionOverlapSlots: null,
      recognitionOverlapActiveSlot: null,
      recognitionOverlapPrestarted: false,
      recognitionOverlapSlotListening: null,
      webSpeechPhraseHintsSuppressed: Boolean(seed.webSpeechPhraseHintsSuppressed),
      webSpeechLanguageSoftFallbackUsed: Boolean(seed.webSpeechLanguageSoftFallbackUsed),
      recognitionGenerationId: 0,
      effectiveContinuousMode: seed.effectiveContinuousMode || "native_continuous",
      currentClientSegmentId: seed.currentClientSegmentId || null,
      nextClientSegmentOrdinal: Number(seed.nextClientSegmentOrdinal || 0),
      currentSegmentLastPartialText: seed.currentSegmentLastPartialText || "",
      currentSegmentLastFinalText: seed.currentSegmentLastFinalText || "",
      currentPartialStableSinceMs: Number(seed.currentPartialStableSinceMs || 0),
      currentSegmentForcedFinalized: Boolean(seed.currentSegmentForcedFinalized),
      lastForcedFinal: seed.lastForcedFinal || null,
      duplicatePartialSuppressed: Number(seed.duplicatePartialSuppressed || 0),
      duplicateFinalSuppressed: Number(seed.duplicateFinalSuppressed || 0),
      lateForcedFinalSuppressed: Number(seed.lateForcedFinalSuppressed || 0),
      minimumReconnectIntervalMs: Number(seed.minimumReconnectIntervalMs || 500),
      normalRestartDelayMs: Number(seed.normalRestartDelayMs || 350),
      noSpeechRestartDelayMs: Number(seed.noSpeechRestartDelayMs || 350),
      networkReconnectInitialMs: Number(seed.networkReconnectInitialMs || 1000),
      networkReconnectMaxMs: Number(seed.networkReconnectMaxMs || 30000),
      maxBrowserSessionAgeMs: Number(seed.maxBrowserSessionAgeMs || 180000),
      networkErrorBurstCount: Number(seed.networkErrorBurstCount || 0),
      networkErrorBurstStartedAtMs: Number(seed.networkErrorBurstStartedAtMs || 0),
      lastNetworkPreflightAtMs: Number(seed.lastNetworkPreflightAtMs || 0),
      lastNetworkPreflightOk: seed.lastNetworkPreflightOk == null ? null : Boolean(seed.lastNetworkPreflightOk),
      networkPreflightInFlight: Boolean(seed.networkPreflightInFlight),
      wakeLockActive: Boolean(seed.wakeLockActive),
      wakeLockSupported: typeof navigator !== "undefined" && Boolean(navigator?.wakeLock?.request),
      prepareCycleBeforeMs: Number(seed.prepareCycleBeforeMs || 15000),
      forceFinalOnInterruption: seed.forceFinalOnInterruption !== false,
      forceFinalMinChars: Number(seed.forceFinalMinChars || 3),
      forceFinalMinStableMs: Number(seed.forceFinalMinStableMs || 700),
      micTrackReadyState: seed.micTrackReadyState || null,
      micTrackMuted: Boolean(seed.micTrackMuted),
      micRms: Number(seed.micRms || 0),
      micActiveRecentMs: seed.micActiveRecentMs == null ? null : Number(seed.micActiveRecentMs || 0),
      lastMicActivityAt: Number(seed.lastMicActivityAt || 0),
      getUserMediaCount: Number(seed.getUserMediaCount || 0),
      getUserMediaLastError: seed.getUserMediaLastError || null,
      micStreamActive: Boolean(seed.micStreamActive),
      mediaTracksStoppedCount: Number(seed.mediaTracksStoppedCount || 0),
      mediaTrackLeakGuardCount: Number(seed.mediaTrackLeakGuardCount || 0),
      workerTranscriptMessageSequence: Number(seed.workerTranscriptMessageSequence || 0),
    };
  };

  root.initializeBrowserAsrState = function initializeBrowserAsrState(target, existing) {
    Object.assign(target, root.createBrowserAsrStateSeed(existing));
  };

  root.applyInstanceDefaults = function applyInstanceDefaults(manager) {
    const defaults = root.INSTANCE_DEFAULTS || {};
    Object.keys(defaults).forEach((key) => {
      manager[key] = defaults[key];
    });
    if (root.RESTART_DELAY_BY_REASON_MS) {
      manager.restartDelayByReasonMs = { ...root.RESTART_DELAY_BY_REASON_MS };
    }
  };
})(typeof window !== "undefined" ? window : globalThis);
