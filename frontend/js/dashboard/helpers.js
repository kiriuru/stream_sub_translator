import {
  BROWSER_RECOGNITION_LANGUAGES,
  BROWSER_RECOGNITION_LABELS,
  LANGUAGES,
  LANGUAGE_LABELS,
  PROVIDERS,
  PROVIDER_GROUP_KEYS,
  SIMPLE_TUNING_LABELS,
  SIMPLE_TUNING_OPTIONS,
} from "./constants.js";

export function clone(value) {
  if (typeof structuredClone === "function") {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
}

export function t(key, variables) {
  if (window.I18n?.t) {
    return window.I18n.t(key, variables);
  }
  const fallback = String(key || "")
    .split(".")
    .pop()
    .replace(/[_-]+/g, " ")
    .trim();
  if (!fallback) {
    return "";
  }
  return fallback.charAt(0).toUpperCase() + fallback.slice(1);
}

export function getCurrentLocale() {
  return window.I18n?.getLocale?.() || "en";
}

export function normalizeSupportedUiLanguage(value) {
  const current = String(value || "").trim().toLowerCase();
  return ["en", "ru"].includes(current) ? current : "en";
}

export function parseIntegerOr(value, fallback) {
  const parsed = Number.parseInt(String(value), 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function parseFloatOr(value, fallback) {
  const parsed = Number.parseFloat(String(value));
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function localizePair(map, key, fallback) {
  const locale = getCurrentLocale();
  return map?.[key]?.[locale] || map?.[key]?.en || fallback;
}

export function getLanguageLabel(code) {
  const item = LANGUAGES.find((entry) => entry.code === code);
  return localizePair(LANGUAGE_LABELS, code, item?.label || code);
}

export function getSubtitleSlotLabel(slotId) {
  const normalized = String(slotId || "").trim().toLowerCase();
  if (normalized === "source") {
    return t("common.source");
  }
  if (/^translation_[1-5]$/.test(normalized)) {
    return t(`obs.output.${normalized}`);
  }
  return normalized || t("common.unknown");
}

export function getRecognitionLanguageLabel(code) {
  const item = BROWSER_RECOGNITION_LANGUAGES.find((entry) => entry.code === code);
  return localizePair(BROWSER_RECOGNITION_LABELS, code, item?.label || code);
}

export function getProviderMeta(providerName) {
  const resolvedProviderName = PROVIDERS[providerName] ? providerName : "google_translate_v2";
  const current = PROVIDERS[resolvedProviderName];
  const locale = getCurrentLocale();
  return {
    ...current,
    group: PROVIDER_GROUP_KEYS[current.group]?.[locale] || current.group,
    hint: t(`provider.${resolvedProviderName}.hint`),
    status: t(`provider.${resolvedProviderName}.status`),
  };
}

export function getRecognitionModeLabel(mode) {
  if (mode === "browser_google") {
    return getCurrentLocale() === "ru" ? "Браузерное распознавание" : "Browser Speech";
  }
  if (mode === "browser_google_experimental") {
    return getCurrentLocale() === "ru" ? "Браузерное (Experimental)" : "Browser Speech (Experimental)";
  }
  return getCurrentLocale() === "ru" ? "Локальный Parakeet" : "Local Parakeet";
}

export function isBrowserRecognitionMode(mode) {
  return ["browser_google", "browser_google_experimental"].includes(String(mode || "").toLowerCase());
}

export function isExperimentalBrowserRecognitionMode(mode) {
  return String(mode || "").toLowerCase() === "browser_google_experimental";
}

export function setElementVisibility(element, visible) {
  if (!element) {
    return;
  }
  element.hidden = !visible;
  element.classList.toggle("is-hidden", !visible);
  element.style.display = visible ? "" : "none";
}

export function clampSimpleLevel(value) {
  return Math.max(1, Math.min(5, parseIntegerOr(value, 3)));
}

export function getSimpleTuningOption(kind, level) {
  return SIMPLE_TUNING_OPTIONS[kind][clampSimpleLevel(level) - 1];
}

export function findClosestSimpleLevel(kind, currentValues) {
  const entries = SIMPLE_TUNING_OPTIONS[kind];
  let bestLevel = 3;
  let bestScore = Number.POSITIVE_INFINITY;
  entries.forEach((option, index) => {
    const score = Object.entries(option)
      .filter(([key]) => key !== "label")
      .reduce((sum, [key, value]) => sum + Math.abs(Number(currentValues[key] ?? 0) - Number(value)), 0);
    if (score < bestScore) {
      bestScore = score;
      bestLevel = index + 1;
    }
  });
  return bestLevel;
}

export function getSimpleTuningLabel(kind, label) {
  return localizePair(SIMPLE_TUNING_LABELS[kind], label, label);
}

export function formatMetric(value) {
  return typeof value === "number" ? `${value.toFixed(1)} ms` : "n/a";
}

export function formatOptionalMetric(value) {
  return typeof value === "number"
    ? `${Number(value).toFixed(1)} ms`
    : (getCurrentLocale() === "ru" ? "нет данных" : "not available");
}

export function formatSecondsFromMs(value, fallbackMs) {
  const ms = Math.max(0, parseIntegerOr(value ?? fallbackMs, fallbackMs));
  return (ms / 1000).toFixed(1);
}

export function parseSecondsToMs(value, fallbackMs, minimumMs) {
  const seconds = parseFloatOr(value ?? String(fallbackMs / 1000), fallbackMs / 1000);
  return Math.max(minimumMs, Math.round(seconds * 1000));
}

export function formatList(items) {
  if (!items.length) {
    return "";
  }
  if (items.length === 1) {
    return items[0];
  }
  if (items.length === 2) {
    return getCurrentLocale() === "ru" ? `${items[0]} и ${items[1]}` : `${items[0]} and ${items[1]}`;
  }
  return getCurrentLocale() === "ru"
    ? `${items.slice(0, -1).join(", ")} и ${items[items.length - 1]}`
    : `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

export function appendTextLog(target, message) {
  if (!target) {
    return;
  }
  if ("value" in target) {
    target.value += `${message}\n`;
  } else {
    target.textContent += `${message}\n`;
  }
  target.scrollTop = target.scrollHeight;
}

const UI_STATUSES = new Set(["ready", "running", "disabled", "warning", "error", "degraded", "loading", "unknown"]);

export function normalizeUiStatus(value, fallback = "unknown") {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return fallback;
  }
  if (UI_STATUSES.has(normalized)) {
    return normalized;
  }
  if (normalized === "ok" || normalized === "healthy") {
    return "ready";
  }
  if (normalized === "active" || normalized === "enabled" || normalized === "listening" || normalized === "transcribing" || normalized === "translating") {
    return "running";
  }
  if (normalized === "starting" || normalized === "pending") {
    return "loading";
  }
  if (normalized === "partial") {
    return "warning";
  }
  if (normalized === "experimental") {
    return "degraded";
  }
  if (normalized === "idle") {
    return "ready";
  }
  return fallback;
}

export function resolveRuntimeUiStatus(runtime) {
  const current = runtime && typeof runtime === "object" ? runtime : {};
  if (current.last_error || current.status === "error") {
    return "error";
  }
  if (current.status === "starting") {
    return "loading";
  }
  if (current.is_running === true) {
    return "running";
  }
  return normalizeUiStatus(current.status, "ready");
}

export function applyStatusDataset(element, status) {
  if (!element) {
    return;
  }
  element.dataset.status = normalizeUiStatus(status, "unknown");
}
