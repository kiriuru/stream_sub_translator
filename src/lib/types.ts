export type LocaleCode = "en" | "ru" | "ja" | "ko" | "zh";

export type RuntimePhase =
  | "idle"
  | "starting"
  | "listening"
  | "transcribing"
  | "translating"
  | "error";

export interface TranscriptState {
  partial: string;
  finals: string[];
}

export interface TranslationResultLine {
  slot_id?: string;
  label?: string;
  target_lang?: string;
  provider?: string;
  text?: string;
  success?: boolean;
  error?: string;
  cached?: boolean;
}

export interface TranslationResultEntry {
  sequence: number;
  source_text: string;
  translations: TranslationResultLine[];
  statusMessage?: string;
  provider?: string;
}

export interface TranslationResultState {
  current: TranslationResultEntry | null;
  history: TranslationResultEntry[];
}

export interface TranslationLine {
  slot_id: string;
  enabled: boolean;
  target_lang: string;
  provider: string;
  label?: string;
}

export interface FontCatalogEntry {
  id: string;
  label: string;
  family: string;
  source: string;
  url?: string;
}

export interface FontCatalog {
  project_fonts_dir: string;
  project_local: FontCatalogEntry[];
  fallback: FontCatalogEntry[];
  system?: FontCatalogEntry[];
}

export type StylePresetCatalog = Record<
  string,
  {
    preset?: string;
    label?: string;
    description?: string;
    built_in?: boolean;
    base?: Record<string, unknown>;
    line_slots?: Record<string, Record<string, unknown>>;
  }
>;

export interface ConfigPayload {
  config_version?: number;
  profile?: string;
  source_lang?: string;
  targets?: string[];
  ui?: {
    language?: string;
    layout?: string;
    theme?: string;
    show_translation_results?: boolean;
    palette?: Record<string, string>;
  };
  asr?: {
    mode?: string;
    browser?: Record<string, unknown>;
    realtime?: Record<string, unknown>;
  };
  overlay?: Record<string, unknown>;
  translation?: {
    enabled?: boolean;
    provider?: string;
    target_languages?: string[];
    lines?: TranslationLine[];
    timeout_ms?: number;
    queue_max_size?: number;
    max_concurrent_jobs?: number;
    cache?: {
      enabled?: boolean;
      persist?: boolean;
      max_entries?: number;
    };
    provider_limits?: Record<string, Record<string, unknown>>;
    provider_settings?: Record<string, Record<string, unknown>>;
  };
  subtitle_output?: {
    display_order?: string[];
    show_source?: boolean;
    show_translations?: boolean;
    max_translation_languages?: number;
  };
  subtitle_lifecycle?: {
    completed_block_ttl_ms?: number;
    completed_source_ttl_ms?: number;
    completed_translation_ttl_ms?: number;
    pause_to_finalize_ms?: number;
    allow_early_replace_on_next_final?: boolean;
    sync_source_and_translation_expiry?: boolean;
    keep_completed_translation_during_active_partial?: boolean;
    hard_max_phrase_ms?: number;
  };
  subtitle_style?: Record<string, unknown>;
  obs_closed_captions?: Record<string, unknown>;
  logging?: {
    full_enabled?: boolean;
  };
  [key: string]: unknown;
}

export interface DiagnosticsSnapshot {
  asr?: Record<string, unknown>;
  translation?: Record<string, unknown>;
  obs?: Record<string, unknown>;
  subtitle?: Record<string, unknown>;
  metrics?: Record<string, unknown>;
  healthStatus?: string;
}

export interface RuntimeStatus {
  running?: boolean;
  starting?: boolean;
  phase?: RuntimePhase;
  status?: RuntimePhase;
  is_running?: boolean;
  last_error?: string | null;
  asr?: {
    active_mode?: string;
    diagnostics?: {
      browser_worker?: Record<string, unknown>;
    };
  };
  asr_diagnostics?: Record<string, unknown>;
  translation_diagnostics?: Record<string, unknown>;
  obs_captions?: {
    enabled?: boolean;
    active?: boolean;
    connected?: boolean;
    connection_state?: string;
    output_mode?: string;
    diagnostics?: Record<string, unknown>;
  };
  obs_caption_diagnostics?: Record<string, unknown>;
  subtitle_router_counters?: Record<string, unknown>;
  overlay?: {
    overlay_url?: string;
  };
  metrics?: Record<string, unknown>;
}

export interface ReleaseSyncStatus {
  provider?: string;
  enabled?: boolean;
  github_repo?: string | null;
  release_channel?: string;
  latest_known_version?: string | null;
  last_checked_utc?: string | null;
  update_available?: boolean;
  check_supported?: boolean;
  check_active?: boolean;
  release_url?: string | null;
  message?: string | null;
}

export interface VersionInfo {
  ok?: boolean;
  current_version?: string;
  version?: string;
  product?: string;
  release_track?: string;
  sync?: ReleaseSyncStatus;
}

export interface WsMessage {
  type: string;
  payload?: Record<string, unknown>;
}

export type TabId =
  | "translation"
  | "subtitles"
  | "style"
  | "theme"
  | "obs"
  | "replacement"
  | "tools"
  | "settings"
  | "help";

/** Compact sidebar panes: live overview or a settings tab. */
export type CompactPaneId = "live" | TabId;
