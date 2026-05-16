/**
 * Degraded reason resolution for browser worker status payloads.
 */
(function attachSstBrowserAsrDegradedReason(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  root.resolveDegradedReason = function resolveDegradedReason(state) {
    if (state.terminalDegradedReason) {
      return state.terminalDegradedReason;
    }
    if (state.visibilityDegraded) {
      return "document_hidden";
    }
    if (state.socketDegraded) {
      return "websocket_disconnected";
    }
    if (state.healthDegradedReason) {
      return state.healthDegradedReason;
    }
    return null;
  };
})(typeof window !== "undefined" ? window : globalThis);
