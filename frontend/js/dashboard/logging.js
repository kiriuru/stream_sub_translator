import { DASHBOARD_EVENTS } from "../core/events.js";
import { getCurrentLocale } from "./helpers.js";

export function shouldPersistDashboardLog(message) {
  const normalized = String(message || "").trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  if (normalized.startsWith("[runtime] status ->")) {
    return [
      "[runtime] status -> idle",
      "[runtime] status -> starting",
      "[runtime] status -> error",
    ].includes(normalized);
  }
  return [
    "[desktop]",
    "[asr]",
    "[translation]",
    "[ui]",
    "[browser-asr]",
    "[overlay]",
    "[obs-cc]",
    "[config] imported",
    "[config] exported",
    "[config] invalid",
    "[config] save failed",
    "[profiles] loaded",
    "[profiles] saved",
    "[profiles] deleted",
    "[audio] detected",
    "[audio] no input devices found",
    "[translation] google key normalized",
    "[ws] connected",
    "[ws] disconnected",
  ].some((token) => normalized.includes(token));
}

export function createLogger({ store, events, api }) {
  const recentPersisted = new Map();

  function log(message, options = {}) {
    const safeMessage = window.SSTRedaction?.redactText ? window.SSTRedaction.redactText(message) : String(message || "");
    const snapshot = store.getState();
    const lastMessage = Array.isArray(snapshot.ui.logs) && snapshot.ui.logs.length
      ? snapshot.ui.logs[snapshot.ui.logs.length - 1]
      : null;
    if (lastMessage === safeMessage && options.allowDuplicate !== true) {
      return;
    }
    const nextLogs = [...(snapshot.ui.logs || []), safeMessage].slice(-500);
    store.updateState({
      ui: {
        logs: nextLogs,
      },
    });
    events.emit(DASHBOARD_EVENTS.LOG, safeMessage);
    if (options.persist !== false && shouldPersistDashboardLog(safeMessage)) {
      const persistKey = `${options.source || "dashboard"}:${safeMessage}`;
      const lastPersistedAt = recentPersisted.get(persistKey);
      if (lastPersistedAt && (Date.now() - lastPersistedAt) < 3000) {
        return;
      }
      recentPersisted.set(persistKey, Date.now());
      const payload = {
        channel: "dashboard",
        source: options.source || "dashboard",
        message: safeMessage.trim(),
      };
      if (options.details && typeof options.details === "object") {
        payload.details = window.SSTRedaction?.redactObject ? window.SSTRedaction.redactObject(options.details) : options.details;
      }
      api.postClientLog(payload).then((result) => {
        if (result?.logged === false) {
          recentPersisted.set(persistKey, Date.now());
        }
      }).catch(() => {
        if (typeof navigator?.sendBeacon === "function") {
          try {
            navigator.sendBeacon(
              "/api/logs/client-event",
              new Blob([JSON.stringify(payload)], { type: "application/json" })
            );
          } catch (_error) {
            // keep logging best-effort
          }
        }
      });
    }
  }

  log(
    getCurrentLocale() === "ru"
      ? "[ui] dashboard frontend modules initialized"
      : "[ui] dashboard frontend modules initialized",
    { persist: false }
  );
  return log;
}
