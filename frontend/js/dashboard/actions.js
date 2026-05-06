import { normalizeConfigShape } from "../normalizers/config-normalizer.js";
import { normalizeDiagnostics } from "../normalizers/diagnostics-normalizer.js";
import { normalizeModelStatus } from "../normalizers/model-normalizer.js";
import { normalizeOverlayPayload } from "../normalizers/overlay-normalizer.js";
import { normalizeRuntimeStatus } from "../normalizers/runtime-normalizer.js";
import { normalizeDisplayOrder, normalizeTranslationResult } from "../normalizers/translation-normalizer.js";
import {
  clone,
  formatList,
  getCurrentLocale,
  getProviderMeta,
  getRecognitionModeLabel,
  isBrowserRecognitionMode,
  isExperimentalBrowserRecognitionMode,
  normalizeSupportedUiLanguage,
  parseIntegerOr,
} from "./helpers.js";

function getResolvedSubtitleStyle(config, presets) {
  if (!window.SubtitleStyleRenderer) {
    return config?.subtitle_style || {};
  }
  return window.SubtitleStyleRenderer.resolveEffectiveStyle(config?.subtitle_style || {}, presets || {});
}

function buildSaveStatusMessage(liveApplied, restartReasons, runtime) {
  if (!restartReasons.length) {
    return liveApplied
      ? (getCurrentLocale() === "ru" ? "Сохранено и сразу применено." : "Saved and applied immediately.")
      : (getCurrentLocale() === "ru" ? "Сохранено локально." : "Saved locally.");
  }
  const subject = formatList(restartReasons);
  const restartLabel = runtime?.is_running
    ? (getCurrentLocale() === "ru" ? "после Стоп/Старт" : "after Stop/Start")
    : (getCurrentLocale() === "ru" ? "при следующем Старт" : "on the next Start");
  if (liveApplied) {
    return getCurrentLocale() === "ru"
      ? `Сохранено и сразу применено. Изменения для: ${subject} вступят в силу ${restartLabel}.`
      : `Saved and applied immediately. ${subject} changes will take effect ${restartLabel}.`;
  }
  return getCurrentLocale() === "ru"
    ? `Сохранено локально. Изменения для: ${subject} вступят в силу ${restartLabel}.`
    : `Saved locally. ${subject} changes will take effect ${restartLabel}.`;
}

function getRestartRequiredReasons(previousPayload, nextPayload) {
  const reasons = [];
  if ((previousPayload?.audio?.input_device_id ?? null) !== (nextPayload?.audio?.input_device_id ?? null)) {
    reasons.push(getCurrentLocale() === "ru" ? "микрофон" : "microphone device");
  }
  if (String(previousPayload?.asr?.mode || "local") !== String(nextPayload?.asr?.mode || "local")) {
    reasons.push(getCurrentLocale() === "ru" ? "режим распознавания" : "recognition mode");
  }
  if (String(previousPayload?.asr?.provider_preference || "") !== String(nextPayload?.asr?.provider_preference || "")) {
    reasons.push(getCurrentLocale() === "ru" ? "ASR-провайдер" : "ASR provider");
  }
  if (Boolean(previousPayload?.asr?.prefer_gpu) !== Boolean(nextPayload?.asr?.prefer_gpu)) {
    reasons.push(getCurrentLocale() === "ru" ? "политика GPU" : "GPU policy");
  }
  if (
    String(previousPayload?.asr?.browser?.recognition_language || "ru-RU") !==
    String(nextPayload?.asr?.browser?.recognition_language || "ru-RU")
  ) {
    reasons.push(getCurrentLocale() === "ru" ? "язык браузерного распознавания" : "browser recognition language");
  }
  return reasons;
}

function addTranslationEntry(state, sequence, sourceText) {
  const current = state.translation?.currentEntry || null;
  if (current && current.sequence === sequence) {
    current.sourceText = sourceText;
    return current;
  }
  const entry = {
    sequence,
    sourceText,
    translations: [],
    providerLabel: "",
    statusMessage: "",
  };
  state.translation = {
    ...(state.translation || {}),
    currentEntry: entry,
  };
  return entry;
}

