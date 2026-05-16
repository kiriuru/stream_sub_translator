/**
 * Controlled recognition start/stop/restart and instance cleanup.
 */
(function attachSstBrowserAsrRecognitionLifecycle(global) {
  "use strict";

  const ASR = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  function collectRecognitionInstances(manager) {
    const slots = [];
    if (ASR.recognitionOverlapActive(manager.state)) {
      (manager.state.recognitionOverlapSlots || []).forEach((rec) => {
        if (rec) {
          slots.push(rec);
        }
      });
    } else if (manager.state.recognition) {
      slots.push(manager.state.recognition);
    }
    return slots;
  }

  function handleRecognitionStartFailure(manager, message) {
    if (String(message).toLowerCase().includes("already started")) {
      manager._setSupervisorState("running");
      manager._setRecognitionState("running");
      manager._setStatus("listening");
      return true;
    }
    manager._setRecognitionState("idle");
    manager._setSupervisorState("restarting");
    return false;
  }

  function invokeRecognitionStart(manager, recognition, reason, startLogThrottle, logSuffix) {
    try {
      recognition.start();
      const line = logSuffix
        ? `recognition.start ${logSuffix} (${reason})`
        : `recognition.start (${reason})`;
      if (startLogThrottle.key) {
        manager._appendLogThrottled(line, startLogThrottle.key, startLogThrottle.gapMs);
      } else {
        manager._appendLog(line);
      }
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || "start failed");
      if (handleRecognitionStartFailure(manager, message)) {
        return true;
      }
      manager._appendLog(`${logSuffix ? `recognition.start ${logSuffix}` : "recognition.start"} failed: ${message}`);
      manager._scheduleRestart("network");
      return false;
    }
  }

  ASR.cleanupRecognitionInstance = function cleanupRecognitionInstance(manager, generationId) {
    if (generationId !== manager.state.recognitionGenerationId) {
      return;
    }
    collectRecognitionInstances(manager).forEach((recognition) => {
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
    });
    manager.state.recognitionOverlapSlots = null;
    manager.state.recognitionOverlapActiveSlot = null;
    manager.state.recognitionOverlapPrestarted = false;
    manager.state.recognitionOverlapSlotListening = null;
    manager.state.recognition = null;
  };

  ASR.createRecognition = function createRecognition(manager, generationId) {
    const recognition = new manager.SpeechRecognitionCtor();
    recognition.maxAlternatives = 1;
    manager.state.recognitionGenerationId = generationId;
    manager.state.recognitionOverlapSlots = null;
    manager.state.recognitionOverlapActiveSlot = null;
    manager.state.recognitionOverlapPrestarted = false;
    manager.state.recognitionOverlapSlotListening = null;
    manager.state.recognition = recognition;
    manager.applyRecognitionSettings();
    manager._wireRecognitionHandlers(recognition, generationId, null);
    return recognition;
  };

  ASR.performControlledStart = function performControlledStart(manager, reason) {
    if (!manager.state.desiredRunning) {
      return;
    }
    if (manager.state.browserSupervisorState === "starting" || manager.state.browserSupervisorState === "running") {
      return;
    }
    if (manager.state.browserSupervisorState === "stopping") {
      manager.state.pendingStart = true;
      manager._appendLog("recognition.start deferred: recognition is stopping");
      return;
    }
    const generationId = Number(manager.state.generationId || 0);
    ASR.cleanupRecognitionInstance(manager, manager.state.recognitionGenerationId);
    manager._setSupervisorState("starting");
    manager._setRecognitionState("starting");
    manager.state.stoppingSinceMs = null;
    manager.state.providerName = manager.state.browserMode || "browser_google";
    manager.state.pendingRestartReason = null;
    manager.ensureSocketConnected();
    const startLogThrottle = manager._recognitionStartBurstThrottle(reason);
    const policy = manager._webSpeechPolicy();
    const settings = manager._getRecognitionSettings();
    if (ASR.recognitionOverlapModeDesired(settings, policy)) {
      ASR.createOverlapRecognitionPair(manager, generationId);
      invokeRecognitionStart(
        manager,
        manager.state.recognitionOverlapSlots[0],
        reason,
        startLogThrottle,
        "overlap slot0"
      );
      return;
    }
    const recognition = ASR.createRecognition(manager, generationId);
    invokeRecognitionStart(manager, recognition, reason, startLogThrottle, null);
  };

  ASR.transitionToStopping = function transitionToStopping(manager, reason) {
    const slots = collectRecognitionInstances(manager);
    if (reason !== "user-stop") {
      manager._forceFinalizeOnInterruption("browser_recognition_interrupted");
    }
    if (!slots.length) {
      ASR.cleanupRecognitionInstance(manager, manager.state.recognitionGenerationId);
      manager._setRecognitionState("idle");
      manager._setSupervisorState(manager.state.desiredRunning ? "restarting" : "idle");
      manager._setStatus(manager.state.desiredRunning ? "restarting" : "stopped");
      if (manager.state.desiredRunning) {
        manager._scheduleRestart(manager.state.pendingRestartReason || "normal_onend");
      }
      return;
    }
    if (manager.state.browserSupervisorState !== "stopping") {
      manager._setSupervisorState("stopping");
    }
    manager._setRecognitionState("stopping");
    manager.state.stoppingSinceMs = manager._now();
    manager._setStatus("stopping");
    try {
      slots.forEach((rec) => {
        try {
          rec.stop();
        } catch (_inner) {
          // best effort
        }
      });
      manager._appendLog(`recognition.stop (${reason})`);
    } catch (_error) {
      ASR.cleanupRecognitionInstance(manager, manager.state.recognitionGenerationId);
      manager._setRecognitionState("idle");
      manager._setSupervisorState(manager.state.desiredRunning ? "restarting" : "idle");
      if (manager.state.desiredRunning) {
        manager._scheduleRestart(manager.state.pendingRestartReason || "normal_onend");
      }
    }
  };

  ASR.scheduleRestart = function scheduleRestart(manager, reason, options = {}) {
    if (!manager.state.desiredRunning) {
      manager._setSupervisorState("idle");
      return;
    }
    const normalizedReason = String(reason || "normal_onend").trim().toLowerCase();
    const requestedDelayMs = Math.max(
      0,
      Number(options.backoffMs != null ? options.backoffMs : manager._restartDelayForReason(normalizedReason))
    );
    const delayMs = manager._minimumReconnectGuardDelayMs(requestedDelayMs);
    manager._clearRestartTimer();
    manager.state.restartCount = Number(manager.state.restartCount || 0) + 1;
    manager.state.lastRestartReason = normalizedReason;
    manager._setSupervisorState(
      delayMs > manager.restartDelayByReasonMs.normal_onend ? "backoff" : "restarting"
    );
    manager._setStatus("restarting");
    const capturedGeneration = Number(manager.state.generationId || 0);
    manager.state.restartTimer = window.setTimeout(() => {
      if (!manager.state.desiredRunning) {
        return;
      }
      if (capturedGeneration !== Number(manager.state.generationId || 0)) {
        return;
      }
      if (manager.state.browserSupervisorState === "stopping") {
        manager.state.pendingStart = true;
        return;
      }
      ASR.performControlledStart(manager, normalizedReason);
    }, delayMs);
    manager._emitWorkerStatus("restart-scheduled");
  };
})(typeof window !== "undefined" ? window : globalThis);
