import { subscribe } from "../core/store.js";
import { LANGUAGES, PROVIDERS } from "../dashboard/constants.js";
import { escapeHtml, getCurrentLocale, getLanguageLabel, getProviderMeta, setElementVisibility, t } from "../dashboard/helpers.js";
import { normalizeDisplayOrder } from "../normalizers/translation-normalizer.js";

const CANONICAL_TRANSLATION_SLOTS = ["translation_1", "translation_2", "translation_3", "translation_4", "translation_5"];

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

function getOrderedLines(config) {
  const translation = config?.translation || {};
  const lineMap = getLineMap(translation.lines);
  const displayOrder = Array.isArray(config?.subtitle_output?.display_order) ? config.subtitle_output.display_order : [];
  const ordered = [];
  displayOrder.forEach((item) => {
    const slotId = String(item || "").toLowerCase();
    if (slotId === "source") {
      return;
    }
    const line = lineMap.get(slotId);
    if (line && !ordered.some((entry) => entry.slot_id === slotId)) {
      ordered.push(line);
    }
  });
  CANONICAL_TRANSLATION_SLOTS.forEach((slotId) => {
    const line = lineMap.get(slotId);
    if (line && !ordered.some((entry) => entry.slot_id === slotId)) {
      ordered.push(line);
    }
  });
  return ordered;
}

