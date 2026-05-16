/**
 * Mic / recognition stall health degraded reason (pure evaluation).
 */
(function attachSstBrowserAsrHealthSignals(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  /**
   * @param {object} ctx
   * @param {object} ctx.state
   * @param {number} ctx.nowMs
   * @param {boolean} ctx.documentHidden
   * @param {object} ctx.limits - instance timing thresholds
   */
  root.computeHealthDegradedReason = function computeHealthDegradedReason(ctx) {
    const state = ctx.state;
    const now = ctx.nowMs;
    const limits = ctx.limits;

    const trackReadyState = String(state.micTrackReadyState || "").trim().toLowerCase();
    const micActivityAgeMs = state.lastMicActivityAt > 0 ? Math.max(0, now - Number(state.lastMicActivityAt)) : null;
    const recognitionQuietMs = Math.max(
      0,
      now
        - Math.max(
          Number(state.lastEventAtMs || 0),
          Number(state.lastResultAtMs || 0),
          Number(state.lastStartAtMs || 0)
        )
    );
    state.micActiveRecentMs = micActivityAgeMs;

    if (!state.desiredRunning) {
      return null;
    }
    if (trackReadyState && trackReadyState !== "live") {
      return "mic_track_unavailable";
    }
    if (
      !ctx.documentHidden
      && state.browserSupervisorState === "running"
      && micActivityAgeMs != null
      && micActivityAgeMs >= limits.micSilentDegradedAfterMs
    ) {
      return "mic_silent";
    }
    const micRms = Number(state.micRms || 0);
    const voiceLevelGoodRecently =
      micRms >= limits.voiceBelowRecognitionRmsThreshold
      || (
        micActivityAgeMs != null
        && micActivityAgeMs <= limits.voiceBelowRecognitionMicWindowMs
        && Number(state.noSpeechCount || 0) >= limits.voiceBelowRecognitionMinNoSpeech
      );
    if (
      !ctx.documentHidden
      && state.browserSupervisorState === "running"
      && recognitionQuietMs >= limits.voiceBelowRecognitionGraceMs
      && voiceLevelGoodRecently
      && Number(state.noSpeechCount || 0) >= limits.voiceBelowRecognitionMinNoSpeech
    ) {
      return "voice_below_recognition_threshold";
    }
    if (
      !ctx.documentHidden
      && state.browserSupervisorState === "running"
      && recognitionQuietMs >= limits.stallDegradedAfterMs
      && micActivityAgeMs != null
      && micActivityAgeMs <= limits.recentMicActivityWindowMs
    ) {
      return "web_speech_stalled";
    }
    return null;
  };
})(typeof window !== "undefined" ? window : globalThis);
