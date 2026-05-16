import { subscribe } from "../core/store.js";
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

const CANONICAL_TRANSLATION_SLOTS = ["translation_1", "translation_2", "translation_3", "translation_4", "translation_5"];
const REQUIRED_PROVIDER_FIELDS = {
  google_translate_v2: ["api_key"],
  google_cloud_translation_v3: ["api_key", "endpoint"],
  google_gas_url: ["gas_url"],
  azure_translator: ["api_key", "endpoint"],
  deepl: ["api_key"],
  openai: ["api_key", "model"],
  openrouter: ["api_key", "model"],
  lm_studio: ["base_url", "model"],
  ollama: ["base_url", "model"],
};
const PROVIDER_SETTING_LABEL_KEYS = {
  api_key: "translation.api_key",
  base_url: "translation.base_url",
  gas_url: "translation.gas_url",
  endpoint: "translation.endpoint",
  region: "translation.region",
  api_url: "translation.provider_url",
  model: "translation.model",
};

function normalizeProviderName(providerName, fallback = "google_translate_v2") {
  const normalized = String(providerName || fallback).trim();
  return PROVIDERS[normalized] ? normalized : fallback;
}

function getTranslationProviderSettingValue(providerName, providerSettings, fieldName) {
  if (providerName === "google_cloud_translation_v3") {
    if (fieldName === "api_key") {
      return providerSettings.access_token || "";
    }
    if (fieldName === "endpoint") {
      return providerSettings.project_id || "";
    }
    if (fieldName === "region") {
      return providerSettings.location || "";
    }
  }
  return providerSettings[fieldName] || "";
}

function setTranslationProviderSettingValue(providerName, targetSettings, fieldName, value) {
  if (providerName === "google_cloud_translation_v3") {
    if (fieldName === "api_key") {
      targetSettings.access_token = String(value || "");
      return;
    }
    if (fieldName === "endpoint") {
      targetSettings.project_id = String(value || "");
      return;
    }
    if (fieldName === "region") {
      targetSettings.location = String(value || "");
      return;
    }
  }
  targetSettings[fieldName] = String(value || "");
}

function getLineMap(lines) {
  const map = new Map();
  (Array.isArray(lines) ? lines : []).forEach((line) => {
    const slotId = String(line?.slot_id || "").toLowerCase();
    if (slotId) {
      map.set(slotId, line);
    }
  });
  return map;
}

function getSlotNumber(slotId) {
  const match = String(slotId || "").match(/(\d+)$/);
  return match ? Number.parseInt(match[1], 10) : 0;
}

function getVirtualLine(config, slotId) {
  const defaultProvider = normalizeProviderName(config?.translation?.provider, "google_translate_v2");
  const targetLang = "en";
  return {
    slot_id: slotId,
    enabled: false,
    target_lang: targetLang,
    provider: defaultProvider,
    label: targetLang.toUpperCase(),
  };
}

function getSelectedSlotId(snapshot) {
  return String(snapshot?.ui?.selectedTranslationLanguage || "").trim().toLowerCase();
}

function getLineBySlot(config, slotId, { includeVirtual = false } = {}) {
  if (!slotId) {
    return null;
  }
  const line = getLineMap(config?.translation?.lines).get(slotId);
  if (line) {
    return line;
  }
  return includeVirtual && CANONICAL_TRANSLATION_SLOTS.includes(slotId) ? getVirtualLine(config, slotId) : null;
}

function getOrderedSlots(config) {
  const displayOrder = Array.isArray(config?.subtitle_output?.display_order) ? config.subtitle_output.display_order : [];
  const ordered = [];
  displayOrder.forEach((item) => {
    const slotId = String(item || "").toLowerCase();
    if (CANONICAL_TRANSLATION_SLOTS.includes(slotId) && !ordered.includes(slotId)) {
      ordered.push(slotId);
    }
  });
  CANONICAL_TRANSLATION_SLOTS.forEach((slotId) => {
    if (!ordered.includes(slotId)) {
      ordered.push(slotId);
    }
  });
  return ordered;
}

function getLineCards(config) {
  const lineMap = getLineMap(config?.translation?.lines);
  const configuredLineSlotIds = Array.from(lineMap.values())
    .filter((line) => line && String(line.slot_id || "").trim())
    .map((line) => String(line.slot_id || "").toLowerCase());

  // Only show lines that were explicitly added by the user.
  // Empty slots remain available via the "Add Line" action, but should not render as cards.
  const ordered = getOrderedSlots(config).filter((slotId) => configuredLineSlotIds.includes(slotId));
  const remaining = configuredLineSlotIds.filter((slotId) => !ordered.includes(slotId));
  return [...ordered, ...remaining].map((slotId) => lineMap.get(slotId)).filter(Boolean);
}

