import { PROVIDER_GROUP_I18N_KEYS, PROVIDERS, type ProviderId } from "./constants";
import { t } from "./i18n";
import type { ConfigPayload, LocaleCode, TranslationLine } from "./types";

type ProviderMeta = (typeof PROVIDERS)[ProviderId];

export type ProviderOptionGroup = {
  group: string;
  labelKey: string;
  providers: Array<{ id: ProviderId; label: string }>;
};

export const CANONICAL_TRANSLATION_SLOTS = [
  "translation_1",
  "translation_2",
  "translation_3",
  "translation_4",
  "translation_5",
] as const;

export const REQUIRED_PROVIDER_FIELDS: Partial<Record<ProviderId, readonly string[]>> = {
  google_translate_v2: ["api_key"],
  google_cloud_translation_v3: ["api_key", "endpoint"],
  google_gas_url: ["gas_url"],
  azure_translator: ["api_key", "endpoint"],
  deepl: ["api_key"],
  openai: ["api_key", "model"],
  openrouter: ["api_key", "model"],
  lm_studio: ["base_url", "model"],
  ollama: ["base_url", "model"],
  libretranslate: ["api_url"],
};

export const PROVIDER_SETTING_LABEL_KEYS: Record<string, string> = {
  api_key: "translation.api_key",
  base_url: "translation.base_url",
  gas_url: "translation.gas_url",
  endpoint: "translation.endpoint",
  region: "translation.region",
  api_url: "translation.provider_url",
  model: "translation.model",
  custom_prompt: "translation.custom_prompt",
};

export function normalizeProviderName(name: string | undefined, fallback = "google_translate_v2"): ProviderId {
  const normalized = String(name || fallback).trim() as ProviderId;
  return normalized in PROVIDERS ? normalized : (fallback as ProviderId);
}

export function getProviderSetting(
  provider: string,
  settings: Record<string, unknown>,
  field: string,
): string {
  if (provider === "google_cloud_translation_v3") {
    if (field === "api_key") return String(settings.access_token || "");
    if (field === "endpoint") return String(settings.project_id || "");
    if (field === "region") return String(settings.location || "");
  }
  return String(settings[field] || "");
}

export function setProviderSetting(
  provider: string,
  settings: Record<string, unknown>,
  field: string,
  value: string,
): Record<string, unknown> {
  const next = { ...settings };
  if (provider === "google_cloud_translation_v3") {
    if (field === "api_key") {
      next.access_token = value;
      return next;
    }
    if (field === "endpoint") {
      next.project_id = value;
      return next;
    }
    if (field === "region") {
      next.location = value;
      return next;
    }
  }
  next[field] = value;
  return next;
}

const GOOGLE_V3_FIELD_LABEL_KEYS: Record<string, string> = {
  api_key: "translation.field.google_v3.api_key",
  endpoint: "translation.field.google_v3.endpoint",
  region: "translation.field.google_v3.region",
  model: "translation.field.google_v3.model",
};

export function buildProviderOptionGroups(): ProviderOptionGroup[] {
  const grouped = new Map<string, ProviderOptionGroup>();
  for (const [id, meta] of Object.entries(PROVIDERS) as Array<[ProviderId, ProviderMeta]>) {
    const labelKey = PROVIDER_GROUP_I18N_KEYS[meta.group] || meta.group;
    const existing = grouped.get(meta.group);
    if (existing) {
      existing.providers.push({ id, label: meta.label });
      continue;
    }
    grouped.set(meta.group, {
      group: meta.group,
      labelKey,
      providers: [{ id, label: meta.label }],
    });
  }
  return [...grouped.values()];
}

export function getProviderHintKey(provider: string): string {
  const id = normalizeProviderName(provider);
  return `provider.${id}.hint`;
}

export function getProviderFieldLabel(
  provider: string,
  field: string,
  translate: (key: string) => string,
): string {
  if (provider === "google_cloud_translation_v3" && GOOGLE_V3_FIELD_LABEL_KEYS[field]) {
    return translate(GOOGLE_V3_FIELD_LABEL_KEYS[field]);
  }
  const key = PROVIDER_SETTING_LABEL_KEYS[field];
  return key ? translate(key) : field;
}

