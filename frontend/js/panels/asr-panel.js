import { collectElements } from "../core/dom.js";
import { createPanelMount } from "../core/panel-mount.js";
import { createAsrConfigMutators, renderAsrPanel } from "./asr/asr-panel-render.js";
import {
  getCurrentLocale,
  getRecognitionModeLabel,
  isBrowserRecognitionMode,
  isDesktopBrowserQuickStartLocked,
} from "../dashboard/helpers.js";

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
    localAsrProviderRow: "#local-asr-provider-row",
    localAsrProviderSelect: "#local-asr-provider-select",
    audioInputSelect: "#audio-input-select",
    audioInputMeta: "#audio-input-meta",
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
  const { mutateRealtimeFromControls, mutateSimpleTuning } = createAsrConfigMutators(elements, actions);
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
    logger(
      getCurrentLocale() === "ru"
        ? "[asr] окно Web Speech: при следующем открытии worker будет использован выбранный браузер (desktop)"
        : "[asr] Web Speech worker will use the selected browser on next open (desktop)"
    );
  });
  add(elements.localAsrProviderSelect, "change", () => {
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
  add(elements.audioInputSelect, "change", () => {
    actions.setSelectedAudioInput(elements.audioInputSelect.value || null);
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
      add(element, eventName, mutateRealtimeFromControls);
      add(element, "change", () => {
        mutateRealtimeFromControls();
        logger("[asr] realtime tuning updated locally");
      });
    });

  const onLocaleChanged = () => rerender(store.getState());
  window.addEventListener("sst:locale-changed", onLocaleChanged);
  const onDesktopContext = (event) => {
    const detail = event?.detail;
    if (detail && window.AppState) {
      window.AppState.desktop = { ...window.AppState.desktop, ...detail };
    }
    rerender(store.getState());
  };
  window.addEventListener("sst:desktop-context", onDesktopContext);

  return () => {
    handlers.forEach((off) => off());
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
