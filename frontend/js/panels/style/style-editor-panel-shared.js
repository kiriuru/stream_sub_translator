import { fillSelectOptions } from "../../core/dom.js";
import { getCurrentLocale, t } from "../../dashboard/helpers.js";

export const FALLBACK_LINE_SLOTS = [
  "source",
  "translation_1",
  "translation_2",
  "translation_3",
  "translation_4",
  "translation_5",
];

export function getUiThemePresets() {
  return [
    {
      id: "custom",
      label: () => (getCurrentLocale() === "ru" ? "Пользовательский" : "Custom"),
      theme: null,
      palette: null,
    },
    {
      id: "ocean",
      label: () => (getCurrentLocale() === "ru" ? "Океан" : "Ocean"),
      theme: "dark",
      palette: { accent: "#6cc7ff", accent_secondary: "#4fe3ff", accent_tertiary: "#7ce3ad" },
    },
    {
      id: "neon",
      label: () => (getCurrentLocale() === "ru" ? "Неон" : "Neon"),
      theme: "dark",
      palette: { accent: "#8bddff", accent_secondary: "#ff6ce6", accent_tertiary: "#ffd166" },
    },
    {
      id: "sunset",
      label: () => (getCurrentLocale() === "ru" ? "Закат" : "Sunset"),
      theme: "dark",
      palette: { accent: "#ffb703", accent_secondary: "#ff5c7a", accent_tertiary: "#6cc7ff" },
    },
    {
      id: "paper",
      label: () => (getCurrentLocale() === "ru" ? "Бумага" : "Paper"),
      theme: "light",
      palette: { accent: "#2563eb", accent_secondary: "#db2777", accent_tertiary: "#059669" },
    },
  ];
}

export function normalizeStyle(config, presets) {
  return window.SubtitleStyleRenderer
    ? window.SubtitleStyleRenderer.normalizeStyleConfig(config || {}, presets || {})
    : config || {};
}

export function buildStyleFromPreset(presets, presetName) {
  return window.SubtitleStyleRenderer
    ? window.SubtitleStyleRenderer.buildStyleFromPreset(presets || {}, presetName)
    : {};
}

export function getLineSlotNames() {
  if (window.SubtitleStyleRenderer?.LINE_SLOT_NAMES?.length) {
    return window.SubtitleStyleRenderer.LINE_SLOT_NAMES.slice();
  }
  return FALLBACK_LINE_SLOTS.slice();
}

export function buildFontCatalogSignature(fontCatalog) {
  const entries = [];
  if (fontCatalog?.project_local?.length) {
    entries.push(...fontCatalog.project_local.map((item) => item?.id || item?.label || ""));
  }
  if (fontCatalog?.system?.length) {
    entries.push(...fontCatalog.system.map((item) => item?.id || item?.label || ""));
  }
  if (fontCatalog?.fallback?.length) {
    entries.push(...fontCatalog.fallback.map((item) => item?.id || item?.label || ""));
  }
  return entries.join("|");
}

export function buildPresetCatalogSignature(presets) {
  const catalog = presets && typeof presets === "object" ? presets : {};
  return Object.keys(catalog).sort().join("|");
}

export function setSelectOptions(select, options) {
  fillSelectOptions(select, options, {
    getValue: (optionConfig) => optionConfig.value,
    getLabel: (optionConfig) => optionConfig.label,
    selectedValue: select?.value,
  });
}

export function styleSlotLabel(slotName) {
  const normalized = String(slotName || "").trim().toLowerCase();
  if (normalized === "source") {
    return t("common.source");
  }
  if (/^translation_[1-5]$/.test(normalized)) {
    return t(`obs.output.${normalized}`);
  }
  return slotName;
}

export function inheritLabel() {
  return t("style.slots.inherit_base");
}

export function normalizeOverrideFieldValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (value === "null") {
    return "";
  }
  return String(value);
}

export function isStyleNumberInput(element) {
  return Boolean(element && element.type === "number");
}