function buildPreviewPayload(state) {
  const config = state.config;
  if (!config) {
    return null;
  }
  if (state.overlay?.payload) {
    return {
      ...state.overlay.payload,
      style: getResolvedSubtitleStyle(config, state.subtitleStylePresets),
    };
  }

  const visibleItems = [];
  const displayOrder = Array.isArray(config.subtitle_output?.display_order) ? config.subtitle_output.display_order : [];
  const maxTranslations = Math.max(0, Math.min(5, Number(config.subtitle_output?.max_translation_languages || 0)));
  let translationsUsed = 0;
  displayOrder.forEach((code) => {
    if (code === "source") {
      if (config.subtitle_output?.show_source !== false) {
        visibleItems.push({
          kind: "source",
          lang: config.source_lang || "auto",
          style_slot: "source",
          text: getCurrentLocale() === "ru" ? "Предпросмотр исходной строки" : "Source subtitle preview",
        });
      }
      return;
    }
    if (config.subtitle_output?.show_translations === false || translationsUsed >= maxTranslations) {
      return;
    }
    visibleItems.push({
      kind: "translation",
      lang: code,
      style_slot: `translation_${translationsUsed + 1}`,
      text: code,
    });
    translationsUsed += 1;
  });

  return {
    preset: config.overlay?.preset || "single",
    compact: Boolean(config.overlay?.compact),
    completed_block_visible: visibleItems.length > 0,
    visible_items: visibleItems,
    active_partial_text:
      visibleItems.length === 0 && config.subtitle_output?.show_source !== false
        ? (getCurrentLocale() === "ru" ? "Предпросмотр live-partial" : "Live partial preview")
        : "",
    style: getResolvedSubtitleStyle(config, state.subtitleStylePresets),
    sequence: 0,
  };
}

function runtimeSnapshotSignature(runtime) {
  return JSON.stringify({
    status: runtime?.status || "idle",
    is_running: runtime?.is_running === true,
    last_error: runtime?.last_error || null,
    status_message: runtime?.status_message || null,
    event_sequence: runtime?.event_sequence || runtime?.sequence || 0,
    browser_worker: runtime?.asr_diagnostics?.browser_worker
      ? {
          worker_connected: runtime.asr_diagnostics.browser_worker.worker_connected,
          recognition_state: runtime.asr_diagnostics.browser_worker.recognition_state,
          supervisor_state: runtime.asr_diagnostics.browser_worker.supervisor_state,
          degraded_reason: runtime.asr_diagnostics.browser_worker.degraded_reason,
          generation_id: runtime.asr_diagnostics.browser_worker.generation_id,
        }
      : null,
  });
}

