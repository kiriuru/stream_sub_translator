import { normalizeConfigShape } from "../../normalizers/config-normalizer.js";
import { applyDesktopProfileLockToAsrConfig, isDesktopBrowserQuickStartLocked } from "../desktop-profile-lock.js";
import {
  applyUiThemeFromConfigPayload,
} from "../../ui-theme.js";
import { clone, getCurrentLocale, normalizeSupportedUiLanguage } from "../helpers.js";
import {
  buildSaveStatusMessage,
  getRestartRequiredReasons,
  mirrorBrowserWorkerSettingsToLocalStorage,
} from "../action-helpers.js";
import { isBrowserRecognitionMode } from "../helpers.js";

export function createConfigActions({ store, api, logger, events }) {
  function syncLanguageSelects(locale) {
    const value = normalizeSupportedUiLanguage(locale);
    ["#ui-language-select", "#ui-language-select-settings"].forEach((selector) => {
      const element = document.querySelector(selector);
      if (element) {
        element.value = value;
      }
    });
  }

  function setConfig(payload) {
    const normalized = applyDesktopProfileLockToAsrConfig(normalizeConfigShape(payload));
    const locale = normalizeSupportedUiLanguage(normalized.ui?.language);
    if (window.I18n?.setLocale && locale !== getCurrentLocale()) {
      window.I18n.setLocale(locale);
    }
    applyUiThemeFromConfigPayload(normalized);
    if (window.SstLayout?.syncLayoutControlsFromConfig) {
      window.SstLayout.syncLayoutControlsFromConfig(normalized);
    }
    const nextState = store.getState();
    const configuredTranslationSlots = (Array.isArray(normalized.translation.lines) ? normalized.translation.lines : [])
      .map((line) => String(line?.slot_id || "").toLowerCase())
      .filter(Boolean);
    const currentTranslationSelection = String(nextState.ui.selectedTranslationLanguage || "").toLowerCase() || null;
    const translationSelection = currentTranslationSelection || configuredTranslationSlots[0] || null;
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
    events?.emit?.("config:loaded", { config: normalized });
  }

  function mutateConfig(mutator) {
    const snapshot = store.getState();
    const draft = normalizeConfigShape(clone(snapshot.config || {}));
    mutator(draft);
    if (isDesktopBrowserQuickStartLocked(draft)) {
      applyDesktopProfileLockToAsrConfig(draft);
    }
    setConfig(draft);
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
      mirrorBrowserWorkerSettingsToLocalStorage(savedPayload);
      store.updateState({
        ui: {
          saveStatus: buildSaveStatusMessage(Boolean(response.live_applied), restartReasons, snapshot.runtime),
          saveTone: restartReasons.length ? "warn" : response.live_applied ? "success" : "info",
        },
      });
      events?.emit?.("config:saved", { payload: savedPayload, live_applied: response.live_applied });
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
        getCurrentLocale() === "ru" ? `[config] ошибка сохранения -> ${message}` : `[config] save failed -> ${message}`
      );
      return null;
    } finally {
      store.updateState({ ui: { saving: false } });
    }
  }

  function setUiLanguage(locale) {
    const nextLocale = normalizeSupportedUiLanguage(locale);
    window.I18n?.setLocale?.(nextLocale);
    mutateConfig((draft) => {
      draft.ui.language = nextLocale;
    });
    syncLanguageSelects(nextLocale);
    events?.emit?.("locale:changed", { locale: nextLocale });
  }

  function setUiLayout(layout) {
    const nextLayout = String(layout || "standard").trim().toLowerCase() === "compact" ? "compact" : "standard";
    window.SstLayout?.applyDashboardLayout?.(nextLayout);
    mutateConfig((draft) => {
      draft.ui.layout = nextLayout;
    });
  }

  function setSelectedAudioInput(deviceId) {
    mutateConfig((draft) => {
      draft.audio.input_device_id = deviceId || null;
    });
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
    const importedPayload = response.payload || payload;
    setConfig(importedPayload);
    mirrorBrowserWorkerSettingsToLocalStorage(importedPayload);
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

  return {
    setConfig,
    mutateConfig,
    saveCurrentConfig,
    setUiLanguage,
    setUiLayout,
    setSelectedAudioInput,
    updateConfigFromEditor,
    importConfigFile,
    exportConfig,
    syncLanguageSelects,
  };
}
