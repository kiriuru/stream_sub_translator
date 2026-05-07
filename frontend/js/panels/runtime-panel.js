import { subscribe } from "../core/store.js";
import { applyStatusDataset, getCurrentLocale, normalizeUiStatus, resolveRuntimeUiStatus, t } from "../dashboard/helpers.js";

function renderProgress(runtime, elements) {
  const message = String(runtime?.status_message || "").trim();
  const card = elements.progressCard;
  if (!card) {
    return;
  }
  const shouldShow = runtime?.status === "starting" || Boolean(message);
  card.hidden = !shouldShow;
  if (!shouldShow) {
    elements.progressPercent.textContent = "0%";
    elements.progressText.textContent = t("runtime.progress.preparing");
    elements.progressFill.style.width = "0%";
    return;
  }
  const percentMatch = message.match(/(\d+(?:\.\d+)?)%/);
  const percent = percentMatch ? Number.parseFloat(percentMatch[1]) : (runtime?.status === "starting" ? 12 : 0);
  elements.progressTitle.textContent =
    message.toLowerCase().includes("browser speech")
      ? t("runtime.progress.browser_speech")
      : t("runtime.progress.title");
  elements.progressPercent.textContent = Number.isFinite(percent) ? `${Math.round(percent)}%` : "...";
  elements.progressText.textContent = message || t("runtime.progress.preparing");
  elements.progressFill.style.width = `${Math.max(0, Math.min(100, percent || 0))}%`;
}

export function mountRuntimePanel(root, { store, actions }) {
  const elements = {
    healthBadge: root.querySelector("#health-badge"),
    runtimeBadge: root.querySelector("#runtime-badge"),
    asrProviderBadge: root.querySelector("#asr-provider-badge"),
    asrDeviceBadge: root.querySelector("#asr-device-badge"),
    asrPartialsBadge: root.querySelector("#asr-partials-badge"),
    asrModeBadge: root.querySelector("#asr-mode-badge"),
    translationStatusBadge: root.querySelector("#translation-status-badge"),
    obsCcBadge: root.querySelector("#obs-cc-badge"),
    startBtn: root.querySelector("#start-btn"),
    stopBtn: root.querySelector("#stop-btn"),
    saveStatusText: root.querySelector("#save-status-text"),
    runtimeStates: [...root.querySelectorAll(".state-pill")],
    overlayUrl: root.querySelector("#overlay-url"),
    overlayLink: root.querySelector("#overlay-link"),
    progressCard: root.querySelector("#runtime-progress-card"),
    progressTitle: root.querySelector("#runtime-progress-title"),
    progressPercent: root.querySelector("#runtime-progress-percent"),
    progressText: root.querySelector("#runtime-progress-text"),
    progressFill: root.querySelector("#runtime-progress-fill"),
    versionTag: root.querySelector(".project-version-tag"),
    globalSaveBtn: root.querySelector("#global-save-btn"),
  };

  async function onStart() {
    const result = await actions.startRuntime();
    const mode = store.getState().config?.asr?.mode || "local";
    if (result?.runtime && mode !== "local") {
      await actions.navigateBrowserAsrWindow();
    }
  }

  function render(snapshot) {
    const runtime = snapshot.runtime || { status: "idle", is_running: false };
    const diagnostics = snapshot.diagnostics?.asr || {};
    const translationDiagnostics = snapshot.diagnostics?.translation || {};
    const obsDiagnostics = snapshot.diagnostics?.obs || {};
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
    const deviceStatus = diagnostics.cpu_fallback_reason || diagnostics.fallback_reason
      ? "degraded"
      : diagnostics.selected_device || diagnostics.selected_execution_provider
        ? "ready"
        : "unknown";
    const obsStatus = obsDiagnostics.last_error
      ? "error"
      : obsDiagnostics.enabled
        ? "ready"
        : "disabled";
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
        value: diagnostics.partials_supported ? (getCurrentLocale() === "ru" ? "вкл" : "on") : (getCurrentLocale() === "ru" ? "выкл" : "off"),
      });
      applyStatusDataset(elements.asrPartialsBadge, diagnostics.partials_supported ? "ready" : "disabled");
    }
    if (elements.asrModeBadge) {
      elements.asrModeBadge.textContent = t("runtime.badge.mode", { value: diagnostics.provider_mode_kind || diagnostics.provider || "unknown" });
      applyStatusDataset(elements.asrModeBadge, asrStatus);
    }
    if (elements.translationStatusBadge) {
      elements.translationStatusBadge.textContent = t("runtime.badge.translation", {
        value: translationStatus,
      });
      applyStatusDataset(elements.translationStatusBadge, translationStatus);
    }
    if (elements.obsCcBadge) {
      const value = obsStatus === "ready" ? (obsDiagnostics.output_mode || "ready") : obsStatus;
      elements.obsCcBadge.textContent = t("runtime.badge.obs_cc", { value });
      applyStatusDataset(elements.obsCcBadge, obsStatus);
    }
    if (elements.startBtn) {
      elements.startBtn.disabled = runtime.is_running || snapshot.ui.runtimeBusy;
      elements.startBtn.textContent = runtime.status === "starting" ? t("common.starting") : t("common.start");
    }
    if (elements.stopBtn) {
      elements.stopBtn.disabled = !runtime.is_running || snapshot.ui.runtimeBusy;
    }
    if (elements.globalSaveBtn) {
      elements.globalSaveBtn.disabled = snapshot.ui.saving;
      elements.globalSaveBtn.textContent = snapshot.ui.saving
        ? (getCurrentLocale() === "ru" ? "Сохранение..." : "Saving...")
        : t("common.save");
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
    renderProgress(runtime, elements);
  }

  elements.startBtn?.addEventListener("click", onStart);
  elements.stopBtn?.addEventListener("click", () => {
    actions.stopRuntime();
  });
  elements.globalSaveBtn?.addEventListener("click", () => {
    actions.saveCurrentConfig();
  });
  elements.overlayLink?.addEventListener("click", async (event) => {
    if (!window.DesktopBridge?.isDesktopMode?.()) {
      return;
    }
    event.preventDefault();
    await window.DesktopBridge.openExternalUrl(elements.overlayLink.href);
  });

  render(store.getState());
  const unsubscribe = subscribe(render);
  return () => unsubscribe();
}
