import { subscribe } from "../core/store.js";
import { fillSelectOptions, setSelectMarkup } from "../core/dom.js";
import {
  buildTranslationResultsKey,
  renderTranslationResults,
} from "./translation/translation-results-view.js";
import { createTranslationLineEditor } from "./translation/translation-line-editor-view.js";
import {
  CANONICAL_TRANSLATION_SLOTS,
  buildProviderOptions,
  ensureLine,
  getLineBySlot,
  getLineCards,
  getMissingProviderFields,
  getSelectedSlotId,
  getSlotNumber,
  getTranslationProviderSettingValue,
  normalizeProviderName,
  setTranslationProviderSettingValue,
} from "./translation/translation-panel-shared.js";
import { LANGUAGES, PROVIDERS } from "../dashboard/constants.js";
import {
  escapeHtml,
  getCurrentLocale,
  getLanguageLabel,
  getProviderMeta,
  setElementVisibility,
  t,
} from "../dashboard/helpers.js";
import { normalizeDisplayOrder } from "../normalizers/translation-normalizer.js";

export function mountTranslationPanel(root, { store, actions, logger }) {
  let lastResultsRenderKey = "";
  let cachedProviderOptionsLocale = "";
  let lastLoadedModelsKey = "";
  let lastLoadedModels = [];

  const elements = {
    enabled: root.querySelector("#translation-enabled"),
    cacheEnabled: root.querySelector("#translation-cache-enabled"),
    cachePersist: root.querySelector("#translation-cache-persist"),
    defaultProvider: root.querySelector("#translation-provider"),
    settingsProvider: root.querySelector("#translation-settings-provider"),
    settingsTitle: root.querySelector("#translation-provider-settings-title"),
    settingsWarning: root.querySelector("#translation-provider-settings-warning"),
    apiKey: root.querySelector("#translation-api-key"),
    apiKeyLabel: root.querySelector("#translation-api-key-label"),
    apiKeyRow: root.querySelector("#translation-api-key-row"),
    apiKeyToggle: root.querySelector("#translation-api-key-toggle"),
    baseUrl: root.querySelector("#translation-base-url"),
    baseUrlRow: root.querySelector("#translation-base-url-row"),
    baseUrlLabel: root.querySelector("#translation-base-url-label"),
    gasUrl: root.querySelector("#translation-gas-url"),
    gasUrlRow: root.querySelector("#translation-gas-url-row"),
    gasUrlLabel: root.querySelector("#translation-gas-url-label"),
    endpoint: root.querySelector("#translation-endpoint"),
    endpointRow: root.querySelector("#translation-endpoint-row"),
    endpointLabel: root.querySelector("#translation-endpoint-label"),
    region: root.querySelector("#translation-region"),
    regionRow: root.querySelector("#translation-region-row"),
    regionLabel: root.querySelector("#translation-region-label"),
    apiUrl: root.querySelector("#translation-api-url"),
    apiUrlRow: root.querySelector("#translation-api-url-row"),
    apiUrlLabel: root.querySelector("#translation-api-url-label"),
    model: root.querySelector("#translation-model"),
    modelRow: root.querySelector("#translation-model-row"),
    modelLabel: root.querySelector("#translation-model-label"),
    modelLoadBtn: root.querySelector("#translation-model-load-btn"),
    modelPickerRow: root.querySelector("#translation-model-picker-row"),
    modelSelect: root.querySelector("#translation-model-select"),
    modelShowAll: root.querySelector("#translation-model-show-all"),
    modelStatus: root.querySelector("#translation-model-status"),
    prompt: root.querySelector("#translation-custom-prompt"),
    promptRow: root.querySelector("#translation-prompt-row"),
    providerHint: root.querySelector("#translation-provider-hint"),
    providerStatus: root.querySelector("#translation-provider-status"),
    languageSelect: root.querySelector("#translation-language-select"),
    languageOrder: root.querySelector("#translation-language-order"),
    addBtn: root.querySelector("#translation-lang-add-btn"),
    removeBtn: root.querySelector("#translation-lang-remove-btn"),
    results: root.querySelector("#translation-results"),
  };

  const lineEditor = createTranslationLineEditor({ elements, actions, store });

  function resolveProviderContext(snapshot) {
    const config = snapshot?.config;
    const translation = config?.translation || {};
    const defaultProvider = normalizeProviderName(translation.provider, "google_translate_v2");
    const selectedSlotId = getSelectedSlotId(snapshot);
    const selectedLine = getLineBySlot(config, selectedSlotId, { includeVirtual: true });
    const providerBeingEdited = normalizeProviderName(
      selectedLine?.provider || lineEditor.getManualSettingsProvider() || defaultProvider,
      defaultProvider
    );
    return {
      selectedLine,
      selectedSlotId,
      defaultProvider,
      providerBeingEdited,
    };
  }

  function syncProviderSettingsConfig() {
    const snapshot = store.getState();
    const { providerBeingEdited } = resolveProviderContext(snapshot);
    actions.mutateConfig((draft) => {
      const meta = PROVIDERS[providerBeingEdited];
      const providerSettings = draft.translation.provider_settings[providerBeingEdited] || {};
      setTranslationProviderSettingValue(providerBeingEdited, providerSettings, "api_key", meta.fields.includes("api_key") ? elements.apiKey?.value || "" : "");
      setTranslationProviderSettingValue(providerBeingEdited, providerSettings, "base_url", meta.fields.includes("base_url") ? elements.baseUrl?.value || meta.baseUrlPlaceholder || "" : "");
      setTranslationProviderSettingValue(providerBeingEdited, providerSettings, "gas_url", meta.fields.includes("gas_url") ? elements.gasUrl?.value || "" : "");
      setTranslationProviderSettingValue(providerBeingEdited, providerSettings, "endpoint", meta.fields.includes("endpoint") ? elements.endpoint?.value || meta.endpointPlaceholder || "" : "");
      setTranslationProviderSettingValue(providerBeingEdited, providerSettings, "region", meta.fields.includes("region") ? elements.region?.value || meta.regionPlaceholder || "" : "");
      setTranslationProviderSettingValue(providerBeingEdited, providerSettings, "api_url", meta.fields.includes("api_url") ? elements.apiUrl?.value || meta.apiUrlPlaceholder || "" : "");
      setTranslationProviderSettingValue(providerBeingEdited, providerSettings, "model", meta.fields.includes("model") ? elements.model?.value || "" : "");
      setTranslationProviderSettingValue(providerBeingEdited, providerSettings, "custom_prompt", meta.fields.includes("custom_prompt") ? elements.prompt?.value || "" : "");
      draft.translation.provider_settings[providerBeingEdited] = providerSettings;
    });
  }

  function renderResults(snapshot) {
    if (!elements.results) {
      return;
    }
    const entry = snapshot.translation?.currentEntry;
    const resultsKey = buildTranslationResultsKey(entry);
    if (resultsKey === lastResultsRenderKey) {
      return;
    }
    lastResultsRenderKey = resultsKey;
    renderTranslationResults(elements.results, entry);
  }

  function ensureProviderSelectOptions() {
    const locale = getCurrentLocale();
    const localeChanged = cachedProviderOptionsLocale !== locale;
    const missingOptions =
      (elements.defaultProvider && !elements.defaultProvider.options.length) ||
      (elements.settingsProvider && !elements.settingsProvider.options.length) ||
      (elements.languageSelect && !elements.languageSelect.options.length);
    if (!localeChanged && !missingOptions) {
      return;
    }
    cachedProviderOptionsLocale = locale;
    const providerMarkup = buildProviderOptions();
    if (elements.defaultProvider) {
      setSelectMarkup(elements.defaultProvider, providerMarkup, { selectedValue: elements.defaultProvider.value });
    }
    if (elements.settingsProvider) {
      setSelectMarkup(elements.settingsProvider, providerMarkup, { selectedValue: elements.settingsProvider.value });
    }
    if (elements.languageSelect) {
      fillSelectOptions(elements.languageSelect, LANGUAGES, {
        getValue: (item) => item.code,
        getLabel: (item) => getLanguageLabel(item.code),
        selectedValue: elements.languageSelect.value || "en",
      });
    }
  }

  function render(snapshot) {
    ensureProviderSelectOptions();
    const config = snapshot.config;
    if (!config) {
      renderResults(snapshot);
      return;
    }
    const translation = config.translation || {};
    const { selectedLine, defaultProvider, providerBeingEdited } = resolveProviderContext(snapshot);
    const providerMeta = getProviderMeta(providerBeingEdited);
    const providerSettings = translation.provider_settings?.[providerBeingEdited] || {};

    if (elements.enabled) {
      elements.enabled.checked = Boolean(translation.enabled);
    }
    const cacheConfig = (translation.cache && typeof translation.cache === "object") ? translation.cache : {};
    if (elements.cacheEnabled) {
      elements.cacheEnabled.checked = cacheConfig.enabled !== false;
    }
    if (elements.cachePersist) {
      const cacheEnabled = cacheConfig.enabled !== false;
      elements.cachePersist.checked = cacheConfig.persist !== false;
      elements.cachePersist.disabled = !cacheEnabled;
    }
    if (elements.defaultProvider) {
      elements.defaultProvider.value = defaultProvider;
    }
    if (elements.settingsProvider) {
      elements.settingsProvider.value = providerBeingEdited;
    }
    if (elements.settingsTitle) {
      elements.settingsTitle.textContent = t("translation.provider_settings.for", { provider: providerMeta.label });
    }
    if (elements.providerHint) {
      elements.providerHint.textContent = providerMeta.hint;
    }

    const fieldRows = [
      ["api_key", elements.apiKeyRow, elements.apiKey, elements.apiKeyLabel, "translation.api_key", providerMeta.apiKeyLabel, providerMeta.apiKeyPlaceholder],
      ["base_url", elements.baseUrlRow, elements.baseUrl, elements.baseUrlLabel, "translation.base_url", providerMeta.baseUrlLabel, providerMeta.baseUrlPlaceholder],
      ["gas_url", elements.gasUrlRow, elements.gasUrl, elements.gasUrlLabel, "translation.gas_url", providerMeta.gasUrlLabel, ""],
      ["endpoint", elements.endpointRow, elements.endpoint, elements.endpointLabel, "translation.endpoint", providerMeta.endpointLabel, providerMeta.endpointPlaceholder],
      ["region", elements.regionRow, elements.region, elements.regionLabel, "translation.region", providerMeta.regionLabel, providerMeta.regionPlaceholder],
      ["api_url", elements.apiUrlRow, elements.apiUrl, elements.apiUrlLabel, "translation.provider_url", providerMeta.apiUrlLabel, providerMeta.apiUrlPlaceholder],
      ["model", elements.modelRow, elements.model, elements.modelLabel, "translation.model", providerMeta.modelLabel, providerMeta.modelPlaceholder],
    ];
    fieldRows.forEach(([field, row, input, label, labelKey, overrideLabel, placeholder]) => {
      const visible = providerMeta.fields.includes(field);
      setElementVisibility(row, visible);
      if (label) {
        label.textContent = overrideLabel?.[window.I18n?.getLocale?.() || "en"] || t(labelKey);
      }
      if (input) {
        input.value = getTranslationProviderSettingValue(providerBeingEdited, providerSettings, field);
        input.placeholder = placeholder || t(labelKey);
        input.disabled = !visible;
      }
    });
    setElementVisibility(elements.promptRow, providerMeta.fields.includes("custom_prompt"));
    if (elements.prompt) {
      elements.prompt.value = providerSettings.custom_prompt || "";
      elements.prompt.disabled = !providerMeta.fields.includes("custom_prompt");
      elements.prompt.placeholder = t("translation.custom_prompt");
    }

    const canLoadModels = providerBeingEdited === "openai";
    setElementVisibility(elements.modelLoadBtn, canLoadModels);
    setElementVisibility(elements.modelPickerRow, canLoadModels);
    setElementVisibility(elements.modelStatus, canLoadModels);
    if (elements.modelStatus && canLoadModels && !elements.modelStatus.textContent) {
      elements.modelStatus.textContent = "";
    }
    if (elements.apiKeyToggle) {
      elements.apiKeyToggle.textContent = elements.apiKey?.type === "password" ? t("security.show") : t("security.hide");
    }

    const lineCards = getLineCards(config);
    const enabledLines = lineCards.filter((line) => line.enabled !== false);
    const enabledProviders = Array.from(new Set(enabledLines.map((line) => normalizeProviderName(line.provider, defaultProvider))));
    if (elements.providerStatus) {
      const statusParts = [];
      if (selectedLine?.slot_id) {
        statusParts.push(
          t("translation.provider_settings.scope.selected", {
            line: t("translation.line.title", { number: getSlotNumber(selectedLine.slot_id) }),
            provider: providerMeta.label,
          })
        );
      } else {
        statusParts.push(
          t("translation.provider_settings.scope.default", {
            provider: providerMeta.label,
            defaultProvider: getProviderMeta(defaultProvider).label,
          })
        );
      }
      if (enabledProviders.length) {
        statusParts.push(
          t("translation.providers_in_use", {
            providers: enabledProviders.map((providerName) => getProviderMeta(providerName).label).join(", "),
          })
        );
      }
      elements.providerStatus.textContent = statusParts.join(" ");
    }

    if (elements.settingsWarning) {
      const linesMissingSettings = enabledLines
        .map((line) => ({
          line,
          missingFields: getMissingProviderFields(
            normalizeProviderName(line.provider, defaultProvider),
            translation.provider_settings?.[normalizeProviderName(line.provider, defaultProvider)] || {}
          ),
        }))
        .filter((entry) => entry.missingFields.length);
      setElementVisibility(elements.settingsWarning, linesMissingSettings.length > 0);
      elements.settingsWarning.textContent = linesMissingSettings.length
        ? t("translation.provider_settings.warning")
        : "";
    }

    lineEditor.renderLineEditor(snapshot);
    renderResults(snapshot);
  }

  function applyModelSelectOptions({ showAll } = {}) {
    if (!elements.modelSelect) {
      return;
    }
    const models = Array.isArray(lastLoadedModels) ? lastLoadedModels : [];
    const visible = Boolean(showAll) ? models : models.filter((item) => item?.recommended);
    elements.modelSelect.innerHTML = "";
    visible.forEach((model) => {
      const id = String(model?.id || "").trim();
      if (!id) {
        return;
      }
      const option = document.createElement("option");
      option.value = id;
      option.textContent = id;
      elements.modelSelect.appendChild(option);
    });
    const current = String(elements.model?.value || "").trim();
    if (current) {
      elements.modelSelect.value = current;
    }
  }

  async function loadOpenAiModelsClick() {
    const snapshot = store.getState();
    const { providerBeingEdited } = resolveProviderContext(snapshot);
    if (providerBeingEdited !== "openai") {
      return;
    }
    const requestKey = JSON.stringify([providerBeingEdited, "recommended"]);
    if (requestKey === lastLoadedModelsKey && lastLoadedModels.length) {
      applyModelSelectOptions({ showAll: elements.modelShowAll?.checked });
      if (elements.modelStatus) {
        const count = lastLoadedModels.length;
        elements.modelStatus.textContent =
          getCurrentLocale() === "ru" ? `Моделей загружено: ${count}.` : `Loaded ${count} models.`;
      }
      return;
    }
    if (elements.modelStatus) {
      elements.modelStatus.textContent = getCurrentLocale() === "ru"
        ? "Загрузка рекомендуемого списка..."
        : "Loading recommended list...";
    }
    if (elements.modelSelect) {
      elements.modelSelect.innerHTML = "";
    }
    try {
      const data = await actions.listRecommendedOpenAiModels();
      const ids = Array.isArray(data?.models) ? data.models : [];
      const models = ids.map((id) => ({ id, recommended: true }));
      lastLoadedModelsKey = requestKey;
      lastLoadedModels = models;
      applyModelSelectOptions({ showAll: elements.modelShowAll?.checked });
      if (elements.modelStatus) {
        elements.modelStatus.textContent = getCurrentLocale() === "ru"
          ? `Список загружен: ${models.length} моделей.`
          : `Loaded ${models.length} models.`;
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load models.";
      if (elements.modelStatus) {
        elements.modelStatus.textContent =
          getCurrentLocale() === "ru" ? `Ошибка: ${message}` : `Error: ${message}`;
      }
    }
  }

  elements.enabled?.addEventListener("change", () => {
    actions.mutateConfig((draft) => {
      draft.translation.enabled = Boolean(elements.enabled.checked);
    });
    logger(`[translation] ${elements.enabled.checked ? "enabled" : "disabled"}`);
  });
  elements.cacheEnabled?.addEventListener("change", () => {
    const nextEnabled = Boolean(elements.cacheEnabled.checked);
    actions.mutateConfig((draft) => {
      if (!draft.translation.cache || typeof draft.translation.cache !== "object") {
        draft.translation.cache = { enabled: true, persist: true, max_entries: 5000 };
      }
      draft.translation.cache.enabled = nextEnabled;
    });
    if (elements.cachePersist) {
      elements.cachePersist.disabled = !nextEnabled;
    }
    logger(`[translation] cache ${nextEnabled ? "enabled" : "disabled"}`);
  });
  elements.cachePersist?.addEventListener("change", () => {
    const nextPersist = Boolean(elements.cachePersist.checked);
    actions.mutateConfig((draft) => {
      if (!draft.translation.cache || typeof draft.translation.cache !== "object") {
        draft.translation.cache = { enabled: true, persist: true, max_entries: 5000 };
      }
      draft.translation.cache.persist = nextPersist;
    });
    logger(`[translation] cache persistence ${nextPersist ? "enabled" : "disabled"}`);
  });
  elements.defaultProvider?.addEventListener("change", () => {
    actions.mutateConfig((draft) => {
      draft.translation.provider = normalizeProviderName(elements.defaultProvider.value, draft.translation.provider);
    });
    if (!getSelectedSlotId(store.getState())) {
      lineEditor.setManualSettingsProvider(null);
    }
    logger(`[translation] default provider -> ${elements.defaultProvider.value}`);
  });
  elements.settingsProvider?.addEventListener("change", () => {
    const selectedSlotId = getSelectedSlotId(store.getState());
    if (selectedSlotId) {
      actions.mutateConfig((draft) => {
        const currentLine = ensureLine(draft, selectedSlotId, {
          enabled: false,
          target_lang: "en",
          provider: elements.settingsProvider.value,
          label: "EN",
        });
        currentLine.provider = normalizeProviderName(elements.settingsProvider.value, draft.translation.provider);
      });
      lineEditor.setManualSettingsProvider(null);
      logger(`[translation] ${selectedSlotId} provider -> ${elements.settingsProvider.value}`);
      return;
    }
    lineEditor.setManualSettingsProvider(
      normalizeProviderName(
        elements.settingsProvider.value,
        store.getState().config?.translation?.provider || "google_translate_v2"
      )
    );
    render(store.getState());
    logger(`[translation] settings editor -> ${elements.settingsProvider.value}`);
  });
  [
    elements.apiKey,
    elements.baseUrl,
    elements.gasUrl,
    elements.endpoint,
    elements.region,
    elements.apiUrl,
    elements.model,
    elements.prompt,
  ]
    .filter(Boolean)
    .forEach((element) => element.addEventListener("input", syncProviderSettingsConfig));

  elements.modelLoadBtn?.addEventListener("click", () => {
    loadOpenAiModelsClick();
  });
  elements.modelShowAll?.addEventListener("change", () => {
    applyModelSelectOptions({ showAll: elements.modelShowAll.checked });
  });
  elements.modelSelect?.addEventListener("change", () => {
    if (!elements.model) {
      return;
    }
    elements.model.value = elements.modelSelect.value || "";
    syncProviderSettingsConfig();
  });
  elements.apiKeyToggle?.addEventListener("click", () => {
    if (!elements.apiKey) {
      return;
    }
    elements.apiKey.type = elements.apiKey.type === "password" ? "text" : "password";
    elements.apiKeyToggle.textContent = elements.apiKey.type === "password" ? t("security.show") : t("security.hide");
  });
  elements.addBtn?.addEventListener("click", () => {
    const code = elements.languageSelect?.value || "en";
    let addedSlotId = null;
    actions.mutateConfig((draft) => {
      const lineMap = getLineMap(draft.translation.lines);
      const slotId = CANONICAL_TRANSLATION_SLOTS.find((candidate) => {
        const line = lineMap.get(candidate);
        return !line || line.enabled === false;
      });
      if (!slotId) {
        return;
      }
      const line = ensureLine(draft, slotId, {
        enabled: true,
        target_lang: code,
        provider: draft.translation.provider,
        label: code.toUpperCase(),
      });
      line.enabled = true;
      line.target_lang = code;
      line.provider = normalizeProviderName(line.provider, draft.translation.provider);
      line.label = line.label || code.toUpperCase();
      draft.subtitle_output.display_order = normalizeDisplayOrder([
        ...draft.subtitle_output.display_order,
        slotId,
      ]);
      addedSlotId = slotId;
    });
    if (addedSlotId) {
      actions.updateTranslationSelection(addedSlotId);
      lineEditor.setManualSettingsProvider(null);
      logger(`[translation] added line ${addedSlotId} -> ${code}`);
    }
  });
  elements.removeBtn?.addEventListener("click", () => {
    const selectedSlotId = getSelectedSlotId(store.getState());
    if (!selectedSlotId) {
      return;
    }
    actions.mutateConfig((draft) => {
      draft.translation.lines = (Array.isArray(draft.translation.lines) ? draft.translation.lines : [])
        .filter((line) => String(line?.slot_id || "").toLowerCase() !== selectedSlotId);
      draft.subtitle_output.display_order = draft.subtitle_output.display_order.filter((item) => item !== selectedSlotId);
    });
    actions.updateTranslationSelection(null);
    logger(`[translation] removed line ${selectedSlotId}`);
  });
  render(store.getState());
  const unsubscribe = subscribe(render);
  return () => unsubscribe();
}
