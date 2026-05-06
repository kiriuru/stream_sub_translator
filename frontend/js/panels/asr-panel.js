import { subscribe } from "../core/store.js";
import {
  BROWSER_RECOGNITION_LANGUAGES,
  SIMPLE_TUNING_OPTIONS,
} from "../dashboard/constants.js";
import {
  findClosestSimpleLevel,
  formatSecondsFromMs,
  getCurrentLocale,
  getRecognitionLanguageLabel,
  getRecognitionModeLabel,
  getSimpleTuningLabel,
  getSimpleTuningOption,
  isBrowserRecognitionMode,
  setElementVisibility,
  t,
} from "../dashboard/helpers.js";

export function mountAsrPanel(root, { store, actions, logger }) {
  const elements = {
    partialTranscript: root.querySelector("#partial-transcript"),
    finalTranscript: root.querySelector("#final-transcript"),
    modeSelect: root.querySelector("#recognition-mode-select"),
    languageRow: root.querySelector("#recognition-language-row"),
    languageSelect: root.querySelector("#recognition-language-select"),
    modeHint: root.querySelector("#recognition-mode-hint"),
    localAsrProviderRow: root.querySelector("#local-asr-provider-row"),
    localAsrProviderSelect: root.querySelector("#local-asr-provider-select"),
    googleLegacyWarning: root.querySelector("#google-legacy-http-warning"),
    googleLegacySettings: root.querySelector("#google-legacy-http-settings"),
    googleLegacyEnabled: root.querySelector("#google-legacy-http-enabled"),
    googleLegacyLanguage: root.querySelector("#google-legacy-http-language"),
    googleLegacyEndpointHost: root.querySelector("#google-legacy-http-endpoint-host"),
    googleLegacyProfanityFilter: root.querySelector("#google-legacy-http-profanity-filter"),
    googleLegacyConnectTimeoutMs: root.querySelector("#google-legacy-http-connect-timeout-ms"),
    googleLegacySendTimeoutMs: root.querySelector("#google-legacy-http-send-timeout-ms"),
    googleLegacyRecvTimeoutMs: root.querySelector("#google-legacy-http-recv-timeout-ms"),
    googleLegacyMaxQueueDepth: root.querySelector("#google-legacy-http-max-queue-depth"),
    audioInputSelect: root.querySelector("#audio-input-select"),
    audioInputMeta: root.querySelector("#audio-input-meta"),
    simpleAppearanceSpeed: root.querySelector("#simple-appearance-speed"),
    simpleAppearanceLabel: root.querySelector("#simple-appearance-label"),
    simpleFinishSpeed: root.querySelector("#simple-finish-speed"),
    simpleFinishLabel: root.querySelector("#simple-finish-label"),
    simpleStability: root.querySelector("#simple-stability"),
    simpleStabilityLabel: root.querySelector("#simple-stability-label"),
    rtVadMode: root.querySelector("#rt-vad-mode"),
    rtPartialEmitInterval: root.querySelector("#rt-partial-emit-interval"),
    rtMinSpeech: root.querySelector("#rt-min-speech"),
    rtSilenceHold: root.querySelector("#rt-silence-hold"),
    rtFinalizationHold: root.querySelector("#rt-finalization-hold"),
    rtMaxSegment: root.querySelector("#rt-max-segment"),
    rtPartialMinDelta: root.querySelector("#rt-partial-min-delta"),
    rtPartialCoalescing: root.querySelector("#rt-partial-coalescing"),
    rtChunkWindow: root.querySelector("#rt-chunk-window"),
    rtChunkOverlap: root.querySelector("#rt-chunk-overlap"),
    rtEnergyGateEnabled: root.querySelector("#rt-energy-gate-enabled"),
    rtMinRms: root.querySelector("#rt-min-rms"),
    rtMinVoicedRatio: root.querySelector("#rt-min-voiced-ratio"),
    rtFirstPartialMinSpeech: root.querySelector("#rt-first-partial-min-speech"),
    subtitleCompletedSourceTtl: root.querySelector("#subtitle-completed-source-ttl"),
    subtitleCompletedTranslationTtl: root.querySelector("#subtitle-completed-translation-ttl"),
    subtitleSyncExpiry: root.querySelector("#subtitle-sync-source-translation-expiry"),
    subtitleAllowEarlyReplace: root.querySelector("#subtitle-allow-early-replace"),
    rnnoiseEnabled: root.querySelector("#asr-rnnoise-enabled"),
    rnnoiseStrength: root.querySelector("#asr-rnnoise-strength"),
    rnnoiseStrengthLabel: root.querySelector("#asr-rnnoise-strength-label"),
  };

  function fillRecognitionLanguages() {
    if (!elements.languageSelect || elements.languageSelect.options.length) {
      return;
    }
    BROWSER_RECOGNITION_LANGUAGES.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.code;
      option.textContent = getRecognitionLanguageLabel(item.code);
      elements.languageSelect.appendChild(option);
    });
  }

  function mutateRealtimeFromControls() {
    actions.mutateConfig((draft) => {
      const realtime = draft.asr.realtime;
      const lifecycle = draft.subtitle_lifecycle;
      draft.asr.rnnoise_enabled = Boolean(elements.rnnoiseEnabled?.checked);
      draft.asr.rnnoise_strength = Number(elements.rnnoiseStrength?.value || 70);
      realtime.vad_mode = Number(elements.rtVadMode?.value || 2);
      realtime.partial_emit_interval_ms = Number(elements.rtPartialEmitInterval?.value || 450);
      realtime.min_speech_ms = Number(elements.rtMinSpeech?.value || 180);
      realtime.silence_hold_ms = Number(elements.rtSilenceHold?.value || 180);
      realtime.finalization_hold_ms = Number(elements.rtFinalizationHold?.value || 350);
      realtime.max_segment_ms = Number(elements.rtMaxSegment?.value || 5500);
      realtime.partial_min_delta_chars = Number(elements.rtPartialMinDelta?.value || 12);
      realtime.partial_coalescing_ms = Number(elements.rtPartialCoalescing?.value || 160);
      realtime.chunk_window_ms = Number(elements.rtChunkWindow?.value || 0);
      realtime.chunk_overlap_ms = Number(elements.rtChunkOverlap?.value || 0);
      realtime.energy_gate_enabled = Boolean(elements.rtEnergyGateEnabled?.checked);
      realtime.min_rms_for_recognition = Number(elements.rtMinRms?.value || 0.0018);
      realtime.min_voiced_ratio = Number(elements.rtMinVoicedRatio?.value || 0);
      realtime.first_partial_min_speech_ms = Number(elements.rtFirstPartialMinSpeech?.value || realtime.min_speech_ms);
      lifecycle.completed_source_ttl_ms = Math.round(Number(elements.subtitleCompletedSourceTtl?.value || 4.5) * 1000);
      lifecycle.completed_translation_ttl_ms = Math.round(Number(elements.subtitleCompletedTranslationTtl?.value || 4.5) * 1000);
      lifecycle.sync_source_and_translation_expiry = Boolean(elements.subtitleSyncExpiry?.checked);
      lifecycle.allow_early_replace_on_next_final = Boolean(elements.subtitleAllowEarlyReplace?.checked);
      lifecycle.pause_to_finalize_ms = realtime.finalization_hold_ms;
      lifecycle.hard_max_phrase_ms = realtime.max_segment_ms;
    });
  }

  function mutateSimpleTuning() {
    actions.mutateConfig((draft) => {
      const realtime = draft.asr.realtime;
      const lifecycle = draft.subtitle_lifecycle;
      const appearance = getSimpleTuningOption("appearance", elements.simpleAppearanceSpeed?.value ?? 3);
      const finish = getSimpleTuningOption("finish", elements.simpleFinishSpeed?.value ?? 3);
      const stability = getSimpleTuningOption("stability", elements.simpleStability?.value ?? 3);
      realtime.partial_emit_interval_ms = appearance.partial_emit_interval_ms;
      realtime.min_speech_ms = appearance.min_speech_ms;
      realtime.silence_hold_ms = finish.silence_hold_ms;
      realtime.finalization_hold_ms = finish.pause_to_finalize_ms;
      lifecycle.pause_to_finalize_ms = finish.pause_to_finalize_ms;
      realtime.partial_min_delta_chars = stability.partial_min_delta_chars;
      realtime.partial_coalescing_ms = stability.partial_coalescing_ms;
    });
  }

  function mutateGoogleLegacyFromControls() {
    actions.mutateConfig((draft) => {
      const provider = draft.asr.google_legacy_http;
      provider.enabled = Boolean(elements.googleLegacyEnabled?.checked);
      provider.language = String(elements.googleLegacyLanguage?.value || "ru-RU").trim() || "ru-RU";
      provider.endpoint_host = String(elements.googleLegacyEndpointHost?.value || "").trim();
      provider.profanity_filter = Boolean(elements.googleLegacyProfanityFilter?.checked);
      provider.connect_timeout_ms = Number(elements.googleLegacyConnectTimeoutMs?.value || 10000);
      provider.send_timeout_ms = Number(elements.googleLegacySendTimeoutMs?.value || 10000);
      provider.recv_timeout_ms = Number(elements.googleLegacyRecvTimeoutMs?.value || 30000);
      provider.max_queue_depth = Number(elements.googleLegacyMaxQueueDepth?.value || 50);
    });
  }

  function render(snapshot) {
    fillRecognitionLanguages();
    if (elements.partialTranscript) {
      elements.partialTranscript.textContent = snapshot.transcript.partial || (getCurrentLocale() === "ru" ? "Ожидание речи..." : "Waiting for speech...");
    }
    if (elements.finalTranscript) {
      elements.finalTranscript.textContent = snapshot.transcript.finals?.length
        ? snapshot.transcript.finals.join("\n")
        : (getCurrentLocale() === "ru" ? "Пока нет завершённого текста." : "No final transcript yet.");
    }
    const config = snapshot.config;
    if (!config) {
      return;
    }
    const mode = config.asr?.mode || "local";
    const browserMode = isBrowserRecognitionMode(mode);
    const localProvider = config.asr?.provider_preference || "official_eu_parakeet_low_latency";
    const googleLegacyProvider = config.asr?.google_legacy_http || {};
    const googleLegacySelected = localProvider === "google_legacy_http_experimental";
    if (elements.modeSelect) {
      elements.modeSelect.value = mode;
    }
    if (elements.languageSelect) {
      elements.languageSelect.value = config.asr?.browser?.recognition_language || "ru-RU";
    }
    setElementVisibility(elements.languageRow, browserMode);
    setElementVisibility(elements.localAsrProviderRow, true);
    setElementVisibility(elements.googleLegacyWarning, googleLegacySelected);
    setElementVisibility(elements.googleLegacySettings, googleLegacySelected);
    if (elements.localAsrProviderSelect) {
      elements.localAsrProviderSelect.value = localProvider;
    }
    if (elements.googleLegacyEnabled) {
      elements.googleLegacyEnabled.checked = Boolean(googleLegacyProvider.enabled);
    }
    if (elements.googleLegacyLanguage) {
      elements.googleLegacyLanguage.value = googleLegacyProvider.language || "ru-RU";
    }
    if (elements.googleLegacyEndpointHost) {
      elements.googleLegacyEndpointHost.value = googleLegacyProvider.endpoint_host || "";
    }
    if (elements.googleLegacyProfanityFilter) {
      elements.googleLegacyProfanityFilter.checked = Boolean(googleLegacyProvider.profanity_filter);
    }
    if (elements.googleLegacyConnectTimeoutMs) {
      elements.googleLegacyConnectTimeoutMs.value = String(googleLegacyProvider.connect_timeout_ms ?? 10000);
    }
    if (elements.googleLegacySendTimeoutMs) {
      elements.googleLegacySendTimeoutMs.value = String(googleLegacyProvider.send_timeout_ms ?? 10000);
    }
    if (elements.googleLegacyRecvTimeoutMs) {
      elements.googleLegacyRecvTimeoutMs.value = String(googleLegacyProvider.recv_timeout_ms ?? 30000);
    }
    if (elements.googleLegacyMaxQueueDepth) {
      elements.googleLegacyMaxQueueDepth.value = String(googleLegacyProvider.max_queue_depth ?? 50);
    }
    if (elements.modeHint) {
      if (browserMode) {
        elements.modeHint.textContent = mode === "browser_google_experimental"
          ? t("overview.recognition.hint.browser_google_experimental")
          : t("overview.recognition.hint.browser_google");
      } else if (googleLegacySelected) {
        elements.modeHint.textContent = t("overview.recognition.hint.google_legacy_http");
      } else {
        elements.modeHint.textContent = t("overview.recognition.hint.local");
      }
    }
    if (elements.audioInputSelect) {
      const currentValue = elements.audioInputSelect.value;
      elements.audioInputSelect.innerHTML = "";
      snapshot.audioDevices.forEach((device) => {
        const option = document.createElement("option");
        option.value = device.id;
        option.textContent = `${device.name}${device.is_default ? (getCurrentLocale() === "ru" ? " (по умолчанию)" : " (default)") : ""}`;
        option.dataset.meta = getCurrentLocale() === "ru"
          ? `каналы: ${device.max_input_channels}, частота: ${device.default_samplerate || "n/a"} Гц`
          : `channels: ${device.max_input_channels}, rate: ${device.default_samplerate || "n/a"} Hz`;
        elements.audioInputSelect.appendChild(option);
      });
      elements.audioInputSelect.value = snapshot.ui.selectedAudioInputId || currentValue || "";
      elements.audioInputSelect.disabled = browserMode;
      const selected = elements.audioInputSelect.selectedOptions?.[0];
      if (elements.audioInputMeta) {
        elements.audioInputMeta.textContent = browserMode
          ? (getCurrentLocale() === "ru"
              ? "В Browser Speech микрофон выбирается через значок разрешений в адресной строке браузера."
              : "In Browser Speech mode, switch microphone using the browser permission icon in the address bar.")
          : selected?.dataset.meta || (getCurrentLocale() === "ru" ? "Устройство не выбрано." : "No device selected.");
      }
    }
    const realtime = config.asr?.realtime || {};
    const lifecycle = config.subtitle_lifecycle || {};
    const appearanceLevel = findClosestSimpleLevel("appearance", realtime);
    const finishLevel = findClosestSimpleLevel("finish", {
      silence_hold_ms: realtime.silence_hold_ms,
      pause_to_finalize_ms: lifecycle.pause_to_finalize_ms,
    });
    const stabilityLevel = findClosestSimpleLevel("stability", realtime);
    if (elements.simpleAppearanceSpeed) {
      elements.simpleAppearanceSpeed.value = String(appearanceLevel);
      elements.simpleAppearanceLabel.textContent = getSimpleTuningLabel("appearance", SIMPLE_TUNING_OPTIONS.appearance[appearanceLevel - 1].label);
    }
    if (elements.simpleFinishSpeed) {
      elements.simpleFinishSpeed.value = String(finishLevel);
      elements.simpleFinishLabel.textContent = getSimpleTuningLabel("finish", SIMPLE_TUNING_OPTIONS.finish[finishLevel - 1].label);
    }
    if (elements.simpleStability) {
      elements.simpleStability.value = String(stabilityLevel);
      elements.simpleStabilityLabel.textContent = getSimpleTuningLabel("stability", SIMPLE_TUNING_OPTIONS.stability[stabilityLevel - 1].label);
    }
    const fieldMap = {
      rtVadMode: realtime.vad_mode ?? 2,
      rtPartialEmitInterval: realtime.partial_emit_interval_ms ?? 450,
      rtMinSpeech: realtime.min_speech_ms ?? 180,
      rtSilenceHold: realtime.silence_hold_ms ?? 180,
      rtFinalizationHold: lifecycle.pause_to_finalize_ms ?? realtime.finalization_hold_ms ?? 350,
      rtMaxSegment: lifecycle.hard_max_phrase_ms ?? realtime.max_segment_ms ?? 5500,
      rtPartialMinDelta: realtime.partial_min_delta_chars ?? 12,
      rtPartialCoalescing: realtime.partial_coalescing_ms ?? 160,
      rtChunkWindow: realtime.chunk_window_ms ?? 0,
      rtChunkOverlap: realtime.chunk_overlap_ms ?? 0,
      rtMinRms: realtime.min_rms_for_recognition ?? 0.0018,
      rtMinVoicedRatio: realtime.min_voiced_ratio ?? 0,
      rtFirstPartialMinSpeech: realtime.first_partial_min_speech_ms ?? realtime.min_speech_ms ?? 180,
    };
    Object.entries(fieldMap).forEach(([key, value]) => {
      if (elements[key]) {
        elements[key].value = String(value);
      }
    });
    if (elements.rtEnergyGateEnabled) {
      elements.rtEnergyGateEnabled.checked = Boolean(realtime.energy_gate_enabled);
    }
    if (elements.subtitleCompletedSourceTtl) {
      elements.subtitleCompletedSourceTtl.value = formatSecondsFromMs(lifecycle.completed_source_ttl_ms ?? 4500, 4500);
    }
    if (elements.subtitleCompletedTranslationTtl) {
      elements.subtitleCompletedTranslationTtl.value = formatSecondsFromMs(lifecycle.completed_translation_ttl_ms ?? 4500, 4500);
    }
    if (elements.subtitleSyncExpiry) {
      elements.subtitleSyncExpiry.checked = lifecycle.sync_source_and_translation_expiry !== false;
    }
    if (elements.subtitleAllowEarlyReplace) {
      elements.subtitleAllowEarlyReplace.checked = lifecycle.allow_early_replace_on_next_final !== false;
    }
    if (elements.rnnoiseEnabled) {
      elements.rnnoiseEnabled.checked = Boolean(config.asr?.rnnoise_enabled);
    }
    if (elements.rnnoiseStrength) {
      elements.rnnoiseStrength.value = String(config.asr?.rnnoise_strength ?? 70);
      elements.rnnoiseStrength.disabled = !Boolean(config.asr?.rnnoise_enabled);
    }
    if (elements.rnnoiseStrengthLabel) {
      elements.rnnoiseStrengthLabel.textContent = `${config.asr?.rnnoise_strength ?? 70}%`;
    }
  }

  elements.modeSelect?.addEventListener("change", () => {
    actions.mutateConfig((draft) => {
      draft.asr.mode = elements.modeSelect.value || "local";
    });
    logger(`[asr] mode -> ${getRecognitionModeLabel(elements.modeSelect.value)}`);
  });
  elements.languageSelect?.addEventListener("change", () => {
    actions.mutateConfig((draft) => {
      draft.asr.browser.recognition_language = elements.languageSelect.value || "ru-RU";
    });
    logger(`[asr] browser recognition language -> ${elements.languageSelect.value}`);
  });
  elements.localAsrProviderSelect?.addEventListener("change", () => {
    actions.mutateConfig((draft) => {
      draft.asr.provider_preference = elements.localAsrProviderSelect.value || "official_eu_parakeet_low_latency";
    });
    logger(`[asr] local provider -> ${elements.localAsrProviderSelect.value}`);
  });
  elements.audioInputSelect?.addEventListener("change", () => {
    actions.setSelectedAudioInput(elements.audioInputSelect.value || null);
  });
  [
    elements.googleLegacyEnabled,
    elements.googleLegacyLanguage,
    elements.googleLegacyEndpointHost,
    elements.googleLegacyProfanityFilter,
    elements.googleLegacyConnectTimeoutMs,
    elements.googleLegacySendTimeoutMs,
    elements.googleLegacyRecvTimeoutMs,
    elements.googleLegacyMaxQueueDepth,
  ]
    .filter(Boolean)
    .forEach((element) => {
      const eventName = element.type === "checkbox" ? "change" : "input";
      element.addEventListener(eventName, mutateGoogleLegacyFromControls);
      element.addEventListener("change", () => {
        mutateGoogleLegacyFromControls();
        logger("[asr] google legacy http provider settings updated locally");
      });
    });
  [elements.simpleAppearanceSpeed, elements.simpleFinishSpeed, elements.simpleStability]
    .filter(Boolean)
    .forEach((element) => {
      element.addEventListener("input", mutateSimpleTuning);
      element.addEventListener("change", () => {
        mutateSimpleTuning();
        logger("[asr] simple tuning updated locally");
      });
    });
  [
    elements.rtVadMode,
    elements.rtPartialEmitInterval,
    elements.rtMinSpeech,
    elements.rtSilenceHold,
    elements.rtFinalizationHold,
    elements.rtMaxSegment,
    elements.rtPartialMinDelta,
    elements.rtPartialCoalescing,
    elements.rtChunkWindow,
    elements.rtChunkOverlap,
    elements.rtEnergyGateEnabled,
    elements.rtMinRms,
    elements.rtMinVoicedRatio,
    elements.rtFirstPartialMinSpeech,
    elements.subtitleCompletedSourceTtl,
    elements.subtitleCompletedTranslationTtl,
    elements.subtitleSyncExpiry,
    elements.subtitleAllowEarlyReplace,
    elements.rnnoiseEnabled,
    elements.rnnoiseStrength,
  ]
    .filter(Boolean)
    .forEach((element) => {
      const eventName = element.type === "checkbox" ? "change" : "input";
      element.addEventListener(eventName, mutateRealtimeFromControls);
      element.addEventListener("change", () => {
        mutateRealtimeFromControls();
        logger("[asr] realtime tuning updated locally");
      });
    });

  render(store.getState());
  const unsubscribe = subscribe(render);
  return () => unsubscribe();
}
