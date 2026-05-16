import { PROVIDERS } from "../../dashboard/constants.js";
import { escapeHtml, getCurrentLocale, getLanguageLabel, getProviderMeta, t } from "../../dashboard/helpers.js";

export const CANONICAL_TRANSLATION_SLOTS = [
  "translation_1",
  "translation_2",
  "translation_3",
  "translation_4",
  "translation_5",
];

export const REQUIRED_PROVIDER_FIELDS = {
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

export const PROVIDER_SETTING_LABEL_KEYS = {
  api_key: "translation.api_key",
  base_url: "translation.base_url",
  gas_url: "translation.gas_url",
  endpoint: "translation.endpoint",
  region: "translation.region",
  api_url: "translation.provider_url",
  model: "translation.model",
};

export function normalizeProviderName(providerName, fallback = "google_translate_v2") {
  const normalized = String(providerName || fallback).trim();
  return PROVIDERS[normalized] ? normalized : fallback;
}

export function getTranslationProviderSettingValue(providerName, providerSettings, fieldName) {
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

export function setTranslationProviderSettingValue(providerName, targetSettings, fieldName, value) {
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

export function getLineMap(lines) {
  const map = new Map();
  (Array.isArray(lines) ? lines : []).forEach((line) => {
    const slotId = String(line?.slot_id || "").toLowerCase();
    if (slotId) {
      map.set(slotId, line);
    }
  });
  return map;
}

export function getSlotNumber(slotId) {
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

export function getSelectedSlotId(snapshot) {
  return String(snapshot?.ui?.selectedTranslationLanguage || "").toLowerCase();
}

export function getLineBySlot(config, slotId, { includeVirtual = false } = {}) {
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

export function getLineCards(config) {
  const lineMap = getLineMap(config?.translation?.lines);
  const configuredLineSlotIds = Array.from(lineMap.values())
    .filter((line) => line && String(line.slot_id || "").trim())
    .map((line) => String(line.slot_id || "").toLowerCase());
  const ordered = getOrderedSlots(config).filter((slotId) => configuredLineSlotIds.includes(slotId));
  const remaining = configuredLineSlotIds.filter((slotId) => !ordered.includes(slotId));
  return [...ordered, ...remaining].map((slotId) => lineMap.get(slotId)).filter(Boolean);
}

export function getFieldLabel(fieldName) {
  return t(PROVIDER_SETTING_LABEL_KEYS[fieldName] || fieldName);
}

export function getSlotDisplayLabel(slotId) {
  const normalized = String(slotId || "").toLowerCase();
  if (CANONICAL_TRANSLATION_SLOTS.includes(normalized)) {
    return t(`obs.output.${normalized}`);
  }
  return normalized || "";
}

export function getMissingProviderFields(providerName, providerSettings) {
  const requiredFields = REQUIRED_PROVIDER_FIELDS[providerName] || [];
  return requiredFields.filter(
    (fieldName) => !String(getTranslationProviderSettingValue(providerName, providerSettings || {}, fieldName) || "").trim()
  );
}

export function buildProviderOptions() {
  const groups = {};
  Object.entries(PROVIDERS).forEach(([providerName]) => {
    const meta = getProviderMeta(providerName);
    groups[meta.group] = groups[meta.group] || [];
    groups[meta.group].push({ providerName, meta });
  });
  return Object.entries(groups)
    .map(([groupName, items]) => {
      const options = items
        .map(({ providerName, meta }) => `<option value="${providerName}">${escapeHtml(meta.label)}</option>`)
        .join("");
      return `<optgroup label="${escapeHtml(groupName)}">${options}</optgroup>`;
    })
    .join("");
}

export function ensureLine(draft, slotId, seed = {}) {
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

export function computeLineCardsFingerprint(snapshot) {
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
    const missingFields = line.enabled !== false ? getMissingProviderFields(providerName, providerSettings) : [];
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
