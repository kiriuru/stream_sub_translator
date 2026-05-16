/**
 * Watchdog tick evaluation (pure decisions; host executes side effects).
 */
(function attachSstBrowserAsrWatchdog(global) {
  "use strict";

  const root = (global.SstBrowserAsr = global.SstBrowserAsr || {});

  /**
   * @returns {{ type: string }}
   * Types: noop | cycle_pending | session_cycle | stopping_timeout | idle_rearm | heartbeat
   */
  root.evaluateWatchdogTick = function evaluateWatchdogTick(ctx) {
    const state = ctx.state;
    const now = Number(ctx.nowMs || 0);
    const limits = ctx.limits || {};
    const documentHidden = Boolean(ctx.documentHidden);

    if (!state?.desiredRunning) {
      return { type: "noop" };
    }

    const sessionAgeMs = root.currentSessionAgeMs?.(state, now);
    const maxSessionAgeMs = Number(state.maxBrowserSessionAgeMs || limits.maxBrowserSessionAgeMs || 0);
    const prepareCycleBeforeMs = Number(state.prepareCycleBeforeMs || limits.prepareCycleBeforeMs || 0);
    const prepareAtMs = Math.max(0, maxSessionAgeMs - prepareCycleBeforeMs);

    if (
      state.browserSupervisorState === "running"
      && sessionAgeMs != null
      && maxSessionAgeMs > 0
      && sessionAgeMs >= maxSessionAgeMs
    ) {
      return { type: "session_cycle" };
    }

    if (
      state.browserSupervisorState === "running"
      && sessionAgeMs != null
      && sessionAgeMs >= prepareAtMs
      && !state.browserCyclePending
    ) {
      return { type: "cycle_pending" };
    }

    if (
      state.browserSupervisorState === "stopping"
      && state.stoppingSinceMs
      && now - Number(state.stoppingSinceMs) >= Number(limits.maxStoppingMs || 2500)
    ) {
      return { type: "stopping_timeout" };
    }

    const lastActivityAt = Math.max(
      Number(state.lastEventAtMs || 0),
      Number(state.lastStartAtMs || 0),
      Number(state.lastResultAtMs || 0)
    );
    const idleThresholdMs = documentHidden
      ? Number(limits.hiddenIdleRestartMs || 60000)
      : Number(limits.visibleIdleRestartMs || 30000);
    if (
      lastActivityAt > 0
      && now - lastActivityAt >= idleThresholdMs
      && state.browserSupervisorState === "running"
    ) {
      return { type: "idle_rearm" };
    }

    return { type: "heartbeat" };
  };
})(typeof window !== "undefined" ? window : globalThis);
