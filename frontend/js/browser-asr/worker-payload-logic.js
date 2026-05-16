/**
 * WebSocket worker status / heartbeat / transcript payload builders.
 */
(function attachSstBrowserAsrWorkerPayload(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  root.buildLastError = function buildLastError(state) {
    const parts = [state.lastErrorKind, state.lastError].filter(Boolean);
    return parts.length ? parts.join(": ") : null;
  };

  /**
   * @param {object} ctx
   * @param {object} ctx.state
   * @param {string} ctx.type
   * @param {object} [ctx.extra]
   * @param {number} ctx.nowMs
   * @param {string} ctx.visibilityState
   * @param {number|null} ctx.browserSessionAgeMs
   * @param {boolean} ctx.wakeLockSupported
   */
  root.buildWorkerPayload = function buildWorkerPayload(ctx) {
    const state = ctx.state;
    const extra = ctx.extra && typeof ctx.extra === "object" ? ctx.extra : {};
    return {
      type: ctx.type,
      session_id: state.sessionId,
      generation_id: Number(state.generationId || 0),
      browser_mode: state.browserMode || "browser_google",
      provider_name: state.providerName || state.browserMode || "browser_google",
      desired_running: Boolean(state.desiredRunning),
      active_recognition: Boolean(state.recognition),
      active_media_stream: Boolean(state.mediaStream),
      recognition_state: state.recognitionState || "idle",
      browser_supervisor_state: state.browserSupervisorState || "idle",
      supervisor_state: state.browserSupervisorState || "idle",
      pending_start: Boolean(state.pendingStart),
      websocket_ready: Boolean(state.websocketReady),
      degraded_reason: state.degradedReason || null,
      last_error: root.buildLastError(state),
      error_type: state.lastErrorKind || null,
      restart_count: Number(state.restartCount || 0),
      no_speech_count: Number(state.noSpeechCount || 0),
      network_error_count: Number(state.networkErrorCount || 0),
      stopping_since_ms: state.stoppingSinceMs
        ? Math.max(0, ctx.nowMs - Number(state.stoppingSinceMs))
        : null,
      recognition_continuous: Boolean(state.actualContinuous),
      effective_continuous_mode: state.effectiveContinuousMode || "native_continuous",
      client_segment_id: state.currentClientSegmentId || null,
      forced_final: Boolean(state.currentSegmentForcedFinalized),
      last_result_index: state.lastResultIndex,
      last_result_at_ms: Number(state.lastResultAtMs || 0) || null,
      last_session_started_at_ms: Number(state.lastSessionStartedAtMs || 0) || null,
      last_session_ended_at_ms: Number(state.lastSessionEndedAtMs || 0) || null,
      browser_session_age_ms: ctx.browserSessionAgeMs,
      browser_cycle_pending: Boolean(state.browserCyclePending),
      browser_cycle_count: Number(state.browserCycleCount || 0),
      browser_minimum_reconnect_suppressed_count: Number(state.browserMinimumReconnectSuppressedCount || 0),
      browser_forced_final_on_interruption_count: Number(state.browserForcedFinalOnInterruptionCount || 0),
      duplicate_partial_suppressed: Number(state.duplicatePartialSuppressed || 0),
      duplicate_final_suppressed: Number(state.duplicateFinalSuppressed || 0),
      late_forced_final_suppressed: Number(state.lateForcedFinalSuppressed || 0),
      mic_track_ready_state: state.micTrackReadyState || null,
      mic_track_muted: Boolean(state.micTrackMuted),
      mic_rms: Number.isFinite(state.micRms) ? Number(state.micRms) : 0,
      mic_active_recent_ms:
        state.micActiveRecentMs == null ? null : Math.max(0, Number(state.micActiveRecentMs || 0)),
      last_mic_activity_at: Number(state.lastMicActivityAt || 0) || null,
      get_user_media_count: Number(state.getUserMediaCount || 0),
      get_user_media_last_error: state.getUserMediaLastError || null,
      mic_stream_active: Boolean(state.micStreamActive),
      media_tracks_stopped_count: Number(state.mediaTracksStoppedCount || 0),
      media_track_leak_guard_count: Number(state.mediaTrackLeakGuardCount || 0),
      visibility_state: ctx.visibilityState,
      wake_lock_active: Boolean(state.wakeLockActive),
      wake_lock_supported: ctx.wakeLockSupported,
      network_error_burst_count: Number(state.networkErrorBurstCount || 0),
      network_preflight_last_at_ms: Number(state.lastNetworkPreflightAtMs || 0) || null,
      network_preflight_last_ok:
        state.lastNetworkPreflightOk == null ? null : Boolean(state.lastNetworkPreflightOk),
      last_seen_at_ms: ctx.nowMs,
      ...extra,
    };
  };
})(typeof window !== "undefined" ? window : globalThis);
