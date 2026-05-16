import { normalizeDiagnostics } from "../../normalizers/diagnostics-normalizer.js";
import { getCurrentLocale } from "../helpers.js";

export function createDataActions({ store, api, logger, configActions }) {
  function updateBusyState(busyKey, isBusy) {
    const snapshot = store.getState();
    if (busyKey === "save") {
      store.updateState({ ui: { saving: isBusy, saveTone: isBusy ? "info" : snapshot.ui.saveTone } });
    }
    if (busyKey === "runtime") {
      store.updateState({ ui: { runtimeBusy: isBusy } });
    }
  }

  function setAudioInputs(devices) {
    const currentDevices = Array.isArray(devices) ? devices.slice() : [];
    const snapshot = store.getState();
    const configuredDeviceId = snapshot.config?.audio?.input_device_id;
    const selectedDeviceId = currentDevices.some((item) => item.id === configuredDeviceId)
      ? configuredDeviceId
      : currentDevices.find((item) => item.is_default)?.id || currentDevices[0]?.id || null;
    store.updateState({
      audioDevices: currentDevices,
      ui: {
        selectedAudioInputId: selectedDeviceId,
      },
    });
    if (currentDevices.length) {
      logger(
        getCurrentLocale() === "ru"
          ? `[audio] найдено входных устройств: ${currentDevices.length}`
          : `[audio] detected ${currentDevices.length} input device(s)`
      );
    } else {
      logger(getCurrentLocale() === "ru" ? "[audio] входные устройства не найдены" : "[audio] no input devices found");
    }
  }

  async function refreshProfiles() {
    const data = await api.listProfiles();
    store.updateState({ profiles: Array.isArray(data?.profiles) ? data.profiles : [] });
    return data;
  }

  async function refreshSystemFonts() {
    if (typeof window.queryLocalFonts !== "function") {
      return;
    }
    const localFonts = await window.queryLocalFonts();
    const seen = new Set();
    const systemFonts = [];
    localFonts.forEach((font) => {
      const family = String(font.family || "").trim();
      if (!family || seen.has(family)) {
        return;
      }
      seen.add(family);
      systemFonts.push({
        id: `system-${family.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
        label: family,
        family: `"${family}"`,
        source: "system",
      });
    });
    const snapshot = store.getState();
    store.updateState({
      fontCatalog: {
        ...snapshot.fontCatalog,
        system: systemFonts.sort((left, right) => left.label.localeCompare(right.label)),
      },
    });
  }

  async function loadInitialData() {
    const [versionInfo, health, obs, settings, audioInputs] = await Promise.all([
      api.getVersionInfo().catch(() => null),
      api.getHealth().catch(() => null),
      api.getObsUrl().catch(() => null),
      api.loadSettings(),
      api.getAudioInputs(),
    ]);

    if (versionInfo) {
      store.updateState({ versionInfo });
    }
    if (health) {
      store.updateState({
        diagnostics: {
          healthStatus: health.status || "unknown",
          asr: normalizeDiagnostics(health.asr_diagnostics || {}),
          translation: health.translation_diagnostics || null,
          metrics: null,
          obs: health.obs_caption_diagnostics || null,
        },
      });
    }
    if (obs) {
      store.updateState({
        overlay: {
          url: obs.overlay_url,
          payload: null,
        },
      });
    }
    if (settings) {
      store.updateState({
        subtitleStylePresets: settings.subtitle_style_presets || {},
        fontCatalog: settings.font_catalog || store.getState().fontCatalog,
      });
      configActions.setConfig(settings.payload);
    }
    if (audioInputs) {
      setAudioInputs(audioInputs.devices || []);
    }
    await refreshProfiles().catch(() => null);
    if (health?.asr_message) {
      logger(`[asr] ${health.asr_message}`);
    }
    if (health?.translation_diagnostics?.summary) {
      logger(`[translation] ${health.translation_diagnostics.summary}`);
    }
  }

  async function exportDiagnostics() {
    const download = await api.downloadDiagnosticsBundle();
    const blob = download?.blob;
    if (!blob) {
      throw new Error("Diagnostics export failed.");
    }
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = download.filename || "sst-diagnostics.zip";
    anchor.click();
    URL.revokeObjectURL(url);
    logger(getCurrentLocale() === "ru" ? "[diagnostics] архив экспортирован" : "[diagnostics] bundle exported");
  }

  async function listOpenAiModels({ apiKey, baseUrl, showAll } = {}) {
    return api.listOpenAiModels({
      api_key: apiKey || "",
      base_url: baseUrl || null,
      show_all: Boolean(showAll),
    });
  }

  async function listUsableOpenAiModels({ apiKey, baseUrl, testAll, forceRefresh } = {}) {
    return api.listUsableOpenAiModels({
      api_key: apiKey || "",
      base_url: baseUrl || null,
      test_all: Boolean(testAll),
      force_refresh: Boolean(forceRefresh),
      max_checks: 25,
    });
  }

  async function listRecommendedOpenAiModels() {
    return api.listRecommendedOpenAiModels();
  }

  return {
    updateBusyState,
    setAudioInputs,
    refreshProfiles,
    refreshSystemFonts,
    loadInitialData,
    exportDiagnostics,
    listOpenAiModels,
    listUsableOpenAiModels,
    listRecommendedOpenAiModels,
  };
}
