import { PROVIDERS } from "../dashboard/constants.js";

function parseIntegerOr(value, fallback) {
  const parsed = Number.parseInt(String(value), 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseFloatOr(value, fallback) {
  const parsed = Number.parseFloat(String(value));
  return Number.isFinite(parsed) ? parsed : fallback;
}

function isBrowserRecognitionMode(mode) {
  return ["browser_google", "browser_google_experimental"].includes(String(mode || "").toLowerCase());
}

function normalizeUiLanguage(value) {
  const current = String(value || "").trim().toLowerCase();
  return ["en", "ru"].includes(current) ? current : "en";
}

export function normalizeConfigShape(config) {
  const normalized = config && typeof config === "object" ? structuredClone(config) : {};
  delete normalized.runtime;
  delete normalized.name;

  if (!normalized.ui || typeof normalized.ui !== "object") {
    normalized.ui = {};
  }
  normalized.ui.language = normalizeUiLanguage(normalized.ui.language);

  if (!normalized.audio || typeof normalized.audio !== "object") {
    normalized.audio = { input_device_id: null };
  }
  if (!normalized.profile || typeof normalized.profile !== "string") {
    normalized.profile = "default";
  }
  if (!normalized.overlay || typeof normalized.overlay !== "object") {
    normalized.overlay = { preset: "single", compact: false };
  }
  normalized.overlay.preset = ["single", "dual-line", "stacked"].includes(String(normalized.overlay.preset || "single"))
    ? String(normalized.overlay.preset || "single")
    : "single";
  normalized.overlay.compact = normalized.overlay.compact === true;

  if (!normalized.obs_closed_captions || typeof normalized.obs_closed_captions !== "object") {
    normalized.obs_closed_captions = {};
  }
  if (!normalized.obs_closed_captions.connection || typeof normalized.obs_closed_captions.connection !== "object") {
    normalized.obs_closed_captions.connection = {};
  }
  if (!normalized.obs_closed_captions.timing || typeof normalized.obs_closed_captions.timing !== "object") {
    normalized.obs_closed_captions.timing = {};
  }
  if (!normalized.obs_closed_captions.debug_mirror || typeof normalized.obs_closed_captions.debug_mirror !== "object") {
    normalized.obs_closed_captions.debug_mirror = {};
  }
  normalized.obs_closed_captions.enabled = normalized.obs_closed_captions.enabled === true;
  normalized.obs_closed_captions.output_mode = [
    "disabled",
    "source_live",
    "source_final_only",
    "translation_1",
    "translation_2",
    "translation_3",
    "translation_4",
    "translation_5",
    "first_visible_line",
  ].includes(String(normalized.obs_closed_captions.output_mode || "disabled"))
    ? String(normalized.obs_closed_captions.output_mode || "disabled")
    : "disabled";
  normalized.obs_closed_captions.connection.host =
    String(normalized.obs_closed_captions.connection.host || "127.0.0.1").trim() || "127.0.0.1";
  normalized.obs_closed_captions.connection.port = Math.max(
    1,
    Math.min(65535, parseIntegerOr(normalized.obs_closed_captions.connection.port ?? 4455, 4455))
  );
  normalized.obs_closed_captions.connection.password = String(normalized.obs_closed_captions.connection.password || "");
  normalized.obs_closed_captions.debug_mirror.enabled = normalized.obs_closed_captions.debug_mirror.enabled === true;
  normalized.obs_closed_captions.debug_mirror.input_name =
    String(normalized.obs_closed_captions.debug_mirror.input_name || "CC_DEBUG").trim() || "CC_DEBUG";
  normalized.obs_closed_captions.debug_mirror.send_partials =
    normalized.obs_closed_captions.debug_mirror.send_partials !== false;
  normalized.obs_closed_captions.timing.send_partials =
    normalized.obs_closed_captions.timing.send_partials !== false;
  normalized.obs_closed_captions.timing.partial_throttle_ms = Math.max(
    0,
    parseIntegerOr(normalized.obs_closed_captions.timing.partial_throttle_ms ?? 250, 250)
  );
  normalized.obs_closed_captions.timing.min_partial_delta_chars = Math.max(
    0,
    parseIntegerOr(normalized.obs_closed_captions.timing.min_partial_delta_chars ?? 3, 3)
  );
  normalized.obs_closed_captions.timing.final_replace_delay_ms = Math.max(
    0,
    parseIntegerOr(normalized.obs_closed_captions.timing.final_replace_delay_ms ?? 0, 0)
  );
  normalized.obs_closed_captions.timing.clear_after_ms = Math.max(
    0,
    parseIntegerOr(normalized.obs_closed_captions.timing.clear_after_ms ?? 2500, 2500)
  );
  normalized.obs_closed_captions.timing.avoid_duplicate_text =
    normalized.obs_closed_captions.timing.avoid_duplicate_text !== false;

  if (!normalized.translation || typeof normalized.translation !== "object") {
    normalized.translation = {};
  }
  if (!normalized.asr || typeof normalized.asr !== "object") {
    normalized.asr = {
      mode: "local",
      provider_preference: "official_eu_parakeet_low_latency",
      prefer_gpu: true,
      browser: {},
      realtime: {},
    };
  }
  if (!normalized.subtitle_output || typeof normalized.subtitle_output !== "object") {
    normalized.subtitle_output = {};
  }
  if (!normalized.remote || typeof normalized.remote !== "object") {
    normalized.remote = {};
  }

  normalized.remote.enabled = normalized.remote.enabled === true;
  normalized.remote.role = String(
    normalized.remote.role || (normalized.remote.enabled ? "controller" : "disabled")
  ).trim().toLowerCase();
  if (!["disabled", "controller", "worker"].includes(normalized.remote.role)) {
    normalized.remote.role = normalized.remote.enabled ? "controller" : "disabled";
  }
  if (!normalized.remote.enabled) {
    normalized.remote.role = "disabled";
  }
  if (!normalized.remote.controller || typeof normalized.remote.controller !== "object") {
    normalized.remote.controller = {};
  }
  normalized.remote.controller.worker_url = String(normalized.remote.controller.worker_url || "").trim();

  normalized.asr.mode = String(normalized.asr.mode || "local").toLowerCase();
  if (!["local", "browser_google", "browser_google_experimental"].includes(normalized.asr.mode)) {
    normalized.asr.mode = "local";
  }
  if (normalized.remote.enabled && normalized.remote.role === "worker" && isBrowserRecognitionMode(normalized.asr.mode)) {
    normalized.asr.mode = "local";
  }
  normalized.asr.provider_preference = String(
    normalized.asr.provider_preference || "official_eu_parakeet_low_latency"
  ).toLowerCase();
  if (![
    "official_eu_parakeet_low_latency",
    "official_eu_parakeet",
    "auto",
    "google_legacy_http_experimental",
  ].includes(normalized.asr.provider_preference)) {
    normalized.asr.provider_preference = "official_eu_parakeet_low_latency";
  }
  normalized.asr.prefer_gpu = normalized.asr.prefer_gpu !== false;
  if (!normalized.asr.browser || typeof normalized.asr.browser !== "object") {
    normalized.asr.browser = {};
  }
  normalized.asr.browser.recognition_language =
    String(normalized.asr.browser.recognition_language || "ru-RU").trim() || "ru-RU";
  normalized.asr.browser.interim_results = normalized.asr.browser.interim_results !== false;
  normalized.asr.browser.continuous_results = normalized.asr.browser.continuous_results === true;
  normalized.asr.browser.force_finalization_enabled = normalized.asr.browser.force_finalization_enabled !== false;
  normalized.asr.browser.force_finalization_timeout_ms = Math.max(
    300,
    Math.min(15000, parseIntegerOr(normalized.asr.browser.force_finalization_timeout_ms ?? 1600, 1600))
  );

  if (!normalized.asr.browser.experimental || typeof normalized.asr.browser.experimental !== "object") {
    normalized.asr.browser.experimental = {};
  }
  if (
    !normalized.asr.browser.experimental.audio_track_constraints ||
    typeof normalized.asr.browser.experimental.audio_track_constraints !== "object"
  ) {
    normalized.asr.browser.experimental.audio_track_constraints = {};
  }
  normalized.asr.browser.experimental.start_with_audio_track =
    normalized.asr.browser.experimental.start_with_audio_track !== false;
  normalized.asr.browser.experimental.fallback_to_default_start =
    normalized.asr.browser.experimental.fallback_to_default_start !== false;
  normalized.asr.browser.experimental.keep_stream_alive =
    normalized.asr.browser.experimental.keep_stream_alive !== false;
  normalized.asr.browser.experimental.audio_track_constraints.echoCancellation =
    normalized.asr.browser.experimental.audio_track_constraints.echoCancellation === true;
  normalized.asr.browser.experimental.audio_track_constraints.noiseSuppression =
    normalized.asr.browser.experimental.audio_track_constraints.noiseSuppression === true;
  normalized.asr.browser.experimental.audio_track_constraints.autoGainControl =
    normalized.asr.browser.experimental.audio_track_constraints.autoGainControl === true;
  if (!normalized.asr.google_legacy_http || typeof normalized.asr.google_legacy_http !== "object") {
    normalized.asr.google_legacy_http = {};
  }
  normalized.asr.google_legacy_http.enabled = normalized.asr.google_legacy_http.enabled === true;
  normalized.asr.google_legacy_http.language =
    String(normalized.asr.google_legacy_http.language || "ru-RU").trim() || "ru-RU";
  normalized.asr.google_legacy_http.profanity_filter = normalized.asr.google_legacy_http.profanity_filter === true;
  normalized.asr.google_legacy_http.connect_timeout_ms = Math.max(
    1000,
    Math.min(120000, parseIntegerOr(normalized.asr.google_legacy_http.connect_timeout_ms ?? 10000, 10000))
  );
  normalized.asr.google_legacy_http.send_timeout_ms = Math.max(
    1000,
    Math.min(120000, parseIntegerOr(normalized.asr.google_legacy_http.send_timeout_ms ?? 10000, 10000))
  );
  normalized.asr.google_legacy_http.recv_timeout_ms = Math.max(
    1000,
    Math.min(300000, parseIntegerOr(normalized.asr.google_legacy_http.recv_timeout_ms ?? 30000, 30000))
  );
  normalized.asr.google_legacy_http.max_queue_depth = Math.max(
    1,
    Math.min(512, parseIntegerOr(normalized.asr.google_legacy_http.max_queue_depth ?? 50, 50))
  );
  normalized.asr.google_legacy_http.reconnect_initial_ms = Math.max(
    100,
    Math.min(120000, parseIntegerOr(normalized.asr.google_legacy_http.reconnect_initial_ms ?? 1000, 1000))
  );
  normalized.asr.google_legacy_http.reconnect_max_ms = Math.max(
    normalized.asr.google_legacy_http.reconnect_initial_ms,
    Math.min(300000, parseIntegerOr(normalized.asr.google_legacy_http.reconnect_max_ms ?? 30000, 30000))
  );
  normalized.asr.google_legacy_http.endpoint_host =
    String(normalized.asr.google_legacy_http.endpoint_host || "").trim();
  normalized.asr.google_legacy_http.pair_id_prefix =
    String(normalized.asr.google_legacy_http.pair_id_prefix || "sst").trim() || "sst";
  delete normalized.asr.google_legacy_http.api_key;
  normalized.asr.rnnoise_enabled =
    normalized.asr.rnnoise_enabled === true ||
    (normalized.asr.rnnoise_enabled == null && normalized.asr.experimental_noise_reduction_enabled === true);
  normalized.asr.rnnoise_strength = Math.max(
    0,
    Math.min(100, parseIntegerOr(normalized.asr.rnnoise_strength ?? 70, 70))
  );

  if (!normalized.asr.realtime || typeof normalized.asr.realtime !== "object") {
    normalized.asr.realtime = {};
  }
  normalized.asr.realtime.vad_mode = Math.max(0, Math.min(3, parseIntegerOr(normalized.asr.realtime.vad_mode ?? 2, 2)));
  normalized.asr.realtime.energy_gate_enabled = normalized.asr.realtime.energy_gate_enabled === true;
  normalized.asr.realtime.min_rms_for_recognition = Math.max(
    0,
    Math.min(0.05, parseFloatOr(normalized.asr.realtime.min_rms_for_recognition ?? 0.0018, 0.0018))
  );
  normalized.asr.realtime.min_voiced_ratio = Math.max(
    0,
    Math.min(1, parseFloatOr(normalized.asr.realtime.min_voiced_ratio ?? 0.0, 0.0))
  );
  normalized.asr.realtime.partial_emit_interval_ms = Math.max(
    60,
    parseIntegerOr(normalized.asr.realtime.partial_emit_interval_ms ?? 450, 450)
  );
  normalized.asr.realtime.min_speech_ms = Math.max(
    0,
    parseIntegerOr(normalized.asr.realtime.min_speech_ms ?? 180, 180)
  );
  normalized.asr.realtime.first_partial_min_speech_ms = Math.max(
    normalized.asr.realtime.min_speech_ms,
    parseIntegerOr(
      normalized.asr.realtime.first_partial_min_speech_ms ?? normalized.asr.realtime.min_speech_ms,
      normalized.asr.realtime.min_speech_ms
    )
  );
  normalized.asr.realtime.max_segment_ms = Math.max(
    500,
    parseIntegerOr(normalized.asr.realtime.max_segment_ms ?? 5500, 5500)
  );
  normalized.asr.realtime.silence_hold_ms = Math.max(
    60,
    parseIntegerOr(normalized.asr.realtime.silence_hold_ms ?? 180, 180)
  );
  normalized.asr.realtime.finalization_hold_ms = Math.max(
    normalized.asr.realtime.silence_hold_ms,
    parseIntegerOr(normalized.asr.realtime.finalization_hold_ms ?? 360, 360)
  );
  normalized.asr.realtime.chunk_window_ms = Math.max(0, parseIntegerOr(normalized.asr.realtime.chunk_window_ms ?? 0, 0));
  normalized.asr.realtime.chunk_overlap_ms = Math.max(
    0,
    Math.min(
      normalized.asr.realtime.chunk_window_ms,
      parseIntegerOr(normalized.asr.realtime.chunk_overlap_ms ?? 0, 0)
    )
  );
  normalized.asr.realtime.partial_min_delta_chars = Math.max(
    0,
    parseIntegerOr(normalized.asr.realtime.partial_min_delta_chars ?? 12, 12)
  );
  normalized.asr.realtime.partial_coalescing_ms = Math.max(
    0,
    parseIntegerOr(normalized.asr.realtime.partial_coalescing_ms ?? 160, 160)
  );

  if (!normalized.subtitle_lifecycle || typeof normalized.subtitle_lifecycle !== "object") {
    normalized.subtitle_lifecycle = {};
  }
  const completedBlockTtl = Math.max(
    500,
    parseIntegerOr(normalized.subtitle_lifecycle.completed_block_ttl_ms ?? 4500, 4500)
  );
  normalized.subtitle_lifecycle.completed_source_ttl_ms = Math.max(
    500,
    parseIntegerOr(normalized.subtitle_lifecycle.completed_source_ttl_ms ?? completedBlockTtl, completedBlockTtl)
  );
  normalized.subtitle_lifecycle.completed_translation_ttl_ms = Math.max(
    500,
    parseIntegerOr(normalized.subtitle_lifecycle.completed_translation_ttl_ms ?? completedBlockTtl, completedBlockTtl)
  );
  normalized.subtitle_lifecycle.completed_block_ttl_ms = Math.max(
    normalized.subtitle_lifecycle.completed_source_ttl_ms,
    normalized.subtitle_lifecycle.completed_translation_ttl_ms
  );
  normalized.subtitle_lifecycle.pause_to_finalize_ms = Math.max(
    120,
    parseIntegerOr(
      normalized.subtitle_lifecycle.pause_to_finalize_ms ?? normalized.asr.realtime.finalization_hold_ms ?? 350,
      normalized.asr.realtime.finalization_hold_ms ?? 350
    )
  );
  normalized.subtitle_lifecycle.allow_early_replace_on_next_final =
    normalized.subtitle_lifecycle.allow_early_replace_on_next_final !== false;
  normalized.subtitle_lifecycle.sync_source_and_translation_expiry =
    normalized.subtitle_lifecycle.sync_source_and_translation_expiry !== false;
  normalized.subtitle_lifecycle.hard_max_phrase_ms = Math.max(
    1000,
    parseIntegerOr(
      normalized.subtitle_lifecycle.hard_max_phrase_ms ?? normalized.asr.realtime.max_segment_ms ?? 5500,
      normalized.asr.realtime.max_segment_ms ?? 5500
    )
  );
  normalized.asr.realtime.finalization_hold_ms = normalized.subtitle_lifecycle.pause_to_finalize_ms;
  normalized.asr.realtime.max_segment_ms = normalized.subtitle_lifecycle.hard_max_phrase_ms;

  const translation = normalized.translation;
  if (!translation.provider || !PROVIDERS[translation.provider]) {
    translation.provider = "google_translate_v2";
  }
  translation.enabled = Boolean(translation.enabled);
  if (!Array.isArray(translation.target_languages)) {
    translation.target_languages = Array.isArray(normalized.targets) ? normalized.targets : ["en"];
  }
  translation.target_languages = translation.target_languages
    .map((item) => String(item || "").toLowerCase())
    .filter((item, index, array) => item && array.indexOf(item) === index);
  if (!translation.provider_settings || typeof translation.provider_settings !== "object") {
    translation.provider_settings = {};
  }
  Object.keys(PROVIDERS).forEach((providerName) => {
    if (!translation.provider_settings[providerName] || typeof translation.provider_settings[providerName] !== "object") {
      translation.provider_settings[providerName] = {};
    }
  });
  translation.provider_settings.google_translate_v2.api_key = String(translation.provider_settings.google_translate_v2.api_key || "");
  translation.provider_settings.google_cloud_translation_v3.project_id =
    String(translation.provider_settings.google_cloud_translation_v3.project_id || "");
  translation.provider_settings.google_cloud_translation_v3.access_token =
    String(
      translation.provider_settings.google_cloud_translation_v3.access_token ||
      translation.provider_settings.google_cloud_translation_v3.api_key ||
      ""
    );
  translation.provider_settings.google_cloud_translation_v3.location =
    String(
      translation.provider_settings.google_cloud_translation_v3.location ||
      translation.provider_settings.google_cloud_translation_v3.region ||
      PROVIDERS.google_cloud_translation_v3.regionPlaceholder
    );
  translation.provider_settings.google_cloud_translation_v3.model =
    String(translation.provider_settings.google_cloud_translation_v3.model || "");
  delete translation.provider_settings.google_cloud_translation_v3.api_key;
  delete translation.provider_settings.google_cloud_translation_v3.endpoint;
  delete translation.provider_settings.google_cloud_translation_v3.region;
  translation.provider_settings.google_gas_url.gas_url = String(translation.provider_settings.google_gas_url.gas_url || "");
  translation.provider_settings.google_web = {};
  translation.provider_settings.azure_translator.api_key = String(translation.provider_settings.azure_translator.api_key || "");
  translation.provider_settings.azure_translator.endpoint =
    String(translation.provider_settings.azure_translator.endpoint || "https://api.cognitive.microsofttranslator.com");
  translation.provider_settings.azure_translator.region = String(translation.provider_settings.azure_translator.region || "");
  translation.provider_settings.deepl.api_key = String(translation.provider_settings.deepl.api_key || "");
  translation.provider_settings.deepl.api_url =
    String(translation.provider_settings.deepl.api_url || PROVIDERS.deepl.apiUrlPlaceholder);
  translation.provider_settings.libretranslate.api_key = String(translation.provider_settings.libretranslate.api_key || "");
  translation.provider_settings.libretranslate.api_url =
    String(translation.provider_settings.libretranslate.api_url || PROVIDERS.libretranslate.apiUrlPlaceholder);
  translation.provider_settings.openai.api_key = String(translation.provider_settings.openai.api_key || "");
  translation.provider_settings.openai.base_url =
    String(translation.provider_settings.openai.base_url || PROVIDERS.openai.baseUrlPlaceholder);
  translation.provider_settings.openai.model = String(translation.provider_settings.openai.model || "");
  translation.provider_settings.openai.custom_prompt = String(translation.provider_settings.openai.custom_prompt || "");
  translation.provider_settings.openrouter.api_key = String(translation.provider_settings.openrouter.api_key || "");
  translation.provider_settings.openrouter.base_url =
    String(translation.provider_settings.openrouter.base_url || PROVIDERS.openrouter.baseUrlPlaceholder);
  translation.provider_settings.openrouter.model = String(translation.provider_settings.openrouter.model || "");
  translation.provider_settings.openrouter.custom_prompt =
    String(translation.provider_settings.openrouter.custom_prompt || "");
  translation.provider_settings.lm_studio.api_key = String(translation.provider_settings.lm_studio.api_key || "");
  translation.provider_settings.lm_studio.base_url =
    String(translation.provider_settings.lm_studio.base_url || PROVIDERS.lm_studio.baseUrlPlaceholder);
  translation.provider_settings.lm_studio.model = String(translation.provider_settings.lm_studio.model || "");
  translation.provider_settings.lm_studio.custom_prompt =
    String(translation.provider_settings.lm_studio.custom_prompt || "");
  translation.provider_settings.ollama.api_key = String(translation.provider_settings.ollama.api_key || "");
  translation.provider_settings.ollama.base_url =
    String(translation.provider_settings.ollama.base_url || PROVIDERS.ollama.baseUrlPlaceholder);
  translation.provider_settings.ollama.model = String(translation.provider_settings.ollama.model || "");
  translation.provider_settings.ollama.custom_prompt = String(translation.provider_settings.ollama.custom_prompt || "");
  translation.provider_settings.public_libretranslate_mirror.api_url =
    String(
      translation.provider_settings.public_libretranslate_mirror.api_url ||
      PROVIDERS.public_libretranslate_mirror.apiUrlPlaceholder
    );
  translation.provider_settings.free_web_translate = {};

  normalized.targets = [...translation.target_languages];

  const subtitleOutput = normalized.subtitle_output;
  subtitleOutput.show_source = subtitleOutput.show_source !== false;
  subtitleOutput.show_translations = subtitleOutput.show_translations !== false;
  subtitleOutput.max_translation_languages = Math.max(
    0,
    Math.min(5, Number.parseInt(String(subtitleOutput.max_translation_languages ?? 2), 10) || 0)
  );
  if (!Array.isArray(subtitleOutput.display_order)) {
    subtitleOutput.display_order = ["source", ...translation.target_languages];
  }
  subtitleOutput.display_order = subtitleOutput.display_order
    .map((item) => String(item || "").toLowerCase())
    .filter((item, index, array) => (item === "source" || translation.target_languages.includes(item)) && array.indexOf(item) === index);
  if (!subtitleOutput.display_order.includes("source")) {
    subtitleOutput.display_order.push("source");
  }
  translation.target_languages.forEach((code) => {
    if (!subtitleOutput.display_order.includes(code)) {
      subtitleOutput.display_order.push(code);
    }
  });

  if (!normalized.subtitle_style || typeof normalized.subtitle_style !== "object") {
    normalized.subtitle_style = {};
  }

  return normalized;
}
