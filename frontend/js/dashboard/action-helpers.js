import { normalizeConfigShape } from "../normalizers/config-normalizer.js";
import { formatList, t } from "./helpers.js";

export const BROWSER_WORKER_SETTINGS_STORAGE_KEY = "sst.browser_worker.settings.v1";
export const BROWSER_WORKER_EXPERIMENTAL_SETTINGS_STORAGE_KEY = "sst.browser_worker.experimental.settings.v1";

// System fonts come from the browser's Local Font Access API, not the backend.
// When we merge a fresh server `font_catalog` into the store after save/reload
// we have to preserve any system entries the user has already enumerated, or
// they vanish from the selector and the previously chosen value can't be
// re-resolved (#fonts-system-bug).
export function mergeFontCatalogPreservingSystem(serverCatalog, currentCatalog) {
  const fallback = currentCatalog && typeof currentCatalog === "object" ? currentCatalog : {};
  if (!serverCatalog || typeof serverCatalog !== "object") {
    return fallback;
  }
  const systemFromServer = Array.isArray(serverCatalog.system) ? serverCatalog.system : null;
  const systemFromCurrent = Array.isArray(fallback.system) ? fallback.system : [];
  return {
    ...serverCatalog,
    system: systemFromServer && systemFromServer.length ? systemFromServer : systemFromCurrent,
  };
}

export function mirrorBrowserWorkerSettingsToLocalStorage(savedPayload) {
  try {
    const mode = String(savedPayload?.asr?.mode || "local");
    const browser = savedPayload?.asr?.browser;
    if (!browser || typeof browser !== "object") {
      return;
    }
    const mirror = {
      recognition_language: String(browser.recognition_language || "ru-RU"),
      interim_results: browser.interim_results !== false,
      continuous_results: browser.continuous_results !== false,
      force_finalization_enabled: browser.force_finalization_enabled !== false,
      force_finalization_timeout_ms: Math.max(300, Number(browser.force_finalization_timeout_ms) || 1600),
    };
    const raw = JSON.stringify(mirror);
    if (mode === "browser_google") {
      window.localStorage.setItem(BROWSER_WORKER_SETTINGS_STORAGE_KEY, raw);
    } else if (mode === "browser_google_experimental") {
      window.localStorage.setItem(BROWSER_WORKER_EXPERIMENTAL_SETTINGS_STORAGE_KEY, raw);
    }
  } catch (_error) {
    // best-effort
  }
}

export function getRestartRequiredReasons(previousPayload, nextPayload) {
  const reasons = [];
  if ((previousPayload?.audio?.input_device_id ?? null) !== (nextPayload?.audio?.input_device_id ?? null)) {
    reasons.push(t("config.restart_reason.microphone"));
  }
  if (String(previousPayload?.asr?.mode || "local") !== String(nextPayload?.asr?.mode || "local")) {
    reasons.push(t("config.restart_reason.recognition_mode"));
  }
  if (String(previousPayload?.asr?.provider_preference || "") !== String(nextPayload?.asr?.provider_preference || "")) {
    reasons.push(t("config.restart_reason.asr_provider"));
  }
  if (Boolean(previousPayload?.asr?.prefer_gpu) !== Boolean(nextPayload?.asr?.prefer_gpu)) {
    reasons.push(t("config.restart_reason.gpu_policy"));
  }
  if (
    String(previousPayload?.asr?.browser?.recognition_language || "ru-RU") !==
    String(nextPayload?.asr?.browser?.recognition_language || "ru-RU")
  ) {
    reasons.push(t("config.restart_reason.web_speech_language"));
  }
  return reasons;
}

export function addTranslationEntry(state, sequence, sourceText) {
  const current = state.translation?.currentEntry || null;
  if (current && current.sequence === sequence) {
    current.sourceText = sourceText;
    return current;
  }
  const entry = {
    sequence,
    sourceText,
    translations: [],
    providerLabel: "",
    statusMessage: "",
  };
  state.translation = {
    ...(state.translation || {}),
    currentEntry: entry,
  };
  return entry;
}

export function hasRenderableOverlayContent(payload) {
  if (!payload || typeof payload !== "object") {
    return false;
  }
  const visibleItems = Array.isArray(payload.visible_items)
    ? payload.visible_items.filter((item) => String(item?.text || "").trim())
    : [];
  if (visibleItems.length > 0) {
    return true;
  }
  return Boolean(String(payload.active_partial_text || "").trim());
}

