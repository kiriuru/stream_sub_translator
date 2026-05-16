/**
 * Screen wake lock acquire/release for long recognition sessions.
 */
(function attachSstBrowserAsrWakeLock(global) {
  "use strict";

  const ASR = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  ASR.hasWakeLockSupport = function hasWakeLockSupport() {
    return typeof navigator !== "undefined" && Boolean(navigator?.wakeLock?.request);
  };

  ASR.clearWakeLockRetryTimer = function clearWakeLockRetryTimer(manager) {
    if (manager._wakeLockRetryTimer) {
      window.clearTimeout(manager._wakeLockRetryTimer);
      manager._wakeLockRetryTimer = null;
    }
  };

  ASR.acquireWakeLock = async function acquireWakeLock(manager, reason) {
    if (!ASR.hasWakeLockSupport()) {
      manager.state.wakeLockActive = false;
      return false;
    }
    if (document.hidden) {
      ASR.clearWakeLockRetryTimer(manager);
      manager._wakeLockRetryTimer = window.setTimeout(
        () => ASR.acquireWakeLock(manager, "retry-after-visibility"),
        1500
      );
      return false;
    }
    if (manager._wakeLockSentinel && !manager._wakeLockSentinel.released) {
      manager.state.wakeLockActive = true;
      return true;
    }
    try {
      const sentinel = await navigator.wakeLock.request("screen");
      if (!sentinel) {
        manager.state.wakeLockActive = false;
        return false;
      }
      manager._wakeLockSentinel = sentinel;
      manager.state.wakeLockActive = true;
      if (!manager._wakeLockBound) {
        manager._wakeLockBound = true;
      }
      sentinel.addEventListener("release", () => {
        if (manager._wakeLockSentinel === sentinel) {
          manager._wakeLockSentinel = null;
          manager.state.wakeLockActive = false;
          if (manager.state.desiredRunning) {
            ASR.clearWakeLockRetryTimer(manager);
            manager._wakeLockRetryTimer = window.setTimeout(
              () => ASR.acquireWakeLock(manager, "re-acquire-after-release"),
              500
            );
          }
        }
      });
      manager._appendLog(`screen wake lock acquired (${reason || "start"})`);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || "");
      manager.state.wakeLockActive = false;
      if (message) {
        manager._appendLog(`screen wake lock acquisition failed: ${message}`);
      }
      return false;
    }
  };

  ASR.releaseWakeLock = async function releaseWakeLock(manager, reason) {
    ASR.clearWakeLockRetryTimer(manager);
    const sentinel = manager._wakeLockSentinel;
    manager._wakeLockSentinel = null;
    manager.state.wakeLockActive = false;
    if (!sentinel) {
      return;
    }
    try {
      await sentinel.release();
      manager._appendLog(`screen wake lock released (${reason || "stop"})`);
    } catch (_error) {
      // best effort
    }
  };
})(typeof window !== "undefined" ? window : globalThis);
