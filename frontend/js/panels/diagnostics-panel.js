import { collectElements } from "../core/dom.js";
import { createPanelMount } from "../core/panel-mount.js";
import { formatMetric, formatOptionalMetric, t } from "../dashboard/helpers.js";

function renderDiagnosticsPanel(snapshot, elements) {
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
    ]
      .filter(Boolean)
      .join(" | ");
  }
  if (elements.translationDiagnosticsText) {
    elements.translationDiagnosticsText.textContent = [
      `provider: ${translationDiagnostics.provider || "none"}`,
      `status: ${translationDiagnostics.status || "unknown"}`,
      `configured: ${translationDiagnostics.configured ? "yes" : "no"}`,
      `ready: ${translationDiagnostics.ready ? "yes" : "no"}`,
      `targets: ${(translationDiagnostics.target_languages || []).join(", ") || "none"}`,
      translationDiagnostics.summary ? `summary: ${translationDiagnostics.summary}` : null,
    ]
      .filter(Boolean)
      .join(" | ");
  }
  if (elements.translationRuntimeText) {
    elements.translationRuntimeText.textContent = [
      `queue: ${translationDiagnostics.queue_depth ?? metrics.translation_queue_depth ?? 0}`,
      `provider latency: ${formatOptionalMetric(translationDiagnostics.provider_latency_ms)}`,
    ].join(" | ");
  }
  if (elements.browserWorkerDiagnosticsText) {
    if (!browserWorker) {
      elements.browserWorkerDiagnosticsText.textContent = t("tools.runtime.browser_worker.not_connected");
    } else {
      const connected = browserWorker.worker_connected === true || browserWorker.connected === true;
      const websocketReady =
        browserWorker.websocket_ready === true || String(browserWorker.websocket_state || "").toLowerCase() === "open";
      elements.browserWorkerDiagnosticsText.textContent = [
        `connected: ${connected ? "yes" : "no"}`,
        `mode: ${browserWorker.browser_mode || browserWorker.provider_name || "n/a"}`,
        `socket: ${websocketReady ? "ready" : browserWorker.websocket_state || "n/a"}`,
        `recognition: ${browserWorker.recognition_state || "n/a"}`,
        `supervisor: ${browserWorker.supervisor_state || "n/a"}`,
      ].join(" | ");
    }
  }
  if (elements.obsCcDiagnosticsText) {
    elements.obsCcDiagnosticsText.textContent = [
      `enabled: ${obs.enabled ? "yes" : "no"}`,
      `mode: ${obs.output_mode || "disabled"}`,
      `state: ${obs.connection_state || "disabled"}`,
      obs.last_error ? `error: ${obs.last_error}` : null,
    ]
      .filter(Boolean)
      .join(" | ");
  }
  if (elements.logsDiscoverabilityText) {
    elements.logsDiscoverabilityText.textContent = t("tools.runtime.logs_location");
  }
  if (elements.configJson && snapshot.config) {
    elements.configJson.value = JSON.stringify(snapshot.config, null, 2);
  }
}

const collectDiagnosticsElements = (root) =>
  collectElements(root, {
    latencyMetricsText: "#latency-metrics-text",
    asrDiagnosticsText: "#asr-diagnostics-text",
    translationDiagnosticsText: "#translation-diagnostics-text",
    translationRuntimeText: "#translation-runtime-text",
    browserWorkerDiagnosticsText: "#browser-worker-diagnostics-text",
    obsCcDiagnosticsText: "#obs-cc-diagnostics-text",
    logsDiscoverabilityText: "#logs-discoverability-text",
    configSaveBtn: "#config-save-btn",
    configExportBtn: "#config-export-btn",
    diagnosticsExportBtn: "#diagnostics-export-btn",
    configImportInput: "#config-import-input",
    configImportBtn: "#config-import-btn",
    configJson: "#config-json",
  });

function bindDiagnosticsEvents(elements, { actions }) {
  const handlers = [];
  const add = (element, event, handler) => {
    if (!element) {
      return;
    }
    element.addEventListener(event, handler);
    handlers.push(() => element.removeEventListener(event, handler));
  };

  add(elements.configSaveBtn, "click", () => actions.saveCurrentConfig());
  add(elements.configExportBtn, "click", () => actions.exportConfig());
  add(elements.diagnosticsExportBtn, "click", () => {
    actions.exportDiagnostics().catch(() => {});
  });
  add(elements.configImportBtn, "click", async () => {
    const file = elements.configImportInput?.files?.[0];
    if (!file) {
      return;
    }
    await actions.importConfigFile(file);
  });
  add(elements.configJson, "change", () => {
    try {
      actions.updateConfigFromEditor(elements.configJson.value || "{}");
    } catch (_error) {
      // keep editor text until user fixes JSON
    }
  });

  return () => handlers.forEach((off) => off());
}

const mountDiagnosticsPanelImpl = createPanelMount({
  collectElements: collectDiagnosticsElements,
  render: renderDiagnosticsPanel,
  bindEvents: bindDiagnosticsEvents,
});

export function mountDiagnosticsPanel(root, context) {
  return mountDiagnosticsPanelImpl(root, context);
}
