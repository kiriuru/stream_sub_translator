from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


CURRENT_CONFIG_VERSION = 7


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


BrowserWorkerLaunchBrowser = Literal["auto", "google_chrome"]


SupportedTranslationProvider = Literal[
    "google_translate_v2",
    "google_cloud_translation_v3",
    "google_gas_url",
    "google_web",
    "azure_translator",
    "deepl",
    "libretranslate",
    "openai",
    "openrouter",
    "lm_studio",
    "ollama",
    "public_libretranslate_mirror",
    "free_web_translate",
]


class UiPaletteConfig(SchemaModel):
    accent: str = "#6cc7ff"
    accent_secondary: str = "#ff6ce6"
    accent_tertiary: str = "#7ce3ad"


class UiConfig(SchemaModel):
    language: Literal["", "en", "ru", "ja", "ko", "zh"] = ""
    layout: Literal["standard", "compact"] = "standard"
    show_remote_tools: bool = False
    theme: Literal["dark", "light"] = "dark"
    palette: UiPaletteConfig = Field(default_factory=UiPaletteConfig)


class OverlayConfig(SchemaModel):
    preset: Literal["single", "dual-line", "stacked"] = "single"
    compact: bool = False


class AudioConfig(SchemaModel):
    input_device_id: str | None = None


class AsrBrowserAudioTrackConstraintsConfig(SchemaModel):
    echoCancellation: bool = False
    noiseSuppression: bool = False
    autoGainControl: bool = False


class AsrBrowserExperimentalConfig(SchemaModel):
    start_with_audio_track: bool = True
    fallback_to_default_start: bool = True
    keep_stream_alive: bool = True
    audio_track_constraints: AsrBrowserAudioTrackConstraintsConfig = Field(
        default_factory=AsrBrowserAudioTrackConstraintsConfig
    )


class AsrBrowserConfig(SchemaModel):
    recognition_language: str = "ru-RU"
    worker_launch_browser: BrowserWorkerLaunchBrowser = "auto"
    interim_results: bool = True
    continuous_results: bool = True
    force_finalization_enabled: bool = True
    force_finalization_timeout_ms: int = 1600
    minimum_reconnect_interval_ms: int = 500
    normal_restart_delay_ms: int = 350
    no_speech_restart_delay_ms: int = 350
    network_reconnect_initial_ms: int = 1000
    network_reconnect_max_ms: int = 30000
    stuck_stopping_timeout_ms: int = 2500
    max_browser_session_age_ms: int = 180000
    prepare_cycle_before_ms: int = 15000
    force_final_on_interruption: bool = True
    force_final_min_chars: int = 3
    force_final_min_stable_ms: int = 700
    experimental: AsrBrowserExperimentalConfig = Field(default_factory=AsrBrowserExperimentalConfig)


class AsrRealtimeConfig(SchemaModel):
    latency_preset: Literal["ultra_low_latency", "balanced", "quality", "custom"] = "balanced"
    vad_mode: int = 3
    energy_gate_enabled: bool = False
    min_rms_for_recognition: float = 0.0018
    min_voiced_ratio: float = 0.0
    first_partial_min_speech_ms: int = 180
    partial_emit_interval_ms: int = 450
    min_speech_ms: int = 180
    max_segment_ms: int = 5500
    silence_hold_ms: int = 180
    finalization_hold_ms: int = 350
    chunk_window_ms: int = 0
    chunk_overlap_ms: int = 0
    partial_min_delta_chars: int = 4
    partial_coalescing_ms: int = 160
    streaming_decode: bool = True
    partial_emit_mode: Literal["word_growth", "char_delta"] = "word_growth"
    partial_min_new_words: int = 1
    vad_speech_attack_frames: int = 2
    vad_speech_preroll_frames: int = 5


class AsrConfig(SchemaModel):
    mode: Literal["local", "browser_google", "browser_google_experimental"] = "local"
    desktop_profile_lock: Literal["", "browser_speech"] = ""
    provider_preference: Literal["official_eu_parakeet_low_latency"] = "official_eu_parakeet_low_latency"
    prefer_gpu: bool = True
    model_load_mode: Literal["auto", "local_nemo", "from_pretrained"] = "auto"
    model_revision: str = ""
    rnnoise_enabled: bool = False
    rnnoise_strength: int = 70
    browser: AsrBrowserConfig = Field(default_factory=AsrBrowserConfig)
    realtime: AsrRealtimeConfig = Field(default_factory=AsrRealtimeConfig)


