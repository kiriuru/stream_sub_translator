import { collectElements } from "../core/dom.js";
import { createPanelMount } from "../core/panel-mount.js";
import { createAsrConfigMutators, renderAsrPanel } from "./asr/asr-panel-render.js";
import {
  getRecognitionModeLabel,
  isBrowserRecognitionMode,
  isDesktopBrowserQuickStartLocked,
  t,
} from "../dashboard/helpers.js";
import { mountFieldHelpButtons } from "../ui/field-help-popover.js";

const collectAsrElements = (root) =>
  collectElements(root, {
    partialTranscript: "#partial-transcript",
    finalTranscript: "#final-transcript",
    modeSelect: "#recognition-mode-select",
    languageRow: "#recognition-language-row",
    languageSelect: "#recognition-language-select",
    workerBrowserRow: "#recognition-worker-browser-row",
    workerBrowserSelect: "#recognition-worker-browser-select",
    workerBrowserWebNote: "#recognition-worker-browser-web-note",
    modeHint: "#recognition-mode-hint",
    audioInputSelect: "#audio-input-select",
    audioInputMeta: "#audio-input-meta",
    parakeetLatencyPresetRow: "#parakeet-latency-preset-row",
    parakeetLatencyPreset: "#parakeet-latency-preset",
    rtToolsLocalParakeetExtras: "#rt-tools-local-parakeet-extras",
    rtToolsLatencyPreset: "#rt-tools-latency-preset",
    rtStreamingDecode: "#rt-streaming-decode",
    rtPartialEmitMode: "#rt-partial-emit-mode",
    rtPartialMinNewWords: "#rt-partial-min-new-words",
    simpleAppearanceSpeed: "#simple-appearance-speed",
    simpleAppearanceLabel: "#simple-appearance-label",
    simpleFinishSpeed: "#simple-finish-speed",
    simpleFinishLabel: "#simple-finish-label",
    simpleStability: "#simple-stability",
    simpleStabilityLabel: "#simple-stability-label",
    rtVadMode: "#rt-vad-mode",
    rtPartialEmitInterval: "#rt-partial-emit-interval",
    rtMinSpeech: "#rt-min-speech",
    rtSilenceHold: "#rt-silence-hold",
    rtFinalizationHold: "#rt-finalization-hold",
    rtMaxSegment: "#rt-max-segment",
    rtPartialMinDelta: "#rt-partial-min-delta",
    rtPartialCoalescing: "#rt-partial-coalescing",
    rtChunkWindow: "#rt-chunk-window",
    rtChunkOverlap: "#rt-chunk-overlap",
    rtEnergyGateEnabled: "#rt-energy-gate-enabled",
    rtMinRms: "#rt-min-rms",
    rtMinVoicedRatio: "#rt-min-voiced-ratio",
    rtFirstPartialMinSpeech: "#rt-first-partial-min-speech",
    subtitleCompletedSourceTtl: "#subtitle-completed-source-ttl",
    subtitleCompletedTranslationTtl: "#subtitle-completed-translation-ttl",
    subtitleSyncExpiry: "#subtitle-sync-source-translation-expiry",
    subtitleAllowEarlyReplace: "#subtitle-allow-early-replace",
    rnnoiseEnabled: "#asr-rnnoise-enabled",
    rnnoiseStrength: "#asr-rnnoise-strength",
    rnnoiseStrengthLabel: "#asr-rnnoise-strength-label",
  });

