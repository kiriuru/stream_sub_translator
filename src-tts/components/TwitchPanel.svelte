<script lang="ts">
  import {
    connectTwitchChat,
    disconnectTwitchChat,
    fetchTwitchStatus,
    setTtsChannelAudioDevice,
    updateTwitchSettings,
  } from "../lib/tts-ipc";
  import { isNativePlaybackMode } from "../lib/audio-player";
  import { isSetSinkIdSupported } from "../lib/browser-audio-output";
  import type { AudioOutputDevice, TtsPlaybackMode } from "../lib/types";
  import { twitchOAuthRedirectUri } from "../lib/twitch-oauth";
  import {
    fetchPendingOAuthToken,
    openTwitchOAuthInSystemBrowser,
  } from "../lib/twitch-oauth-flow";
  import { defaultTwitchSettings } from "../lib/twitch-defaults";
  import ReplacementPairEditor from "./ReplacementPairEditor.svelte";
  import { locale, t, getLocale } from "../../src/lib/i18n";
  import type { LocaleCode } from "../../src/lib/types";
  import { prependActivityLog } from "../lib/activity-log";
  import { ttsTrace, ttsTraceText } from "../lib/tts-trace";
  import type {
    TwitchPauseStyle,
    TwitchChatMessage,
    TwitchConnectionStatus,
    TwitchReplacement,
    TwitchTtsSettings,
  } from "../lib/types";

  interface Props {
    twitch: TwitchTtsSettings;
    moduleEnabled: boolean;
    moduleSpeechRate?: number;
    moduleSpeechVolume?: number;
    playbackMode?: TtsPlaybackMode;
    audioOutputs?: AudioOutputDevice[];
    onConnectionChange?: (status: TwitchConnectionStatus) => void;
    onTwitchConfigSaved?: (twitch: TwitchTtsSettings) => void;
  }

  let {
    twitch = $bindable(),
    moduleEnabled,
    moduleSpeechRate = 1,
    moduleSpeechVolume = 1,
    playbackMode = "browser",
    audioOutputs = [],
    onConnectionChange,
    onTwitchConfigSaved,
  }: Props = $props();

  const twitchRateOverride = $derived((twitch.speech_rate ?? 0) > 0);
  const twitchVolumeOverride = $derived(
    typeof twitch.speech_volume === "number" && twitch.speech_volume >= 0,
  );

  const nativePlayback = $derived(isNativePlaybackMode(playbackMode));
  const setSinkSupported = isSetSinkIdSupported();

  let status = $state<TwitchConnectionStatus>({
    state: "disconnected",
    channel: "",
    message: "",
  });
  let error = $state("");
  let busy = $state(false);
  let chatLog = $state<TwitchChatMessage[]>([]);
  let ignoreUsersText = $state("");
  let enabledLanguagesText = $state("");
  let ignoreUsersDirty = $state(false);
  let enabledLanguagesDirty = $state(false);
  let ignoreUsersInput: HTMLInputElement | null = null;

  const nickPairs = $derived(twitch.nick_replacements ?? []);

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
  let settingsTimer: ReturnType<typeof setTimeout> | null = null;
  let oauthPollTimer: ReturnType<typeof setInterval> | null = null;
  let showOAuthToken = $state(false);
  let oauthNotice = $state("");
  const oauthRedirectUri = twitchOAuthRedirectUri();

  const isConnected = $derived(status.state === "connected");
  const isConnecting = $derived(status.state === "connecting");

  const twitchAudioOutputs = $derived.by(() => {
    const deviceId = twitch.audio_output_device_id || "";
    if (!deviceId) return audioOutputs;
    if (audioOutputs.some((entry) => entry.id === deviceId)) {
      return audioOutputs;
    }
    return [
      ...audioOutputs,
      {
        id: deviceId,
        label: twitch.audio_output_device_label || tr("tts.module.saved_output"),
        is_default: false,
      },
    ];
  });

  $effect(() => {
    const users = (twitch.ignore_users || []).join(", ");
    if (!ignoreUsersDirty && document.activeElement !== ignoreUsersInput) {
      ignoreUsersText = users;
    }
    const langs = (twitch.enabled_languages ?? []).join(", ");
    if (!enabledLanguagesDirty) {
      enabledLanguagesText = langs;
    }
  });

  export function handleConnectionUpdate(next: TwitchConnectionStatus) {
    status = next;
    ttsTrace("twitch", "connection_update", {
      state: next.state,
      channel: next.channel,
      message: next.message,
    });
    onConnectionChange?.(next);
  }

  export function recordChatMessage(message: TwitchChatMessage) {
    chatLog = prependActivityLog(chatLog, message);
    ttsTraceText("twitch", "chat_message", message.text, {
      id: message.id,
      user: message.user,
      speakable: message.speakable ?? true,
      lang: message.language,
    });
  }

  async function refreshStatus() {
    try {
      status = await fetchTwitchStatus();
      ttsTrace("twitch", "status_refresh", {
        state: status.state,
        channel: status.channel,
      });
      onConnectionChange?.(status);
    } catch (err) {
      ttsTrace("twitch", "status_refresh_error", {
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }

  function queueSave() {
    if (settingsTimer) clearTimeout(settingsTimer);
    settingsTimer = setTimeout(() => {
      settingsTimer = null;
      void persistSettings();
    }, 400);
  }

  function flushPendingSave() {
    if (!settingsTimer) return;
    clearTimeout(settingsTimer);
    settingsTimer = null;
    void persistSettings();
  }

  function stopOAuthPoll() {
    if (oauthPollTimer) {
      clearInterval(oauthPollTimer);
      oauthPollTimer = null;
    }
  }

  async function pollOAuthFromBrowser() {
    try {
      const token = await fetchPendingOAuthToken();
      if (!token) return;
      stopOAuthPoll();
      twitch = { ...twitch, oauth_token: token };
      oauthNotice = tr("tts.twitch.oauth_received");
      ttsTrace("twitch", "oauth_implicit_ok", { source: "system_browser" });
      queueSave();
      error = "";
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      ttsTrace("twitch", "oauth_poll_error", { message });
    }
  }

  function startOAuthPoll() {
    stopOAuthPoll();
    oauthNotice = tr("tts.twitch.oauth_waiting");
    void pollOAuthFromBrowser();
    oauthPollTimer = setInterval(() => {
      void pollOAuthFromBrowser();
    }, 1500);
  }

  async function handleGetOAuthToken() {
    error = "";
    oauthNotice = "";
    stopOAuthPoll();
    try {
      ttsTrace("twitch", "oauth_implicit_start", {
        redirect_uri: oauthRedirectUri,
      });
      await openTwitchOAuthInSystemBrowser(twitch.oauth_client_id);
      startOAuthPoll();
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    }
  }

  function toggleOAuthTokenVisibility() {
    showOAuthToken = !showOAuthToken;
  }

  function updateNickReplacements(pairs: TwitchReplacement[]) {
    twitch = { ...twitch, nick_replacements: pairs };
    queueSave();
  }

  function emoteSources() {
    const defaults = defaultTwitchSettings().emote_sources!;
    return { ...defaults, ...twitch.emote_sources };
  }

  async function persistSettings() {
    try {
      const ignore_users = ignoreUsersText
        .split(/[,\n;]/)
        .map((entry) => entry.trim())
        .filter(Boolean);
      const enabled_languages = enabledLanguagesText
        .split(/[,;\s]+/)
        .map((entry) => entry.trim().toLowerCase())
        .filter(Boolean);
      const next = {
        ...twitch,
        ignore_users,
        enabled_languages,
        nick_replacements: [...(twitch.nick_replacements ?? [])],
        emote_sources: emoteSources(),
      };
      twitch = next;
      const saved = await updateTwitchSettings(next);
      twitch = saved.twitch ?? next;
      ignoreUsersDirty = false;
      enabledLanguagesDirty = false;
      onTwitchConfigSaved?.(twitch);
      ttsTrace("twitch", "settings_saved", {
        channel: next.channel,
        enabled: next.enabled,
        lang: next.language,
        ignore_users: next.ignore_users.length,
      });
      error = "";
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      ttsTrace("twitch", "settings_save_error", { message });
      error = message;
    }
  }

  async function handleConnect() {
    busy = true;
    error = "";
    ttsTrace("twitch", "connect_click", { channel: twitch.channel });
    try {
      await persistSettings();
      status = await connectTwitchChat();
      ttsTrace("twitch", "connect_ok", {
        state: status.state,
        channel: status.channel,
      });
      onConnectionChange?.(status);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      ttsTrace("twitch", "connect_error", { message });
      error = message;
    } finally {
      busy = false;
    }
  }

  async function handleTwitchAudioDeviceChange(event: Event) {
    const target = event.target as HTMLSelectElement;
    const deviceId = target.value;
    const device = audioOutputs.find((entry) => entry.id === deviceId);
    try {
      const saved = await setTtsChannelAudioDevice(
        "twitch",
        deviceId,
        device?.label || "",
      );
      twitch = saved.twitch ?? twitch;
      onTwitchConfigSaved?.(twitch);
      error = "";
      ttsTrace("twitch", "audio_device", {
        device_id: deviceId || "default",
        native: nativePlayback,
      });
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    }
  }

  async function handleDisconnect() {
    busy = true;
    error = "";
    ttsTrace("twitch", "disconnect_click", {});
    try {
      await disconnectTwitchChat();
      status = { state: "disconnected", channel: "", message: "" };
      ttsTrace("twitch", "disconnect_ok", {});
      onConnectionChange?.(status);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      ttsTrace("twitch", "disconnect_error", { message });
      error = message;
    } finally {
      busy = false;
    }
  }

  $effect(() => {
    void refreshStatus();
    return () => {
      flushPendingSave();
      stopOAuthPoll();
    };
  });
</script>

<section class="glass-panel bento-tile panel-padding stack">
  <div class="section-heading section-heading--stacked">
    <p class="eyebrow">{tr("tts.twitch.eyebrow")}</p>
    <h2>{tr("tts.twitch.title")}</h2>
  </div>

  <div class="tts-status-badges">
    <span class="badge" class:active={isConnected}>
      {tr("tts.twitch.irc")}: {status.state}
    </span>
    {#if status.channel}
      <span class="badge">{status.channel}</span>
    {/if}
    {#if error || status.message}
      <span class="badge err">{error || status.message}</span>
    {/if}
  </div>

  <p class="muted">{tr("tts.twitch.intro")}</p>

  <div class="tts-settings-grid">
    <label class="checkbox-row stack-field--full">
      <input
        type="checkbox"
        checked={twitch.enabled}
        onchange={(e) => {
          twitch = { ...twitch, enabled: (e.currentTarget as HTMLInputElement).checked };
          queueSave();
        }}
      />
      <span>{tr("tts.twitch.enable")}</span>
    </label>

    <label class="stack-field">
      <span>{tr("tts.twitch.channel")}</span>
      <input
        class="control"
        placeholder={tr("tts.twitch.channel_placeholder")}
        value={twitch.channel}
        oninput={(e) => {
          twitch = { ...twitch, channel: (e.currentTarget as HTMLInputElement).value };
          queueSave();
        }}
      />
    </label>

    <label class="stack-field">
      <span>{tr("tts.twitch.nick")}</span>
      <input
        class="control"
        placeholder={tr("tts.twitch.nick_placeholder")}
        value={twitch.nick}
        oninput={(e) => {
          twitch = { ...twitch, nick: (e.currentTarget as HTMLInputElement).value };
          queueSave();
        }}
      />
    </label>

    <div class="stack-field stack-field--full">
      <span>{tr("tts.twitch.oauth_token")}</span>
      <div class="tts-oauth-token-row">
        <input
          class="control"
          type={showOAuthToken ? "text" : "password"}
          autocomplete="off"
          placeholder={tr("tts.twitch.oauth_placeholder")}
          value={twitch.oauth_token}
          oninput={(e) => {
            twitch = { ...twitch, oauth_token: (e.currentTarget as HTMLInputElement).value };
            queueSave();
          }}
        />
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          onclick={toggleOAuthTokenVisibility}
        >
          {showOAuthToken ? tr("tts.twitch.oauth_hide") : tr("tts.twitch.oauth_show")}
        </button>
      </div>
      <button
        type="button"
        class="btn btn-primary tts-twitch-oauth-btn"
        onclick={handleGetOAuthToken}
      >
        {tr("tts.twitch.oauth_get")}
      </button>
      {#if oauthNotice}
        <p class="muted tts-oauth-notice">{oauthNotice}</p>
      {/if}
      <p class="muted tts-oauth-hint">
        {tr("tts.twitch.oauth_hint", { uri: oauthRedirectUri })}
      </p>
    </div>

    <label class="stack-field stack-field--full">
      <span>{tr("tts.twitch.audio_output")}</span>
      <select
        class="control"
        value={twitch.audio_output_device_id || ""}
        onchange={(e) => void handleTwitchAudioDeviceChange(e)}
        disabled={!nativePlayback && !setSinkSupported}
      >
        {#each twitchAudioOutputs as device (device.id || "default")}
          <option value={device.id}>{device.label}</option>
        {/each}
      </select>
      {#if !nativePlayback && !setSinkSupported}
        <span class="muted">{tr("tts.twitch.audio_output_unsupported")}</span>
      {/if}
    </label>

    <label class="stack-field">
      <span>{tr("tts.twitch.fallback_lang")}</span>
      <input
        class="control"
        placeholder="en"
        value={twitch.language}
        oninput={(e) => {
          twitch = { ...twitch, language: (e.currentTarget as HTMLInputElement).value };
          queueSave();
        }}
      />
    </label>

    <label class="stack-field">
      <span>{tr("tts.twitch.min_chars")}</span>
      <input
        class="control"
        type="number"
        min="1"
        max="32"
        value={twitch.min_chars}
        onchange={(e) => {
          twitch = {
            ...twitch,
            min_chars: Number((e.currentTarget as HTMLInputElement).value) || 1,
          };
          queueSave();
        }}
      />
    </label>

    <label class="checkbox-row">
      <input
        type="checkbox"
        checked={twitch.include_username}
        onchange={(e) => {
          twitch = {
            ...twitch,
            include_username: (e.currentTarget as HTMLInputElement).checked,
          };
          queueSave();
        }}
      />
      <span>{tr("tts.twitch.include_username")}</span>
    </label>

    <label class="checkbox-row">
      <input
        type="checkbox"
        checked={twitch.block_commands}
        onchange={(e) => {
          twitch = {
            ...twitch,
            block_commands: (e.currentTarget as HTMLInputElement).checked,
          };
          queueSave();
        }}
      />
      <span>{tr("tts.twitch.block_commands")}</span>
    </label>

    <label class="stack-field stack-field--full">
      <span>{tr("tts.twitch.ignore_users")}</span>
      <input
        class="control"
        bind:this={ignoreUsersInput}
        placeholder={tr("tts.twitch.ignore_users_placeholder")}
        value={ignoreUsersText}
        oninput={(e) => {
          ignoreUsersDirty = true;
          ignoreUsersText = (e.currentTarget as HTMLInputElement).value;
          queueSave();
        }}
        onblur={() => flushPendingSave()}
      />
    </label>

    <details class="tts-twitch-advanced stack-field--full">
      <summary>{tr("tts.twitch.advanced")}</summary>
      <div class="tts-twitch-advanced__body">
        <div class="stack-field">
          <label class="checkbox-row">
            <input
              type="checkbox"
              checked={twitchRateOverride}
              onchange={(e) => {
                const checked = (e.currentTarget as HTMLInputElement).checked;
                twitch = {
                  ...twitch,
                  speech_rate: checked ? moduleSpeechRate : 0,
                };
                queueSave();
              }}
            />
            <span>{tr("tts.twitch.override_rate")}</span>
          </label>
          {#if twitchRateOverride}
            <input
              type="range"
              min="0.5"
              max="2"
              step="0.05"
              value={twitch.speech_rate ?? moduleSpeechRate}
              onchange={(e) => {
                twitch = {
                  ...twitch,
                  speech_rate: Number((e.currentTarget as HTMLInputElement).value) || 0.5,
                };
                queueSave();
              }}
            />
          {:else}
            <span class="muted">
              {tr("tts.twitch.inherit_rate", { rate: moduleSpeechRate })}
            </span>
          {/if}
        </div>

        <div class="stack-field">
          <label class="checkbox-row">
            <input
              type="checkbox"
              checked={twitchVolumeOverride}
              onchange={(e) => {
                const checked = (e.currentTarget as HTMLInputElement).checked;
                twitch = {
                  ...twitch,
                  speech_volume: checked ? moduleSpeechVolume : -1,
                };
                queueSave();
              }}
            />
            <span>{tr("tts.twitch.override_volume")}</span>
          </label>
          {#if twitchVolumeOverride}
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={twitch.speech_volume ?? moduleSpeechVolume}
              onchange={(e) => {
                twitch = {
                  ...twitch,
                  speech_volume: Number((e.currentTarget as HTMLInputElement).value),
                };
                queueSave();
              }}
            />
          {:else}
            <span class="muted">
              {tr("tts.twitch.inherit_volume", { volume: moduleSpeechVolume })}
            </span>
          {/if}
        </div>

        <label class="stack-field">
          <span>{tr("tts.twitch.max_queue")}</span>
          <input
            class="control"
            type="number"
            min="0"
            max="32"
            value={twitch.max_queue_items ?? 0}
            onchange={(e) => {
              twitch = {
                ...twitch,
                max_queue_items: Number((e.currentTarget as HTMLInputElement).value) || 0,
              };
              queueSave();
            }}
          />
          <span class="muted">{tr("tts.twitch.max_queue_hint")}</span>
        </label>

        <label class="checkbox-row">
          <input
            type="checkbox"
            checked={twitch.strip_emotes ?? true}
            onchange={(e) => {
              twitch = {
                ...twitch,
                strip_emotes: (e.currentTarget as HTMLInputElement).checked,
              };
              queueSave();
            }}
          />
          <span>{tr("tts.twitch.strip_emotes")}</span>
        </label>
        <label class="checkbox-row">
          <input
            type="checkbox"
            checked={twitch.strip_emoji ?? true}
            onchange={(e) => {
              twitch = {
                ...twitch,
                strip_emoji: (e.currentTarget as HTMLInputElement).checked,
              };
              queueSave();
            }}
          />
          <span>{tr("tts.twitch.strip_emoji")}</span>
        </label>
        <div class="tts-twitch-emote-sources">
          <span class="muted">{tr("tts.twitch.emote_sources")}</span>
          <label class="checkbox-row">
            <input
              type="checkbox"
              checked={emoteSources().twitch}
              onchange={(e) => {
                twitch = {
                  ...twitch,
                  emote_sources: {
                    ...emoteSources(),
                    twitch: (e.currentTarget as HTMLInputElement).checked,
                  },
                };
                queueSave();
              }}
            />
            <span>{tr("tts.twitch.emote_twitch")}</span>
          </label>
          <label class="checkbox-row">
            <input
              type="checkbox"
              checked={emoteSources().bttv}
              onchange={(e) => {
                twitch = {
                  ...twitch,
                  emote_sources: {
                    ...emoteSources(),
                    bttv: (e.currentTarget as HTMLInputElement).checked,
                  },
                };
                queueSave();
              }}
            />
            <span>{tr("tts.twitch.emote_bttv")}</span>
          </label>
          <label class="checkbox-row">
            <input
              type="checkbox"
              checked={emoteSources().seventv}
              onchange={(e) => {
                twitch = {
                  ...twitch,
                  emote_sources: {
                    ...emoteSources(),
                    seventv: (e.currentTarget as HTMLInputElement).checked,
                  },
                };
                queueSave();
              }}
            />
            <span>{tr("tts.twitch.emote_7tv")}</span>
          </label>
        </div>
        <label class="checkbox-row">
          <input
            type="checkbox"
            checked={twitch.detect_language ?? true}
            onchange={(e) => {
              twitch = {
                ...twitch,
                detect_language: (e.currentTarget as HTMLInputElement).checked,
              };
              queueSave();
            }}
          />
          <span>{tr("tts.twitch.detect_language")}</span>
        </label>
        <label class="stack-field">
          <span>{tr("tts.twitch.lang_min_chars")}</span>
          <input
            class="control"
            type="number"
            min="1"
            max="32"
            value={twitch.lang_min_chars ?? 4}
            onchange={(e) => {
              twitch = {
                ...twitch,
                lang_min_chars: Number((e.currentTarget as HTMLInputElement).value) || 4,
              };
              queueSave();
            }}
          />
        </label>
        <label class="stack-field stack-field--full">
          <span>{tr("tts.twitch.allowed_languages")}</span>
          <input
            class="control"
            placeholder={tr("tts.twitch.allowed_languages_placeholder")}
            value={enabledLanguagesText}
            oninput={(e) => {
              enabledLanguagesDirty = true;
              enabledLanguagesText = (e.currentTarget as HTMLInputElement).value;
              queueSave();
            }}
            onblur={() => flushPendingSave()}
          />
        </label>
        <label class="stack-field">
          <span>{tr("tts.twitch.max_chars")}</span>
          <input
            class="control"
            type="number"
            min="16"
            max="2000"
            value={twitch.max_chars}
            onchange={(e) => {
              twitch = {
                ...twitch,
                max_chars: Number((e.currentTarget as HTMLInputElement).value) || 200,
              };
              queueSave();
            }}
          />
          <span class="muted">{tr("tts.twitch.max_chars_hint")}</span>
        </label>
        <label class="stack-field">
          <span>{tr("tts.twitch.pause_style")}</span>
          <select
            class="control"
            value={twitch.pause_style ?? "period"}
            onchange={(e) => {
              twitch = {
                ...twitch,
                pause_style: (e.currentTarget as HTMLSelectElement).value as TwitchPauseStyle,
              };
              queueSave();
            }}
          >
            <option value="period">{tr("tts.twitch.pause.period")}</option>
            <option value="comma">{tr("tts.twitch.pause.comma")}</option>
            <option value="dash">{tr("tts.twitch.pause.dash")}</option>
            <option value="ellipsis">{tr("tts.twitch.pause.ellipsis")}</option>
          </select>
        </label>
        <label class="stack-field stack-field--full">
          <span>{tr("tts.twitch.speak_template")}</span>
          <input
            class="control"
            placeholder={tr("tts.twitch.speak_template_placeholder")}
            value={twitch.speak_template ?? "{nick}. {text}"}
            oninput={(e) => {
              twitch = {
                ...twitch,
                speak_template: (e.currentTarget as HTMLInputElement).value,
              };
              queueSave();
            }}
          />
        </label>
        <label class="checkbox-row stack-field--full">
          <input
            type="checkbox"
            checked={twitch.include_builtin_profanity !== false}
            onchange={(e) => {
              twitch = {
                ...twitch,
                include_builtin_profanity: (e.currentTarget as HTMLInputElement).checked,
              };
              queueSave();
            }}
          />
          <span>{tr("tts.twitch.profanity_builtin")}</span>
        </label>
        <ReplacementPairEditor
          title={tr("tts.twitch.nick_replacements")}
          wordLabel={tr("tts.twitch.word_from")}
          replaceLabel={tr("tts.twitch.word_to")}
          wordPlaceholder={tr("tts.twitch.nick_from_placeholder")}
          replacePlaceholder={tr("tts.twitch.nick_to_placeholder")}
          addLabel={tr("tts.twitch.word_add")}
          removeLabel={tr("tts.twitch.word_remove_selected")}
          emptyLabel={tr("tts.twitch.nick_list_empty")}
          pairs={nickPairs}
          onChange={updateNickReplacements}
        />
      </div>
    </details>
  </div>

  <div class="tts-inline-actions">
    <button
      type="button"
      class="btn btn-primary"
      disabled={busy || isConnecting || isConnected || !moduleEnabled || !twitch.enabled}
      onclick={() => void handleConnect()}
    >
      {isConnecting ? tr("tts.twitch.connecting") : tr("tts.twitch.connect")}
    </button>
    <button
      type="button"
      class="btn btn-ghost"
      disabled={busy || !isConnected}
      onclick={() => void handleDisconnect()}
    >
      {tr("tts.twitch.disconnect")}
    </button>
  </div>

  {#if chatLog.length}
    <ul class="transcript-box tts-activity-log">
      {#each chatLog as line (line.id)}
        <li>
          <strong>{line.display_name}</strong>: {line.text}
          {#if line.speakable !== false}
            <span class="muted">
              → [{line.language}] {line.speak_text}
              {#if line.clean_text && line.clean_text !== line.text}
                ({tr("tts.twitch.clean")}: {line.clean_text})
              {/if}
            </span>
          {:else}
            <span class="muted"> {tr("tts.twitch.filtered")}</span>
          {/if}
        </li>
      {/each}
    </ul>
  {:else}
    <p class="muted">{tr("tts.twitch.chat_empty")}</p>
  {/if}
</section>
