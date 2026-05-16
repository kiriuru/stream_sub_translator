import { clearElement } from "../../core/dom.js";
import { LANGUAGES } from "../../dashboard/constants.js";
import { escapeHtml, getLanguageLabel, getProviderMeta, t } from "../../dashboard/helpers.js";
import { normalizeDisplayOrder } from "../../normalizers/translation-normalizer.js";
import {
  buildProviderOptions,
  computeLineCardsFingerprint,
  ensureLine,
  getFieldLabel,
  getLineCards,
  getMissingProviderFields,
  getSelectedSlotId,
  getSlotDisplayLabel,
  getSlotNumber,
  normalizeProviderName,
} from "./translation-panel-shared.js";

function buildLineCardHtml(line, { slotId, lineNumber, providerMeta, missingFields, providerOptions }) {
  const summary = `${String(line.target_lang || "en").toUpperCase()} · ${providerMeta.label}`;
  return `
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
}

export function createTranslationLineEditor({ elements, actions, store, state }) {
  const editorState = state || {
    lastLineCardsFingerprint: "",
    lastSelectedSlotForLines: "",
    manualSettingsProvider: null,
  };

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

  function renderLineEditor(snapshot) {
    if (!elements.languageOrder) {
      return;
    }
    const config = snapshot.config;
    if (!config) {
      return;
    }
    const selectedSlotId = getSelectedSlotId(snapshot);
    const fingerprint = computeLineCardsFingerprint(snapshot);
    const selectionChanged = selectedSlotId !== editorState.lastSelectedSlotForLines;
    if (fingerprint === editorState.lastLineCardsFingerprint && !selectionChanged) {
      updateLineCardActiveState(snapshot);
      return;
    }
    editorState.lastLineCardsFingerprint = fingerprint;
    editorState.lastSelectedSlotForLines = selectedSlotId;

    const translation = config.translation || {};
    const providerOptions = buildProviderOptions();
    clearElement(elements.languageOrder);

    getLineCards(config).forEach((line) => {
      const slotId = String(line.slot_id || "").toLowerCase();
      const lineNumber = getSlotNumber(slotId);
      const providerName = normalizeProviderName(line.provider, translation.provider);
      const providerMeta = getProviderMeta(providerName);
      const providerSettings = translation.provider_settings?.[providerName] || {};
      const missingFields = line.enabled !== false ? getMissingProviderFields(providerName, providerSettings) : [];
      const row = document.createElement("li");
      row.dataset.code = slotId;
      row.className = "translation-line-card";
      row.classList.toggle("active", slotId === selectedSlotId);
      row.innerHTML = buildLineCardHtml(line, { slotId, lineNumber, providerMeta, missingFields, providerOptions });

      row.addEventListener("click", (event) => {
        const target = event?.target;
        if (target instanceof Element && target.closest("select, input, textarea, button, label, a")) {
          return;
        }
        actions.updateTranslationSelection(slotId);
      });

      const enabledInput = row.querySelector('[data-role="enabled"]');
      const targetLangInput = row.querySelector('[data-role="target_lang"]');
      const providerInput = row.querySelector('[data-role="provider"]');
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
            label: String(line.label || targetLangInput?.value || line.target_lang || "en").toUpperCase(),
          });
          currentLine.enabled = Boolean(enabledInput.checked);
          currentLine.target_lang = String(targetLangInput?.value || currentLine.target_lang || "en").toLowerCase();
          currentLine.provider = normalizeProviderName(providerInput?.value || currentLine.provider, draft.translation.provider);
          currentLine.label = String(currentLine.label || currentLine.target_lang.toUpperCase());
          if (currentLine.enabled) {
            draft.subtitle_output.display_order = normalizeDisplayOrder([...draft.subtitle_output.display_order, slotId]);
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
          editorState.manualSettingsProvider = null;
        }
      });

      elements.languageOrder.appendChild(row);
    });
  }

  return {
    renderLineEditor,
    updateLineCardActiveState,
    getManualSettingsProvider: () => editorState.manualSettingsProvider,
    setManualSettingsProvider: (value) => {
      editorState.manualSettingsProvider = value;
    },
  };
}
