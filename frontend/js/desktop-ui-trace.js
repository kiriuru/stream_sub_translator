/**
 * Desktop shell / pywebview observability (ui-trace.jsonl via POST /api/logs/ui-trace).
 */
(function attachSstDesktopUiTrace(global) {
  "use strict";

  const PYWEBVIEW_API_TIMEOUT_MS = 4000;

  function sendPayload(payload) {
    const body = JSON.stringify(payload);
    if (global.Api?.postUiTrace) {
      void global.Api.postUiTrace(payload).catch(() => {
        if (typeof navigator?.sendBeacon === "function") {
          try {
            navigator.sendBeacon("/api/logs/ui-trace", new Blob([body], { type: "application/json" }));
          } catch (_error) {
            // best-effort
          }
        }
      });
      return;
    }
    fetch("/api/logs/ui-trace", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    }).catch(() => {
      if (typeof navigator?.sendBeacon === "function") {
        try {
          navigator.sendBeacon("/api/logs/ui-trace", new Blob([body], { type: "application/json" }));
        } catch (_error2) {
          // best-effort
        }
      }
    });
  }

  function trace(event, fields) {
    sendPayload({
      surface: "desktop",
      phase: "pywebview",
      event: String(event || "event"),
      fields: fields && typeof fields === "object" ? fields : undefined,
    });
  }

  trace.pywebviewApiTimeoutMs = PYWEBVIEW_API_TIMEOUT_MS;

  global.SstDesktopUiTrace = trace;
})(typeof window !== "undefined" ? window : globalThis);
