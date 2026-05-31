import { collectElements } from "../core/dom.js";
import { createPanelMount } from "../core/panel-mount.js";
import { selectAsrMode } from "../core/selectors.js";
import {
  applyStatusDataset,
  getCurrentLocale,
  isBrowserRecognitionMode,
  normalizeUiStatus,
  resolveRuntimeUiStatus,
  t,
} from "../dashboard/helpers.js";
import { traceRuntimeVisualState, traceUi } from "../dashboard/ui-trace.js";

function renderProgress(runtime, elements, mode, snapshot) {
  const message = String(runtime?.status_message || "").trim();
  const card = elements.progressCard;
  if (!card) {
    return;
  }
  if (isBrowserRecognitionMode(mode)) {
    card.hidden = true;
    card.classList.remove("is-compact");
    return;
  }
  const metrics = runtime?.metrics || {};
  const localAsrLoading =
    !isBrowserRecognitionMode(mode) &&
    Boolean(message) &&
    /loading|initializing|warming|preparing|download/i.test(message);
  const awaitingFirstRecognition =
    runtime?.status === "listening" &&
    Boolean(runtime?.is_running) &&
    Number(metrics.partial_updates_emitted ?? 0) === 0 &&
    Number(metrics.finals_emitted ?? 0) === 0;
  const shouldShow =
    runtime?.status === "starting" ||
    Boolean(snapshot?.ui?.runtimeBusy) ||
    localAsrLoading ||
    awaitingFirstRecognition ||
    (Boolean(message) && runtime?.status === "transcribing");
  card.hidden = !shouldShow;
  if (!shouldShow) {
    card.classList.remove("is-compact");
    if (elements.progressPercent) {
      elements.progressPercent.textContent = "0%";
    }
    if (elements.progressText) {
      elements.progressText.textContent = t("runtime.progress.preparing");
    }
    if (elements.progressFill) {
      elements.progressFill.style.width = "0%";
    }
    return;
  }
  card.classList.remove("is-compact");
  const percentMatch = message.match(/(\d+(?:\.\d+)?)%/);
  const percent = percentMatch ? Number.parseFloat(percentMatch[1]) : runtime?.status === "starting" ? 12 : 0;
  if (elements.progressTitle) {
    elements.progressTitle.textContent = t("runtime.progress.title");
  }
  if (elements.progressPercent) {
    elements.progressPercent.textContent = Number.isFinite(percent) ? `${Math.round(percent)}%` : "...";
  }
  if (elements.progressText) {
    elements.progressText.textContent = message || t("runtime.progress.preparing");
  }
  if (elements.progressFill) {
    elements.progressFill.style.width = `${Math.max(0, Math.min(100, percent || 0))}%`;
  }
}

function renderRuntimePanel(snapshot, elements) {
  const runtime = snapshot.runtime || { status: "idle", is_running: false };
  const diagnostics = snapshot.diagnostics?.asr || {};
  const translationDiagnostics = snapshot.diagnostics?.translation || {};
  const obsDiagnostics = snapshot.diagnostics?.obs || {};
  const mode = selectAsrMode(snapshot);
  const healthStatus = normalizeUiStatus(snapshot.diagnostics?.healthStatus, "unknown");
  const runtimeStatus = resolveRuntimeUiStatus(runtime);
  const translationStatus = normalizeUiStatus(
    translationDiagnostics.status || (translationDiagnostics.enabled ? "ready" : "disabled"),
    translationDiagnostics.enabled ? "ready" : "disabled"
  );
  const asrStatus = runtime.last_error
    ? "error"
    : diagnostics.degraded_mode
      ? "degraded"
      : diagnostics.provider
        ? "ready"
        : "unknown";
  const deviceStatus =
    diagnostics.cpu_fallback_reason || diagnostics.fallback_reason
      ? "degraded"
      : diagnostics.selected_device || diagnostics.selected_execution_provider
        ? "ready"
        : "unknown";
  const obsStatus = obsDiagnostics.last_error ? "error" : obsDiagnostics.enabled ? "ready" : "disabled";

  if (elements.healthBadge) {
    elements.healthBadge.textContent = t("runtime.badge.health", { value: healthStatus });
    applyStatusDataset(elements.healthBadge, healthStatus);
  }
  if (elements.runtimeBadge) {
    elements.runtimeBadge.textContent = t("runtime.badge.runtime", { value: runtimeStatus });
    elements.runtimeBadge.title = [runtime.status, runtime.status_message, runtime.last_error].filter(Boolean).join(" | ");
    applyStatusDataset(elements.runtimeBadge, runtimeStatus);
  }
  if (elements.asrProviderBadge) {
    elements.asrProviderBadge.textContent = t("runtime.badge.asr", { value: diagnostics.provider || "unknown" });
    applyStatusDataset(elements.asrProviderBadge, asrStatus);
  }
  if (elements.asrDeviceBadge) {
    const value = diagnostics.selected_device || diagnostics.selected_execution_provider || "unknown";
    elements.asrDeviceBadge.textContent = t("runtime.badge.device", { value });
    applyStatusDataset(elements.asrDeviceBadge, deviceStatus);
  }
  if (elements.asrPartialsBadge) {
    elements.asrPartialsBadge.textContent = t("runtime.badge.partials", {
      value: diagnostics.partials_supported ? t("common.on") : t("common.off"),
    });
    applyStatusDataset(elements.asrPartialsBadge, diagnostics.partials_supported ? "ready" : "disabled");
  }
  if (elements.asrModeBadge) {
    elements.asrModeBadge.textContent = t("runtime.badge.mode", {
      value: diagnostics.provider_mode_kind || diagnostics.provider || "unknown",
    });
    applyStatusDataset(elements.asrModeBadge, asrStatus);
  }
  if (elements.translationStatusBadge) {
    elements.translationStatusBadge.textContent = t("runtime.badge.translation", { value: translationStatus });
    applyStatusDataset(elements.translationStatusBadge, translationStatus);
  }
  if (elements.obsCcBadge) {
    const value = obsStatus === "ready" ? obsDiagnostics.output_mode || "ready" : obsStatus;
    elements.obsCcBadge.textContent = t("runtime.badge.obs_cc", { value });
    applyStatusDataset(elements.obsCcBadge, obsStatus);
  }
  if (elements.startBtn) {
    elements.startBtn.disabled = runtime.is_running || snapshot.ui.runtimeBusy;
    elements.startBtn.textContent = runtime.status === "starting" ? t("common.starting") : t("common.start");
  }
  if (elements.stopBtn) {
    const stoppableStatuses = new Set(["starting", "listening", "transcribing", "translating", "error"]);
    const canStop =
      Boolean(runtime.is_running) ||
      stoppableStatuses.has(String(runtime.status || "").toLowerCase());
    // Never block Stop on runtimeBusy — users must cancel a long model load.
    elements.stopBtn.disabled = !canStop;
  }
  if (elements.globalSaveBtn) {
    elements.globalSaveBtn.disabled = snapshot.ui.saving;
    elements.globalSaveBtn.textContent = snapshot.ui.saving ? t("runtime.save_button.saving") : t("common.save");
  }
  if (elements.saveStatusText) {
    elements.saveStatusText.textContent = snapshot.ui.saveStatus || t("save.status.default");
    if (snapshot.ui.saveTone && snapshot.ui.saveTone !== "info") {
      elements.saveStatusText.dataset.tone = snapshot.ui.saveTone;
    } else {
      delete elements.saveStatusText.dataset.tone;
    }
  }
  elements.runtimeStates.forEach((pill) => {
    pill.classList.toggle("active", pill.dataset.state === runtime.status);
  });
  if (elements.overlayUrl && snapshot.overlay?.url) {
    elements.overlayUrl.textContent = snapshot.overlay.url;
  }
  if (elements.overlayLink && snapshot.overlay?.url) {
    elements.overlayLink.textContent = snapshot.overlay.url;
    elements.overlayLink.href = snapshot.overlay.url;
  }
  if (elements.versionTag && snapshot.versionInfo?.current_version) {
    elements.versionTag.textContent = `v${snapshot.versionInfo.current_version}`;
    elements.versionTag.title = snapshot.versionInfo.current_version;
  }
  renderProgress(runtime, elements, mode, snapshot);
  traceRuntimeVisualState(snapshot, "runtime_panel_render");
}

