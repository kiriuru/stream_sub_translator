import { normalizeConfigShape } from "../../normalizers/config-normalizer.js";
import { normalizeDiagnostics } from "../../normalizers/diagnostics-normalizer.js";
import { normalizeRuntimeStatus } from "../../normalizers/runtime-normalizer.js";
import { runtimeSnapshotSignature } from "../action-helpers.js";
import {
  clone,
  getCurrentLocale,
  isBrowserRecognitionMode,
  isExperimentalBrowserRecognitionMode,
} from "../helpers.js";

export function createRuntimeActions({ store, api, logger, events }) {
  const runtimeLogState = { signature: "" };

  function setRuntime(runtimePayload) {
    const runtime = normalizeRuntimeStatus(runtimePayload);
    const nextSnapshotSignature = runtimeSnapshotSignature(runtime);
    const previousSignature = runtimeSnapshotSignature(store.getState().runtime);
    if (nextSnapshotSignature === previousSignature) {
      return;
    }
    const signature = JSON.stringify([runtime.status, runtime.last_error || "", runtime.status_message || ""]);
    if (runtimeLogState.signature !== signature) {
      runtimeLogState.signature = signature;
      if (runtime.last_error) {
        logger(`[runtime] ${runtime.last_error}`);
      } else if (runtime.status_message) {
        logger(`[runtime] ${runtime.status_message}`);
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
    events?.emit?.("runtime:status", { runtime });
  }

  async function startRuntime() {
    const snapshot = store.getState();
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
            ? getCurrentLocale() === "ru"
              ? "Подготавливается Web Speech (Experimental)..."
              : "Preparing Web Speech (Experimental)..."
            : getCurrentLocale() === "ru"
              ? "Подготавливается Web Speech..."
              : "Preparing Web Speech..."
          : getCurrentLocale() === "ru"
            ? "Подготавливается ASR runtime..."
            : "Preparing ASR runtime...",
        last_error: null,
      },
    });
    const data = await api.startRuntime(deviceId, configPayload);
    setRuntime(data.runtime);
    events?.emit?.("runtime:started", { runtime: data.runtime });
    logger(`[ui] runtime start -> ${data.runtime?.status || "unknown"}`);
    return data;
  }

  async function stopRuntime() {
    const data = await api.stopRuntime();
    setRuntime(data.runtime);
    store.updateState({
      transcript: {
        partial: "",
        finals: [],
      },
    });
    events?.emit?.("runtime:stopped", { runtime: data.runtime });
    logger("[ui] runtime stopped");
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
