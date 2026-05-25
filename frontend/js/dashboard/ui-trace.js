import { selectAsrMode } from "../core/selectors.js";
import {
  normalizeUiStatus,
  resolveRuntimeUiStatus,
} from "./helpers.js";

let postUiTraceFn = null;
let lastVisualSignature = "";

export function configureUiTrace(poster) {
  postUiTraceFn = typeof poster === "function" ? poster : null;
}

export function buildRuntimeVisualSnapshot(snapshot) {
  const runtime = snapshot?.runtime && typeof snapshot.runtime === "object" ? snapshot.runtime : {};
  const metrics = runtime.metrics && typeof runtime.metrics === "object" ? runtime.metrics : {};
  const diagnostics = snapshot?.diagnostics?.asr && typeof snapshot.diagnostics.asr === "object"
    ? snapshot.diagnostics.asr
    : {};
  const translationDiagnostics = snapshot?.diagnostics?.translation || {};
  const obsDiagnostics = snapshot?.diagnostics?.obs || {};
  const mode = selectAsrMode(snapshot || {});
  const status = String(runtime.status || "idle").toLowerCase();
  const partials = Number(metrics.partial_updates_emitted ?? 0);
  const finals = Number(metrics.finals_emitted ?? 0);
  const awaitingFirstRecognition =
    status === "listening" &&
    runtime.is_running === true &&
    partials === 0 &&
    finals === 0;
  const progressMessage = String(runtime.status_message || "").trim();
  const localAsrLoading =
    mode === "local" &&
    Boolean(progressMessage) &&
    /loading|initializing|warming|preparing|download/i.test(progressMessage);
  const progressCardVisible =
    status === "starting" ||
    Boolean(snapshot?.ui?.runtimeBusy) ||
    localAsrLoading ||
    awaitingFirstRecognition ||
    (Boolean(progressMessage) && status === "transcribing");

  return {
    asr_mode: mode,
    runtime_status: status,
    runtime_ui_status: resolveRuntimeUiStatus(runtime),
    is_running: runtime.is_running === true,
    last_error: runtime.last_error || null,
    status_message: progressMessage || null,
    badges: {
      health: normalizeUiStatus(snapshot?.diagnostics?.healthStatus, "unknown"),
      runtime: resolveRuntimeUiStatus(runtime),
      asr: runtime.last_error
        ? "error"
        : diagnostics.degraded_mode
          ? "degraded"
          : diagnostics.provider
            ? "ready"
            : "unknown",
      device:
        diagnostics.cpu_fallback_reason || diagnostics.fallback_reason
          ? "degraded"
          : diagnostics.selected_device || diagnostics.selected_execution_provider
            ? "ready"
            : "unknown",
      translation: normalizeUiStatus(
        translationDiagnostics.status || (translationDiagnostics.enabled ? "ready" : "disabled"),
        translationDiagnostics.enabled ? "ready" : "disabled"
      ),
      obs: obsDiagnostics.last_error ? "error" : obsDiagnostics.enabled ? "ready" : "disabled",
    },
    progress_card_visible: progressCardVisible,
    awaiting_first_recognition: awaitingFirstRecognition,
    metrics: {
      partial_updates_emitted: partials,
      finals_emitted: finals,
      vad_segments_partial: Number(metrics.vad_segments_partial ?? 0),
      vad_segments_final: Number(metrics.vad_segments_final ?? 0),
      asr_queue_depth: Number(metrics.asr_queue_depth ?? 0),
      capture_open: diagnostics.capture_open ?? metrics.capture_open ?? null,
      model_loaded: diagnostics.model_loaded ?? metrics.model_loaded ?? null,
    },
    controls: {
      start_disabled: runtime.is_running === true || snapshot?.ui?.runtimeBusy === true,
      stop_disabled: !(
        runtime.is_running === true ||
        ["starting", "listening", "transcribing", "translating", "error"].includes(status)
      ),
    },
    ws_connected: snapshot?.ui?.wsConnected === true,
  };
}

function sendTrace(payload) {
  if (!postUiTraceFn) {
    return;
  }
  void postUiTraceFn(payload).catch(() => {
    if (typeof navigator?.sendBeacon !== "function") {
      return;
    }
    try {
      navigator.sendBeacon(
        "/api/logs/ui-trace",
        new Blob([JSON.stringify(payload)], { type: "application/json" })
      );
    } catch (_error) {
      // best-effort
    }
  });
}

export function traceUi(surface, phase, event, fields = {}, options = {}) {
  const payload = {
    surface: surface || "dashboard",
    phase: phase || "ui",
    event: event || "event",
    fields: fields && typeof fields === "object" ? fields : undefined,
  };
  sendTrace(payload);
  if (options.logMessage && typeof window.__appLog === "function") {
    window.__appLog(options.logMessage, {
      source: options.source || "ui-trace",
      persist: options.persist !== false,
      details: payload.fields,
    });
  }
}

export function traceRuntimeVisualState(snapshot, reason, options = {}) {
  const visual = buildRuntimeVisualSnapshot(snapshot);
  const signature = JSON.stringify(visual);
  if (!options.force && signature === lastVisualSignature) {
    return visual;
  }
  lastVisualSignature = signature;
  const anomalies = [];
  if (visual.awaiting_first_recognition) {
    anomalies.push("listening_without_partials");
  }
  if (visual.last_error) {
    anomalies.push("runtime_error_visible");
  }
  if (visual.badges.device === "degraded") {
    anomalies.push("device_degraded");
  }
  if (visual.badges.asr === "error" || visual.badges.asr === "degraded") {
    anomalies.push(`asr_${visual.badges.asr}`);
  }
  traceUi("dashboard", "ui", "visual_state", {
    reason: reason || "update",
    visual,
    anomalies,
  });
  if (anomalies.length) {
    traceUi("dashboard", "ui", "visual_anomaly", {
      reason: reason || "update",
      anomalies,
      visual,
    });
  }
  return visual;
}

export function traceRuntimeStatusTransition(previousRuntime, nextRuntime, source = "runtime") {
  const previousStatus = String(previousRuntime?.status || "idle").toLowerCase();
  const nextStatus = String(nextRuntime?.status || "idle").toLowerCase();
  if (previousStatus === nextStatus && (previousRuntime?.last_error || null) === (nextRuntime?.last_error || null)) {
    return;
  }
  traceUi("dashboard", "runtime", "status_transition", {
    source,
    from_status: previousStatus,
    to_status: nextStatus,
    is_running: nextRuntime?.is_running === true,
    last_error: nextRuntime?.last_error || null,
    status_message: nextRuntime?.status_message || null,
  });
}
