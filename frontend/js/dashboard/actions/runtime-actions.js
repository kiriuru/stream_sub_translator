import { normalizeConfigShape } from "../../normalizers/config-normalizer.js";
import { normalizeDiagnostics } from "../../normalizers/diagnostics-normalizer.js";
import { normalizeRuntimeStatus } from "../../normalizers/runtime-normalizer.js";
import { runtimeSnapshotSignature } from "../action-helpers.js";
import {
  clone,
  isBrowserRecognitionMode,
  isExperimentalBrowserRecognitionMode,
  t,
} from "../helpers.js";
import { traceRuntimeStatusTransition, traceRuntimeVisualState, traceUi } from "../ui-trace.js";

export function createRuntimeActions({ store, api, logger, events }) {
  const runtimeLogState = { signature: "" };

  function setRuntime(runtimePayload) {
    const previousRuntime = store.getState().runtime || {};
    const runtime = normalizeRuntimeStatus(runtimePayload);
    const nextSnapshotSignature = runtimeSnapshotSignature(runtime);
    const previousSignature = runtimeSnapshotSignature(previousRuntime);
    if (nextSnapshotSignature === previousSignature) {
      return;
    }
    traceRuntimeStatusTransition(previousRuntime, runtime, "setRuntime");
    const signature = JSON.stringify([runtime.status, runtime.last_error || "", runtime.status_message || ""]);
    if (runtimeLogState.signature !== signature) {
      runtimeLogState.signature = signature;
      if (runtime.last_error) {
        logger(`[runtime] ${runtime.last_error}`, {
          tracePhase: "runtime",
          traceEvent: "error_visible",
          details: { status: runtime.status, last_error: runtime.last_error },
        });
      } else if (runtime.status_message) {
        logger(`[runtime] ${runtime.status_message}`, {
          tracePhase: "runtime",
          traceEvent: "status_message",
          details: { status: runtime.status, status_message: runtime.status_message },
        });
      }
      const nextStatus = String(runtime.status || "").trim().toLowerCase();
      if (nextStatus) {
        logger(`[runtime] status -> ${nextStatus}`, {
          source: "runtime",
          tracePhase: "runtime",
          traceEvent: "status_line",
          details: { status: nextStatus, is_running: runtime.is_running === true },
        });
      }
    }
    const prevDiagnostics = store.getState().diagnostics || {};
    store.updateState({
      runtime,
      diagnostics: {
        ...prevDiagnostics,
        asr: normalizeDiagnostics(runtime.asr_diagnostics || {}),
        translation: runtime.translation_diagnostics || null,
        metrics: runtime.metrics || null,
        obs: runtime.obs_caption_diagnostics || null,
      },
    });
    traceRuntimeVisualState(store.getState(), "setRuntime");
    events?.emit?.("runtime:status", { runtime });
  }

  async function startRuntime() {
    const startedAtMs = Date.now();
    const snapshot = store.getState();
    traceUi("dashboard", "runtime", "start_click", {
      selected_device_id: snapshot.ui?.selectedAudioInputId ?? null,
      prior_status: snapshot.runtime?.status || "idle",
      prior_is_running: snapshot.runtime?.is_running === true,
      runtime_busy: snapshot.ui?.runtimeBusy === true,
    });
    const mode = snapshot.config?.asr?.mode || "local";
    const deviceId = isBrowserRecognitionMode(mode) ? null : snapshot.ui.selectedAudioInputId;
    const configPayload = normalizeConfigShape(clone(snapshot.config || {}));
    store.updateState({
      runtime: {
        ...(snapshot.runtime || {}),
        is_running: false,
        status: "starting",
        status_message: isBrowserRecognitionMode(mode)
          ? isExperimentalBrowserRecognitionMode(mode)
            ? t("runtime.start.preparing_experimental")
            : t("runtime.start.preparing_web_speech")
          : t("runtime.start.preparing_asr"),
        last_error: null,
      },
    });
    let data;
    try {
      data = await api.startRuntime(deviceId, configPayload);
    } catch (error) {
      traceUi("dashboard", "runtime", "start_failed", {
        elapsed_ms: Date.now() - startedAtMs,
        message: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
    setRuntime(data.runtime);
    events?.emit?.("runtime:started", { runtime: data.runtime });
    traceUi("dashboard", "runtime", "start_complete", {
      elapsed_ms: Date.now() - startedAtMs,
      status: data.runtime?.status || "unknown",
      is_running: data.runtime?.is_running === true,
      last_error: data.runtime?.last_error || null,
      mode,
    });
    logger(`[ui] runtime start -> ${data.runtime?.status || "unknown"}`, {
      tracePhase: "ui",
      traceEvent: "start_clicked",
      details: { status: data.runtime?.status || "unknown", mode },
    });
    traceRuntimeVisualState(store.getState(), "startRuntime", { force: true });
    return data;
  }

  async function stopRuntime() {
    const startedAtMs = Date.now();
    const snapshot = store.getState();
    traceUi("dashboard", "runtime", "stop_click", {
      prior_status: snapshot.runtime?.status || "idle",
      prior_is_running: snapshot.runtime?.is_running === true,
      runtime_busy: snapshot.ui?.runtimeBusy === true,
      stop_disabled: !(
        snapshot.runtime?.is_running === true ||
        ["starting", "listening", "transcribing", "translating", "error"].includes(
          String(snapshot.runtime?.status || "").toLowerCase()
        )
      ),
    });
    let data;
    try {
      data = await api.stopRuntime();
    } catch (error) {
      traceUi("dashboard", "runtime", "stop_failed", {
        elapsed_ms: Date.now() - startedAtMs,
        message: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
    setRuntime(data.runtime);
    store.updateState({
      transcript: {
        partial: "",
        finals: [],
      },
    });
    events?.emit?.("runtime:stopped", { runtime: data.runtime });
    traceUi("dashboard", "runtime", "stop_complete", {
      elapsed_ms: Date.now() - startedAtMs,
      status: data.runtime?.status || "unknown",
      is_running: data.runtime?.is_running === true,
      last_error: data.runtime?.last_error || null,
    });
    logger("[ui] runtime stopped", {
      tracePhase: "ui",
      traceEvent: "stop_clicked",
      details: { status: data.runtime?.status || "unknown" },
    });
    traceRuntimeVisualState(store.getState(), "stopRuntime", { force: true });
    return data;
  }

  async function pollRuntimeStatus() {
    const runtimeStatus = await api.getRuntimeStatus();
    setRuntime(runtimeStatus);
    return runtimeStatus;
  }

  return {
    setRuntime,
    startRuntime,
    stopRuntime,
    pollRuntimeStatus,
  };
}
