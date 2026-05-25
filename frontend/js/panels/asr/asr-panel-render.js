import { fillSelectOptions, setCheckedIfChanged, setInputValueIfChanged } from "../../core/dom.js";
import { BROWSER_RECOGNITION_LANGUAGES, SIMPLE_TUNING_OPTIONS } from "../../dashboard/constants.js";
import {
  applyParakeetLatencyPresetToDraft,
  markParakeetLatencyPresetCustom,
  getParakeetSimpleTuningLevelsForRender,
  resolveParakeetLatencyPresetFromConfig,
} from "../../normalizers/parakeet-latency-presets.js";
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

function isLocalParakeetMode(config) {
  const mode = config?.asr?.mode || "local";
  return !isBrowserRecognitionMode(mode) && !isDesktopBrowserQuickStartLocked(config);
}

// Parakeet tuning controls (latency preset, incremental streaming decode,
// partial_emit_mode, partial_min_new_words, …) are exposed whenever the
// install can run Parakeet at all. The Browser Speech quick-start lock
// pins the install to Web Speech only — in that case Parakeet is genuinely
// unavailable and the controls stay hidden. In every other state (including
// when the user is currently using browser_google mode), allow tuning
// Parakeet ahead of a mode switch. Matches the 0.4.1 main-branch
// expectation that these knobs are visible in the standard layout for
// any non-quick-start install regardless of the currently selected mode.
function isLocalParakeetTuningAvailable(config) {
  return !isDesktopBrowserQuickStartLocked(config);
}

