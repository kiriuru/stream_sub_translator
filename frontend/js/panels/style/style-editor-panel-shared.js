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

// Built-in presets store a full CSS font-family chain (e.g.
// `"Mochiy Pop One Regular", "Comfortaa Bold", "Segoe UI", sans-serif`) so the
// browser can fall through to a Cyrillic-capable face or to system defaults
// when a project font is missing. The font dropdown, however, exposes one
// entry per registered face (each option's value is a single quoted family
// name). Without this helper the editor would compare the full chain to the
// single-name option values, find no match, and leave the dropdown blank —
// which the user reads as "preset doesn't show which font is selected".
export function extractPrimaryFontFamily(chain) {
  const str = String(chain || "").trim();
  if (!str) {
    return "";
  }
  // Prefer the first quoted name (handles `"Mochiy Pop One Regular", ...`).
  const quoted = str.match(/"([^"]+)"/);
  if (quoted && quoted[1]) {
    return `"${quoted[1].trim()}"`;
  }
  // Fall back to the first comma-separated token (handles unquoted
  // single-name values like `sans-serif`).
  const bare = str.split(",")[0].trim();
  return bare || "";
}

export function isStyleNumberInput(element) {
  return Boolean(element && element.type === "number");
}

export function isStyleColorInput(element) {
  return Boolean(element && element.type === "color");
}

export const STYLE_COLOR_PICKER_OPEN_ATTR = "data-sst-color-picker-open";

export function markStyleColorPickerOpen(element) {
  if (element) {
    element.setAttribute(STYLE_COLOR_PICKER_OPEN_ATTR, "1");
  }
}

export function clearStyleColorPickerOpen(element) {
  if (element) {
    element.removeAttribute(STYLE_COLOR_PICKER_OPEN_ATTR);
  }
}

export function isStyleColorPickerOpen(element) {
  return Boolean(element?.hasAttribute?.(STYLE_COLOR_PICKER_OPEN_ATTR));
}

/** Avoid overwriting controls during in-progress edits (number focus or open color picker). */
export function shouldSkipStyleControlRenderSync(element) {
  if (!element) {
    return false;
  }
  if (isStyleNumberInput(element) && document.activeElement === element) {
    return true;
  }
  if (isStyleColorInput(element) && (document.activeElement === element || isStyleColorPickerOpen(element))) {
    return true;
  }
  return false;
}

export function bindStyleColorPickerEvents(element, add, onApply) {
  if (!element || !isStyleColorInput(element) || typeof add !== "function" || typeof onApply !== "function") {
    return;
  }
  const markOpen = () => markStyleColorPickerOpen(element);
  const applyAndClose = () => {
    onApply();
    clearStyleColorPickerOpen(element);
  };
  add(element, "pointerdown", markOpen);
  add(element, "focus", markOpen);
  add(element, "change", applyAndClose);
  add(element, "blur", () => {
    window.setTimeout(() => {
      if (document.activeElement !== element) {
        clearStyleColorPickerOpen(element);
      }
    }, 200);
  });
}
