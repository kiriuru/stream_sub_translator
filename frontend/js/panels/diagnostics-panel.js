import { subscribe } from "../core/store.js";
import { appendTextLog, formatMetric, formatOptionalMetric, t } from "../dashboard/helpers.js";

function renderLogBox(logBox, logs) {
  if (!logBox) {
    return;
  }
  if (logBox.__sstRenderFrame) {
    cancelAnimationFrame(logBox.__sstRenderFrame);
  }
  logBox.__sstRenderFrame = requestAnimationFrame(() => {
    if (!logBox.isConnected || logBox.closest(".tab-panel")?.classList.contains("active") === false) {
      return;
    }
    logBox.value = Array.isArray(logs) ? logs.join("\n") : "";
    logBox.scrollTop = logBox.scrollHeight;
  });
}

export function mountDiagnosticsPanel(root, { store, actions, events }) {
  const elements = {
    latencyMetricsText: root.querySelector("#latency-metrics-text"),
    asrDiagnosticsText: root.querySelector("#asr-diagnostics-text"),
    translationDiagnosticsText: root.querySelector("#translation-diagnostics-text"),
    translationRuntimeText: root.querySelector("#translation-runtime-text"),
    browserWorkerDiagnosticsText: root.querySelector("#browser-worker-diagnostics-text"),
    obsCcDiagnosticsText: root.querySelector("#obs-cc-diagnostics-text"),
    logsDiscoverabilityText: root.querySelector("#logs-discoverability-text"),
    logBox: root.querySelector("#log-box"),
    configSaveBtn: root.querySelector("#config-save-btn"),
    configExportBtn: root.querySelector("#config-export-btn"),
    diagnosticsExportBtn: root.querySelector("#diagnostics-export-btn"),
    configImportInput: root.querySelector("#config-import-input"),
    configImportBtn: root.querySelector("#config-import-btn"),
    configJson: root.querySelector("#config-json"),
  };

  function render(snapshot) {
    const diagnostics = snapshot.diagnostics?.asr || {};
    const translationDiagnostics = snapshot.diagnostics?.translation || {};
    const metrics = snapshot.diagnostics?.metrics || {};
    const obs = snapshot.diagnostics?.obs || {};
    const browserWorker = diagnostics.browser_worker || null;
    if (elements.latencyMetricsText) {
      elements.latencyMetricsText.textContent = [
        `vad ${formatMetric(metrics.vad_ms)}`,
        `asr partial ${formatMetric(metrics.asr_partial_ms)}`,
        `asr final ${formatMetric(metrics.asr_final_ms)}`,
        `translation ${formatMetric(metrics.translation_ms)}`,
        `total ${formatMetric(metrics.total_ms)}`,
        `partials ${metrics.partial_updates_emitted ?? 0}`,
        `finals ${metrics.finals_emitted ?? 0}`,
      ].join(" | ");
    }
    if (elements.asrDiagnosticsText) {
      elements.asrDiagnosticsText.textContent = [
        `provider: ${diagnostics.provider || "n/a"}`,
        `device: ${diagnostics.selected_device || diagnostics.selected_execution_provider || "n/a"}`,
        `requested device policy: ${diagnostics.requested_device_policy || "n/a"}`,
        `partials: ${diagnostics.partials_supported ? "yes" : "no"}`,
        `degraded: ${diagnostics.degraded_mode ? "yes" : "no"}`,
        diagnostics.fallback_reason ? `fallback: ${diagnostics.fallback_reason}` : null,
        diagnostics.cpu_fallback_reason ? `cpu fallback: ${diagnostics.cpu_fallback_reason}` : null,
        diagnostics.message ? `note: ${diagnostics.message}` : null,
      ].filter(Boolean).join(" | ");
    }
    if (elements.translationDiagnosticsText) {
      elements.translationDiagnosticsText.textContent = [
        `provider: ${translationDiagnostics.provider || "none"}`,
        `status: ${translationDiagnostics.status || "unknown"}`,
        `configured: ${translationDiagnostics.configured ? "yes" : "no"}`,
        `ready: ${translationDiagnostics.ready ? "yes" : "no"}`,
        `targets: ${(translationDiagnostics.target_languages || []).join(", ") || "none"}`,
        translationDiagnostics.summary ? `summary: ${translationDiagnostics.summary}` : null,
      ].filter(Boolean).join(" | ");
    }
    if (elements.translationRuntimeText) {
      elements.translationRuntimeText.textContent = [
        `queue: ${translationDiagnostics.queue_depth ?? metrics.translation_queue_depth ?? 0}`,
        `provider latency: ${formatOptionalMetric(translationDiagnostics.provider_latency_ms)}`,
      ].join(" | ");
    }
    if (elements.browserWorkerDiagnosticsText) {
      elements.browserWorkerDiagnosticsText.textContent = browserWorker
        ? [
            `connected: ${browserWorker.connected ? "yes" : "no"}`,
            `mode: ${browserWorker.browser_mode || "n/a"}`,
            `socket: ${browserWorker.websocket_state || "n/a"}`,
          ].join(" | ")
        : t("tools.runtime.browser_worker.not_connected");
    }
    if (elements.obsCcDiagnosticsText) {
      elements.obsCcDiagnosticsText.textContent = [
        `enabled: ${obs.enabled ? "yes" : "no"}`,
        `mode: ${obs.output_mode || "disabled"}`,
        `state: ${obs.connection_state || "disabled"}`,
        obs.last_error ? `error: ${obs.last_error}` : null,
      ].filter(Boolean).join(" | ");
    }
    if (elements.logsDiscoverabilityText) {
      elements.logsDiscoverabilityText.textContent = t("tools.runtime.logs_location");
    }
    if (elements.configJson && snapshot.config) {
      elements.configJson.value = JSON.stringify(snapshot.config, null, 2);
    }
    renderLogBox(elements.logBox, snapshot.ui.logs);
  }

  elements.configSaveBtn?.addEventListener("click", () => {
    actions.saveCurrentConfig();
  });
  elements.configExportBtn?.addEventListener("click", () => {
    actions.exportConfig();
  });
  elements.diagnosticsExportBtn?.addEventListener("click", () => {
    actions.exportDiagnostics().catch(() => {
      appendTextLog(elements.logBox, t("tools.runtime.export_failed"));
    });
  });
  elements.configImportBtn?.addEventListener("click", async () => {
    const file = elements.configImportInput?.files?.[0];
    if (!file) {
      return;
    }
    await actions.importConfigFile(file);
  });
  elements.configJson?.addEventListener("change", () => {
    try {
      actions.updateConfigFromEditor(elements.configJson.value || "{}");
    } catch (_error) {
      // keep current editor text until user explicitly saves/fixes it
    }
  });

  render(store.getState());
  const unsubscribe = subscribe(render);
  return () => unsubscribe();
}
