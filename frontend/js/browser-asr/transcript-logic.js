/**
 * Transcript normalization, dedupe, segment ids, update payload shaping.
 */
(function attachSstBrowserAsrTranscript(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  root.normalizeTranscriptText = function normalizeTranscriptText(value) {
    return String(value || "")
      .trim()
      .replace(/\s+/g, " ");
  };

  root.currentGenerationId = function currentGenerationId(state) {
    return Number(state.generationId || 0);
  };

  root.ensureClientSegmentId = function ensureClientSegmentId(state) {
    if (state.currentClientSegmentId && !state.currentSegmentForcedFinalized) {
      return state.currentClientSegmentId;
    }
    state.nextClientSegmentOrdinal = Number(state.nextClientSegmentOrdinal || 0) + 1;
    const ordinal = state.nextClientSegmentOrdinal;
    const sessionId = String(state.sessionId || "browser-worker").replace(/[^a-z0-9_-]+/gi, "-");
    const generationId = root.currentGenerationId(state);
    state.currentClientSegmentId = `${sessionId}-g${generationId}-s${ordinal}`;
    state.currentSegmentLastPartialText = "";
    state.currentSegmentLastFinalText = "";
    state.currentSegmentForcedFinalized = false;
    return state.currentClientSegmentId;
  };

  root.consumeCompletedSegment = function consumeCompletedSegment(state) {
    state.currentClientSegmentId = null;
    state.currentSegmentLastPartialText = "";
    state.currentSegmentLastFinalText = "";
    state.currentSegmentForcedFinalized = false;
  };

  root.resetSegmentTrackingFields = function resetSegmentTrackingFields(state) {
    state.currentClientSegmentId = null;
    state.currentSegmentLastPartialText = "";
    state.currentSegmentLastFinalText = "";
    state.currentPartialStableSinceMs = 0;
    state.currentSegmentForcedFinalized = false;
    state.lastForcedFinal = null;
  };

  root.shouldSuppressDuplicatePartial = function shouldSuppressDuplicatePartial(state, text) {
    const normalizedText = root.normalizeTranscriptText(text);
    if (!normalizedText) {
      return true;
    }
    if (normalizedText === state.currentSegmentLastPartialText) {
      state.duplicatePartialSuppressed = Number(state.duplicatePartialSuppressed || 0) + 1;
      return true;
    }
    return false;
  };

  root.shouldSuppressFinal = function shouldSuppressFinal(state, text, { forcedFinal = false } = {}) {
    const normalizedText = root.normalizeTranscriptText(text);
    if (!normalizedText) {
      return true;
    }
    const lateForcedFinal = state.lastForcedFinal;
    if (
      !forcedFinal
      && state.currentSegmentForcedFinalized
      && lateForcedFinal
      && Number(lateForcedFinal.generation_id || 0) === root.currentGenerationId(state)
      && root.normalizeTranscriptText(lateForcedFinal.text) === normalizedText
    ) {
      state.lateForcedFinalSuppressed = Number(state.lateForcedFinalSuppressed || 0) + 1;
      root.consumeCompletedSegment(state);
      return true;
    }
    if (normalizedText === state.currentSegmentLastFinalText) {
      state.duplicateFinalSuppressed = Number(state.duplicateFinalSuppressed || 0) + 1;
      return true;
    }
    return false;
  };

  root.canForceFinalizeOnInterruption = function canForceFinalizeOnInterruption(state, isForceFinalizationEnabled) {
    if (!state.forceFinalOnInterruption || isForceFinalizationEnabled === false) {
      return false;
    }
    const normalizedText = root.normalizeTranscriptText(state.currentPartial);
    if (!normalizedText || normalizedText.length < Math.max(1, Number(state.forceFinalMinChars || 0))) {
      return false;
    }
    if (normalizedText === state.currentSegmentLastFinalText) {
      return false;
    }
    const stableSinceMs = Number(state.currentPartialStableSinceMs || 0);
    if (!stableSinceMs) {
      return false;
    }
    return Date.now() - stableSinceMs >= Math.max(0, Number(state.forceFinalMinStableMs || 0));
  };

  root.buildTranscriptUpdatePayload = function buildTranscriptUpdatePayload(state, payload, nowMs) {
    state.workerTranscriptMessageSequence = Number(state.workerTranscriptMessageSequence || 0) + 1;
    return {
      partial: payload.partial || "",
      final: payload.final || "",
      is_final: Boolean(payload.is_final),
      source_lang: payload.source_lang || state.sourceLang || "auto",
      client_segment_id: payload.client_segment_id || state.currentClientSegmentId || null,
      forced_final: Boolean(payload.forced_final),
      forced_final_reason: payload.forced_final_reason || null,
      asr_result_created_at_ms: payload.asr_result_created_at_ms || nowMs,
      worker_send_started_at_ms: nowMs,
      worker_message_sequence: state.workerTranscriptMessageSequence,
    };
  };

  root.markResultActivity = function markResultActivity(state, nowMs) {
    state.lastEventAtMs = nowMs;
    state.lastResultAtMs = state.lastEventAtMs;
    state.noSpeechBackoffMs = 0;
    state.restartBackoffMs = 0;
  };
})(typeof window !== "undefined" ? window : globalThis);
