/**
 * Restart/backoff timing and network preflight burst tracking.
 */
(function attachSstBrowserAsrRestartTiming(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  root.currentSessionAgeMs = function currentSessionAgeMs(state, nowMs) {
    if (!state.lastSessionStartedAtMs) {
      return null;
    }
    return Math.max(0, nowMs - Number(state.lastSessionStartedAtMs || 0));
  };

  root.minimumReconnectGuardDelayMs = function minimumReconnectGuardDelayMs(state, delayMs, nowMs, instanceMinimumReconnectIntervalMs) {
    const minimumIntervalMs = Math.max(
      0,
      Number(state.minimumReconnectIntervalMs || instanceMinimumReconnectIntervalMs || 0)
    );
    if (!minimumIntervalMs) {
      return delayMs;
    }
    const anchorMs = Math.max(
      Number(state.lastSessionEndedAtMs || 0),
      Number(state.lastEndAtMs || 0),
      Number(state.lastStartAtMs || 0)
    );
    if (!anchorMs) {
      return delayMs;
    }
    const remainingMs = minimumIntervalMs - Math.max(0, nowMs - anchorMs);
    if (remainingMs <= 0 || remainingMs <= delayMs) {
      return delayMs;
    }
    state.browserMinimumReconnectSuppressedCount = Number(state.browserMinimumReconnectSuppressedCount || 0) + 1;
    return remainingMs;
  };

  root.nextNetworkBackoffMs = function nextNetworkBackoffMs(state, initialNetworkBackoffMs, maxNetworkBackoffMs) {
    const current = Number(state.restartBackoffMs || 0);
    if (!current) {
      state.restartBackoffMs = Math.max(0, Number(state.networkReconnectInitialMs || initialNetworkBackoffMs || 1000));
    } else {
      state.restartBackoffMs = Math.min(
        maxNetworkBackoffMs,
        Math.max(Number(state.networkReconnectInitialMs || initialNetworkBackoffMs || 1000), current * 2)
      );
    }
    return state.restartBackoffMs;
  };

  root.restartDelayForReason = function restartDelayForReason(state, reason, limits) {
    const normalized = String(reason || "").trim().toLowerCase();
    if (normalized === "no_speech") {
      if (!state.noSpeechBackoffMs) {
        state.noSpeechBackoffMs = Math.max(0, Number(state.noSpeechRestartDelayMs || limits.initialNoSpeechDelayMs || 350));
      } else {
        state.noSpeechBackoffMs = Math.min(
          limits.maxNoSpeechDelayMs,
          Math.max(
            Math.max(0, Number(state.noSpeechRestartDelayMs || limits.initialNoSpeechDelayMs || 350)),
            state.noSpeechBackoffMs + 800
          )
        );
      }
      return state.noSpeechBackoffMs;
    }
    if (normalized === "network") {
      return root.nextNetworkBackoffMs(state, limits.initialNetworkBackoffMs, limits.maxNetworkBackoffMs);
    }
    return limits.restartDelayByReasonMs[normalized] || limits.restartDelayByReasonMs.normal_onend;
  };

  root.resetNetworkErrorBurst = function resetNetworkErrorBurst(state) {
    state.networkErrorBurstCount = 0;
    state.networkErrorBurstStartedAtMs = 0;
  };

  root.registerNetworkErrorBurst = function registerNetworkErrorBurst(state, nowMs, limits) {
    const startedAt = Number(state.networkErrorBurstStartedAtMs || 0);
    if (!startedAt || nowMs - startedAt > limits.networkPreflightBurstWindowMs) {
      state.networkErrorBurstStartedAtMs = nowMs;
      state.networkErrorBurstCount = 1;
    } else {
      state.networkErrorBurstCount = Number(state.networkErrorBurstCount || 0) + 1;
    }
    return root.shouldRunNetworkPreflight(state, nowMs, limits);
  };

  root.shouldRunNetworkPreflight = function shouldRunNetworkPreflight(state, nowMs, limits) {
    if (state.networkPreflightInFlight) {
      return false;
    }
    if (Number(state.networkErrorBurstCount || 0) < limits.networkPreflightBurstThreshold) {
      return false;
    }
    const burstStartedAt = Number(state.networkErrorBurstStartedAtMs || 0);
    if (!burstStartedAt || nowMs - burstStartedAt > limits.networkPreflightBurstWindowMs) {
      return false;
    }
    const lastPreflightAt = Number(state.lastNetworkPreflightAtMs || 0);
    if (lastPreflightAt && nowMs - lastPreflightAt < limits.networkPreflightCooldownMs) {
      return false;
    }
    return true;
  };
})(typeof window !== "undefined" ? window : globalThis);