export function getEnabledProviderNames(config: ConfigPayload, defaultProvider: string): ProviderId[] {
  const seen = new Set<ProviderId>();
  const names: ProviderId[] = [];
  for (const line of getLineCards(config)) {
    if (!line.enabled) continue;
    const name = normalizeProviderName(line.provider, defaultProvider);
    if (!seen.has(name)) {
      seen.add(name);
      names.push(name);
    }
  }
  return names;
}

export function getLinesWithMissingSettings(config: ConfigPayload, defaultProvider: string) {
  const settingsMap = config.translation?.provider_settings || {};
  return getLineCards(config)
    .filter((line) => line.enabled)
    .map((line) => {
      const providerName = normalizeProviderName(line.provider, defaultProvider);
      const settings = (settingsMap[providerName] || {}) as Record<string, unknown>;
      return {
        line,
        providerName,
        missingFields: getMissingProviderFields(providerName, settings),
      };
    })
    .filter((entry) => entry.missingFields.length > 0);
}

export function getProviderFieldPlaceholder(provider: string, field: string): string {
  const meta = PROVIDERS[normalizeProviderName(provider)] as ProviderMeta;
  if (field === "api_key" && "apiKeyPlaceholder" in meta) return String(meta.apiKeyPlaceholder || "");
  if (field === "endpoint" && "endpointPlaceholder" in meta) return String(meta.endpointPlaceholder || "");
  if (field === "region" && "regionPlaceholder" in meta) return String(meta.regionPlaceholder || "");
  if (field === "model" && "modelPlaceholder" in meta) return String(meta.modelPlaceholder || "");
  if (field === "base_url" && "baseUrlPlaceholder" in meta) return String(meta.baseUrlPlaceholder || "");
  if (field === "api_url" && "apiUrlPlaceholder" in meta) return String(meta.apiUrlPlaceholder || "");
  return "";
}

export function getMissingProviderFields(provider: string, settings: Record<string, unknown>): string[] {
  const required = REQUIRED_PROVIDER_FIELDS[normalizeProviderName(provider)] || [];
  return required.filter((field) => !getProviderSetting(provider, settings, field).trim());
}

export function getLineMap(lines: TranslationLine[] | undefined): Map<string, TranslationLine> {
  const map = new Map<string, TranslationLine>();
  for (const line of lines || []) {
    const slotId = String(line.slot_id || "").toLowerCase();
    if (slotId) map.set(slotId, line);
  }
  return map;
}

export function getSlotNumber(slotId: string): number {
  const match = String(slotId).match(/(\d+)$/);
  return match ? Number.parseInt(match[1], 10) : 0;
}

export function getSlotDisplayLabel(slotId: string, localeCode?: LocaleCode): string {
  const normalized = String(slotId || "").toLowerCase();
  if (CANONICAL_TRANSLATION_SLOTS.includes(normalized as (typeof CANONICAL_TRANSLATION_SLOTS)[number])) {
    return t(`obs.output.${normalized}`, undefined, localeCode);
  }
  return normalized || "";
}

export function getSubtitleSlotLabel(slotId: string, localeCode?: LocaleCode): string {
  const normalized = String(slotId || "").trim().toLowerCase();
  if (normalized === "source") return t("common.source", undefined, localeCode);
  if (/^translation_[1-5]$/.test(normalized)) return t(`obs.output.${normalized}`, undefined, localeCode);
  return normalized || t("common.unknown", undefined, localeCode);
}

function orderedSlots(config: ConfigPayload): string[] {
  const displayOrder = config.subtitle_output?.display_order || [];
  const ordered: string[] = [];
  for (const item of displayOrder) {
    const slotId = String(item || "").toLowerCase();
    if (CANONICAL_TRANSLATION_SLOTS.includes(slotId as (typeof CANONICAL_TRANSLATION_SLOTS)[number]) && !ordered.includes(slotId)) {
      ordered.push(slotId);
    }
  }
  for (const slotId of CANONICAL_TRANSLATION_SLOTS) {
    if (!ordered.includes(slotId)) ordered.push(slotId);
  }
  return ordered;
}