export function shouldUseLiveOverlayPreview(state) {
  const payload = state?.overlay?.payload;
  if (state?.runtime?.is_running === true) {
    return Boolean(payload);
  }
  return hasRenderableOverlayContent(payload);
}

export function buildPreviewPayload(state, { getResolvedSubtitleStyle }) {
  const config = state.config;
  if (!config) {
    return null;
  }
  if (shouldUseLiveOverlayPreview(state)) {
    return {
      ...state.overlay.payload,
      style: getResolvedSubtitleStyle(config, state.subtitleStylePresets),
    };
  }

  const visibleItems = [];
  const displayOrder = Array.isArray(config.subtitle_output?.display_order) ? config.subtitle_output.display_order : [];
  const maxTranslations = Math.max(0, Math.min(5, Number(config.subtitle_output?.max_translation_languages || 0)));
  const lineMap = new Map(
    (Array.isArray(config.translation?.lines) ? config.translation.lines : [])
      .filter((line) => line?.enabled !== false)
      .map((line) => [String(line.slot_id || "").toLowerCase(), line])
  );
  let translationsUsed = 0;
  displayOrder.forEach((code) => {
    if (code === "source") {
      if (config.subtitle_output?.show_source !== false) {
        visibleItems.push({
          kind: "source",
          lang: config.source_lang || "auto",
          style_slot: "source",
          text: t("preview.source_line"),
        });
      }
      return;
    }
    if (config.subtitle_output?.show_translations === false || translationsUsed >= maxTranslations) {
      return;
    }
    const line = lineMap.get(String(code || "").toLowerCase());
    if (!line) {
      return;
    }
    visibleItems.push({
      kind: "translation",
      lang: String(line.target_lang || code),
      slot_id: String(line.slot_id || code),
      target_lang: String(line.target_lang || code),
      label: String(line.label || String(line.target_lang || code).toUpperCase()),
      style_slot: String(line.slot_id || code),
      text: String(line.label || line.target_lang || code),
    });
    translationsUsed += 1;
  });

  return {
    preset: config.overlay?.preset || "single",
    compact: Boolean(config.overlay?.compact),
    completed_block_visible: visibleItems.length > 0,
    visible_items: visibleItems,
    active_partial_text:
      visibleItems.length === 0 && config.subtitle_output?.show_source !== false
        ? t("preview.live_partial")
        : "",
    style: getResolvedSubtitleStyle(config, state.subtitleStylePresets),
    sequence: 0,
  };
}

export function runtimeSnapshotSignature(runtime) {
  return JSON.stringify({
    status: runtime?.status || "idle",
    is_running: runtime?.is_running === true,
    last_error: runtime?.last_error || null,
    status_message: runtime?.status_message || null,
    event_sequence: runtime?.event_sequence || runtime?.sequence || 0,
    browser_worker: runtime?.asr_diagnostics?.browser_worker
      ? {
          worker_connected: runtime.asr_diagnostics.browser_worker.worker_connected,
          recognition_state: runtime.asr_diagnostics.browser_worker.recognition_state,
          supervisor_state: runtime.asr_diagnostics.browser_worker.supervisor_state,
          degraded_reason: runtime.asr_diagnostics.browser_worker.degraded_reason,
          generation_id: runtime.asr_diagnostics.browser_worker.generation_id,
        }
      : null,
  });
}

export function buildSaveStatusMessage(liveApplied, restartReasons, runtime) {
  if (!restartReasons.length) {
    return liveApplied ? t("config.save.applied_immediately") : t("config.save.saved_locally");
  }
  const subject = formatList(restartReasons);
  const restartLabel = runtime?.is_running
    ? t("config.save.restart_after_stop_start")
    : t("config.save.restart_on_next_start");
  if (liveApplied) {
    return t("config.save.applied_with_restart", { subject, restartLabel });
  }
  return t("config.save.local_with_restart", { subject, restartLabel });
}

export function getResolvedSubtitleStyle(config, presets) {
  if (!window.SubtitleStyleRenderer) {
    return config?.subtitle_style || {};
  }
  return window.SubtitleStyleRenderer.resolveEffectiveStyle(config?.subtitle_style || {}, presets || {});
}
