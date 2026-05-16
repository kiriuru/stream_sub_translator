import { setHtmlFromTemplate } from "../../core/dom.js";
import { escapeHtml, getLanguageLabel, getProviderMeta, t } from "../../dashboard/helpers.js";

export function buildTranslationResultsKey(entry) {
  if (!entry) {
    return "__empty__";
  }
  return JSON.stringify({
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
}

export function renderTranslationResults(container, entry) {
  if (!container) {
    return;
  }
  if (!entry) {
    setHtmlFromTemplate(container, `<p class="muted">${escapeHtml(t("translation.result.empty"))}</p>`);
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
  setHtmlFromTemplate(
    container,
    [
      '<div class="translation-card">',
      `<h3>${escapeHtml(t("translation.segment", { sequence: entry.sequence }))}</h3>`,
      `<p class="label">${escapeHtml(t("common.source"))}</p>`,
      `<p>${escapeHtml(entry.sourceText)}</p>`,
      entry.providerLabel ? `<p class="label">${escapeHtml(entry.providerLabel)}</p>` : "",
      entry.statusMessage ? `<p class="muted">${escapeHtml(entry.statusMessage)}</p>` : "",
      translationsHtml,
      "</div>",
    ].join("")
  );
}