class ObsClosedCaptionsConnectionConfig(SchemaModel):
    host: str = "127.0.0.1"
    port: int = 4455
    password: str = ""


class ObsClosedCaptionsDebugMirrorConfig(SchemaModel):
    enabled: bool = False
    input_name: str = "CC_DEBUG"
    send_partials: bool = True


class ObsClosedCaptionsTimingConfig(SchemaModel):
    send_partials: bool = True
    partial_throttle_ms: int = 140
    min_partial_delta_chars: int = 1
    final_replace_delay_ms: int = 0
    clear_after_ms: int = 2500
    avoid_duplicate_text: bool = True


class ObsClosedCaptionsConfig(SchemaModel):
    enabled: bool = False
    output_mode: str = "disabled"
    connection: ObsClosedCaptionsConnectionConfig = Field(default_factory=ObsClosedCaptionsConnectionConfig)
    debug_mirror: ObsClosedCaptionsDebugMirrorConfig = Field(default_factory=ObsClosedCaptionsDebugMirrorConfig)
    timing: ObsClosedCaptionsTimingConfig = Field(default_factory=ObsClosedCaptionsTimingConfig)


class RemoteLanConfig(SchemaModel):
    bind_enabled: bool = False
    bind_host: str = "0.0.0.0"
    port: int = 8876


class RemoteControllerConfig(SchemaModel):
    worker_url: str = ""
    connect_timeout_ms: int = 8000
    reconnect_delay_ms: int = 2000


class RemoteWorkerConfig(SchemaModel):
    allow_unpaired: bool = False
    heartbeat_timeout_ms: int = 15000


class RemoteConfig(SchemaModel):
    enabled: bool = False
    role: Literal["disabled", "controller", "worker"] = "disabled"
    session_id: str = ""
    pair_code: str = ""
    lan: RemoteLanConfig = Field(default_factory=RemoteLanConfig)
    controller: RemoteControllerConfig = Field(default_factory=RemoteControllerConfig)
    worker: RemoteWorkerConfig = Field(default_factory=RemoteWorkerConfig)


class UpdatesConfig(SchemaModel):
    enabled: bool = False
    provider: Literal["github_releases"] = "github_releases"
    github_repo: str = ""
    release_channel: Literal["stable", "prerelease"] = "stable"
    check_interval_hours: int = 12
    last_checked_utc: str = ""
    latest_known_version: str = ""


class GoogleTranslateV2ProviderSettings(SchemaModel):
    api_key: str = ""


class GoogleCloudTranslationV3ProviderSettings(SchemaModel):
    project_id: str = ""
    access_token: str = ""
    location: str = "global"
    model: str = ""


class GoogleGasUrlProviderSettings(SchemaModel):
    gas_url: str = ""


class GoogleWebProviderSettings(SchemaModel):
    pass


class AzureTranslatorProviderSettings(SchemaModel):
    api_key: str = ""
    endpoint: str = "https://api.cognitive.microsofttranslator.com"
    region: str = ""


class DeepLProviderSettings(SchemaModel):
    api_key: str = ""
    api_url: str = "https://api-free.deepl.com/v2/translate"


class LibreTranslateProviderSettings(SchemaModel):
    api_key: str = ""
    api_url: str = "https://libretranslate.com/translate"


