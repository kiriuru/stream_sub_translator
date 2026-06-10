import { writable } from "svelte/store";
import { diagnosticsFromRuntime } from "../diagnostics";
import { normalizeDiagnosticsPayload } from "../diagnostics-normalizer";
import { normalizeOverlayPayload } from "../overlay-normalizer";
import type { SaveStatusState } from "../save-status";
import type {
  ConfigPayload,
  DiagnosticsSnapshot,
  FontCatalog,
  RuntimeStatus,
  StylePresetCatalog,
  TabId,
  TranscriptState,
  TranslationResultEntry,
  TranslationResultState,
  VersionInfo,
  WsMessage,
} from "../types";

export interface AppSnapshot {
  config: ConfigPayload;
  runtime: RuntimeStatus;
  diagnostics: DiagnosticsSnapshot;
  transcript: TranscriptState;
  translation: TranslationResultState;
  overlayPayload: Record<string, unknown> | null;
  overlayUrl: string;
  wsConnected: boolean;
  activeTab: TabId;
  saveStatus: SaveStatusState;
  version: string;
  versionInfo: VersionInfo | null;
  updateBannerDismissed: boolean;
  busy: boolean;
  subtitleStylePresets: StylePresetCatalog;
  fontCatalog: FontCatalog | null;
}

const defaultConfig: ConfigPayload = {
  config_version: 7,
  ui: { theme: "dark", language: "", layout: "standard" },
  asr: { mode: "browser_google", browser: { recognition_language: "en-US" } },
  translation: { enabled: false, provider: "google_translate_v2", lines: [] },
};

const idleRuntime: RuntimeStatus = { phase: "idle", status: "idle", running: false, is_running: false };

export const appStore = writable<AppSnapshot>({
  config: structuredClone(defaultConfig),
  runtime: idleRuntime,
  diagnostics: diagnosticsFromRuntime(idleRuntime),
  transcript: { partial: "", finals: [] },
  translation: { current: null, history: [] },
  overlayPayload: null,
  overlayUrl: "",
  wsConnected: false,
  activeTab: "translation",
  saveStatus: { tone: "default" },
  version: "0.5.0",
  versionInfo: null,
  updateBannerDismissed: false,
  busy: false,
  subtitleStylePresets: {},
  fontCatalog: null,
});

export function patchApp(partial: Partial<AppSnapshot>) {
  appStore.update((s) => {
    const next = { ...s, ...partial };
    if (partial.runtime && !partial.diagnostics) {
      next.diagnostics = diagnosticsFromRuntime(partial.runtime);
    }
    return next;
  });
}

export function mutateConfig(mutator: (draft: ConfigPayload) => void) {
  appStore.update((s) => {
    const draft = structuredClone(s.config);
    mutator(draft);
    return { ...s, config: draft };
  });
}

function normalizeTranslationPayload(payload: Record<string, unknown>): TranslationResultEntry {
  const translations = Array.isArray(payload.translations) ? payload.translations : [];
  return {
    sequence: Number.isFinite(Number(payload.sequence)) ? Number(payload.sequence) : 0,
    source_text: String(payload.source_text || ""),
    provider: String(payload.provider || ""),
    statusMessage: String(payload.status_message || ""),
    translations: translations.map((item) => {
      const row = (item || {}) as Record<string, unknown>;
      return {
        slot_id: String(row.slot_id || "").toLowerCase(),
        label: String(row.label || ""),
        target_lang: String(row.target_lang || "").toLowerCase(),
        provider: String(row.provider || ""),
        text: String(row.text || ""),
        success: row.success !== false,
        error: String(row.error || ""),
        cached: row.cached === true,
      };
    }),
  };
}

export function handleWsEvent(message: WsMessage) {
  appStore.update((s) => {
    const type = message.type;
    const payload = (message.payload || {}) as Record<string, unknown>;

    if (type === "transcript_update") {
      const event = String(payload.event || "");
      const isFinal = payload.is_final === true || event === "final";
      const isPartial = payload.is_final === false || event === "partial";
      const text = String(
        (payload.segment as { text?: string } | undefined)?.text || payload.text || "",
      );
      const transcript = { ...s.transcript };
      if (isPartial && !isFinal) {
        transcript.partial = text;
      } else if (isFinal) {
        transcript.partial = "";
        transcript.finals = [text, ...transcript.finals].slice(0, 12);
      } else if (text) {
        transcript.partial = text;
      }
      return { ...s, transcript };
    }

    if (type === "translation_update") {
      const entry = normalizeTranslationPayload(payload);
      const history = [entry, ...s.translation.history.filter((row) => row.sequence !== entry.sequence)].slice(0, 8);
      return {
        ...s,
        translation: {
          current: entry,
          history,
        },
      };
    }

    if (type === "subtitle_payload_update" || type === "overlay_update") {
      return { ...s, overlayPayload: normalizeOverlayPayload(payload) };
    }

    if (type === "runtime_update" || type === "runtime_status") {
      const runtime = { ...s.runtime, ...(payload as RuntimeStatus) };
      const runtimeStopped = runtime.is_running === false || runtime.running === false;
      return {
        ...s,
        runtime,
        diagnostics: diagnosticsFromRuntime(runtime),
        overlayPayload: runtimeStopped ? null : s.overlayPayload,
      };
    }

    if (type === "diagnostics_update") {
      return {
        ...s,
        diagnostics: {
          ...s.diagnostics,
          asr: normalizeDiagnosticsPayload(payload),
        },
      };
    }

    return s;
  });
}
