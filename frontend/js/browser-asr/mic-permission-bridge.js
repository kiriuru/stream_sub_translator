/**
 * Microphone permission gate via worker options.ensureMicrophonePermission.
 */
(function attachSstBrowserAsrMicPermission(global) {
  "use strict";

  const ASR = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  ASR.ensureMicrophonePermission = function ensureMicrophonePermission(manager) {
    if (manager._permissionPromise) {
      return manager._permissionPromise;
    }
    manager._appendLog("requesting microphone permission");
    manager._permissionPromise = Promise.resolve(manager.options.ensureMicrophonePermission?.())
      .then((result) => {
        manager._permissionPromise = null;
        manager.state.getUserMediaLastError = null;
        manager._appendLog("microphone permission granted");
        return result;
      })
      .catch((error) => {
        manager._permissionPromise = null;
        manager.state.getUserMediaLastError = error instanceof Error ? error.message : String(error || "");
        manager._appendLog(`microphone permission failed: ${error instanceof Error ? error.message : error}`);
        throw error;
      });
    return manager._permissionPromise;
  };
})(typeof window !== "undefined" ? window : globalThis);
