import { normalizeDiagnostics } from "../../normalizers/diagnostics-normalizer.js";
import { normalizeModelStatus } from "../../normalizers/model-normalizer.js";
import { normalizeOverlayPayload } from "../../normalizers/overlay-normalizer.js";
import { normalizeTranslationResult } from "../../normalizers/translation-normalizer.js";
import { clone, getCurrentLocale, getProviderMeta } from "../helpers.js";
import { addTranslationEntry } from "../action-helpers.js";

export function createWsHandlers({ store, runtimeActions, events }) {
  function handleTranscriptEvent(payload) {
    const snapshot = store.getState();
    const text = payload?.segment?.text || payload?.text || "";
    const transcript = clone(snapshot.transcript || { partial: "", finals: [] });
    const nextState = {};
    if (payload?.event === "partial") {
      transcript.partial = text;
    } else if (payload?.event === "final") {
      transcript.partial = "";
      transcript.finals.unshift(text);
      transcript.finals = transcript.finals.slice(0, 12);
      const translationBag = { translation: clone(snapshot.translation || {}) };
      addTranslationEntry(translationBag, Number(payload.sequence || 0), text);
      nextState.translation = translationBag.translation;
    }
    nextState.transcript = transcript;
    store.updateState(nextState);
    events?.emit?.("ws:event", { type: "transcript_update", payload });
  }

  function handleTranslationEvent(payload) {
    const snapshot = store.getState();
    const draft = {
      translation: clone(snapshot.translation || {}),
    };
    const normalized = normalizeTranslationResult(payload);
    const entry = addTranslationEntry(draft, normalized.sequence, normalized.source_text);
    if (normalized.translations.length) {
      const merged = new Map();
      entry.translations.forEach((item) => {
        const identity = String(item?.slot_id || item?.target_lang || "").toLowerCase();
        if (identity) {
          merged.set(identity, item);
        }
      });
      normalized.translations.forEach((item) => {
        const identity = String(item?.slot_id || item?.target_lang || "").toLowerCase();
        if (identity) {
          merged.set(identity, item);
        }
      });
      entry.translations = Array.from(merged.values());
    }
    const meta = normalized.provider ? getProviderMeta(normalized.provider) : null;
    const labelParts = [];
    if (normalized.provider) {
      labelParts.push(
        getCurrentLocale() === "ru"
          ? `Провайдер: ${meta?.label || normalized.provider}`
          : `Provider: ${meta?.label || normalized.provider}`
      );
    }
    if (normalized.provider_group) {
      labelParts.push(
        getCurrentLocale() === "ru" ? `Группа: ${normalized.provider_group}` : `Group: ${normalized.provider_group}`
      );
    }
    if (normalized.local_provider) {
      labelParts.push(getCurrentLocale() === "ru" ? "Локальный провайдер" : "Local provider");
    }
    if (normalized.experimental) {
      labelParts.push(getCurrentLocale() === "ru" ? "Экспериментально" : "Experimental");
    }
    if (normalized.used_default_prompt) {
      labelParts.push(getCurrentLocale() === "ru" ? "Prompt по умолчанию" : "Default prompt");
    }
    entry.providerLabel = labelParts.join(" | ");
    entry.statusMessage = normalized.status_message || "";
    store.updateState({
      translation: {
        ...(snapshot.translation || {}),
        currentEntry: entry,
        lastResult: normalized,
      },
    });
    events?.emit?.("ws:event", { type: "translation_update", payload });
  }

  function handleOverlayEvent(payload) {
    const snapshot = store.getState();
    store.updateState({
      overlay: {
        ...(snapshot.overlay || {}),
        payload: normalizeOverlayPayload(payload),
      },
    });
    events?.emit?.("ws:event", { type: "overlay_update", payload });
  }

  function handleWsMessage(message) {
    if (message.type === "transcript_update") {
      handleTranscriptEvent(message.payload);
      return;
    }
    if (message.type === "translation_update") {
      handleTranslationEvent(message.payload);
      return;
    }
    if (message.type === "overlay_update") {
      handleOverlayEvent(message.payload);
      return;
    }
    if (message.type === "runtime_status") {
      runtimeActions.setRuntime(message.payload);
      return;
    }
    if (message.type === "diagnostics_update") {
      const snapshot = store.getState();
      store.updateState({
        diagnostics: {
          ...(snapshot.diagnostics || {}),
          asr: normalizeDiagnostics(message.payload),
        },
      });
      events?.emit?.("ws:event", message);
      return;
    }
    if (message.type === "model_status_update") {
      store.updateState({ model: normalizeModelStatus(message.payload) });
      events?.emit?.("ws:event", message);
      return;
    }
    if (message.type === "preflight_update") {
      store.updateState({ ui: { preflightRunning: message.payload?.running === true } });
      events?.emit?.("ws:event", message);
    }
  }

  return { handleWsMessage };
}
