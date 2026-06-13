<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { EventsSocket } from "./lib/ws";
  import { fetchRuntimeStatus, isRuntimeActive } from "./lib/runtime";
  import { createAudioPlayer, isNativePlaybackMode } from "./lib/audio-player";
  import { SpeechEngine } from "./lib/speech-engine";
  import {
    bindTtsWindowAudio,
    fetchAudioRoutingMode,
    loadTtsConfig,
    listRustOutputDevices,
    planSubtitleSpeech,
    recoverStuckSpeechQueues,
    resetSubtitlePlanner,
    fetchPythonTtsStatus,
    fetchResourceTelemetry,
    setTtsAudioDevice,
    setTtsChannelAudioDevice,
    setTtsPlaybackMode,
    setTtsEnabled,
    setTtsProvider,
    updateSpeechSettings,
    updateVoiceSettings,
    type TtsAudioRoutingMode,
  } from "./lib/tts-ipc";
  import type { AudioOutputDevice } from "./lib/types";
  import { prependActivityLog } from "./lib/activity-log";
  import {
    findWatchedProcess,
    formatCompactBytes,
    formatHandleCount,
    isResourceTelemetryWarning,
    type ResourceTelemetry,
  } from "./lib/resource-telemetry";
  import { formatSpeechVolume } from "./lib/playback-format";
  import { warmupTtsFetch } from "./lib/google-tts";
  import { startTtsKeepalive, stopTtsKeepalive, updateTtsKeepalive } from "./lib/tts-keepalive";
  import { ttsTrace, ttsTraceText, setTtsFullLoggingEnabled } from "./lib/tts-trace";
  import { buildTtsAudioUrl } from "./lib/google-tts";
  import {
    loadSampleLang,
    saveSampleLang,
    TTS_TEST_LANG_CODES,
  } from "./lib/tts-lang";
  import {
    applyDashboardUiPresentation,
    applyUiThemeFromConfig,
    buildSpeechContextFromConfig,
    fetchSettingsPayload,
    readFullLoggingEnabled,
  } from "./lib/app-settings";
  import {
    getActiveTranslationLines,
    isTranslationSlotSelected,
    reconcileSpeechSlots,
    toggleTranslationSlot,
    type AppSpeechContext,
  } from "./lib/translation-lines";
  import TwitchPanel from "./components/TwitchPanel.svelte";
  import { defaultTwitchSettings } from "./lib/twitch-defaults";
  import { tryCompleteExternalOAuthCallback } from "./lib/external-oauth-callback";
  import {
    subscribeUiConfigSync,
    subscribeUiLocaleSync,
    UI_CONFIG_WS_EVENT,
    uiConfigFromWsPayload,
  } from "../src/lib/ui-config-sync";
  import { normalizeConfigPayload } from "../src/lib/config-normalize";
  import { setLocale, t, locale, getLocale } from "../src/lib/i18n";
  import type { LocaleCode } from "../src/lib/types";
  import type { ConfigPayload } from "../src/lib/types";
  import type {
    RuntimeStatus,
    PythonTtsStatus,
    TtsConfig,
    TtsProvider,
    TtsSpeechSettings,
    TtsTab,
    TwitchChatMessage,
    WsConnectionStatus,
  } from "./lib/types";

  const defaultSpeech = (): TtsSpeechSettings => ({
    speak_source: true,
    speak_translations: true,
    min_chars: 2,
    max_queue_items: 8,
  });

  let externalOAuthDone = $state(false);
  let tab = $state<TtsTab>("speech");
  let version = $state("0.5.0");
  let config = $state<TtsConfig>({
    enabled: true,
    tts_provider: "browser_google",
    playback_mode: "native",
    audio_output_device_id: "",
    speech_rate: 1,
    speech_volume: 1,
    speech: defaultSpeech(),
    twitch: defaultTwitchSettings(),
  });
  let audioOutputs = $state<AudioOutputDevice[]>([
    { id: "", label: "", is_default: true },
  ]);
  let audioRoutingMode = $state<TtsAudioRoutingMode>("browser");
  let sampleText = $state("");
  let sampleTextIsDefault = $state(true);
  let sampleLang = $state("en");
  let lastTestRequest = $state("");
  let appSpeech = $state<AppSpeechContext>({
    translationEnabled: false,
    sourceLang: "en",
    lines: [],
  });
  let status = $state("");
  let error = $state("");
  let activity = $state<string[]>([]);
  let wsStatus = $state<WsConnectionStatus>("disconnected");
  let runtime = $state<RuntimeStatus | null>(null);
  let pythonStatus = $state<PythonTtsStatus | null>(null);
  let resourceTelemetry = $state<ResourceTelemetry | null>(null);
  let telemetryHelpOpen = $state(false);
  let telemetryHelpTriggerEl = $state<HTMLButtonElement | null>(null);
  let telemetryHelpPos = $state({ top: 0, left: 0 });
  const initialEngineConfig = (): TtsConfig => ({
    enabled: true,
    tts_provider: "browser_google",
    playback_mode: "native",
    audio_output_device_id: "",
    speech_rate: 1,
    speech_volume: 1,
    speech: defaultSpeech(),
    twitch: defaultTwitchSettings(),
  });

  let speechEngine = new SpeechEngine(
    "speech",
    createAudioPlayer("speech", initialEngineConfig().playback_mode),
    initialEngineConfig(),
  );
  let twitchEngine = new SpeechEngine(
    "twitch",
    createAudioPlayer("twitch", initialEngineConfig().playback_mode),
    initialEngineConfig(),
  );

  function syncEnginesFromConfig(cfg: TtsConfig) {
    const mode = cfg.playback_mode ?? "native";
    speechEngine.setPlayer(createAudioPlayer("speech", mode));
    twitchEngine.setPlayer(createAudioPlayer("twitch", mode));
    speechEngine.setConfig(cfg);
    twitchEngine.setConfig(cfg);
    speechEngine.setEnabled(cfg.enabled);
    twitchEngine.setEnabled(cfg.enabled);
    refreshKeepaliveContext();
  }

  function clearAllEngines() {
    speechEngine.clear();
    twitchEngine.clear();
  }

  let socket: EventsSocket | null = null;
  let runtimeTimer: ReturnType<typeof setInterval> | null = null;
  let resourceTelemetryTimer: ReturnType<typeof setInterval> | null = null;
  let settingsTimer: ReturnType<typeof setTimeout> | null = null;
  let speechContextTimer: ReturnType<typeof setInterval> | null = null;
  let unsubscribeUiSync: (() => void) | null = null;
  let unsubscribeUiLocale: (() => void) | null = null;
  let runtimeWasActive = false;
  let twitchPanel = $state<TwitchPanel | undefined>(undefined);
  let subtitlePayloadTask: Promise<void> = Promise.resolve();

  const activeTranslationLines = $derived(getActiveTranslationLines(appSpeech));
  const obsResourceTelemetry = $derived(findWatchedProcess(resourceTelemetry, "obs64.exe"));
  const shellResourceTelemetry = $derived(
    findWatchedProcess(resourceTelemetry, "voicesub-app.exe"),
  );
  let currentLocale = $state<LocaleCode>(getLocale());

  $effect(() => {
    const unsubscribe = locale.subscribe((code) => {
      currentLocale = code;
    });
    return unsubscribe;
  });

  function tr(key: string, vars?: Record<string, string | number>) {
    return t(key, vars, currentLocale);
  }

  function toggleTelemetryHelp(event: MouseEvent) {
    event.stopPropagation();
    if (telemetryHelpOpen) {
      telemetryHelpOpen = false;
      return;
    }
    if (telemetryHelpTriggerEl) {
      const rect = telemetryHelpTriggerEl.getBoundingClientRect();
      telemetryHelpPos = {
        top: rect.bottom + 6,
        left: rect.left,
      };
    }
    telemetryHelpOpen = true;
  }

  function closeTelemetryHelp() {
    telemetryHelpOpen = false;
  }

  function applyDashboardLocale(next: LocaleCode) {
    if (getLocale() === next) {
      if (sampleTextIsDefault) {
        refreshDefaultSampleText();
      }
      return;
    }
    setLocale(next);
    if (sampleTextIsDefault) {
      refreshDefaultSampleText();
    }
  }

  function refreshKeepaliveContext() {
    updateTtsKeepalive({
      runtimeActive: isRuntimeActive(runtime),
      ttsEnabled: config.enabled,
      enginesBusy: speechEngine.isBusy() || twitchEngine.isBusy(),
    });
  }

  function handleSpeechEngineEvent(
    event: import("./lib/speech-engine").SpeechEngineEvent,
  ) {
    if (event.type === "started") {
      const providerLabel =
        event.provider === "python_stdlib" ? "python" : "browser";
      activity = prependActivityLog(
        activity,
        `[${event.lang}] ${providerLabel}: ${event.text}`,
      );
      status = tr("tts.status.speaking", { lang: event.lang });
    } else if (event.type === "ended") {
      status = config.enabled ? tr("tts.status.listening") : tr("tts.status.disabled");
    } else if (event.type === "error") {
      error = event.message;
      status = tr("tts.status.error");
    }
    refreshKeepaliveContext();
  }

  function handleTwitchEngineEvent(
    event: import("./lib/speech-engine").SpeechEngineEvent,
  ) {
    if (event.type === "started") {
      activity = prependActivityLog(
        activity,
        `[twitch:${event.lang}] ${event.text}`,
      );
      status = tr("tts.status.speaking_twitch", { lang: event.lang });
    } else if (event.type === "ended") {
      status = config.enabled ? tr("tts.status.listening") : tr("tts.status.disabled");
    } else if (event.type === "error") {
      error = event.message;
      status = tr("tts.status.error");
    }
    refreshKeepaliveContext();
  }

  const unsubscribeSpeech = speechEngine.on(handleSpeechEngineEvent);
  const unsubscribeTwitch = twitchEngine.on(handleTwitchEngineEvent);

  function applySpeechContext(nextSpeech: AppSpeechContext) {
    appSpeech = nextSpeech;
    const activeLines = getActiveTranslationLines(nextSpeech);
    const reconciled = reconcileSpeechSlots(config.speech, activeLines);
    if (
      reconciled.speak_translations !== config.speech.speak_translations ||
      JSON.stringify(reconciled.translation_slots || []) !==
        JSON.stringify(config.speech.translation_slots || [])
    ) {
      config = { ...config, speech: reconciled };
      syncEnginesFromConfig(config);
      queueSpeechSettingsSave();
    }
    ttsTrace("speech", "context_updated", {
      source_lang: nextSpeech.sourceLang,
      translation_enabled: nextSpeech.translationEnabled,
      active_lines: activeLines.length,
    });
  }

  function refreshDefaultSampleText() {
    sampleText = tr("tts.speech.sample_default");
    sampleTextIsDefault = true;
  }

  function handleLocaleChanged(event: Event) {
    const detail = (event as CustomEvent<{ locale?: LocaleCode }>).detail;
    const next = detail?.locale;
    if (next === "en" || next === "ru" || next === "ja" || next === "ko" || next === "zh") {
      applyDashboardLocale(next);
    }
  }

  function applyUiLocaleFromConfig(payload: ConfigPayload) {
    const uiLang = String(payload.ui?.language || "").trim().slice(0, 2).toLowerCase();
    if (uiLang === "en" || uiLang === "ru" || uiLang === "ja" || uiLang === "ko" || uiLang === "zh") {
      applyDashboardLocale(uiLang as LocaleCode);
    }
  }

  function applyDashboardUiSync(partial: ConfigPayload) {
    applyDashboardUiPresentation(partial);
  }

  function applyDashboardConfigPayload(raw: ConfigPayload) {
    const payload = normalizeConfigPayload(raw);
    setTtsFullLoggingEnabled(readFullLoggingEnabled(payload));
    applyUiThemeFromConfig(payload);
    applyUiLocaleFromConfig(payload);
    const context = buildSpeechContextFromConfig(payload);
    ttsTrace("sync", "dashboard_config", {
      source_lang: context.sourceLang,
      active_lines: context.lines.filter((line) => line.enabled).length,
    });
    applySpeechContext(context);
  }

  async function refreshSpeechContext() {
    try {
      const payload = await fetchSettingsPayload();
      setTtsFullLoggingEnabled(readFullLoggingEnabled(payload));
      applySpeechContext(buildSpeechContextFromConfig(payload));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      ttsTrace("speech", "context_refresh_error", { message });
    }
  }

  const NATIVE_DEVICE_HINT_KEY = "voicesub-tts-native-hint-dismissed";
  let nativeDeviceHint = $state(false);

  const nativePlayback = $derived(isNativePlaybackMode(config.playback_mode));

  function refreshNativeDeviceHint(cfg: TtsConfig) {
    if (!isNativePlaybackMode(cfg.playback_mode)) {
      nativeDeviceHint = false;
      return;
    }
    try {
      if (sessionStorage.getItem(NATIVE_DEVICE_HINT_KEY) === "1") {
        nativeDeviceHint = false;
        return;
      }
    } catch {
      // sessionStorage unavailable
    }
    const speechUnset = !cfg.audio_output_device_label?.trim();
    const twitchUnset =
      !!cfg.twitch?.enabled && !cfg.twitch.audio_output_device_label?.trim();
    nativeDeviceHint = speechUnset || twitchUnset;
  }

  function dismissNativeDeviceHint() {
    nativeDeviceHint = false;
    try {
      sessionStorage.setItem(NATIVE_DEVICE_HINT_KEY, "1");
    } catch {
      // ignore
    }
  }

  async function refreshAudioOutputs() {
    try {
      audioRoutingMode = await fetchAudioRoutingMode();
      const rustDevices = await listRustOutputDevices();
      audioOutputs = rustDevices.map((device) => ({
        id: device.id,
        label: device.label,
        is_default: device.is_default,
      }));
      const selected = audioOutputs.find(
        (device) => device.id === (config.audio_output_device_id || ""),
      );
      if (!selected && config.audio_output_device_id) {
        audioOutputs = [
          ...audioOutputs,
          {
            id: config.audio_output_device_id,
            label: config.audio_output_device_label || tr("tts.module.saved_output"),
            is_default: false,
          },
        ];
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      ttsTrace("audio", "refresh_outputs_failed", { message });
    }
  }

  async function refreshPythonStatus() {
    try {
      pythonStatus = await fetchPythonTtsStatus();
      ttsTrace("python", "status_ok", {
        available: pythonStatus?.available ?? false,
        kind: pythonStatus?.kind ?? "",
      });
    } catch (err) {
      pythonStatus = null;
      const message = err instanceof Error ? err.message : String(err);
      ttsTrace("python", "status_error", { message });
    }
  }

  async function refreshResourceTelemetry() {
    try {
      resourceTelemetry = await fetchResourceTelemetry();
    } catch {
      resourceTelemetry = null;
    }
  }

  async function refreshRuntime() {
    const wasActive = runtimeWasActive;
    try {
      runtime = await fetchRuntimeStatus();
    } catch {
      runtime = null;
    }
    const isActive = isRuntimeActive(runtime);
    if (wasActive && !isActive) {
      ttsTrace("runtime", "stopped", {});
      clearAllEngines();
      await resetSubtitlePlanner().catch(() => {});
      activity = [];
      if (config.enabled) status = tr("tts.status.listening");
    }
    runtimeWasActive = isActive;
    refreshKeepaliveContext();
  }

  async function handleSubtitlePayload(payload: Record<string, unknown>) {
    if (!config.enabled || !isRuntimeActive(runtime)) {
      ttsTrace("speech", "skip", {
        enabled: config.enabled,
        runtime_active: isRuntimeActive(runtime),
        sequence: payload.sequence ?? null,
      });
      return;
    }
    try {
      const planned = await planSubtitleSpeech(payload);
      ttsTrace("speech", "planned", {
        sequence: payload.sequence ?? null,
        count: planned.length,
      });
      for (const item of planned) {
        speechEngine.enqueue(item.id, item.text, item.lang || "en");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      ttsTrace("speech", "plan_error", { message });
      error = message;
    }
  }

  function handleTwitchChatMessage(message: TwitchChatMessage) {
    twitchPanel?.recordChatMessage(message);
    if (
      !config.enabled ||
      !config.twitch?.enabled ||
      message.speakable === false
    ) {
      ttsTrace("twitch", "chat_skip_speak", {
        module_enabled: config.enabled,
        twitch_enabled: config.twitch?.enabled ?? false,
        speakable: message.speakable ?? true,
        id: message.id,
      });
      return;
    }
    handleTwitchSpeak(message);
  }

  function handleTwitchSpeak(message: TwitchChatMessage) {
    if (!config.enabled || message.speakable === false) {
      ttsTrace("twitch", "speak_skip", {
        enabled: config.enabled,
        speakable: message.speakable ?? true,
        id: message.id,
      });
      return;
    }
    ttsTraceText("twitch", "speak_enqueue", message.speak_text, {
      id: message.id,
      lang: message.language,
      user: message.user,
    });
    twitchEngine.enqueue(`twitch-${message.id}`, message.speak_text, message.language || "en");
  }

  function scheduleSubtitlePayload(payload: Record<string, unknown>) {
    subtitlePayloadTask = subtitlePayloadTask
      .then(() => handleSubtitlePayload(payload))
      .catch((err) => {
        const message = err instanceof Error ? err.message : String(err);
        ttsTrace("speech", "plan_chain_error", { message });
      });
  }

  function connectWs() {
    socket?.disconnect();
    socket = new EventsSocket(
      async (message) => {
        if (message.type === "subtitle_payload_update") {
          const payload = (message.payload || {}) as Record<string, unknown>;
          scheduleSubtitlePayload(payload);
        }
        if (message.type === "twitch_chat_message") {
          handleTwitchChatMessage(
            (message.payload || {}) as TwitchChatMessage,
          );
        }
        if (message.type === "twitch_connection_update") {
          twitchPanel?.handleConnectionUpdate(
            (message.payload || {}) as import("./lib/types").TwitchConnectionStatus,
          );
        }
        if (message.type === UI_CONFIG_WS_EVENT) {
          const partial = uiConfigFromWsPayload(message.payload);
          if (partial) {
            applyDashboardUiSync(partial);
          }
        }
        if (message.type === "runtime_update" || message.type === "runtime_status") {
          const wasActive = runtimeWasActive;
          runtime = { ...(runtime || {}), ...(message.payload as RuntimeStatus) };
          const isActive = isRuntimeActive(runtime);
          if (wasActive && !isActive) {
            ttsTrace("runtime", "stopped_ws", {});
            clearAllEngines();
            void resetSubtitlePlanner();
            activity = [];
          }
          runtimeWasActive = isActive;
          refreshKeepaliveContext();
        }
      },
      (next) => {
        wsStatus = next;
      },
    );
    socket.connect();
  }

  onMount(async () => {
    if (await tryCompleteExternalOAuthCallback()) {
      externalOAuthDone = true;
      return;
    }

    ttsTrace("app", "mount", {});
    startTtsKeepalive();
    warmupTtsFetch();
    status = tr("tts.status.loading");
    refreshDefaultSampleText();
    sampleLang = loadSampleLang(appSpeech.sourceLang || "en");
    if (!audioOutputs[0]?.label) {
      audioOutputs = [{ id: "", label: tr("tts.module.audio_default"), is_default: true }];
    }
    try {
      const versionRes = await fetch("/api/version");
      if (versionRes.ok) {
        const body = (await versionRes.json()) as { version?: string };
        if (body.version) version = body.version;
      }
    } catch {
      // keep default
    }

    try {
      await recoverStuckSpeechQueues();
      config = await loadTtsConfig();
      ttsTrace("app", "config_loaded", {
        enabled: config.enabled,
        device_id: config.audio_output_device_id || "default",
      });
      if (!config.speech) {
        config.speech = defaultSpeech();
      }
      if (!config.twitch) {
        config.twitch = defaultTwitchSettings();
      } else {
        const twitchDefaults = defaultTwitchSettings();
        config.twitch = {
          ...twitchDefaults,
          ...config.twitch,
          emote_sources: {
            ...twitchDefaults.emote_sources,
            ...config.twitch.emote_sources,
          },
        };
      }
      await refreshAudioOutputs();
      if (audioRoutingMode === "winapi") {
        try {
          config = await bindTtsWindowAudio();
          ttsTrace("audio", "bind_window_ok", {
            device_id: config.audio_output_device_id || "default",
          });
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err);
          ttsTrace("audio", "bind_window_failed", { message });
        }
      }
      syncEnginesFromConfig(config);
      refreshNativeDeviceHint(config);
      if (!config.tts_provider) {
        config.tts_provider = "browser_google";
      }
      await refreshSpeechContext();
      await refreshPythonStatus();
      await refreshRuntime();
      await refreshResourceTelemetry();
      runtimeWasActive = isRuntimeActive(runtime);
      connectWs();
      runtimeTimer = setInterval(() => void refreshRuntime(), 3000);
      refreshKeepaliveContext();
      resourceTelemetryTimer = setInterval(() => void refreshResourceTelemetry(), 30_000);
      speechContextTimer = setInterval(() => void refreshSpeechContext(), 5000);
      unsubscribeUiSync = subscribeUiConfigSync(
        (partial) => {
          applyDashboardUiSync(partial);
        },
        { enableWebSocket: false },
      );
      unsubscribeUiLocale = subscribeUiLocaleSync((next) => {
        applyDashboardLocale(next);
      });
      window.addEventListener("sst:locale-changed", handleLocaleChanged);
      window.addEventListener("focus", handleWindowFocus);
      status = config.enabled ? tr("tts.status.listening") : tr("tts.status.disabled");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      ttsTrace("app", "mount_error", { message });
      error = message;
      status = tr("tts.status.ipc_unavailable");
    }
  });

  function handleWindowFocus() {
    void refreshSpeechContext();
    void refreshAudioOutputs();
  }

  onDestroy(() => {
    ttsTrace("app", "destroy", {});
    stopTtsKeepalive();
    speechEngine.dispose();
    twitchEngine.dispose();
    unsubscribeSpeech();
    unsubscribeTwitch();
    unsubscribeUiSync?.();
    unsubscribeUiLocale?.();
    window.removeEventListener("sst:locale-changed", handleLocaleChanged);
    window.removeEventListener("focus", handleWindowFocus);
    clearAllEngines();
    socket?.disconnect();
    if (runtimeTimer) clearInterval(runtimeTimer);
    if (resourceTelemetryTimer) clearInterval(resourceTelemetryTimer);
    if (speechContextTimer) clearInterval(speechContextTimer);
    if (settingsTimer) clearTimeout(settingsTimer);
  });

  async function handleAudioDeviceChange(event: Event) {
    const target = event.target as HTMLSelectElement;
    const deviceId = target.value;
    const device = audioOutputs.find((entry) => entry.id === deviceId);
    try {
      config = await setTtsAudioDevice(deviceId, device?.label || "");
      syncEnginesFromConfig(config);
      refreshNativeDeviceHint(config);
      status = tr("tts.status.audio_updated");
      error = "";
      ttsTrace("audio", "device_selected", {
        device_id: deviceId || "default",
        routing: audioRoutingMode,
      });
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    }
  }

  async function handleEnabledChange(event: Event) {
    const target = event.target as HTMLInputElement;
    ttsTrace("settings", "enabled_change", { enabled: target.checked });
    try {
      config = await setTtsEnabled(target.checked);
      syncEnginesFromConfig(config);
      status = config.enabled ? tr("tts.status.listening") : tr("tts.status.disabled");
      error = "";
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    }
  }

  function queueSpeechSettingsSave() {
    if (settingsTimer) clearTimeout(settingsTimer);
    settingsTimer = setTimeout(() => {
      void persistSpeechSettings();
    }, 350);
  }

  async function persistSpeechSettings() {
    try {
      config = await updateSpeechSettings(config.speech);
      syncEnginesFromConfig(config);
      error = "";
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    }
  }

  async function handleProviderChange(event: Event) {
    const target = event.target as HTMLSelectElement;
    const provider = target.value as TtsProvider;
    ttsTrace("settings", "provider_change", { provider });
    try {
      config = await setTtsProvider(provider);
      syncEnginesFromConfig(config);
      await refreshPythonStatus();
      error = "";
      if (provider === "python_stdlib" && pythonStatus && !pythonStatus.available) {
        error = pythonStatus.build_hint || tr("tts.speech.python_runtime_hint");
      }
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    }
  }

  async function persistVoiceSettings() {
    try {
      config = await updateVoiceSettings(config.speech_rate, config.speech_volume);
      syncEnginesFromConfig(config);
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    }
  }

  async function handlePlaybackModeChange(event: Event) {
    const target = event.target as HTMLSelectElement;
    const mode = target.value === "sonic" ? "sonic" : "native";
    try {
      config = await setTtsPlaybackMode(mode);
      syncEnginesFromConfig(config);
      refreshNativeDeviceHint(config);
      await refreshAudioOutputs();
      status = tr("tts.status.playback_mode_updated");
      error = "";
      ttsTrace("audio", "playback_mode", { mode });
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    }
  }

  function handleSampleLangChange() {
    saveSampleLang(sampleLang);
  }

  function handleSourceToggle(event: Event) {
    const checked = (event.currentTarget as HTMLInputElement).checked;
    config.speech.speak_source = checked;
    queueSpeechSettingsSave();
  }

  function handleTranslationLineToggle(slotId: string, event: Event) {
    const checked = (event.currentTarget as HTMLInputElement).checked;
    config.speech = toggleTranslationSlot(
      config.speech,
      slotId,
      checked,
      activeTranslationLines,
    );
    queueSpeechSettingsSave();
  }

  function speakSample() {
    if (!config.enabled) return;
    const provider =
      config.tts_provider === "python_stdlib" ? "python_stdlib" : "browser_google";
    const lang = sampleLang;
    lastTestRequest = buildTtsAudioUrl(sampleText, lang, provider);
    ttsTrace("speech", "speak_test", {
      tl: lang,
      provider,
      request_url: lastTestRequest,
    });
    speechEngine.enqueue(`local-${Date.now()}`, sampleText, lang);
  }

  async function clearQueue() {
    ttsTrace("speech", "clear_queue", {});
    clearAllEngines();
    activity = [];
    await resetSubtitlePlanner().catch(() => {});
    status = config.enabled ? tr("tts.status.listening") : tr("tts.status.disabled");
  }

  function translationLineTitle(slotId: string, label?: string | null) {
    const trimmed = label?.trim();
    if (trimmed) return trimmed;
    const num = slotId.replace(/\D+/g, "") || "?";
    return tr("tts.speech.line_fallback", { num });
  }

  function selectTab(next: TtsTab) {
    tab = next;
    queueMicrotask(() => {
      const targetId = next === "twitch" ? "tts-panel-twitch" : "tts-panel-speech";
      document.getElementById(targetId)?.scrollIntoView({ block: "start" });
    });
  }
</script>

{#if externalOAuthDone}
  <div class="app-shell tts-module-shell tts-oauth-success-shell">
    <section class="glass-panel bento-tile panel-padding stack">
      <div class="section-heading section-heading--stacked">
        <p class="eyebrow">{tr("tts.oauth.eyebrow")}</p>
        <h2>{tr("tts.oauth.done_title")}</h2>
      </div>
      <p class="muted">{tr("tts.oauth.done_body")}</p>
      <p class="muted">{tr("tts.oauth.done_close")}</p>
    </section>
  </div>
{:else}
<div class="app-shell tts-module-shell">
  <header class="app-chrome glass-chrome tts-chrome">
    <div class="tts-chrome__brand">
      <span class="tts-chrome__mark" aria-hidden="true">◆</span>
      <div>
        <div class="tts-chrome__title">{tr("tts.module.title")}</div>
        <div class="tts-chrome__subtitle">{tr("tts.module.version", { version })}</div>
        {#if resourceTelemetry}
          <div class="tts-chrome__telemetry" role="status">
            <span
              class="tts-telemetry-chip"
              class:warn={isResourceTelemetryWarning(resourceTelemetry.self_process)}
              title={tr("tts.telemetry.tts_title")}
            >
              {tr("tts.telemetry.tts_label")}:
              {formatHandleCount(resourceTelemetry.self_process.handle_count)}
              {tr("tts.telemetry.handles")} ·
              {formatCompactBytes(resourceTelemetry.self_process.commit_bytes)}
              {tr("tts.telemetry.commit")}
            </span>
            {#if shellResourceTelemetry}
              <span
                class="tts-telemetry-chip"
                class:warn={isResourceTelemetryWarning(shellResourceTelemetry)}
                title={tr("tts.telemetry.shell_title")}
              >
                {tr("tts.telemetry.shell_label")}:
                {formatHandleCount(shellResourceTelemetry.handle_count)}
                {tr("tts.telemetry.handles")} ·
                {formatCompactBytes(shellResourceTelemetry.commit_bytes)}
                {tr("tts.telemetry.commit")}
              </span>
            {/if}
            {#if obsResourceTelemetry}
              <span
                class="tts-telemetry-chip"
                class:warn={isResourceTelemetryWarning(obsResourceTelemetry)}
                title={tr("tts.telemetry.obs_title")}
              >
                {tr("tts.telemetry.obs_label")}:
                {formatHandleCount(obsResourceTelemetry.handle_count)}
                {tr("tts.telemetry.handles")} ·
                {formatCompactBytes(obsResourceTelemetry.commit_bytes)}
                {tr("tts.telemetry.commit")}
              </span>
            {/if}
            <span class="tts-telemetry-help">
              <button
                type="button"
                class="tts-telemetry-help-trigger"
                bind:this={telemetryHelpTriggerEl}
                aria-label={tr("tts.telemetry.help_trigger")}
                aria-expanded={telemetryHelpOpen}
                onclick={toggleTelemetryHelp}
              >
                ?
              </button>
            </span>
          </div>
        {/if}
      </div>
    </div>
    <div class="tts-chrome__actions">
      <label class="checkbox-row">
        <input type="checkbox" checked={config.enabled} onchange={handleEnabledChange} />
        <span>{tr("tts.module.enabled")}</span>
      </label>
      <label class="tts-audio-output stack-field">
        <span class="sr-only">{tr("tts.module.audio_output")}</span>
        <select
          class="control control-sm"
          value={config.audio_output_device_id || ""}
          onchange={(e) => void handleAudioDeviceChange(e)}
        >
          {#each audioOutputs as device (device.id || "default")}
            <option value={device.id}>{device.label}</option>
          {/each}
        </select>
      </label>
      <label class="tts-audio-output stack-field">
        <span class="sr-only">{tr("tts.module.playback_mode")}</span>
        <select
          class="control control-sm"
          value={config.playback_mode === "sonic" ? "sonic" : "native"}
          onchange={(e) => void handlePlaybackModeChange(e)}
        >
          <option value="native">{tr("tts.module.playback_mode.native")}</option>
          <option value="sonic">{tr("tts.module.playback_mode.sonic")}</option>
        </select>
      </label>
    </div>
  </header>

  {#if nativeDeviceHint}
    <div class="tts-native-hint glass-panel panel-padding" role="status">
      <p>{tr("tts.module.native_device_hint")}</p>
      <button type="button" class="btn btn-ghost btn-sm" onclick={dismissNativeDeviceHint}>
        {tr("tts.module.native_device_hint_dismiss")}
      </button>
    </div>
  {/if}

  <nav class="tab-bar" aria-label="TTS module sections">
    <button
      type="button"
      class="tab-btn"
      class:active={tab === "speech"}
      onclick={() => selectTab("speech")}
    >
      {tr("tts.tab.speech")}
    </button>
    <button
      type="button"
      class="tab-btn"
      class:active={tab === "twitch"}
      onclick={() => selectTab("twitch")}
    >
      {tr("tts.tab.twitch")}
    </button>
  </nav>

  <section
    id="tts-panel-speech"
    class="glass-panel bento-tile panel-padding stack"
    hidden={tab !== "speech"}
    aria-hidden={tab !== "speech"}
  >
      <div class="section-heading section-heading--stacked">
        <p class="eyebrow">{tr("tts.speech.eyebrow")}</p>
        <h2>{tr("tts.speech.title")}</h2>
      </div>

      <div class="tts-status-badges">
        <span class="badge" class:active={wsStatus === "connected"}>{tr("tts.badge.ws")}: {wsStatus}</span>
        <span class="badge" class:active={isRuntimeActive(runtime)}>
          {tr("tts.badge.runtime")}: {isRuntimeActive(runtime) ? tr("tts.badge.runtime_active") : tr("tts.badge.runtime_idle")}
        </span>
        <span class="badge" class:active={config.enabled}>{tr("tts.badge.status")}: {status}</span>
        {#if error}
          <span class="badge err">{error}</span>
        {/if}
      </div>

      <div class="tts-settings-grid">
        <label class="stack-field stack-field--full">
          <span>{tr("tts.speech.engine")}</span>
          <select
            class="control"
            value={config.tts_provider || "browser_google"}
            onchange={handleProviderChange}
          >
            <option value="browser_google">{tr("tts.speech.engine.browser")}</option>
            <option value="python_stdlib">{tr("tts.speech.engine.python")}</option>
          </select>
        </label>

        {#if config.tts_provider === "python_stdlib"}
          <p class="muted stack-field--full">
            {#if pythonStatus?.available}
              {#if pythonStatus.kind === "embedded"}
                {tr("tts.speech.python_embedded")}: <strong>{pythonStatus.command}</strong>
              {:else}
                {tr("tts.speech.python_dev")}: <strong>{pythonStatus.command}</strong>
                {#if pythonStatus.version}
                  · {pythonStatus.version}
                {/if}
              {/if}
            {:else if pythonStatus}
              {tr("tts.speech.python_missing")} {pythonStatus.build_hint}
            {:else}
              {tr("tts.speech.python_checking")}
            {/if}
          </p>
        {/if}

        <div class="stack-field stack-field--full">
          <span>{tr("tts.speech.what_to_speak")}</span>
          <ul class="tts-speak-targets">
            <li class="tts-speak-target">
              <label class="checkbox-row">
                <input
                  type="checkbox"
                  checked={config.speech.speak_source}
                  onchange={handleSourceToggle}
                />
                <span class="tts-speak-target__meta">
                  <span class="tts-speak-target__title">{tr("tts.speech.source_transcript")}</span>
                  <span class="tts-speak-target__lang">
                    {tr("tts.speech.recognition_lang", { lang: appSpeech.sourceLang })}
                  </span>
                </span>
              </label>
            </li>
            {#if !appSpeech.translationEnabled}
              <li class="muted">{tr("tts.speech.translation_disabled")}</li>
            {:else if activeTranslationLines.length === 0}
              <li class="muted">{tr("tts.speech.no_translation_lines")}</li>
            {:else}
              {#each activeTranslationLines as line (line.slot_id)}
                <li class="tts-speak-target">
                  <label class="checkbox-row">
                    <input
                      type="checkbox"
                      checked={isTranslationSlotSelected(config.speech, line.slot_id)}
                      onchange={(e) => handleTranslationLineToggle(line.slot_id, e)}
                    />
                    <span class="tts-speak-target__meta">
                      <span class="tts-speak-target__title">
                        {translationLineTitle(line.slot_id, line.label)}
                      </span>
                      <span class="tts-speak-target__lang">
                        {line.slot_id} · tl={line.target_lang}
                      </span>
                    </span>
                  </label>
                </li>
              {/each}
            {/if}
          </ul>
        </div>

        <label class="stack-field">
          <span>{tr("tts.speech.min_chars")}</span>
          <input
            class="control"
            type="number"
            min="1"
            max="32"
            value={config.speech.min_chars}
            onchange={(e) => {
              config.speech.min_chars = Number((e.currentTarget as HTMLInputElement).value) || 1;
              queueSpeechSettingsSave();
            }}
          />
        </label>

        {#if !nativePlayback}
          <label class="stack-field stack-field--range">
            <span class="stack-field__label-row">
              <span>{tr("tts.speech.rate")}</span>
              <output class="stack-field__value" for="tts-speech-rate">
                {config.speech_rate.toFixed(2)}×
              </output>
            </span>
            <input
              id="tts-speech-rate"
              type="range"
              min="0.5"
              max="2"
              step="0.05"
              bind:value={config.speech_rate}
              onchange={() => void persistVoiceSettings()}
            />
          </label>
        {/if}

        <label class="stack-field stack-field--range">
          <span class="stack-field__label-row">
            <span>{tr("tts.speech.volume")}</span>
            <output class="stack-field__value" for="tts-speech-volume">
              {formatSpeechVolume(config.speech_volume)}
            </output>
          </span>
          <input
            id="tts-speech-volume"
            type="range"
            min="0"
            max="1"
            step="0.05"
            bind:value={config.speech_volume}
            onchange={() => void persistVoiceSettings()}
          />
        </label>
      </div>

      <div class="section-heading section-heading--stacked" style="margin-top: var(--space-4)">
        <p class="eyebrow">{tr("tts.speech.test_eyebrow")}</p>
        <h3>{tr("tts.speech.test_title")}</h3>
      </div>

      <label class="stack-field stack-field--full">
        <span>{tr("tts.speech.test_language")}</span>
        <select
          class="control"
          bind:value={sampleLang}
          onchange={handleSampleLangChange}
        >
          {#each TTS_TEST_LANG_CODES as code (code)}
            <option value={code}>{tr(`tts.lang.${code}`)} ({code})</option>
          {/each}
        </select>
      </label>

      <label class="stack-field stack-field--full" style="margin-top: var(--space-3)">
        <span>{tr("tts.speech.sample_label")}</span>
        <textarea
          class="control"
          bind:value={sampleText}
          oninput={() => {
            sampleTextIsDefault = false;
          }}
          rows="3"
        ></textarea>
      </label>

      <div class="tts-inline-actions" style="margin-top: var(--space-3)">
        <button
          type="button"
          class="btn btn-primary"
          onclick={speakSample}
          disabled={!config.enabled || !sampleText.trim()}
        >
          {tr("tts.speech.test_speak")}
        </button>
        <button type="button" class="btn btn-ghost" onclick={() => void clearQueue()}>
          {tr("tts.speech.clear_queue")}
        </button>
      </div>

      {#if lastTestRequest}
        <p class="tts-request-preview">{tr("tts.speech.request_preview")}: {lastTestRequest}</p>
      {/if}

      {#if activity.length}
        <ul class="transcript-box tts-activity-log">
          {#each activity as line}
            <li>{line}</li>
          {/each}
        </ul>
      {:else}
        <p class="muted">{tr("tts.speech.queue_empty")}</p>
      {/if}
  </section>

  <div id="tts-panel-twitch" hidden={tab !== "twitch"} aria-hidden={tab !== "twitch"}>
    <TwitchPanel
      bind:this={twitchPanel}
      bind:twitch={config.twitch}
      moduleEnabled={config.enabled}
      moduleSpeechRate={config.speech_rate}
      moduleSpeechVolume={config.speech_volume}
      playbackMode={config.playback_mode ?? "native"}
      audioOutputs={audioOutputs}
      onTwitchConfigSaved={(next) => {
        config = { ...config, twitch: next };
        syncEnginesFromConfig(config);
        refreshNativeDeviceHint(config);
      }}
    />
  </div>

  {#if telemetryHelpOpen}
    <button
      type="button"
      class="tts-telemetry-help-backdrop"
      aria-label={tr("tts.telemetry.help_close")}
      tabindex="-1"
      onclick={closeTelemetryHelp}
    ></button>
    <div
      class="tts-telemetry-help-popover"
      role="dialog"
      aria-labelledby="tts-telemetry-help-title"
      style:top="{telemetryHelpPos.top}px"
      style:left="{telemetryHelpPos.left}px"
      onclick={(event) => event.stopPropagation()}
    >
      <p id="tts-telemetry-help-title" class="tts-telemetry-help-popover__title">
        {tr("tts.telemetry.help_title")}
      </p>
      <p>{tr("tts.telemetry.help_intro")}</p>
      <p>{tr("tts.telemetry.help_handles")}</p>
      <p>{tr("tts.telemetry.help_commit")}</p>
      <p>{tr("tts.telemetry.help_warn")}</p>
      <p>{tr("tts.telemetry.help_processes")}</p>
    </div>
  {/if}
</div>
{/if}
