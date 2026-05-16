/**
 * Google generate_204 network preflight after Web Speech network error bursts.
 */
(function attachSstBrowserAsrNetworkPreflight(global) {
  "use strict";

  const ASR = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  const PREFLIGHT_URL = "https://www.google.com/generate_204";

  ASR.registerNetworkErrorForPreflight = function registerNetworkErrorForPreflight(manager) {
    const now = manager._now();
    if (ASR.registerNetworkErrorBurst?.(manager.state, now, manager._timingLimits())) {
      ASR.runNetworkPreflight(manager, "network-burst-threshold");
    }
  };

  ASR.runNetworkPreflight = async function runNetworkPreflight(manager, reason) {
    manager.state.networkPreflightInFlight = true;
    manager.state.lastNetworkPreflightAtMs = manager._now();
    manager._appendLog(`network preflight probe started (${reason || "network-burst"})`);
    manager._emitWorkerStatus("network-preflight-start");
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const timeoutId = controller
      ? window.setTimeout(() => controller.abort(), manager.networkPreflightTimeoutMs)
      : null;
    let ok = false;
    try {
      const response = await fetch(PREFLIGHT_URL, {
        method: "GET",
        mode: "no-cors",
        cache: "no-store",
        credentials: "omit",
        referrerPolicy: "no-referrer",
        signal: controller ? controller.signal : undefined,
      });
      ok = Boolean(response);
    } catch (_error) {
      ok = false;
    } finally {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    }
    manager.state.lastNetworkPreflightOk = ok;
    manager.state.networkPreflightInFlight = false;
    manager._appendLog(`network preflight probe result: ${ok ? "reachable" : "unreachable"}`);
    manager._emitWorkerStatus(ok ? "network-preflight-ok" : "network-preflight-failed");
    if (!ok) {
      manager.state.desiredRunning = false;
      manager.state.pendingStart = false;
      manager._clearAllTimers();
      manager._setSupervisorState("fatal");
      manager._setTerminalDegradedReason("recognition_network_unreachable");
      manager._setStatus(
        manager._locale() === "ru"
          ? "сеть недоступна для Web Speech"
          : "recognition cloud unreachable"
      );
      manager._appendLog(
        manager._locale() === "ru"
          ? "Web Speech: сетевой preflight provalil — облако распознавания недоступно. Проверьте VPN/firewall/DNS/прокси и нажмите Start заново."
          : "Web Speech: network preflight failed — recognition cloud unreachable. Check VPN/firewall/DNS/proxy and press Start again."
      );
      await ASR.releaseWakeLock(manager, "network-preflight-failed");
      manager._emitWorkerStatus("terminal-network-unreachable");
      return false;
    }
    return true;
  };
})(typeof window !== "undefined" ? window : globalThis);