export function createAsrConfigMutators(elements, actions) {
  function mutateRealtimeFromControls() {
    actions.mutateConfig((draft) => {
      markParakeetLatencyPresetCustom(draft);
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
      draft.asr.realtime.streaming_decode = elements.rtStreamingDecode ? Boolean(elements.rtStreamingDecode.checked) : true;
      const pem = String(elements.rtPartialEmitMode?.value || "word_growth").trim().toLowerCase();
      draft.asr.realtime.partial_emit_mode = pem === "char_delta" ? "char_delta" : "word_growth";
      draft.asr.realtime.partial_min_new_words = Math.max(
        1,
        Number.parseInt(String(elements.rtPartialMinNewWords?.value || "1"), 10) || 1
      );
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
      markParakeetLatencyPresetCustom(draft);
      const realtime = draft.asr.realtime;
      const lifecycle = draft.subtitle_lifecycle;
      const appearance = getSimpleTuningOption("appearance", elements.simpleAppearanceSpeed?.value ?? 3);
      const finish = getSimpleTuningOption("finish", elements.simpleFinishSpeed?.value ?? 3);
      const stability = getSimpleTuningOption("stability", elements.simpleStability?.value ?? 3);
      realtime.partial_emit_interval_ms = appearance.partial_emit_interval_ms;
      realtime.min_speech_ms = appearance.min_speech_ms;
      realtime.first_partial_min_speech_ms = appearance.min_speech_ms;
      realtime.silence_hold_ms = finish.silence_hold_ms;
      realtime.finalization_hold_ms = finish.pause_to_finalize_ms;
      lifecycle.pause_to_finalize_ms = finish.pause_to_finalize_ms;
      realtime.partial_min_delta_chars = stability.partial_min_delta_chars;
      realtime.partial_coalescing_ms = stability.partial_coalescing_ms;
    });
    if (elements.parakeetLatencyPreset) {
      elements.parakeetLatencyPreset.value = "custom";
    }
    if (elements.rtToolsLatencyPreset) {
      elements.rtToolsLatencyPreset.value = "custom";
    }
  }

  function applyParakeetLatencyPreset(presetId) {
    if (!presetId || presetId === "custom") {
      return;
    }
    actions.mutateConfig((draft) => {
      applyParakeetLatencyPresetToDraft(draft, presetId);
    });
  }

  return { mutateRealtimeFromControls, mutateSimpleTuning, applyParakeetLatencyPreset };
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
  const parakeetTuningVisible = isLocalParakeetTuningAvailable(config);
  setElementVisibility(elements.parakeetLatencyPresetRow, parakeetTuningVisible);
  setElementVisibility(elements.rtToolsLocalParakeetExtras, parakeetTuningVisible);
  const realtime = config.asr?.realtime || {};
  const lifecycle = config.subtitle_lifecycle || {};
  if (elements.parakeetLatencyPreset) {
    elements.parakeetLatencyPreset.value = resolveParakeetLatencyPresetFromConfig(realtime, lifecycle);
  }
  if (elements.rtToolsLatencyPreset) {
    elements.rtToolsLatencyPreset.value = resolveParakeetLatencyPresetFromConfig(realtime, lifecycle);
  }
  const presetResolved = resolveParakeetLatencyPresetFromConfig(realtime, lifecycle);
  const appearanceClosest = findClosestSimpleLevel("appearance", realtime);
  const finishClosest = findClosestSimpleLevel("finish", {
    silence_hold_ms: realtime.silence_hold_ms,
    pause_to_finalize_ms: lifecycle.pause_to_finalize_ms,
  });
  const stabilityClosest = findClosestSimpleLevel("stability", realtime);
  const tuningLevels = getParakeetSimpleTuningLevelsForRender(
    presetResolved,
    appearanceClosest,
    finishClosest,
    stabilityClosest
  );
  if (elements.simpleAppearanceSpeed) {
    setInputValueIfChanged(elements.simpleAppearanceSpeed, tuningLevels.appearance);
    elements.simpleAppearanceLabel.textContent = getSimpleTuningLabel(
      "appearance",
      SIMPLE_TUNING_OPTIONS.appearance[tuningLevels.appearance - 1].label
    );
  }
  if (elements.simpleFinishSpeed) {
    setInputValueIfChanged(elements.simpleFinishSpeed, tuningLevels.finish);
    elements.simpleFinishLabel.textContent = getSimpleTuningLabel(
      "finish",
      SIMPLE_TUNING_OPTIONS.finish[tuningLevels.finish - 1].label
    );
  }
  if (elements.simpleStability) {
    setInputValueIfChanged(elements.simpleStability, tuningLevels.stability);
    elements.simpleStabilityLabel.textContent = getSimpleTuningLabel(
      "stability",
      SIMPLE_TUNING_OPTIONS.stability[tuningLevels.stability - 1].label
    );
  }
  setCheckedIfChanged(elements.rtStreamingDecode, realtime.streaming_decode !== false);
  if (elements.rtPartialEmitMode) {
    const emitMode = String(realtime.partial_emit_mode || "word_growth").toLowerCase();
    setInputValueIfChanged(elements.rtPartialEmitMode, emitMode === "char_delta" ? "char_delta" : "word_growth");
  }
  if (elements.rtPartialMinNewWords) {
    setInputValueIfChanged(
      elements.rtPartialMinNewWords,
      Math.max(1, Number(realtime.partial_min_new_words ?? 1) || 1)
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
      setInputValueIfChanged(elements[key], value);
    }
  });
  setCheckedIfChanged(elements.rtEnergyGateEnabled, Boolean(realtime.energy_gate_enabled));
  if (elements.subtitleCompletedSourceTtl) {
    setInputValueIfChanged(
      elements.subtitleCompletedSourceTtl,
      formatSecondsFromMs(lifecycle.completed_source_ttl_ms ?? 4500, 4500)
    );
  }
  if (elements.subtitleCompletedTranslationTtl) {
    setInputValueIfChanged(
      elements.subtitleCompletedTranslationTtl,
      formatSecondsFromMs(lifecycle.completed_translation_ttl_ms ?? 4500, 4500)
    );
  }
  setCheckedIfChanged(elements.subtitleSyncExpiry, lifecycle.sync_source_and_translation_expiry !== false);
  setCheckedIfChanged(elements.subtitleAllowEarlyReplace, lifecycle.allow_early_replace_on_next_final !== false);
  setCheckedIfChanged(elements.rnnoiseEnabled, Boolean(config.asr?.rnnoise_enabled));
  if (elements.rnnoiseStrength) {
    setInputValueIfChanged(elements.rnnoiseStrength, config.asr?.rnnoise_strength ?? 70);
    elements.rnnoiseStrength.disabled = !Boolean(config.asr?.rnnoise_enabled);
  }
  if (elements.rnnoiseStrengthLabel) {
    elements.rnnoiseStrengthLabel.textContent = `${config.asr?.rnnoise_strength ?? 70}%`;
  }
}