function getFieldLabel(fieldName) {
  return t(PROVIDER_SETTING_LABEL_KEYS[fieldName] || fieldName);
}

function getSlotDisplayLabel(slotId) {
  const normalized = String(slotId || "").toLowerCase();
  if (CANONICAL_TRANSLATION_SLOTS.includes(normalized)) {
    return t(`obs.output.${normalized}`);
  }
  return normalized || "";
}

function getMissingProviderFields(providerName, providerSettings) {
  const requiredFields = REQUIRED_PROVIDER_FIELDS[providerName] || [];
  return requiredFields.filter((fieldName) => !String(getTranslationProviderSettingValue(providerName, providerSettings || {}, fieldName) || "").trim());
}

function buildProviderOptions() {
  const groups = {};
  Object.entries(PROVIDERS).forEach(([providerName]) => {
    const meta = getProviderMeta(providerName);
    groups[meta.group] = groups[meta.group] || [];
    groups[meta.group].push({ providerName, meta });
  });
  return Object.entries(groups)
    .map(([groupName, items]) => {
      const options = items.map(({ providerName, meta }) => `<option value="${providerName}">${escapeHtml(meta.label)}</option>`).join("");
      return `<optgroup label="${escapeHtml(groupName)}">${options}</optgroup>`;
    })
    .join("");
}

function ensureLine(draft, slotId, seed = {}) {
  const lineMap = getLineMap(draft.translation.lines);
  const existing = lineMap.get(slotId);
  if (existing) {
    return existing;
  }
  const targetLang = String(seed.target_lang || "en").trim().toLowerCase() || "en";
  const nextLine = {
    slot_id: slotId,
    enabled: seed.enabled === true,
    target_lang: targetLang,
    provider: normalizeProviderName(seed.provider, draft.translation.provider),
    label: String(seed.label || targetLang.toUpperCase()),
  };
  draft.translation.lines.push(nextLine);
  return nextLine;
}

/** Stable key for translation line cards — excludes selected slot (handled separately). */
function computeLineCardsFingerprint(snapshot) {
  const config = snapshot.config;
  if (!config) {
    return "no-config";
  }
  const locale = getCurrentLocale();
  const translation = config.translation || {};
  const lines = getLineCards(config).map((line) => {
    const slotId = String(line.slot_id || "").toLowerCase();
    const providerName = normalizeProviderName(line.provider, translation.provider);
    const providerSettings = translation.provider_settings?.[providerName] || {};
    const missingFields =
      line.enabled !== false ? getMissingProviderFields(providerName, providerSettings) : [];
    return {
      slot_id: slotId,
      enabled: line.enabled !== false,
      target_lang: String(line.target_lang || "").toLowerCase(),
      provider: providerName,
      label: String(line.label || ""),
      missing: missingFields.length,
    };
  });
  const order = Array.isArray(config.subtitle_output?.display_order)
    ? config.subtitle_output.display_order.map((item) => String(item || "").toLowerCase())
    : [];
  return JSON.stringify({ locale, lines, order });
}