export function getLineCards(config: ConfigPayload): TranslationLine[] {
  const lineMap = getLineMap(config.translation?.lines);
  const configured = [...lineMap.values()].map((line) => String(line.slot_id).toLowerCase());
  const ordered = orderedSlots(config).filter((slotId) => configured.includes(slotId));
  const remaining = configured.filter((slotId) => !ordered.includes(slotId));
  return [...ordered, ...remaining].map((slotId) => lineMap.get(slotId)).filter(Boolean) as TranslationLine[];
}

export function ensureLine(config: ConfigPayload, slotId: string, seed: Partial<TranslationLine> = {}): TranslationLine {
  const lines = config.translation?.lines ? [...config.translation.lines] : [];
  const map = getLineMap(lines);
  const existing = map.get(slotId);
  if (existing) return existing;
  const targetLang = String(seed.target_lang || "en").trim().toLowerCase() || "en";
  const nextLine: TranslationLine = {
    slot_id: slotId,
    enabled: seed.enabled === true,
    target_lang: targetLang,
    provider: normalizeProviderName(seed.provider, config.translation?.provider),
    label: String(seed.label || targetLang.toUpperCase()),
  };
  lines.push(nextLine);
  if (!config.translation) config.translation = {};
  config.translation.lines = lines;
  return nextLine;
}

export function normalizeDisplayOrder(items: string[]): string[] {
  return items
    .map((item) => String(item || "").trim().toLowerCase())
    .filter((item, index, array) => item && array.indexOf(item) === index);
}

export function nextAvailableSlot(config: ConfigPayload): string | null {
  const used = new Set((config.translation?.lines || []).map((line) => String(line.slot_id).toLowerCase()));
  for (const slotId of CANONICAL_TRANSLATION_SLOTS) {
    if (!used.has(slotId)) return slotId;
  }
  return null;
}

export function getDuplicateEnabledTargetLangs(config: ConfigPayload): string[] {
  const seen = new Map<string, number>();
  for (const line of getLineCards(config)) {
    if (!line.enabled) continue;
    const lang = String(line.target_lang || "")
      .trim()
      .toLowerCase();
    if (!lang) continue;
    seen.set(lang, (seen.get(lang) || 0) + 1);
  }
  return [...seen.entries()].filter(([, count]) => count > 1).map(([lang]) => lang);
}

export function getTranslationConfigErrors(
  config: ConfigPayload,
  defaultProvider = "google_translate_v2",
): string[] {
  const errors: string[] = [];
  if (!config.translation?.enabled) {
    return errors;
  }
  const duplicates = getDuplicateEnabledTargetLangs(config);
  if (duplicates.length > 0) {
    errors.push(`duplicate_target:${duplicates.join(",")}`);
  }
  const missing = getLinesWithMissingSettings(config, defaultProvider);
  if (missing.length > 0) {
    const fields = [
      ...new Set(
        missing.flatMap((entry) =>
          entry.missingFields.map((field) => `${entry.providerName}.${field}`),
        ),
      ),
    ];
    errors.push(`missing_provider_fields:${fields.join(";")}`);
  }
  return errors;
}

export function formatTranslationConfigError(
  errorKey: string,
  translate: (key: string, vars?: Record<string, string | number>) => string,
): string {
  if (errorKey.startsWith("duplicate_target:")) {
    const langs = errorKey.slice("duplicate_target:".length);
    return translate("translation.validation.duplicate_target", { langs });
  }
  if (errorKey.startsWith("missing_provider_fields:")) {
    const fields = errorKey.slice("missing_provider_fields:".length);
    return translate("translation.validation.missing_provider_fields", { fields });
  }
  return errorKey;
}
