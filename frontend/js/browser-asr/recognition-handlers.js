/**
 * Web Speech recognition event wiring (delegates transcript/timing to sibling modules).
 */
(function attachSstBrowserAsrRecognitionHandlers(global) {
  "use strict";

  const ASR = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  function overlapSlotInactive(manager, overlapSlotIndex) {
    return (
      overlapSlotIndex != null
      && overlapSlotIndex !== Number(manager.state.recognitionOverlapActiveSlot || 0) % 2
    );
  }

  function applyRecognitionError(manager, generationId, overlapSlotIndex, event) {
    const policy = manager._webSpeechPolicy();
    const classified = ASR.classifyRecognitionError(event, policy, manager.state);
    const { errorKind, errorMessage } = classified;
    manager._setLastError(errorKind, errorMessage);
    manager._markActivity("error");

    switch (classified.kind) {
      case "phrases_retry":
        manager.state.webSpeechPhraseHintsSuppressed = true;
        manager.state.pendingRestartReason = "normal_onend";
        manager._setStatus("restarting");
        manager._appendLog(
          manager._locale() === "ru"
            ? "Web Speech: phrases-not-supported — повтор без on-device phrase hints."
            : "Web Speech: phrases-not-supported — retrying without on-device phrase hints."
        );
        manager._emitWorkerStatus("recognition-error");
        return;
      case "language_retry": {
        manager.state.webSpeechLanguageSoftFallbackUsed = true;
        const stripTargets = ASR.recognitionOverlapActive(manager.state)
          ? manager.state.recognitionOverlapSlots
          : [manager.state.recognition];
        stripTargets.forEach((rec) => manager._stripWebSpeechExperimentalHints(rec));
        manager.state.pendingRestartReason = "normal_onend";
        manager._setStatus("restarting");
        manager._appendLog(
          manager._locale() === "ru"
            ? "Web Speech: language-not-supported — одна попытка повтора после сброса on-device подсказок."
            : "Web Speech: language-not-supported — one retry after clearing on-device hints."
        );
        manager._emitWorkerStatus("recognition-error");
        return;
      }
      case "no_speech":
        manager.state.noSpeechCount = Number(manager.state.noSpeechCount || 0) + 1;
        manager.state.pendingRestartReason = "no_speech";
        manager._setStatus("restarting");
        manager._emitWorkerStatus("recognition-error");
        return;
      case "network":
        manager.state.networkErrorCount = Number(manager.state.networkErrorCount || 0) + 1;
        manager.state.pendingRestartReason = "network";
        manager._setSupervisorState("backoff");
        manager._setStatus("socket-reconnecting");
        {
          const now = manager._now();
          const last = Number(manager._lastWebSpeechNetworkHintAtMs || 0);
          if (now - last > 15000) {
            manager._lastWebSpeechNetworkHintAtMs = now;
            manager._appendLog(ASR.networkErrorHintMessages(manager._locale()));
          }
        }
        ASR.registerNetworkErrorForPreflight(manager);
        manager._emitWorkerStatus("recognition-error");
        return;
      case "aborted":
        if (ASR.recognitionOverlapActive(manager.state) && overlapSlotIndex != null) {
          const active = Number(manager.state.recognitionOverlapActiveSlot || 0) % 2;
          const buddy = (active + 1) % 2;
          if (
            overlapSlotIndex === active
            && manager.state.recognitionOverlapSlotListening
            && manager.state.recognitionOverlapSlotListening[buddy]
          ) {
            manager._emitWorkerStatus("recognition-error");
            return;
          }
        }
        if (manager.state.desiredRunning) {
          manager.state.pendingRestartReason = "normal_onend";
        }
        manager._emitWorkerStatus("recognition-error");
        return;
      case "terminal_permission":
        manager.state.desiredRunning = false;
        manager.state.pendingStart = false;
        manager._clearAllTimers();
        manager._setSupervisorState("fatal");
        manager._setStatus(manager._locale() === "ru" ? `ошибка: ${errorKind}` : `error: ${errorKind}`);
        manager._setTerminalDegradedReason(classified.terminalReason);
        manager._emitWorkerStatus("terminal-error");
        return;
      case "terminal_language":
        manager.state.desiredRunning = false;
        manager.state.pendingStart = false;
        manager._clearAllTimers();
        manager._setSupervisorState("fatal");
        manager._setStatus(manager._locale() === "ru" ? `ошибка: ${errorKind}` : `error: ${errorKind}`);
        manager._setTerminalDegradedReason("permission_denied");
        manager._emitWorkerStatus("terminal-error");
        return;
      default:
        break;
    }
  }

  function handleRecognitionResult(manager, generationId, overlapSlotIndex, event) {
    if (!manager._isActiveGeneration(generationId)) {
      return;
    }
    if (!ASR.overlapResultAllowed(manager.state, overlapSlotIndex)) {
      return;
    }
    const { interimText, finalText, resultIndex } = ASR.parseRecognitionResultEvent(event);
    manager.state.lastResultIndex = resultIndex;
    manager.state.restartBackoffMs = 0;

    if (interimText) {
      manager._markActivity("result");
      const clientSegmentId = manager._ensureClientSegmentId();
      const nowMs = manager._now();
      const normalizedInterimText = manager._normalizeTranscriptText(interimText);
      if (normalizedInterimText !== manager.state.currentSegmentLastPartialText) {
        manager.state.currentPartialStableSinceMs = nowMs;
      }
      manager.state.currentPartial = interimText;
      manager.state.lastPartialAt = nowMs;
      manager.options.setPartialText?.(interimText);
      if (!manager._shouldSuppressDuplicatePartial(interimText)) {
        manager.state.currentSegmentLastPartialText = normalizedInterimText;
        manager.state.currentSegmentForcedFinalized = false;
        manager._sendUpdate({
          partial: interimText,
          final: "",
          is_final: false,
          source_lang: manager.state.sourceLang,
          client_segment_id: clientSegmentId,
          forced_final: false,
        });
      }
      manager._scheduleForceFinalize();
      manager._setStatus("interim");
    }

    if (finalText) {
      manager._markActivity("result");
      const clientSegmentId = manager.state.currentClientSegmentId || manager._ensureClientSegmentId();
      if (manager._shouldSuppressFinal(finalText)) {
        manager._clearForceFinalizeTimer();
        manager.state.currentPartial = "";
        manager.options.setPartialText?.("");
        manager._emitWorkerStatus("result");
        manager._updateCounters();
        return;
      }
      manager._clearForceFinalizeTimer();
      manager.state.currentPartial = "";
      manager.state.currentPartialStableSinceMs = 0;
      manager.state.lastFinalAt = manager._now();
      manager.state.finalCount = Number(manager.state.finalCount || 0) + 1;
      manager.state.currentSegmentLastFinalText = manager._normalizeTranscriptText(finalText);
      manager.options.setFinalText?.(finalText);
      manager.options.setPartialText?.("");
      manager._sendUpdate({
        partial: "",
        final: finalText,
        is_final: true,
        source_lang: manager.state.sourceLang,
        client_segment_id: clientSegmentId,
        forced_final: false,
      });
      manager._consumeCompletedSegment();
      manager._setStatus("final");
      ASR.prestartOverlapBuddyIfNeeded(manager, overlapSlotIndex);
    }

    manager._emitWorkerStatus("result");
    manager._updateCounters();
  }

  ASR.wireRecognitionHandlers = function wireRecognitionHandlers(manager, recognition, generationId, overlapSlotIndex) {
    recognition.onstart = () => {
      if (!manager._isActiveGeneration(generationId)) {
        return;
      }
      if (overlapSlotIndex != null) {
        if (!manager.state.recognitionOverlapSlotListening) {
          manager.state.recognitionOverlapSlotListening = [false, false];
        }
        manager.state.recognitionOverlapSlotListening[overlapSlotIndex] = true;
        if (overlapSlotInactive(manager, overlapSlotIndex)) {
          manager._markActivity("start");
          return;
        }
      }
      manager.state.lastStartAtMs = manager._now();
      manager.state.lastSessionStartedAtMs = manager.state.lastStartAtMs;
      manager.state.stoppingSinceMs = null;
      manager._setLastError(null, null);
      manager.state.noSpeechBackoffMs = 0;
      manager.state.restartBackoffMs = 0;
      manager._setTerminalDegradedReason(null);
      manager.state.pendingRestartReason = null;
      manager._resetCycleState();
      manager._setRecognitionState("running");
      manager._setSupervisorState("running");
      manager._setStatus("listening");
      manager.state.visibilityDegraded = Boolean(document.hidden && manager.state.desiredRunning);
      manager._refreshDegradedReason();
      manager._markActivity("start");
      manager._emitWorkerStatus("recognition-started");
    };

    recognition.onsoundstart = () => {
      if (!manager._isActiveGeneration(generationId)) {
        return;
      }
      if (overlapSlotInactive(manager, overlapSlotIndex)) {
        return;
      }
      manager.state.onSound = true;
      manager._markActivity("sound");
      manager._updateCounters();
    };

    recognition.onsoundend = () => {
      if (!manager._isActiveGeneration(generationId)) {
        return;
      }
      if (overlapSlotInactive(manager, overlapSlotIndex)) {
        return;
      }
      manager.state.onSound = false;
      manager._updateCounters();
    };

    recognition.onspeechstart = () => {
      if (!manager._isActiveGeneration(generationId)) {
        return;
      }
      if (overlapSlotInactive(manager, overlapSlotIndex)) {
        return;
      }
      manager._markActivity("speech");
    };

    recognition.onerror = (event) => {
      if (!manager._isActiveGeneration(generationId)) {
        return;
      }
      applyRecognitionError(manager, generationId, overlapSlotIndex, event);
    };

    recognition.onend = () => {
      if (!manager._isActiveGeneration(generationId)) {
        return;
      }
      manager.state.lastEndAtMs = manager._now();
      manager.state.lastSessionEndedAtMs = manager.state.lastEndAtMs;
      manager.state.onSound = false;
      manager._setRecognitionState("idle");
      if (!manager.state.desiredRunning) {
        manager._cleanupRecognitionInstance(generationId);
        manager._resetSegmentTracking();
        manager._setSupervisorState("idle");
        manager._setStatus("stopped");
        manager._emitWorkerStatus("recognition-ended");
        return;
      }
      if (overlapSlotIndex != null && ASR.handleOverlapRecognitionEnded(manager, overlapSlotIndex)) {
        return;
      }
      manager._cleanupRecognitionInstance(generationId);
      manager._emitWorkerStatus("recognition-ended");
      if (manager.state.pendingStart) {
        manager.state.pendingStart = false;
        const pendingReason = manager.state.pendingRestartReason || "normal_onend";
        manager.state.pendingRestartReason = null;
        manager._scheduleRestart(pendingReason);
        return;
      }
      const restartReason = manager.state.pendingRestartReason
        || (manager.state.lastErrorKind === "network" ? "network" : null)
        || (manager.state.lastErrorKind === "no-speech" ? "no_speech" : null)
        || "normal_onend";
      manager.state.pendingRestartReason = null;
      manager._scheduleRestart(restartReason);
    };

    recognition.onresult = (event) => {
      handleRecognitionResult(manager, generationId, overlapSlotIndex, event);
    };
  };
})(typeof window !== "undefined" ? window : globalThis);