export function createDashboardActions({ store, api, logger }) {
  const runtimeLogState = {
    signature: "",
  };

  function updateBusyState(busyKey, isBusy) {
    const snapshot = store.getState();
    if (busyKey === "save") {
      store.updateState({ ui: { saving: isBusy, saveTone: isBusy ? "info" : snapshot.ui.saveTone } });
    }
    if (busyKey === "runtime") {
      store.updateState({ ui: { runtimeBusy: isBusy } });
    }
  }

  function setConfig(payload) {
    const normalized = normalizeConfigShape(payload);
    const locale = normalizeSupportedUiLanguage(normalized.ui?.language);
    if (window.I18n?.setLocale && locale !== getCurrentLocale()) {
      window.I18n.setLocale(locale);
    }
    const nextState = store.getState();
    const translationSelection = normalized.translation.target_languages.includes(nextState.ui.selectedTranslationLanguage)
      ? nextState.ui.selectedTranslationLanguage
      : normalized.translation.target_languages[0] || null;
    const subtitleSelection = normalized.subtitle_output.display_order.includes(nextState.ui.selectedSubtitleOrderItem)
      ? nextState.ui.selectedSubtitleOrderItem
      : normalized.subtitle_output.display_order[0] || null;
    store.updateState({
      config: normalized,
      subtitleStylePresets: nextState.subtitleStylePresets || {},
      ui: {
        uiLanguage: locale,
        selectedAudioInputId: normalized.audio.input_device_id || null,
        selectedTranslationLanguage: translationSelection,
        selectedSubtitleOrderItem: subtitleSelection,
        selectedStyleLineSlot: nextState.ui.selectedStyleLineSlot || "source",
      },
    });
  }

  function mutateConfig(mutator) {
    const snapshot = store.getState();
    const draft = normalizeConfigShape(clone(snapshot.config || {}));
    mutator(draft);
    setConfig(draft);
  }

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
    store.updateState({
      runtime,
      diagnostics: {
        asr: normalizeDiagnostics(runtime.asr_diagnostics || {}),
        translation: runtime.translation_diagnostics || null,
        metrics: runtime.metrics || null,
        obs: runtime.obs_caption_diagnostics || null,
      },
    });
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

  function setUiLanguage(locale) {
    const nextLocale = normalizeSupportedUiLanguage(locale);
    window.I18n?.setLocale?.(nextLocale);
    mutateConfig((draft) => {
      draft.ui.language = nextLocale;
    });
  }

  async function saveCurrentConfig(options = {}) {
    const snapshot = store.getState();
    const previousPayload = clone(snapshot.config || {});
    const payload = normalizeConfigShape(clone(snapshot.config || {}));
    store.updateState({ ui: { saving: true } });
    try {
      if (options?.preserveLatestBrowserWorkerSettings && isBrowserRecognitionMode(payload?.asr?.mode || "local")) {
        try {
          const latestSettings = await api.loadSettings();
          const latestPayload = normalizeConfigShape(latestSettings?.payload || {});
          if (latestPayload?.asr?.browser && typeof latestPayload.asr.browser === "object") {
            payload.asr.browser = clone(latestPayload.asr.browser);
          }
        } catch (_error) {
          // keep save flow operational
        }
      }
      const response = await api.saveSettings(payload);
      const savedPayload = response.payload || payload;
      const restartReasons = getRestartRequiredReasons(previousPayload, savedPayload);
      store.updateState({
        subtitleStylePresets: response.subtitle_style_presets || snapshot.subtitleStylePresets,
        fontCatalog: response.font_catalog || snapshot.fontCatalog,
      });
      setConfig(savedPayload);
      store.updateState({
        ui: {
          saveStatus: buildSaveStatusMessage(Boolean(response.live_applied), restartReasons, snapshot.runtime),
          saveTone: restartReasons.length ? "warn" : response.live_applied ? "success" : "info",
        },
      });
      logger(
        getCurrentLocale() === "ru"
          ? `[config] сохранено локально${response.live_applied ? " и применено сразу" : ""}`
          : `[config] saved locally${response.live_applied ? " and applied live" : ""}`
      );
      return response;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Save failed.";
      store.updateState({
        ui: {
          saveStatus: getCurrentLocale() === "ru" ? `Сохранение не удалось: ${message}` : `Save failed: ${message}`,
          saveTone: "error",
        },
      });
      logger(
        getCurrentLocale() === "ru"
          ? `[config] ошибка сохранения -> ${message}`
          : `[config] save failed -> ${message}`
      );
      return null;
    } finally {
      store.updateState({ ui: { saving: false } });
    }
  }

  function setSelectedAudioInput(deviceId) {
    mutateConfig((draft) => {
      draft.audio.input_device_id = deviceId || null;
    });
  }

  function updateTranslationSelection(code) {
    store.updateState({ ui: { selectedTranslationLanguage: code || null } });
  }

  function updateSubtitleSelection(code) {
    store.updateState({ ui: { selectedSubtitleOrderItem: code || null } });
  }

  function updateStyleSlot(slotName) {
    store.updateState({ ui: { selectedStyleLineSlot: slotName || "source" } });
  }

  function setActiveTab(tabName) {
    store.updateState({ ui: { activeTab: tabName } });
  }

  function updateConfigFromEditor(text) {
    const parsed = normalizeConfigShape(JSON.parse(text || "{}"));
    setConfig(parsed);
  }

  async function importConfigFile(file) {
    const text = await file.text();
    const payload = normalizeConfigShape(JSON.parse(text));
    const response = await api.saveSettings(payload);
    store.updateState({
      subtitleStylePresets: response.subtitle_style_presets || store.getState().subtitleStylePresets,
      fontCatalog: response.font_catalog || store.getState().fontCatalog,
    });
    setConfig(response.payload || payload);
    logger(getCurrentLocale() === "ru" ? "[config] импорт выполнен" : "[config] imported");
    return response;
  }

  function exportConfig() {
    const payload = normalizeConfigShape(clone(store.getState().config || {}));
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "config.export.json";
    anchor.click();
    URL.revokeObjectURL(url);
    logger(getCurrentLocale() === "ru" ? "[config] экспорт выполнен" : "[config] exported");
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

  async function startRuntime() {
    const snapshot = store.getState();
    const mode = snapshot.config?.asr?.mode || "local";
    const deviceId = isBrowserRecognitionMode(mode) ? null : snapshot.ui.selectedAudioInputId;
    store.updateState({
      runtime: {
        ...(snapshot.runtime || {}),
        is_running: false,
        status: "starting",
        status_message: isBrowserRecognitionMode(mode)
          ? (
            isExperimentalBrowserRecognitionMode(mode)
              ? (getCurrentLocale() === "ru" ? "Подготавливается experimental browser speech worker..." : "Preparing experimental browser speech worker...")
              : (getCurrentLocale() === "ru" ? "Подготавливается browser speech worker..." : "Preparing browser speech worker...")
          )
          : (getCurrentLocale() === "ru" ? "Подготавливается ASR runtime..." : "Preparing ASR runtime..."),
        last_error: null,
      },
    });
    const data = await api.startRuntime(deviceId);
    setRuntime(data.runtime);
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
    logger("[ui] runtime stopped");
    return data;
  }

  function handleTranscriptEvent(payload) {
    const snapshot = store.getState();
    const text = payload?.segment?.text || payload?.text || "";
    const transcript = clone(snapshot.transcript || { partial: "", finals: [] });
    const nextState = {};
    if (payload?.event === "partial") {
      transcript.partial = text;
    } else if (payload?.event === "final") {
      transcript.partial = "";
      transcript.finals.unshift(text);
      transcript.finals = transcript.finals.slice(0, 12);
      addTranslationEntry(nextState, Number(payload.sequence || 0), text);
    }
    nextState.transcript = transcript;
    store.updateState(nextState);
  }

  function handleTranslationEvent(payload) {
    const snapshot = store.getState();
    const draft = {
      translation: clone(snapshot.translation || {}),
    };
    const normalized = normalizeTranslationResult(payload);
    const entry = addTranslationEntry(draft, normalized.sequence, normalized.source_text);
    if (normalized.translations.length) {
      const merged = new Map();
      entry.translations.forEach((item) => {
        if (item?.target_lang) {
          merged.set(item.target_lang, item);
        }
      });
      normalized.translations.forEach((item) => {
        if (item?.target_lang) {
          merged.set(item.target_lang, item);
        }
      });
      entry.translations = Array.from(merged.values());
    }
    const meta = normalized.provider ? getProviderMeta(normalized.provider) : null;
    const labelParts = [];
    if (normalized.provider) {
      labelParts.push(getCurrentLocale() === "ru" ? `Провайдер: ${meta?.label || normalized.provider}` : `Provider: ${meta?.label || normalized.provider}`);
    }
    if (normalized.provider_group) {
      labelParts.push(getCurrentLocale() === "ru" ? `Группа: ${normalized.provider_group}` : `Group: ${normalized.provider_group}`);
    }
    if (normalized.local_provider) {
      labelParts.push(getCurrentLocale() === "ru" ? "Локальный провайдер" : "Local provider");
    }
    if (normalized.experimental) {
      labelParts.push(getCurrentLocale() === "ru" ? "Экспериментально" : "Experimental");
    }
    if (normalized.used_default_prompt) {
      labelParts.push(getCurrentLocale() === "ru" ? "Prompt по умолчанию" : "Default prompt");
    }
    entry.providerLabel = labelParts.join(" | ");
    entry.statusMessage = normalized.status_message || "";
    store.updateState({
      translation: {
        ...(snapshot.translation || {}),
        currentEntry: entry,
        lastResult: normalized,
      },
    });
  }

  function handleOverlayEvent(payload) {
    const snapshot = store.getState();
    store.updateState({
      overlay: {
        ...(snapshot.overlay || {}),
        payload: normalizeOverlayPayload(payload),
      },
    });
  }

  function handleWsMessage(message) {
    if (message.type === "transcript_update") {
      handleTranscriptEvent(message.payload);
      return;
    }
    if (message.type === "translation_update") {
      handleTranslationEvent(message.payload);
      return;
    }
    if (message.type === "overlay_update") {
      handleOverlayEvent(message.payload);
      return;
    }
    if (message.type === "runtime_status") {
      setRuntime(message.payload);
      return;
    }
    if (message.type === "diagnostics_update") {
      store.updateState({ diagnostics: normalizeDiagnostics(message.payload) });
      return;
    }
    if (message.type === "model_status_update") {
      store.updateState({ model: normalizeModelStatus(message.payload) });
      return;
    }
    if (message.type === "preflight_update") {
      store.updateState({ ui: { preflightRunning: message.payload?.running === true } });
    }
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
      setConfig(settings.payload);
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

  async function pollRuntimeStatus() {
    const runtimeStatus = await api.getRuntimeStatus();
    setRuntime(runtimeStatus);
    return runtimeStatus;
  }

  function getPreviewPayload() {
    return buildPreviewPayload(store.getState());
  }

  function buildBrowserAsrUrl(mode) {
    const params = new URLSearchParams();
    params.set("autostart", "1");
    params.set("locale", getCurrentLocale());
    const relativeUrl = isExperimentalBrowserRecognitionMode(mode)
      ? `/google-asr-experimental?${params.toString()}`
      : `/google-asr?${params.toString()}`;
    try {
      return new URL(relativeUrl, window.location.href).toString();
    } catch (_error) {
      return relativeUrl;
    }
  }

  async function navigateBrowserAsrWindow() {
    const browserAsrUrl = buildBrowserAsrUrl(store.getState().config?.asr?.mode || "browser_google");
    if (window.DesktopBridge?.isDesktopMode?.()) {
      const opened = await window.DesktopBridge.openExternalUrl(browserAsrUrl);
      if (!opened) {
        logger(getCurrentLocale() === "ru" ? "[browser-asr] не удалось открыть внешний browser worker" : "[browser-asr] failed to open external browser worker");
      }
      return;
    }
    const popup = window.open(browserAsrUrl, "browser_asr_worker");
    if (!popup) {
      logger("[browser-asr] popup blocked; allow popups for this local app");
      return;
    }
    popup.focus();
  }

  return {
    updateBusyState,
    setConfig,
    mutateConfig,
    setRuntime,
    setAudioInputs,
    refreshProfiles,
    refreshSystemFonts,
    setUiLanguage,
    saveCurrentConfig,
    setSelectedAudioInput,
    updateTranslationSelection,
    updateSubtitleSelection,
    updateStyleSlot,
    setActiveTab,
    updateConfigFromEditor,
    importConfigFile,
    exportConfig,
    exportDiagnostics,
    startRuntime,
    stopRuntime,
    handleWsMessage,
    loadInitialData,
    pollRuntimeStatus,
    getPreviewPayload,
    navigateBrowserAsrWindow,
  };
}
