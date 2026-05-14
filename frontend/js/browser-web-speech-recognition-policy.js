/**
 * Small, dependency-free helpers for Chrome Web Speech quirks (overlap sessions,
 * on-device hint stripping). Loaded before browser-asr-session-manager.js.
 */
(function attachSstWebSpeechRecognitionPolicy(global) {
  "use strict";

  /**
   * Overlap (dual-session) mode reduces audio gaps between Chrome recognition
   * sessions when continuous=false. Opt-out via overlap_recognition_sessions: false.
   */
  function shouldEnableRecognitionOverlap(settings) {
    if (!settings || typeof settings !== "object") {
      return false;
    }
    if (settings.overlap_recognition_sessions === false) {
      return false;
    }
    if (settings.overlap_recognition_sessions === true) {
      return true;
    }
    return settings.continuous === false;
  }

  function stripChromeOnDeviceHints(recognition) {
    if (!recognition || typeof recognition !== "object") {
      return;
    }
    try {
      recognition.processLocally = false;
    } catch (_e) {
      // ignore
    }
    try {
      const phrases = recognition.phrases;
      if (phrases && typeof phrases.pop === "function") {
        while (phrases.length > 0) {
          phrases.pop();
        }
      } else {
        recognition.phrases = [];
      }
    } catch (_e) {
      try {
        delete recognition.phrases;
      } catch (_e2) {
        // ignore
      }
    }
  }

  function isPhrasesNotSupportedError(kind) {
    return String(kind || "").trim().toLowerCase() === "phrases-not-supported";
  }

  function isLanguageNotSupportedError(kind) {
    return String(kind || "").trim().toLowerCase() === "language-not-supported";
  }

  global.SSTWebSpeechRecognitionPolicy = {
    shouldEnableRecognitionOverlap,
    stripChromeOnDeviceHints,
    isPhrasesNotSupportedError,
    isLanguageNotSupportedError,
  };
})(window);