class LlmTranslationProviderSettings(SchemaModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    custom_prompt: str = ""


class PublicLibreTranslateMirrorProviderSettings(SchemaModel):
    api_url: str = "https://translate.fedilab.app/translate"


class FreeWebTranslateProviderSettings(SchemaModel):
    pass


class TranslationProviderSettings(SchemaModel):
    google_translate_v2: GoogleTranslateV2ProviderSettings = Field(default_factory=GoogleTranslateV2ProviderSettings)
    google_cloud_translation_v3: GoogleCloudTranslationV3ProviderSettings = Field(
        default_factory=GoogleCloudTranslationV3ProviderSettings
    )
    google_gas_url: GoogleGasUrlProviderSettings = Field(default_factory=GoogleGasUrlProviderSettings)
    google_web: GoogleWebProviderSettings = Field(default_factory=GoogleWebProviderSettings)
    azure_translator: AzureTranslatorProviderSettings = Field(default_factory=AzureTranslatorProviderSettings)
    deepl: DeepLProviderSettings = Field(default_factory=DeepLProviderSettings)
    libretranslate: LibreTranslateProviderSettings = Field(default_factory=LibreTranslateProviderSettings)
    openai: LlmTranslationProviderSettings = Field(
        default_factory=lambda: LlmTranslationProviderSettings(base_url="https://api.openai.com/v1")
    )
    openrouter: LlmTranslationProviderSettings = Field(
        default_factory=lambda: LlmTranslationProviderSettings(base_url="https://openrouter.ai/api/v1")
    )
    lm_studio: LlmTranslationProviderSettings = Field(
        default_factory=lambda: LlmTranslationProviderSettings(base_url="http://127.0.0.1:1234/v1")
    )
    ollama: LlmTranslationProviderSettings = Field(
        default_factory=lambda: LlmTranslationProviderSettings(base_url="http://127.0.0.1:11434/v1")
    )
    public_libretranslate_mirror: PublicLibreTranslateMirrorProviderSettings = Field(
        default_factory=PublicLibreTranslateMirrorProviderSettings
    )
    free_web_translate: FreeWebTranslateProviderSettings = Field(default_factory=FreeWebTranslateProviderSettings)


class TranslationLineConfig(SchemaModel):
    slot_id: Literal["translation_1", "translation_2", "translation_3", "translation_4", "translation_5"]
    enabled: bool = True
    target_lang: str
    provider: SupportedTranslationProvider = "google_translate_v2"
    label: str = ""


class TranslationCacheConfig(SchemaModel):
    enabled: bool = True
    persist: bool = True
    max_entries: int = 5000


class TranslationConfig(SchemaModel):
    enabled: bool = False
    provider: SupportedTranslationProvider = "google_translate_v2"
    target_languages: list[str] = Field(default_factory=lambda: ["en"])
    timeout_ms: int = 10000
    queue_max_size: int = 8
    max_concurrent_jobs: int = 2
    provider_settings: TranslationProviderSettings = Field(default_factory=TranslationProviderSettings)
    lines: list[TranslationLineConfig] = Field(default_factory=lambda: [
        TranslationLineConfig(
            slot_id="translation_1",
            enabled=True,
            target_lang="en",
            provider="google_translate_v2",
            label="EN",
        )
    ])
    cache: TranslationCacheConfig = Field(default_factory=TranslationCacheConfig)
    provider_limits: dict[str, dict[str, Any]] = Field(default_factory=dict)


class SubtitleOutputConfig(SchemaModel):
    show_source: bool = True
    show_translations: bool = True
    max_translation_languages: int = 2
    display_order: list[str] = Field(default_factory=lambda: ["source", "translation_1"])


class SubtitleLifecycleConfig(SchemaModel):
    completed_block_ttl_ms: int = 4500
    completed_source_ttl_ms: int = 4500
    completed_translation_ttl_ms: int = 4500
    pause_to_finalize_ms: int = 350
    allow_early_replace_on_next_final: bool = True
    sync_source_and_translation_expiry: bool = True
    keep_completed_translation_during_active_partial: bool = True
    hard_max_phrase_ms: int = 5500


class SourceTextReplacementPairConfig(SchemaModel):
    source: str = ""
    target: str = ""


class SourceTextReplacementConfig(SchemaModel):
    """Post-ASR text replacements before translation and on-screen output."""

    enabled: bool = False
    include_builtin: bool = True
    case_insensitive: bool = True
    whole_words: bool = True
    pairs: list[SourceTextReplacementPairConfig] = Field(default_factory=list)


class ConfigSchema(SchemaModel):
    config_version: int = CURRENT_CONFIG_VERSION
    profile: str = "default"
    ui: UiConfig = Field(default_factory=UiConfig)
    source_lang: str = "auto"
    targets: list[str] = Field(default_factory=lambda: ["en"])
    asr: AsrConfig = Field(default_factory=AsrConfig)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    overlay: OverlayConfig = Field(default_factory=OverlayConfig)
    obs_closed_captions: ObsClosedCaptionsConfig = Field(default_factory=ObsClosedCaptionsConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    remote: RemoteConfig = Field(default_factory=RemoteConfig)
    updates: UpdatesConfig = Field(default_factory=UpdatesConfig)
    subtitle_output: SubtitleOutputConfig = Field(default_factory=SubtitleOutputConfig)
    subtitle_style: dict[str, Any] = Field(default_factory=dict)
    subtitle_lifecycle: SubtitleLifecycleConfig = Field(default_factory=SubtitleLifecycleConfig)
    source_text_replacement: SourceTextReplacementConfig = Field(default_factory=SourceTextReplacementConfig)


def build_default_config(*, prefer_gpu: bool = True) -> ConfigSchema:
    return ConfigSchema(
        asr=AsrConfig(prefer_gpu=prefer_gpu),
        subtitle_style={},
    )
