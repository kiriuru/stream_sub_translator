/**
 * Wait for tab visibility / window focus before recognition.start.
 */
(function attachSstBrowserAsrVisibilityWait(global) {
  "use strict";

  const ASR = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  ASR.waitUntilDocumentVisibleForRecognition = async function waitUntilDocumentVisibleForRecognition(
    manager,
    options = {}
  ) {
    const visibilityMaxMs = Math.max(0, Number(options.visibilityMaxMs ?? 20000));
    const focusMaxMs = Math.max(0, Number(options.focusMaxMs ?? 6000));
    const waitFocus = Boolean(options.waitWindowFocus ?? false);

    if (document.hidden) {
      manager._appendLog("document hidden; waiting for tab visibility before recognition start");
      await new Promise((resolve) => {
        let done = false;
        const cleanup = () => {
          document.removeEventListener("visibilitychange", onVis);
          window.clearTimeout(timer);
        };
        const finish = () => {
          if (done) {
            return;
          }
          done = true;
          cleanup();
          resolve();
        };
        const onVis = () => {
          if (!document.hidden) {
            manager._appendLog("tab became visible; continuing recognition start");
            finish();
          }
        };
        document.addEventListener("visibilitychange", onVis);
        const timer = window.setTimeout(() => {
          manager._appendLog("visibility wait timed out; continuing recognition start anyway");
          finish();
        }, visibilityMaxMs);
      });
    }

    if (!manager.state.desiredRunning) {
      return false;
    }

    if (waitFocus && typeof document.hasFocus === "function" && !document.hasFocus()) {
      manager._appendLog("window not focused; waiting briefly before recognition start");
      const startAt = manager._now();
      await new Promise((resolve) => {
        const timer = window.setInterval(() => {
          if (!manager.state.desiredRunning) {
            window.clearInterval(timer);
            resolve();
            return;
          }
          if (document.hasFocus()) {
            manager._appendLog("window focused; continuing recognition start");
            window.clearInterval(timer);
            resolve();
            return;
          }
          if (manager._now() - startAt >= focusMaxMs) {
            manager._appendLog("focus wait timed out; continuing recognition start anyway");
            window.clearInterval(timer);
            resolve();
          }
        }, 80);
      });
    }

    return Boolean(manager.state.desiredRunning);
  };
})(typeof window !== "undefined" ? window : globalThis);
