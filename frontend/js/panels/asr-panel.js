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
  isDesktopBrowserQuickStartLocked,
  syncRecognitionModeSelectLock,
  parseSecondsToMs,
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
    workerBrowserRow: root.querySelector("#recognition-worker-browser-row"),
    workerBrowserSelect: root.querySelector("#recognition-worker-browser-select"),
    workerBrowserWebNote: root.querySelector("#recognition-worker-browser-web-note"),
    modeHint: root.querySelector("#recognition-mode-hint"),
    localAsrProviderRow: root.querySelector("#local-asr-provider-row"),
    localAsrProviderSelect: root.querySelector("#local-asr-provider-select"),
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
    if (!elements.languageSelect) {
      return;
    }
    const previous = String(elements.languageSelect.value || "");
    elements.languageSelect.innerHTML = "";
    BROWSER_RECOGNITION_LANGUAGES.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.code;
      option.textContent = getRecognitionLanguageLabel(item.code);
      elements.languageSelect.appendChild(option);
    });
    const codes = BROWSER_RECOGNITION_LANGUAGES.map((item) => item.code);
    if (previous && codes.includes(previous)) {
      elements.languageSelect.value = previous;
    }
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
      lifecycle.completed_source_ttl_ms = parseSecondsToMs(
        elements.subtitleCompletedSourceTtl?.value,
        4500,
        500
      );
      lifecycle.completed_translation_ttl_ms = parseSecondsToMs(
        elements.subtitleCompletedTranslationTtl?.value,
        4500,
        500
      );
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
    const quickStartLocked = isDesktopBrowserQuickStartLocked(config);
    const mode = config.asr?.mode || "local";
    const browserMode = isBrowserRecognitionMode(mode);
    const localProvider = config.asr?.provider_preference || "official_eu_parakeet_low_latency";
    if (elements.modeSelect) {
      syncRecognitionModeSelectLock(elements.modeSelect, quickStartLocked);
      elements.modeSelect.value = browserMode ? mode : quickStartLocked ? "browser_google" : mode;
    }
    if (elements.languageSelect) {
      elements.languageSelect.value = config.asr?.browser?.recognition_language || "ru-RU";
    }
    if (elements.workerBrowserSelect) {
      const wb = String(config.asr?.browser?.worker_launch_browser || "auto").toLowerCase();
      const allowed = ["auto", "google_chrome"];
      elements.workerBrowserSelect.value = allowed.includes(wb) ? wb : "auto";
    }
    const launcherPicksWorkerBrowser = Boolean(window.DesktopBridge?.controlsWorkerBrowserLaunch?.());
    setElementVisibility(elements.languageRow, browserMode);
    setElementVisibility(elements.workerBrowserRow, browserMode && launcherPicksWorkerBrowser);
    setElementVisibility(elements.workerBrowserWebNote, browserMode && !launcherPicksWorkerBrowser);
    if (elements.workerBrowserWebNote) {
      elements.workerBrowserWebNote.textContent = t("overview.recognition.worker_browser.web_hint");
    }
    setElementVisibility(elements.localAsrProviderRow, !browserMode && !quickStartLocked);
    if (elements.localAsrProviderSelect) {
      elements.localAsrProviderSelect.value = localProvider;
      elements.localAsrProviderSelect.disabled = quickStartLocked || browserMode;
    }
    if (elements.modeHint) {
      if (quickStartLocked) {
        elements.modeHint.textContent = t("overview.recognition.hint.browser_quick_start_locked");
        setElementVisibility(elements.modeHint, true);
      } else if (browserMode) {
        const browserHint = mode === "browser_google_experimental"
          ? t("overview.recognition.hint.browser_google_experimental")
          : t("overview.recognition.hint.browser_google");
        elements.modeHint.textContent = browserHint;
        setElementVisibility(elements.modeHint, Boolean(browserHint));
      } else {
        const localHint = t("overview.recognition.hint.local");
        elements.modeHint.textContent = localHint;
        setElementVisibility(elements.modeHint, Boolean(localHint));
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
          ? t("overview.recognition.browser_mic_note")
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
    const nextMode = elements.modeSelect.value || "local";
    if (isDesktopBrowserQuickStartLocked(store.getState().config) && nextMode === "local") {
      const fallback = store.getState().config?.asr?.mode || "browser_google";
      elements.modeSelect.value = isBrowserRecognitionMode(fallback) ? fallback : "browser_google";
      logger("[asr] local Parakeet is locked for this desktop quick start profile");
      return;
    }
    actions.mutateConfig((draft) => {
      draft.asr.mode = nextMode;
    });
    logger(`[asr] mode -> ${getRecognitionModeLabel(elements.modeSelect.value)}`);
  });
  elements.languageSelect?.addEventListener("change", () => {
    actions.mutateConfig((draft) => {
      draft.asr.browser.recognition_language = elements.languageSelect.value || "ru-RU";
    });
    logger(`[asr] browser recognition language -> ${elements.languageSelect.value}`);
  });
  elements.workerBrowserSelect?.addEventListener("change", () => {
    const value = elements.workerBrowserSelect.value || "auto";
    actions.mutateConfig((draft) => {
      draft.asr.browser.worker_launch_browser = value;
    });
    const label =
      getCurrentLocale() === "ru"
        ? "[asr] окно Web Speech: при следующем открытии worker будет использован выбранный браузер (desktop)"
        : "[asr] Web Speech worker will use the selected browser on next open (desktop)";
    logger(label);
  });
  elements.localAsrProviderSelect?.addEventListener("change", () => {
    if (isDesktopBrowserQuickStartLocked(store.getState().config)) {
      logger("[asr] backend provider selection is locked for this desktop quick start profile");
      return;
    }
    actions.mutateConfig((draft) => {
      const nextProvider = elements.localAsrProviderSelect.value || "official_eu_parakeet_low_latency";
      draft.asr.provider_preference = nextProvider;
      draft.asr.mode = "local";
    });
    logger(`[asr] backend provider -> ${elements.localAsrProviderSelect.value}`);
  });
  elements.audioInputSelect?.addEventListener("change", () => {
    actions.setSelectedAudioInput(elements.audioInputSelect.value || null);
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
  const onLocaleChanged = () => {
    fillRecognitionLanguages();
    render(store.getState());
  };
  window.addEventListener("sst:locale-changed", onLocaleChanged);
  const onDesktopContext = (event) => {
    const detail = event?.detail;
    if (detail && window.AppState) {
      window.AppState.desktop = { ...window.AppState.desktop, ...detail };
    }
    render(store.getState());
  };
  window.addEventListener("sst:desktop-context", onDesktopContext);
  return () => {
    window.removeEventListener("sst:locale-changed", onLocaleChanged);
    window.removeEventListener("sst:desktop-context", onDesktopContext);
    unsubscribe();
  };
}