function bindAsrEvents(elements, { store, actions, logger }, rerender) {
  const { mutateRealtimeFromControls, mutateSimpleTuning, applyParakeetLatencyPreset } =
    createAsrConfigMutators(elements, actions);
  const handlers = [];
  const add = (element, event, handler) => {
    if (!element) {
      return;
    }
    element.addEventListener(event, handler);
    handlers.push(() => element.removeEventListener(event, handler));
  };

  add(elements.modeSelect, "change", () => {
    const nextMode = elements.modeSelect.value || "local";
    const snapshot = store.getState();
    if (isDesktopBrowserQuickStartLocked(snapshot.config, snapshot.desktop) && nextMode === "local") {
      const fallback = snapshot.config?.asr?.mode || "browser_google";
      elements.modeSelect.value = isBrowserRecognitionMode(fallback) ? fallback : "browser_google";
      logger("[asr] local Parakeet is locked for this desktop quick start profile");
      return;
    }
    actions.mutateConfig((draft) => {
      draft.asr.mode = nextMode;
    });
    logger(`[asr] mode -> ${getRecognitionModeLabel(elements.modeSelect.value)}`);
  });
  add(elements.languageSelect, "change", () => {
    actions.mutateConfig((draft) => {
      draft.asr.browser.recognition_language = elements.languageSelect.value || "ru-RU";
    });
    logger(`[asr] browser recognition language -> ${elements.languageSelect.value}`);
  });
  add(elements.workerBrowserSelect, "change", () => {
    const value = elements.workerBrowserSelect.value || "auto";
    actions.mutateConfig((draft) => {
      draft.asr.browser.worker_launch_browser = value;
    });
    logger(t("asr.worker_browser_next_open_log"));
  });
  add(elements.audioInputSelect, "change", () => {
    actions.setSelectedAudioInput(elements.audioInputSelect.value || null);
  });

  add(elements.rtToolsLatencyPreset, "change", () => {
    const presetId = elements.rtToolsLatencyPreset?.value || "custom";
    if (presetId === "custom") {
      return;
    }
    applyParakeetLatencyPreset(presetId);
    rerender(store.getState());
    logger(`[asr] tools latency preset -> ${presetId}`);
  });

  add(elements.parakeetLatencyPreset, "change", () => {
    const presetId = elements.parakeetLatencyPreset?.value || "custom";
    if (presetId === "custom") {
      return;
    }
    applyParakeetLatencyPreset(presetId);
    rerender(store.getState());
    logger(`[asr] parakeet latency preset -> ${presetId}`);
  });

  [elements.simpleAppearanceSpeed, elements.simpleFinishSpeed, elements.simpleStability]
    .filter(Boolean)
    .forEach((element) => {
      add(element, "input", mutateSimpleTuning);
      add(element, "change", () => {
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
    elements.rtStreamingDecode,
    elements.rtPartialEmitMode,
    elements.rtPartialMinNewWords,
    elements.subtitleCompletedSourceTtl,
    elements.subtitleCompletedTranslationTtl,
    elements.subtitleSyncExpiry,
    elements.subtitleAllowEarlyReplace,
    elements.rnnoiseEnabled,
    elements.rnnoiseStrength,
  ]
    .filter(Boolean)
    .forEach((element) => {
      const isCheckboxOrSelect = element.type === "checkbox" || element.tagName === "SELECT";
      const liveEvent = isCheckboxOrSelect ? "change" : "input";
      // For text/number inputs we want a live "input" sync as the user types
      // and an extra "change" listener that also writes the log line on
      // commit (blur / Enter). For checkbox/select there is only "change",
      // so binding both would fire the mutator twice per toggle and double
      // every store update.
      if (isCheckboxOrSelect) {
        add(element, "change", () => {
          mutateRealtimeFromControls();
          logger("[asr] realtime tuning updated locally");
        });
        return;
      }
      add(element, liveEvent, mutateRealtimeFromControls);
      add(element, "change", () => {
        mutateRealtimeFromControls();
        logger("[asr] realtime tuning updated locally");
      });
    });

  const onLocaleChanged = () => rerender(store.getState());
  window.addEventListener("sst:locale-changed", onLocaleChanged);
  const onDesktopContext = () => {
    rerender(store.getState());
  };
  window.addEventListener("sst:desktop-context", onDesktopContext);

  const asrAdvancedPanel = document.querySelector('[data-tab-panel="asr_advanced"]');
  const unmountFieldHelp = mountFieldHelpButtons(asrAdvancedPanel, t);

  return () => {
    handlers.forEach((off) => off());
    unmountFieldHelp();
    window.removeEventListener("sst:locale-changed", onLocaleChanged);
    window.removeEventListener("sst:desktop-context", onDesktopContext);
  };
}

const mountAsrPanelImpl = createPanelMount({
  collectElements: collectAsrElements,
  render: renderAsrPanel,
  bindEvents: bindAsrEvents,
});

export function mountAsrPanel(root, context) {
  return mountAsrPanelImpl(root, context);
}
