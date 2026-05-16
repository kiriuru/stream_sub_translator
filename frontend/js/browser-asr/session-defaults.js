/**
 * Timing defaults for BrowserAsrSessionManager (instance + state seed).
 */
(function attachSstBrowserAsrDefaults(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  root.RESTART_DELAY_BY_REASON_MS = {
    normal_onend: 350,
    settings_change: 350,
    websocket_reconnect: 350,
    watchdog_stall: 750,
    session_cycle: 350,
  };

  root.INSTANCE_DEFAULTS = {
    restartDelayByReasonMs: { ...root.RESTART_DELAY_BY_REASON_MS },
    initialNoSpeechDelayMs: 350,
    maxNoSpeechDelayMs: 5000,
    initialNetworkBackoffMs: 1000,
    maxNetworkBackoffMs: 30000,
    watchdogIntervalMs: 1000,
    maxStoppingMs: 2500,
    visibleIdleRestartMs: 30000,
    hiddenIdleRestartMs: 60000,
    stallDegradedAfterMs: 6000,
    micSilentDegradedAfterMs: 5000,
    recentMicActivityWindowMs: 2000,
    minimumReconnectIntervalMs: 500,
    maxBrowserSessionAgeMs: 180000,
    prepareCycleBeforeMs: 15000,
    forceFinalOnInterruption: true,
    forceFinalMinChars: 3,
    forceFinalMinStableMs: 700,
    voiceBelowRecognitionRmsThreshold: 0.025,
    voiceBelowRecognitionGraceMs: 8000,
    voiceBelowRecognitionMicWindowMs: 2000,
    voiceBelowRecognitionMinNoSpeech: 1,
    networkPreflightBurstThreshold: 3,
    networkPreflightBurstWindowMs: 12000,
    networkPreflightTimeoutMs: 4000,
    networkPreflightCooldownMs: 30000,
    recognitionStartLogMinGapMs: 4200,
  };
})(typeof window !== "undefined" ? window : globalThis);
