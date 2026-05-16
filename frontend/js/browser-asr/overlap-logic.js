/**
 * Dual-slot recognition overlap helpers (classic browser worker).
 */
(function attachSstBrowserAsrOverlap(global) {
  "use strict";

  const ASR = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  ASR.recognitionOverlapModeDesired = function recognitionOverlapModeDesired(settings, policy) {
    if (policy && typeof policy.shouldEnableRecognitionOverlap === "function") {
      return Boolean(policy.shouldEnableRecognitionOverlap(settings));
    }
    return Boolean(settings && settings.continuous === false && settings.overlap_recognition_sessions !== false);
  };

  ASR.recognitionOverlapActive = function recognitionOverlapActive(state) {
    return Array.isArray(state.recognitionOverlapSlots) && state.recognitionOverlapSlots.length === 2;
  };

  ASR.overlapResultAllowed = function overlapResultAllowed(state, overlapSlotIndex) {
    if (overlapSlotIndex == null) {
      return true;
    }
    if (!ASR.recognitionOverlapActive(state)) {
      return true;
    }
    const active = Number(state.recognitionOverlapActiveSlot || 0) % 2;
    if (overlapSlotIndex === active) {
      return true;
    }
    const buddy = (active + 1) % 2;
    return overlapSlotIndex === buddy && Boolean(state.recognitionOverlapPrestarted);
  };

  ASR.createOverlapRecognitionPair = function createOverlapRecognitionPair(manager, generationId) {
    const slots = [new manager.SpeechRecognitionCtor(), new manager.SpeechRecognitionCtor()];
    slots[0].maxAlternatives = 1;
    slots[1].maxAlternatives = 1;
    manager.state.recognitionOverlapSlots = slots;
    manager.state.recognitionOverlapActiveSlot = 0;
    manager.state.recognitionOverlapPrestarted = false;
    manager.state.recognitionOverlapSlotListening = [false, false];
    manager.state.recognitionGenerationId = generationId;
    manager.state.recognition = slots[0];
    manager.applyRecognitionSettings();
    manager._wireRecognitionHandlers(slots[0], generationId, 0);
    manager._wireRecognitionHandlers(slots[1], generationId, 1);
    return slots;
  };

  ASR.prestartOverlapBuddyIfNeeded = function prestartOverlapBuddyIfNeeded(manager, overlapSlotIndex) {
    if (overlapSlotIndex == null || !ASR.recognitionOverlapActive(manager.state)) {
      return;
    }
    if (Number(manager.state.recognitionOverlapActiveSlot || 0) !== overlapSlotIndex) {
      return;
    }
    if (manager.state.recognitionOverlapPrestarted) {
      return;
    }
    const slots = manager.state.recognitionOverlapSlots;
    const buddy = (overlapSlotIndex + 1) % 2;
    const buddyRec = slots[buddy];
    if (!buddyRec) {
      return;
    }
    if (manager.state.recognitionOverlapSlotListening && manager.state.recognitionOverlapSlotListening[buddy]) {
      manager.state.recognitionOverlapPrestarted = true;
      return;
    }
    try {
      buddyRec.start();
      manager.state.recognitionOverlapPrestarted = true;
      manager._appendLog("overlap: pre-started buddy recognition slot");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || "buddy start failed");
      manager._appendLog(`overlap: buddy pre-start failed: ${message}`);
    }
  };

  /** @returns {boolean} true when overlap handoff consumed onend */
  ASR.handleOverlapRecognitionEnded = function handleOverlapRecognitionEnded(manager, overlapSlotIndex) {
    if (!ASR.recognitionOverlapActive(manager.state)) {
      return false;
    }
    if (!manager.state.recognitionOverlapSlotListening) {
      manager.state.recognitionOverlapSlotListening = [false, false];
    }
    manager.state.recognitionOverlapSlotListening[overlapSlotIndex] = false;
    if (!manager.state.desiredRunning) {
      return false;
    }
    const active = Number(manager.state.recognitionOverlapActiveSlot || 0) % 2;
    const buddy = (active + 1) % 2;
    if (overlapSlotIndex === active) {
      if (manager.state.recognitionOverlapSlotListening[buddy]) {
        manager.state.recognitionOverlapActiveSlot = buddy;
        manager.state.recognition = manager.state.recognitionOverlapSlots[buddy];
        manager.state.recognitionOverlapPrestarted = false;
        manager._setSupervisorState("running");
        manager._setRecognitionState("running");
        manager._emitWorkerStatus("recognition-ended");
        return true;
      }
    }
    return false;
  };
})(typeof window !== "undefined" ? window : globalThis);
