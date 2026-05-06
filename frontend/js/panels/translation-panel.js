import { subscribe } from "../core/store.js";
import { LANGUAGES, PROVIDERS } from "../dashboard/constants.js";
import { escapeHtml, getCurrentLocale, getLanguageLabel, getProviderMeta, setElementVisibility, t } from "../dashboard/helpers.js";
import { normalizeDisplayOrder } from "../normalizers/translation-normalizer.js";

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

export function mountTranslationPanel(root, { store, actions, logger }) {
  const elements = {
    enabled: root.querySelector("#translation-enabled"),
    provider: root.querySelector("#translation-provider"),
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

  function syncConfigFromControls() {
    actions.mutateConfig((draft) => {
      draft.translation.enabled = Boolean(elements.enabled?.checked);
      const provider = elements.provider?.value && PROVIDERS[elements.provider.value]
        ? elements.provider.value
        : draft.translation.provider;
      draft.translation.provider = provider;
      const meta = PROVIDERS[provider];
      const providerSettings = draft.translation.provider_settings[provider] || {};
      setTranslationProviderSettingValue(provider, providerSettings, "api_key", meta.fields.includes("api_key") ? elements.apiKey?.value || "" : "");
      setTranslationProviderSettingValue(provider, providerSettings, "base_url", meta.fields.includes("base_url") ? elements.baseUrl?.value || meta.baseUrlPlaceholder || "" : "");
      setTranslationProviderSettingValue(provider, providerSettings, "gas_url", meta.fields.includes("gas_url") ? elements.gasUrl?.value || "" : "");
      setTranslationProviderSettingValue(provider, providerSettings, "endpoint", meta.fields.includes("endpoint") ? elements.endpoint?.value || meta.endpointPlaceholder || "" : "");
      setTranslationProviderSettingValue(provider, providerSettings, "region", meta.fields.includes("region") ? elements.region?.value || meta.regionPlaceholder || "" : "");
      setTranslationProviderSettingValue(provider, providerSettings, "api_url", meta.fields.includes("api_url") ? elements.apiUrl?.value || meta.apiUrlPlaceholder || "" : "");
      setTranslationProviderSettingValue(provider, providerSettings, "model", meta.fields.includes("model") ? elements.model?.value || "" : "");
      setTranslationProviderSettingValue(provider, providerSettings, "custom_prompt", meta.fields.includes("custom_prompt") ? elements.prompt?.value || "" : "");
      draft.translation.provider_settings[provider] = providerSettings;
    });
  }

  function renderResults(snapshot) {
    if (!elements.results) {
      return;
    }
    const entry = snapshot.translation?.currentEntry;
    if (!entry) {
      elements.results.innerHTML = `<p class="muted">${escapeHtml(getCurrentLocale() === "ru" ? "Пока нет переведённых результатов." : "No translated results yet.")}</p>`;
      return;
    }
    const translationsHtml = entry.translations.length
      ? entry.translations
          .map((item) => {
            const meta = `${getLanguageLabel(item.target_lang)}${item.cached ? " (cached)" : ""}`;
            const content = item.success
              ? escapeHtml(item.text)
              : `<span class="translation-error">${escapeHtml(item.error || (getCurrentLocale() === "ru" ? "Ошибка перевода." : "Translation failed."))}</span>`;
            return `<p class="label">${escapeHtml(meta)}</p><p>${content}</p>`;
          })
          .join("")
      : `<p class="muted">${escapeHtml(getCurrentLocale() === "ru" ? "Перевод выключен или не настроены целевые языки." : "Translation disabled or no target languages configured.")}</p>`;
    elements.results.innerHTML = `
      <div class="translation-card">
        <h3>${escapeHtml(getCurrentLocale() === "ru" ? `Сегмент ${entry.sequence}` : `Segment ${entry.sequence}`)}</h3>
        <p class="label">${escapeHtml(t("common.source"))}</p>
        <p>${escapeHtml(entry.sourceText)}</p>
        ${entry.providerLabel ? `<p class="label">${escapeHtml(entry.providerLabel)}</p>` : ""}
        ${entry.statusMessage ? `<p class="muted">${escapeHtml(entry.statusMessage)}</p>` : ""}
        ${translationsHtml}
      </div>
    `;
  }

  function render(snapshot) {
    if (elements.provider && !elements.provider.options.length) {
      const groups = {};
      Object.entries(PROVIDERS).forEach(([providerName]) => {
        const meta = getProviderMeta(providerName);
        groups[meta.group] = groups[meta.group] || [];
        groups[meta.group].push({ providerName, meta });
      });
      elements.provider.innerHTML = Object.entries(groups)
        .map(([groupName, items]) => {
          const options = items.map(({ providerName, meta }) => `<option value="${providerName}">${meta.label}</option>`).join("");
          return `<optgroup label="${groupName}">${options}</optgroup>`;
        })
        .join("");
    }
    if (elements.languageSelect && !elements.languageSelect.options.length) {
      elements.languageSelect.innerHTML = LANGUAGES.map((item) => `<option value="${item.code}">${item.label}</option>`).join("");
    }
    const config = snapshot.config;
    if (!config) {
      renderResults(snapshot);
      return;
    }
    const translation = config.translation;
    if (elements.enabled) {
      elements.enabled.checked = translation.enabled;
    }
    if (elements.provider) {
      elements.provider.value = translation.provider;
    }
    const providerMeta = getProviderMeta(translation.provider);
    const providerSettings = translation.provider_settings[translation.provider] || {};
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
      setElementVisibility(row, providerMeta.fields.includes(field));
      if (label) {
        label.textContent = overrideLabel?.[getCurrentLocale()] || t(labelKey);
      }
      if (input) {
        input.value = getTranslationProviderSettingValue(translation.provider, providerSettings, field);
        input.placeholder = placeholder || t(labelKey);
        input.disabled = !providerMeta.fields.includes(field);
      }
    });
    setElementVisibility(elements.promptRow, providerMeta.fields.includes("custom_prompt"));
    if (elements.prompt) {
      elements.prompt.value = providerSettings.custom_prompt || "";
      elements.prompt.disabled = !providerMeta.fields.includes("custom_prompt");
    }
    if (elements.providerHint) {
      elements.providerHint.textContent = providerMeta.hint;
    }
    if (elements.providerStatus) {
      elements.providerStatus.textContent = providerMeta.status;
    }
    if (elements.languageOrder) {
      elements.languageOrder.innerHTML = "";
      translation.target_languages.forEach((code) => {
        const li = document.createElement("li");
        li.dataset.code = code;
        li.textContent = `${getLanguageLabel(code)} (${code})`;
        li.classList.toggle("active", code === snapshot.ui.selectedTranslationLanguage);
        li.addEventListener("click", () => actions.updateTranslationSelection(code));
        elements.languageOrder.appendChild(li);
      });
    }
    renderResults(snapshot);
  }

  elements.enabled?.addEventListener("change", () => {
    syncConfigFromControls();
    logger(`[translation] ${elements.enabled.checked ? "enabled" : "disabled"}`);
  });
  elements.provider?.addEventListener("change", () => {
    syncConfigFromControls();
    logger(`[translation] provider -> ${elements.provider.value}`);
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
    .forEach((element) => element.addEventListener("input", syncConfigFromControls));
  elements.apiKeyToggle?.addEventListener("click", () => {
    if (!elements.apiKey) {
      return;
    }
    elements.apiKey.type = elements.apiKey.type === "password" ? "text" : "password";
    elements.apiKeyToggle.textContent = elements.apiKey.type === "password" ? t("security.show") : t("security.hide");
  });
  elements.addBtn?.addEventListener("click", () => {
    const code = elements.languageSelect?.value;
    if (!code) {
      return;
    }
    actions.mutateConfig((draft) => {
      if (!draft.translation.target_languages.includes(code)) {
        draft.translation.target_languages.push(code);
      }
      draft.targets = [...draft.translation.target_languages];
      draft.subtitle_output.display_order = normalizeDisplayOrder([
        ...draft.subtitle_output.display_order,
        code,
      ]);
      if (!draft.subtitle_output.display_order.includes("source")) {
        draft.subtitle_output.display_order.push("source");
      }
    });
    actions.updateTranslationSelection(code);
    logger(`[translation] added target ${code}`);
  });
  elements.removeBtn?.addEventListener("click", () => {
    const selected = store.getState().ui.selectedTranslationLanguage;
    if (!selected) {
      return;
    }
    actions.mutateConfig((draft) => {
      draft.translation.target_languages = draft.translation.target_languages.filter((item) => item !== selected);
      draft.targets = [...draft.translation.target_languages];
      draft.subtitle_output.display_order = draft.subtitle_output.display_order.filter((item) => item === "source" || draft.translation.target_languages.includes(item));
    });
    logger("[translation] removed target language");
  });
  elements.upBtn?.addEventListener("click", () => {
    const snapshot = store.getState();
    const selected = snapshot.ui.selectedTranslationLanguage;
    if (!selected) {
      return;
    }
    actions.mutateConfig((draft) => {
      const items = draft.translation.target_languages;
      const index = items.indexOf(selected);
      if (index > 0) {
        [items[index - 1], items[index]] = [items[index], items[index - 1]];
      }
    });
    logger("[translation] moved target up");
  });
  elements.downBtn?.addEventListener("click", () => {
    const snapshot = store.getState();
    const selected = snapshot.ui.selectedTranslationLanguage;
    if (!selected) {
      return;
    }
    actions.mutateConfig((draft) => {
      const items = draft.translation.target_languages;
      const index = items.indexOf(selected);
      if (index >= 0 && index < items.length - 1) {
        [items[index + 1], items[index]] = [items[index], items[index + 1]];
      }
    });
    logger("[translation] moved target down");
  });

  render(store.getState());
  const unsubscribe = subscribe(render);
  return () => unsubscribe();
}