function getSelectedLine(config, selectedSlotId) {
  return getLineMap(config?.translation?.lines).get(String(selectedSlotId || "").toLowerCase()) || null;
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
      const options = items.map(({ providerName, meta }) => `<option value="${providerName}">${meta.label}</option>`).join("");
      return `<optgroup label="${groupName}">${options}</optgroup>`;
    })
    .join("");
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

  function syncGlobalProviderConfig() {
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
            const providerMeta = item.provider ? getProviderMeta(item.provider) : null;
            const languageLabel = item.label || getLanguageLabel(item.target_lang);
            const slotLabel = item.slot_id ? ` | ${item.slot_id}` : "";
            const providerLabel = providerMeta ? ` | ${providerMeta.label}` : "";
            const meta = `${languageLabel}${slotLabel}${providerLabel}${item.cached ? " (cached)" : ""}`;
            const content = item.success
              ? escapeHtml(item.text)
              : `<span class="translation-error">${escapeHtml(item.error || (getCurrentLocale() === "ru" ? "Ошибка перевода." : "Translation failed."))}</span>`;
            return `<p class="label">${escapeHtml(meta)}</p><p>${content}</p>`;
          })
          .join("")
      : `<p class="muted">${escapeHtml(getCurrentLocale() === "ru" ? "Перевод выключен или не настроены целевые линии." : "Translation disabled or no translation lines configured.")}</p>`;
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

  function renderLineEditor(snapshot) {
    if (!elements.languageOrder) {
      return;
    }
    const config = snapshot.config;
    const selectedSlotId = String(snapshot.ui.selectedTranslationLanguage || "");
    const orderedLines = getOrderedLines(config);
    const providerOptions = buildProviderOptions();

    elements.languageOrder.innerHTML = "";
    orderedLines.forEach((line) => {
      const slotId = String(line.slot_id || "").toLowerCase();
      const row = document.createElement("li");
      row.dataset.code = slotId;
      row.className = "translation-line-row";
      row.classList.toggle("active", slotId === selectedSlotId);
      row.innerHTML = `
        <label class="checkbox-row">
          <input type="checkbox" data-role="enabled" ${line.enabled !== false ? "checked" : ""} />
          <span>${escapeHtml(slotId)}</span>
        </label>
        <select data-role="target_lang">${LANGUAGES.map((item) => `<option value="${item.code}" ${item.code === line.target_lang ? "selected" : ""}>${item.label}</option>`).join("")}</select>
        <select data-role="provider">${providerOptions}</select>
        <input type="text" data-role="label" value="${escapeHtml(line.label || "")}" placeholder="Label" />
      `;
      row.addEventListener("click", () => actions.updateTranslationSelection(slotId));

      const enabledInput = row.querySelector('[data-role="enabled"]');
      const targetLangInput = row.querySelector('[data-role="target_lang"]');
      const providerInput = row.querySelector('[data-role="provider"]');
      const labelInput = row.querySelector('[data-role="label"]');

      if (providerInput) {
        providerInput.value = line.provider || config.translation.provider;
      }

      enabledInput?.addEventListener("change", (event) => {
        event.stopPropagation();
        actions.mutateConfig((draft) => {
          const currentLine = getLineMap(draft.translation.lines).get(slotId);
          if (!currentLine) {
            return;
          }
          currentLine.enabled = Boolean(enabledInput.checked);
          if (currentLine.enabled) {
            if (!draft.subtitle_output.display_order.includes(slotId)) {
              draft.subtitle_output.display_order = normalizeDisplayOrder([
                ...draft.subtitle_output.display_order,
                slotId,
              ]);
            }
          } else {
            draft.subtitle_output.display_order = draft.subtitle_output.display_order.filter((item) => item !== slotId);
          }
        });
      });
      targetLangInput?.addEventListener("change", (event) => {
        event.stopPropagation();
        actions.mutateConfig((draft) => {
          const currentLine = getLineMap(draft.translation.lines).get(slotId);
          if (!currentLine) {
            return;
          }
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
          const currentLine = getLineMap(draft.translation.lines).get(slotId);
          if (currentLine) {
            currentLine.provider = providerInput.value;
          }
        });
      });
      labelInput?.addEventListener("input", (event) => {
        event.stopPropagation();
        actions.mutateConfig((draft) => {
          const currentLine = getLineMap(draft.translation.lines).get(slotId);
          if (currentLine) {
            currentLine.label = String(labelInput.value || "");
          }
        });
      });

      elements.languageOrder.appendChild(row);
    });
  }

  function render(snapshot) {
    if (elements.provider && !elements.provider.options.length) {
      elements.provider.innerHTML = buildProviderOptions();
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
      const usedProviders = Array.from(new Set((translation.lines || []).filter((line) => line.enabled !== false).map((line) => line.provider)));
      elements.providerStatus.textContent = usedProviders.length > 1
        ? `${providerMeta.status} | ${getCurrentLocale() === "ru" ? "Используются провайдеры:" : "Providers in use:"} ${usedProviders.join(", ")}`
        : providerMeta.status;
    }
    renderLineEditor(snapshot);
    renderResults(snapshot);
  }

  elements.enabled?.addEventListener("change", () => {
    syncGlobalProviderConfig();
    logger(`[translation] ${elements.enabled.checked ? "enabled" : "disabled"}`);
  });
  elements.provider?.addEventListener("change", () => {
    syncGlobalProviderConfig();
    logger(`[translation] default provider -> ${elements.provider.value}`);
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
    .forEach((element) => element.addEventListener("input", syncGlobalProviderConfig));
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
      const line = lineMap.get(slotId);
      const nextLine = {
        slot_id: slotId,
        enabled: true,
        target_lang: code,
        provider: draft.translation.provider,
        label: code.toUpperCase(),
      };
      if (line) {
        Object.assign(line, nextLine);
      } else {
        draft.translation.lines.push(nextLine);
      }
      draft.subtitle_output.display_order = normalizeDisplayOrder([
        ...draft.subtitle_output.display_order,
        slotId,
      ]);
      addedSlotId = slotId;
    });
    if (addedSlotId) {
      actions.updateTranslationSelection(addedSlotId);
      logger(`[translation] added line ${addedSlotId} -> ${code}`);
    }
  });
  elements.removeBtn?.addEventListener("click", () => {
    const selectedSlotId = String(store.getState().ui.selectedTranslationLanguage || "").toLowerCase();
    if (!selectedSlotId) {
      return;
    }
    actions.mutateConfig((draft) => {
      const line = getLineMap(draft.translation.lines).get(selectedSlotId);
      if (line) {
        line.enabled = false;
      }
      draft.subtitle_output.display_order = draft.subtitle_output.display_order.filter((item) => item !== selectedSlotId);
    });
    logger(`[translation] disabled line ${selectedSlotId}`);
  });
  elements.upBtn?.addEventListener("click", () => {
    const selectedSlotId = String(store.getState().ui.selectedTranslationLanguage || "").toLowerCase();
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
    const selectedSlotId = String(store.getState().ui.selectedTranslationLanguage || "").toLowerCase();
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
