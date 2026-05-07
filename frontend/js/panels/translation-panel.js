import { subscribe } from "../core/store.js";
import { LANGUAGES, PROVIDERS } from "../dashboard/constants.js";
import {
  escapeHtml,
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
  return getOrderedSlots(config).map((slotId) => lineMap.get(slotId) || getVirtualLine(config, slotId));
}

function getFieldLabel(fieldName) {
  return t(PROVIDER_SETTING_LABEL_KEYS[fieldName] || fieldName);
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

export function mountTranslationPanel(root, { store, actions, logger }) {
  let manualSettingsProvider = null;

  const elements = {
    enabled: root.querySelector("#translation-enabled"),
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
    prompt: root.querySelector("#translation-custom-prompt"),
    promptRow: root.querySelector("#translation-prompt-row"),
    providerHint: root.querySelector("#translation-provider-hint"),
    providerStatus: root.querySelector("#translation-provider-status"),
    languageSelect: root.querySelector("#translation-language-select"),
    languageOrder: root.querySelector("#translation-language-order"),
    addBtn: root.querySelector("#translation-lang-add-btn"),
    removeBtn: root.querySelector("#translation-lang-remove-btn"),
    upBtn: root.querySelector("#translation-lang-up-btn"),
    downBtn: root.querySelector("#translation-lang-down-btn"),
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
              <span class="translation-line-slot">${escapeHtml(slotId)}</span>
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
          <label class="stack-field">
            <span>${escapeHtml(t("translation.line.label"))}</span>
            <input type="text" data-role="label" value="${escapeHtml(line.label || "")}" placeholder="${escapeHtml(t("translation.line.label.placeholder"))}" />
          </label>
        </div>
        ${missingFields.length ? `<p class="muted translation-line-note">${escapeHtml(t("translation.line.missing_settings", { fields: missingFields.map(getFieldLabel).join(", ") }))}</p>` : ""}
      `;
      row.addEventListener("click", () => {
        actions.updateTranslationSelection(slotId);
      });

      const enabledInput = row.querySelector('[data-role="enabled"]');
      const targetLangInput = row.querySelector('[data-role="target_lang"]');
      const providerInput = row.querySelector('[data-role="provider"]');
      const labelInput = row.querySelector('[data-role="label"]');

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
            label: labelInput?.value || String(targetLangInput?.value || line.target_lang || "en").toUpperCase(),
          });
          currentLine.enabled = Boolean(enabledInput.checked);
          currentLine.target_lang = String(targetLangInput?.value || currentLine.target_lang || "en").toLowerCase();
          currentLine.provider = normalizeProviderName(providerInput?.value || currentLine.provider, draft.translation.provider);
          currentLine.label = String(labelInput?.value || currentLine.label || currentLine.target_lang.toUpperCase());
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
            label: labelInput?.value || String(targetLangInput.value || "en").toUpperCase(),
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
            label: labelInput?.value || String(targetLangInput?.value || line.target_lang || "en").toUpperCase(),
          });
          currentLine.provider = normalizeProviderName(providerInput.value, draft.translation.provider);
        });
        if (slotId === getSelectedSlotId(store.getState())) {
          manualSettingsProvider = null;
        }
      });
      labelInput?.addEventListener("change", (event) => {
        event.stopPropagation();
        actions.mutateConfig((draft) => {
          const currentLine = ensureLine(draft, slotId, {
            enabled: Boolean(enabledInput?.checked),
            target_lang: targetLangInput?.value || line.target_lang || "en",
            provider: providerInput?.value || providerName,
            label: labelInput.value,
          });
          currentLine.label = String(labelInput.value || "");
        });
      });

      elements.languageOrder.appendChild(row);
    });
  }

  function render(snapshot) {
    if (elements.defaultProvider) {
      elements.defaultProvider.innerHTML = buildProviderOptions();
    }
    if (elements.settingsProvider) {
      elements.settingsProvider.innerHTML = buildProviderOptions();
    }
    if (elements.languageSelect) {
      const currentLanguage = elements.languageSelect.value || "en";
      elements.languageSelect.innerHTML = LANGUAGES.map((item) => `<option value="${item.code}">${escapeHtml(getLanguageLabel(item.code))}</option>`).join("");
      elements.languageSelect.value = currentLanguage;
    }
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

    renderLineEditor(snapshot);
    renderResults(snapshot);
  }

  elements.enabled?.addEventListener("change", () => {
    actions.mutateConfig((draft) => {
      draft.translation.enabled = Boolean(elements.enabled.checked);
    });
    logger(`[translation] ${elements.enabled.checked ? "enabled" : "disabled"}`);
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
      const line = ensureLine(draft, selectedSlotId, {
        enabled: false,
        target_lang: "en",
        provider: draft.translation.provider,
        label: "EN",
      });
      line.enabled = false;
      draft.subtitle_output.display_order = draft.subtitle_output.display_order.filter((item) => item !== selectedSlotId);
    });
    logger(`[translation] disabled line ${selectedSlotId}`);
  });
  elements.upBtn?.addEventListener("click", () => {
    const selectedSlotId = getSelectedSlotId(store.getState());
    if (!selectedSlotId) {
      return;
    }
    actions.mutateConfig((draft) => {
      const order = Array.isArray(draft.subtitle_output.display_order) ? draft.subtitle_output.display_order : [];
      const index = order.indexOf(selectedSlotId);
      if (index > 0) {
        [order[index - 1], order[index]] = [order[index], order[index - 1]];
      }
    });
    logger(`[translation] moved line up ${selectedSlotId}`);
  });
  elements.downBtn?.addEventListener("click", () => {
    const selectedSlotId = getSelectedSlotId(store.getState());
    if (!selectedSlotId) {
      return;
    }
    actions.mutateConfig((draft) => {
      const order = Array.isArray(draft.subtitle_output.display_order) ? draft.subtitle_output.display_order : [];
      const index = order.indexOf(selectedSlotId);
      if (index >= 0 && index < order.length - 1) {
        [order[index + 1], order[index]] = [order[index], order[index + 1]];
      }
    });
    logger(`[translation] moved line down ${selectedSlotId}`);
  });

  render(store.getState());
  const unsubscribe = subscribe(render);
  return () => unsubscribe();
}