export function mountTranslationPanel(root, { store, actions, logger }) {
  let manualSettingsProvider = null;
  let lastLineCardsFingerprint = "";
  let lastSelectedSlotForLines = "";
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

  function resolveProviderContext(snapshot) {
    const config = snapshot?.config;
    const translation = config?.translation || {};
    const defaultProvider = normalizeProviderName(translation.provider, "google_translate_v2");
    const selectedSlotId = getSelectedSlotId(snapshot);
    const selectedLine = getLineBySlot(config, selectedSlotId, { includeVirtual: true });
    const providerBeingEdited = normalizeProviderName(
      selectedLine?.provider || manualSettingsProvider || defaultProvider,
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
    const resultsKey = !entry
      ? "__empty__"
      : JSON.stringify({
          sequence: entry.sequence,
          sourceText: entry.sourceText,
          providerLabel: entry.providerLabel || "",
          statusMessage: entry.statusMessage || "",
          translations: (entry.translations || []).map((item) => ({
            slot_id: item.slot_id,
            target_lang: item.target_lang,
            text: item.text,
            success: item.success,
            error: item.error || "",
            cached: Boolean(item.cached),
            provider: item.provider || "",
          })),
        });
    if (resultsKey === lastResultsRenderKey) {
      return;
    }
    lastResultsRenderKey = resultsKey;
    if (!entry) {
      elements.results.innerHTML = `<p class="muted">${escapeHtml(t("translation.result.empty"))}</p>`;
      return;
    }
    const translationsHtml = entry.translations.length
      ? entry.translations
          .map((item) => {
            const providerMeta = item.provider ? getProviderMeta(item.provider) : null;
            const languageLabel = item.label || getLanguageLabel(item.target_lang);
            const slotLabel = item.slot_id ? ` | ${item.slot_id}` : "";
            const providerLabel = providerMeta ? ` | ${providerMeta.label}` : "";
            const meta = `${languageLabel}${slotLabel}${providerLabel}${item.cached ? ` (${t("translation.result.cached")})` : ""}`;
            const content = item.success
              ? escapeHtml(item.text)
              : `<span class="translation-error">${escapeHtml(item.error || t("translation.result.failed"))}</span>`;
            return `<p class="label">${escapeHtml(meta)}</p><p>${content}</p>`;
          })
          .join("")
      : `<p class="muted">${escapeHtml(t("translation.result.disabled"))}</p>`;
    elements.results.innerHTML = `
      <div class="translation-card">
        <h3>${escapeHtml(t("translation.segment", { sequence: entry.sequence }))}</h3>
        <p class="label">${escapeHtml(t("common.source"))}</p>
        <p>${escapeHtml(entry.sourceText)}</p>
        ${entry.providerLabel ? `<p class="label">${escapeHtml(entry.providerLabel)}</p>` : ""}
        ${entry.statusMessage ? `<p class="muted">${escapeHtml(entry.statusMessage)}</p>` : ""}
        ${translationsHtml}
      </div>
    `;
  }

  function renderLineEditor(snapshot) {
    if (!elements.languageOrder) {
      return;
    }
    const config = snapshot.config;
    const selectedSlotId = getSelectedSlotId(snapshot);
    const translation = config.translation || {};
    const providerOptions = buildProviderOptions();

    elements.languageOrder.innerHTML = "";
    getLineCards(config).forEach((line) => {
      const slotId = String(line.slot_id || "").toLowerCase();
      const lineNumber = getSlotNumber(slotId);
      const providerName = normalizeProviderName(line.provider, translation.provider);
      const providerMeta = getProviderMeta(providerName);
      const providerSettings = translation.provider_settings?.[providerName] || {};
      const missingFields = line.enabled !== false ? getMissingProviderFields(providerName, providerSettings) : [];
      const summary = `${String(line.target_lang || "en").toUpperCase()} · ${providerMeta.label}`;
      const row = document.createElement("li");
      row.dataset.code = slotId;
      row.className = "translation-line-card";
      row.classList.toggle("active", slotId === selectedSlotId);
      row.innerHTML = `
        <div class="translation-line-head">
          <div class="translation-line-title-block">
            <div class="translation-line-title-row">
              <strong class="translation-line-title">${escapeHtml(t("translation.line.title", { number: lineNumber }))}</strong>
              <span class="translation-line-slot">${escapeHtml(getSlotDisplayLabel(slotId))}</span>
            </div>
            <p class="translation-line-summary">${escapeHtml(summary)}</p>
          </div>
          <div class="translation-line-badges">
            <span class="translation-line-badge" data-tone="${line.enabled !== false ? "ready" : "muted"}">${escapeHtml(line.enabled !== false ? t("translation.line.state.enabled") : t("translation.line.state.disabled"))}</span>
            ${missingFields.length ? `<span class="translation-line-badge" data-tone="warn">${escapeHtml(t("translation.line.missing_settings.short"))}</span>` : ""}
          </div>
        </div>
        <label class="checkbox-row translation-line-enabled">
          <input type="checkbox" data-role="enabled" ${line.enabled !== false ? "checked" : ""} />
          <span>${escapeHtml(t("translation.line.enabled"))}</span>
        </label>
        <div class="translation-line-fields">
          <label class="stack-field">
            <span>${escapeHtml(t("translation.line.target_lang"))}</span>
            <select data-role="target_lang">
              ${LANGUAGES.map((item) => `<option value="${item.code}" ${item.code === line.target_lang ? "selected" : ""}>${escapeHtml(getLanguageLabel(item.code))}</option>`).join("")}
            </select>
          </label>
          <label class="stack-field">
            <span>${escapeHtml(t("translation.line.provider"))}</span>
            <select data-role="provider">${providerOptions}</select>
          </label>
        </div>
        ${missingFields.length ? `<p class="muted translation-line-note">${escapeHtml(t("translation.line.missing_settings", { fields: missingFields.map(getFieldLabel).join(", ") }))}</p>` : ""}
      `;
      row.addEventListener("click", (event) => {
        const target = event?.target;
        if (target instanceof Element) {
          const interactive = target.closest("select, input, textarea, button, label, a");
          if (interactive) {
            return;
          }
        }
        actions.updateTranslationSelection(slotId);
      });

      const enabledInput = row.querySelector('[data-role="enabled"]');
      const targetLangInput = row.querySelector('[data-role="target_lang"]');
      const providerInput = row.querySelector('[data-role="provider"]');
      const labelInput = null;

      if (providerInput) {
        providerInput.value = providerName;
      }

      enabledInput?.addEventListener("change", (event) => {
        event.stopPropagation();
        actions.mutateConfig((draft) => {
          const currentLine = ensureLine(draft, slotId, {
            enabled: false,
            target_lang: targetLangInput?.value || line.target_lang || "en",
            provider: providerInput?.value || providerName,
            label: String((line.label || targetLangInput?.value || line.target_lang || "en")).toUpperCase(),
          });
          currentLine.enabled = Boolean(enabledInput.checked);
          currentLine.target_lang = String(targetLangInput?.value || currentLine.target_lang || "en").toLowerCase();
          currentLine.provider = normalizeProviderName(providerInput?.value || currentLine.provider, draft.translation.provider);
          currentLine.label = String(currentLine.label || currentLine.target_lang.toUpperCase());
          if (currentLine.enabled) {
            draft.subtitle_output.display_order = normalizeDisplayOrder([
              ...draft.subtitle_output.display_order,
              slotId,
            ]);
          } else {
            draft.subtitle_output.display_order = draft.subtitle_output.display_order.filter((item) => item !== slotId);
          }
        });
        actions.updateTranslationSelection(slotId);
      });
      targetLangInput?.addEventListener("change", (event) => {
        event.stopPropagation();
        actions.mutateConfig((draft) => {
          const currentLine = ensureLine(draft, slotId, {
            enabled: Boolean(enabledInput?.checked),
            target_lang: targetLangInput.value || "en",
            provider: providerInput?.value || providerName,
            label: String(line.label || targetLangInput.value || "en").toUpperCase(),
          });
          const previousTarget = String(currentLine.target_lang || "").toUpperCase();
          currentLine.target_lang = String(targetLangInput.value || "en").toLowerCase();
          if (!String(currentLine.label || "").trim() || String(currentLine.label).trim().toUpperCase() === previousTarget) {
            currentLine.label = currentLine.target_lang.toUpperCase();
          }
        });
      });
      providerInput?.addEventListener("change", (event) => {
        event.stopPropagation();
        actions.mutateConfig((draft) => {
          const currentLine = ensureLine(draft, slotId, {
            enabled: Boolean(enabledInput?.checked),
            target_lang: targetLangInput?.value || line.target_lang || "en",
            provider: providerInput.value,
            label: String(line.label || targetLangInput?.value || line.target_lang || "en").toUpperCase(),
          });
          currentLine.provider = normalizeProviderName(providerInput.value, draft.translation.provider);
        });
        if (slotId === getSelectedSlotId(store.getState())) {
          manualSettingsProvider = null;
        }
      });
      // Note: line label is still supported in config/backend, but hidden in the UI for now.

      elements.languageOrder.appendChild(row);
    });
  }

  function updateLineCardActiveState(snapshot) {
    if (!elements.languageOrder) {
      return;
    }
    const selectedSlotId = getSelectedSlotId(snapshot);
    elements.languageOrder.querySelectorAll(".translation-line-card").forEach((row) => {
      if (!(row instanceof HTMLElement)) {
        return;
      }
      const code = String(row.dataset.code || "").toLowerCase();
      row.classList.toggle("active", code === selectedSlotId);
    });
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
      elements.defaultProvider.innerHTML = providerMarkup;
    }
    if (elements.settingsProvider) {
      elements.settingsProvider.innerHTML = providerMarkup;
    }
    if (elements.languageSelect) {
      const preserved = elements.languageSelect.value || "en";
      elements.languageSelect.innerHTML = LANGUAGES.map(
        (item) => `<option value="${item.code}">${escapeHtml(getLanguageLabel(item.code))}</option>`
      ).join("");
      elements.languageSelect.value = preserved;
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

    const cardsKey = computeLineCardsFingerprint(snapshot);
    const selectedSlotId = getSelectedSlotId(snapshot);
    if (cardsKey !== lastLineCardsFingerprint) {
      renderLineEditor(snapshot);
      lastLineCardsFingerprint = cardsKey;
      lastSelectedSlotForLines = selectedSlotId;
    } else if (selectedSlotId !== lastSelectedSlotForLines) {
      updateLineCardActiveState(snapshot);
      lastSelectedSlotForLines = selectedSlotId;
    }
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
      manualSettingsProvider = null;
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
      manualSettingsProvider = null;
      logger(`[translation] ${selectedSlotId} provider -> ${elements.settingsProvider.value}`);
      return;
    }
    manualSettingsProvider = normalizeProviderName(elements.settingsProvider.value, store.getState().config?.translation?.provider || "google_translate_v2");
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
      manualSettingsProvider = null;
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
