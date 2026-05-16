import { fillSelectOptions } from "../../core/dom.js";
import { BROWSER_RECOGNITION_LANGUAGES, SIMPLE_TUNING_OPTIONS } from "../../dashboard/constants.js";
import {
  findClosestSimpleLevel,
  formatSecondsFromMs,
  getCurrentLocale,
  getRecognitionLanguageLabel,
  getSimpleTuningLabel,
  getSimpleTuningOption,
  isBrowserRecognitionMode,
  isDesktopBrowserQuickStartLocked,
  syncRecognitionModeSelectLock,
  parseSecondsToMs,
  setElementVisibility,
  t,
} from "../../dashboard/helpers.js";

export function fillRecognitionLanguages(languageSelect) {
  if (!languageSelect) {
    return;
  }
  fillSelectOptions(languageSelect, BROWSER_RECOGNITION_LANGUAGES, {
    getValue: (item) => item.code,
    getLabel: (item) => getRecognitionLanguageLabel(item.code),
    selectedValue: languageSelect.value,
  });
}

export function fillAudioInputDevices(elements, snapshot) {
  if (!elements.audioInputSelect) {
    return;
  }
  const browserMode = isBrowserRecognitionMode(snapshot.config?.asr?.mode || "local");
  fillSelectOptions(elements.audioInputSelect, snapshot.audioDevices || [], {
    getValue: (device) => device.id,
    getLabel: (device) =>
      `${device.name}${device.is_default ? (getCurrentLocale() === "ru" ? " (по умолчанию)" : " (default)") : ""}`,
    getDataset: (device) => ({
      meta:
        getCurrentLocale() === "ru"
          ? `каналы: ${device.max_input_channels}, частота: ${device.default_samplerate || "n/a"} Гц`
          : `channels: ${device.max_input_channels}, rate: ${device.default_samplerate || "n/a"} Hz`,
    }),
    selectedValue: snapshot.ui.selectedAudioInputId,
  });
  elements.audioInputSelect.disabled = browserMode;
  const selected = elements.audioInputSelect.selectedOptions?.[0];
  if (elements.audioInputMeta) {
    elements.audioInputMeta.textContent = browserMode
      ? t("overview.recognition.browser_mic_note")
      : selected?.dataset.meta || (getCurrentLocale() === "ru" ? "Устройство не выбрано." : "No device selected.");
  }
}

export function createAsrConfigMutators(elements, actions) {
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
      lifecycle.completed_source_ttl_ms = parseSecondsToMs(elements.subtitleCompletedSourceTtl?.value, 4500, 500);
      lifecycle.completed_translation_ttl_ms = parseSecondsToMs(elements.subtitleCompletedTranslationTtl?.value, 4500, 500);
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

  return { mutateRealtimeFromControls, mutateSimpleTuning };
}

export function renderAsrPanel(snapshot, elements) {
  fillRecognitionLanguages(elements.languageSelect);
  if (elements.partialTranscript) {
    elements.partialTranscript.textContent =
      snapshot.transcript.partial || (getCurrentLocale() === "ru" ? "Ожидание речи..." : "Waiting for speech...");
  }
  if (elements.finalTranscript) {
    elements.finalTranscript.textContent = snapshot.transcript.finals?.length
      ? snapshot.transcript.finals.join("\n")
      : getCurrentLocale() === "ru"
        ? "Пока нет завершённого текста."
        : "No final transcript yet.";
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
      const browserHint =
        mode === "browser_google_experimental"
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
  fillAudioInputDevices(elements, snapshot);
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
    elements.simpleAppearanceLabel.textContent = getSimpleTuningLabel(
      "appearance",
      SIMPLE_TUNING_OPTIONS.appearance[appearanceLevel - 1].label
    );
  }
  if (elements.simpleFinishSpeed) {
    elements.simpleFinishSpeed.value = String(finishLevel);
    elements.simpleFinishLabel.textContent = getSimpleTuningLabel("finish", SIMPLE_TUNING_OPTIONS.finish[finishLevel - 1].label);
  }
  if (elements.simpleStability) {
    elements.simpleStability.value = String(stabilityLevel);
    elements.simpleStabilityLabel.textContent = getSimpleTuningLabel(
      "stability",
      SIMPLE_TUNING_OPTIONS.stability[stabilityLevel - 1].label
    );
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