const collectRuntimeElements = (root) =>
  collectElements(root, {
    healthBadge: "#health-badge",
    runtimeBadge: "#runtime-badge",
    asrProviderBadge: "#asr-provider-badge",
    asrDeviceBadge: "#asr-device-badge",
    asrPartialsBadge: "#asr-partials-badge",
    asrModeBadge: "#asr-mode-badge",
    translationStatusBadge: "#translation-status-badge",
    obsCcBadge: "#obs-cc-badge",
    startBtn: "#start-btn",
    stopBtn: "#stop-btn",
    saveStatusText: "#save-status-text",
    runtimeStates: [".state-pill"],
    overlayUrl: "#overlay-url",
    overlayLink: "#overlay-link",
    progressCard: "#runtime-progress-card",
    progressTitle: "#runtime-progress-title",
    progressPercent: "#runtime-progress-percent",
    progressText: "#runtime-progress-text",
    progressFill: "#runtime-progress-fill",
    versionTag: ".project-version-tag",
    globalSaveBtn: "#global-save-btn",
    globalSaveBtnToolbar: "#global-save-btn-toolbar",
  });

function bindRuntimeEvents(elements, { store, actions }) {
  async function onStart() {
    const mode = selectAsrMode(store.getState());
    const openWorker =
      mode !== "local" && typeof actions.navigateBrowserAsrWindow === "function"
        ? actions.navigateBrowserAsrWindow()
        : null;
    const result = await actions.startRuntime();
    if (openWorker) {
      await openWorker;
    }
  }

  const onGlobalSave = () => {
    actions.saveCurrentConfig();
  };

  const handlers = [];
  const add = (element, event, handler) => {
    if (!element) {
      return;
    }
    element.addEventListener(event, handler);
    handlers.push(() => element.removeEventListener(event, handler));
  };

  add(elements.startBtn, "click", onStart);
  if (elements.stopBtn) {
    const onStop = (event) => {
      event.preventDefault();
      event.stopPropagation();
      const snapshot = store.getState();
      traceUi("dashboard", "runtime", "stop_button_dom_click", {
        prior_status: snapshot.runtime?.status || "idle",
        prior_is_running: snapshot.runtime?.is_running === true,
      });
      void actions.stopRuntime();
    };
    elements.stopBtn.addEventListener("click", onStop, true);
    handlers.push(() => elements.stopBtn.removeEventListener("click", onStop, true));
  }
  add(elements.globalSaveBtn, "click", onGlobalSave);
  add(elements.globalSaveBtnToolbar, "click", onGlobalSave);
  add(elements.overlayLink, "click", async (event) => {
    if (!window.DesktopBridge?.isDesktopMode?.()) {
      return;
    }
    event.preventDefault();
    await window.DesktopBridge.openExternalUrl(elements.overlayLink.href);
  });

  return () => handlers.forEach((off) => off());
}

const mountRuntimePanelImpl = createPanelMount({
  collectElements: collectRuntimeElements,
  render: renderRuntimePanel,
  bindEvents: bindRuntimeEvents,
});

export function mountRuntimePanel(root, context) {
  return mountRuntimePanelImpl(root, context);
}
