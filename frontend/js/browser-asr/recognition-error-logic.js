/**
 * Web Speech onerror classification (pure; host applies state transitions).
 */
(function attachSstBrowserAsrRecognitionError(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  const TERMINAL_PERMISSION_ERRORS = ["not-allowed", "service-not-allowed", "audio-capture"];

  function normalizeErrorKind(event) {
    return String(event?.error || "").trim().toLowerCase() || "unknown";
  }

  function isPhrasesUnsupported(errorKind, policy) {
    return (
      (policy && typeof policy.isPhrasesNotSupportedError === "function" && policy.isPhrasesNotSupportedError(errorKind))
      || errorKind === "phrases-not-supported"
    );
  }

  function isLanguageUnsupported(errorKind, policy) {
    return (
      (policy && typeof policy.isLanguageNotSupportedError === "function" && policy.isLanguageNotSupportedError(errorKind))
      || errorKind === "language-not-supported"
    );
  }

  /**
   * @returns {{ kind: string, errorKind: string, errorMessage: string, logKey?: string }}
   */
  root.classifyRecognitionError = function classifyRecognitionError(event, policy, state) {
    const errorKind = normalizeErrorKind(event);
    const errorMessage = String(event?.message || "").trim();

    if (isPhrasesUnsupported(errorKind, policy)) {
      return { kind: "phrases_retry", errorKind, errorMessage };
    }
    if (isLanguageUnsupported(errorKind, policy) && !state.webSpeechLanguageSoftFallbackUsed) {
      return { kind: "language_retry", errorKind, errorMessage };
    }
    if (errorKind === "no-speech") {
      return { kind: "no_speech", errorKind, errorMessage };
    }
    if (errorKind === "network") {
      return { kind: "network", errorKind, errorMessage, logKey: "network_hint" };
    }
    if (errorKind === "aborted") {
      return { kind: "aborted", errorKind, errorMessage };
    }
    if (TERMINAL_PERMISSION_ERRORS.includes(errorKind)) {
      return {
        kind: "terminal_permission",
        errorKind,
        errorMessage,
        terminalReason: errorKind === "audio-capture" ? "audio_capture_recovery" : "permission_denied",
      };
    }
    if (isLanguageUnsupported(errorKind, policy)) {
      return { kind: "terminal_language", errorKind, errorMessage, terminalReason: "permission_denied" };
    }
    return { kind: "unknown", errorKind, errorMessage };
  };

  root.networkErrorHintMessages = function networkErrorHintMessages(locale) {
    if (locale === "ru") {
      return "Web Speech: ошибка network — облако распознавания недоступно (VPN, фаервол, DNS, прокси, блокировщики). Проверьте интернет; смена микрофона в браузере это обычно не лечит.";
    }
    return "Web Speech network error: recognition service unreachable (VPN, firewall, DNS, proxy, blockers). Check connectivity; changing the browser microphone usually does not fix this.";
  };
})(typeof window !== "undefined" ? window : globalThis);
