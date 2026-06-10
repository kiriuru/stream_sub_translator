use std::fs;
use std::path::PathBuf;
use std::sync::Arc;

use serde_json::Value;

use tauri::{AppHandle, Manager, State, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

use tracing::{debug, info, warn};

use voicesub_twitch::{SourceTextReplacementSettings, TwitchTtsSettings};
use voicesub_audio::{PlaybackHub, CHANNEL_SPEECH, CHANNEL_TWITCH};
use voicesub_tts::{
    bind_window_process, build_tts_module_url, speech_queue_item_id, tts_webview_data_dir,
    validate_twitch_oauth_url, SpeechQueueItem, TtsConfig, TtsModuleService, TtsSpeechSettings,
    TTS_WINDOW_LABEL,
};
use voicesub_twitch::TwitchConnectionStatus;

/// Close the module window when the desktop shell shuts down (same lifecycle as browser worker).
pub fn close_tts_window(app: &AppHandle) {
    let Some(window) = app.get_webview_window(TTS_WINDOW_LABEL) else {
        return;
    };
    info!(
        target: "voicesub.tts.ipc",
        "closing tts module window on app shutdown"
    );
    let _ = window.destroy();
}

pub struct TtsState {
    pub service: Arc<TtsModuleService>,
    pub bind_addr: std::net::SocketAddr,
    pub playback: Arc<PlaybackHub>,
}

pub fn sync_playback_devices(state: &TtsState) {
    let Ok(config) = state.service.load_config() else {
        return;
    };
    let speech_label = TtsModuleService::device_label_for_channel(&config, CHANNEL_SPEECH);
    let twitch_label = TtsModuleService::device_label_for_channel(&config, CHANNEL_TWITCH);
    let _ = state
        .playback
        .set_device_label(CHANNEL_SPEECH, speech_label);
    let _ = state
        .playback
        .set_device_label(CHANNEL_TWITCH, twitch_label);
}



#[tauri::command]

pub fn tts_get_config(state: State<'_, TtsState>) -> Result<TtsConfig, String> {

    debug!(target: "voicesub.tts.ipc", "tts_get_config");

    state.service.load_config().map_err(|e| e.to_string())

}



#[tauri::command]

pub fn tts_set_provider(state: State<'_, TtsState>, provider: String) -> Result<TtsConfig, String> {
    info!(target: "voicesub.tts.ipc", provider = %provider, "tts_set_provider");
    state
        .service
        .set_tts_provider(&provider)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn tts_set_enabled(state: State<'_, TtsState>, enabled: bool) -> Result<TtsConfig, String> {

    info!(target: "voicesub.tts.ipc", enabled, "tts_set_enabled");

    state

        .service

        .set_enabled(enabled)

        .map_err(|e| e.to_string())

}



#[tauri::command]

pub fn tts_set_audio_device(
    state: State<'_, TtsState>,
    device_id: String,
    device_label: Option<String>,
) -> Result<TtsConfig, String> {
    info!(
        target: "voicesub.tts.ipc",
        device_id = if device_id.is_empty() { "default" } else { device_id.as_str() },
        device_label = device_label.as_deref().unwrap_or(""),
        "tts_set_audio_device"
    );

    if !state.service.validate_device_id(&device_id) {
        warn!(target: "voicesub.tts.ipc", device_id = %device_id, "unknown audio device rejected");
        return Err(format!("unknown audio device: {device_id}"));
    }

    let config = state
        .service
        .set_audio_device(&device_id, device_label.as_deref())
        .map_err(|e| e.to_string())?;
    let label = TtsModuleService::device_label_for_channel(&config, CHANNEL_SPEECH);
    state
        .playback
        .set_device_label(CHANNEL_SPEECH, label)
        .map_err(|e| e.to_string())?;
    Ok(config)
}

#[tauri::command]
pub fn tts_set_channel_audio_device(
    state: State<'_, TtsState>,
    channel: String,
    device_id: String,
    device_label: Option<String>,
) -> Result<TtsConfig, String> {
    info!(
        target: "voicesub.tts.ipc",
        channel = %channel,
        device_id = if device_id.is_empty() { "default" } else { device_id.as_str() },
        device_label = device_label.as_deref().unwrap_or(""),
        "tts_set_channel_audio_device"
    );
    let config = state
        .service
        .set_channel_audio_device(&channel, &device_id, device_label.as_deref())
        .map_err(|e| e.to_string())?;
    let label = TtsModuleService::device_label_for_channel(&config, channel.as_str());
    state
        .playback
        .set_device_label(channel.as_str(), label)
        .map_err(|e| e.to_string())?;
    Ok(config)
}

#[tauri::command]
pub fn tts_set_playback_mode(
    state: State<'_, TtsState>,
    mode: String,
) -> Result<TtsConfig, String> {
    info!(target: "voicesub.tts.ipc", mode = %mode, "tts_set_playback_mode");
    let config = state
        .service
        .set_playback_mode(&mode)
        .map_err(|e| e.to_string())?;
    sync_playback_devices(&state);
    Ok(config)
}

#[tauri::command]
pub fn tts_play_audio(
    state: State<'_, TtsState>,
    channel: String,
    item_id: String,
    audio_bytes: Vec<u8>,
    volume: f32,
    rate: Option<f32>,
) -> Result<(), String> {
    let rate = rate.unwrap_or(1.0);
    debug!(
        target: "voicesub.tts.ipc",
        channel = %channel,
        item_id = %item_id,
        bytes = audio_bytes.len(),
        volume,
        rate,
        "tts_play_audio"
    );
    state
        .playback
        .play(&channel, item_id, audio_bytes, volume, rate)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn tts_stop_channel(state: State<'_, TtsState>, channel: String) -> Result<(), String> {
    info!(target: "voicesub.tts.ipc", channel = %channel, "tts_stop_channel");
    state
        .playback
        .stop_channel(&channel)
        .map_err(|e| e.to_string())
}



#[tauri::command]

pub fn tts_list_output_devices() -> Result<Vec<voicesub_audio::AudioOutputDevice>, String> {

    debug!(target: "voicesub.tts.ipc", "tts_list_output_devices");

    voicesub_audio::list_output_devices_on_thread().map_err(|e| e.to_string())

}



#[tauri::command]

pub fn tts_get_audio_routing() -> Result<String, String> {

    Ok(if voicesub_audio::is_per_process_routing_enabled() {

        "winapi".to_string()

    } else {

        "browser".to_string()

    })

}



#[tauri::command]

pub fn tts_bind_window_audio(

    app: AppHandle,

    state: State<'_, TtsState>,

) -> Result<TtsConfig, String> {

    let window = app

        .get_webview_window(TTS_WINDOW_LABEL)

        .ok_or_else(|| "TTS window is not open".to_string())?;

    bind_tts_window_audio(&state.service, &window)

}



#[tauri::command]

pub fn tts_update_speech_settings(

    state: State<'_, TtsState>,

    speech: TtsSpeechSettings,

) -> Result<TtsConfig, String> {

    info!(target: "voicesub.tts.ipc", "tts_update_speech_settings");

    state

        .service

        .update_speech_settings(speech)

        .map_err(|e| e.to_string())

}



#[tauri::command]

pub fn tts_update_voice_settings(
    state: State<'_, TtsState>,
    speech_rate: f32,
    speech_volume: f32,
) -> Result<TtsConfig, String> {
    info!(
        target: "voicesub.tts.ipc",
        speech_rate,
        speech_volume,
        "tts_update_voice_settings"
    );
    state
        .service
        .update_voice_settings(speech_rate, speech_volume)
        .map_err(|e| e.to_string())
}



#[tauri::command]

pub fn tts_plan_subtitle_speech(

    state: State<'_, TtsState>,

    payload: Value,

) -> Result<Vec<SpeechQueueItem>, String> {

    let sequence = payload

        .get("sequence")

        .and_then(|v| v.as_u64())

        .unwrap_or(0);

    debug!(

        target: "voicesub.tts.ipc",

        sequence,

        "tts_plan_subtitle_speech"

    );

    Ok(state.service.plan_subtitle_speech(&payload))

}



#[tauri::command]

pub fn tts_reset_subtitle_planner(state: State<'_, TtsState>) -> Result<(), String> {

    info!(target: "voicesub.tts.ipc", "tts_reset_subtitle_planner");

    state.service.reset_subtitle_planner();

    Ok(())

}



#[tauri::command]
pub fn tts_channel_enqueue(
    state: State<'_, TtsState>,
    channel: String,
    id: String,
    text: String,
    lang: String,
) -> Result<usize, String> {
    info!(
        target: "voicesub.tts.ipc",
        channel = %channel,
        id = %id,
        text_len = text.chars().count(),
        lang = %lang,
        "tts_channel_enqueue"
    );
    state
        .service
        .enqueue_channel(
            &channel,
            SpeechQueueItem {
                id,
                text,
                source: channel.clone(),
                lang,
            },
        )
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn tts_channel_begin_next(
    state: State<'_, TtsState>,
    channel: String,
) -> Result<Option<SpeechQueueItem>, String> {
    state
        .service
        .queue_begin_next(&channel)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn tts_channel_finish(
    state: State<'_, TtsState>,
    channel: String,
    item_id: String,
) -> Result<(), String> {
    state
        .service
        .queue_mark_finished(&channel, &item_id)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn tts_channel_clear(state: State<'_, TtsState>, channel: String) -> Result<(), String> {
    info!(target: "voicesub.tts.ipc", channel = %channel, "tts_channel_clear");
    state
        .service
        .queue_clear_channel(&channel)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn tts_channel_snapshot(
    state: State<'_, TtsState>,
    channel: String,
) -> Result<Vec<SpeechQueueItem>, String> {
    state
        .service
        .queue_snapshot(&channel)
        .map_err(|e| e.to_string())
}

/// Deprecated: use [`tts_channel_enqueue`] with channel `speech`.
#[tauri::command]
pub fn tts_enqueue(
    state: State<'_, TtsState>,
    text: String,
    source: Option<String>,
) -> Result<usize, String> {
    let id = speech_queue_item_id();
    warn!(
        target: "voicesub.tts.ipc",
        id = %id,
        "tts_enqueue is deprecated; use tts_channel_enqueue"
    );
    state
        .service
        .enqueue_channel(
            voicesub_audio::CHANNEL_SPEECH,
            SpeechQueueItem {
                id,
                text,
                source: source.unwrap_or_default(),
                lang: "en".to_string(),
            },
        )
        .map_err(|e| e.to_string())
}



#[tauri::command]
pub fn tts_twitch_get_status(state: State<'_, TtsState>) -> Result<TwitchConnectionStatus, String> {
    let status = state.service.twitch_status();
    debug!(
        target: "voicesub.tts.ipc",
        state = ?status.state,
        channel = %status.channel,
        "tts_twitch_get_status"
    );
    Ok(status)
}

#[tauri::command]
pub fn tts_twitch_connect(state: State<'_, TtsState>) -> Result<TwitchConnectionStatus, String> {
    info!(target: "voicesub.tts.ipc", "tts_twitch_connect");
    state.service.twitch_connect().map_err(|e| {
        warn!(target: "voicesub.tts.ipc", error = %e, "tts_twitch_connect failed");
        e.to_string()
    })
}

#[tauri::command]
pub fn tts_twitch_disconnect(state: State<'_, TtsState>) -> Result<(), String> {
    info!(target: "voicesub.tts.ipc", "tts_twitch_disconnect");
    state.service.twitch_disconnect();
    Ok(())
}

#[tauri::command]
pub fn tts_update_twitch_settings(
    state: State<'_, TtsState>,
    twitch: TwitchTtsSettings,
) -> Result<TtsConfig, String> {
    info!(
        target: "voicesub.tts.ipc",
        channel = %twitch.normalized_channel(),
        enabled = twitch.enabled,
        "tts_update_twitch_settings"
    );
    let config = state
        .service
        .update_twitch_settings(twitch)
        .map_err(|e| {
            warn!(target: "voicesub.tts.ipc", error = %e, "tts_update_twitch_settings failed");
            e.to_string()
        })?;
    let label = TtsModuleService::device_label_for_channel(&config, CHANNEL_TWITCH);
    state
        .playback
        .set_device_label(CHANNEL_TWITCH, label)
        .map_err(|e| e.to_string())?;
    Ok(config)
}

#[tauri::command]
pub fn tts_sync_source_text_replacement(
    state: State<'_, TtsState>,
    replacement: SourceTextReplacementSettings,
) -> Result<(), String> {
    info!(
        target: "voicesub.tts.ipc",
        enabled = replacement.enabled,
        pairs = replacement.pairs.len(),
        "tts_sync_source_text_replacement"
    );
    state
        .service
        .sync_source_text_replacement(replacement)
        .map_err(|e| {
            warn!(
                target: "voicesub.tts.ipc",
                error = %e,
                "tts_sync_source_text_replacement failed"
            );
            e.to_string()
        })
}

#[tauri::command]
pub fn tts_open_system_url(url: String) -> Result<(), String> {
    validate_twitch_oauth_url(&url)?;
    let trimmed = url.trim();
    info!(target: "voicesub.tts.ipc", url = %trimmed, "opening twitch oauth in system browser");
    open::that(trimmed).map_err(|err| err.to_string())
}

#[tauri::command]

pub async fn tts_open_window(app: AppHandle, state: State<'_, TtsState>) -> Result<(), String> {

    if let Some(window) = app.get_webview_window(TTS_WINDOW_LABEL) {

        info!(target: "voicesub.tts.ipc", "tts window focus existing");

        let _ = window.show();

        let _ = window.set_focus();

        if voicesub_audio::is_per_process_routing_enabled() {
            let _ = bind_tts_window_audio(&state.service, &window);
        }

        return Ok(());

    }



    let url = build_tts_module_url(state.bind_addr);

    info!(target: "voicesub.tts.ipc", url = %url, "creating tts window");

    let parsed = url

        .parse::<url::Url>()

        .map_err(|e| e.to_string())?;

    let data_dir: PathBuf = tts_webview_data_dir(state.service.config_path());
    let _ = fs::create_dir_all(&data_dir);

    let window = WebviewWindowBuilder::new(&app, TTS_WINDOW_LABEL, WebviewUrl::External(parsed))

        .title("VoiceSub TTS")

        .inner_size(720.0, 560.0)

        .min_inner_size(480.0, 420.0)

        .resizable(true)

        .data_directory(data_dir)

        .build()

        .map_err(|e| e.to_string())?;



    if voicesub_audio::is_per_process_routing_enabled() {
        let _ = bind_tts_window_audio(&state.service, &window);
    }

    info!(target: "voicesub.tts.ipc", "tts module window opened");

    Ok(())

}



fn bind_tts_window_audio(
    service: &TtsModuleService,
    window: &WebviewWindow,
) -> Result<TtsConfig, String> {
    let pid = window_process_id(window).ok_or_else(|| {
        warn!(target: "voicesub.tts.ipc", "unable to resolve TTS window process id");
        "unable to resolve TTS window process id".to_string()
    })?;
    debug!(target: "voicesub.tts.ipc", pid, "binding tts window audio route");
    bind_window_process(service, pid)
}

fn window_process_id(window: &WebviewWindow) -> Option<u32> {

    #[cfg(windows)]

    {

        use windows::Win32::UI::WindowsAndMessaging::GetWindowThreadProcessId;

        let hwnd = window.hwnd().ok()?;

        let mut pid = 0u32;

        unsafe {

            GetWindowThreadProcessId(hwnd, Some(&mut pid));

        }

        if pid == 0 { None } else { Some(pid) }

    }

    #[cfg(not(windows))]

    {

        let _ = window;

        None

    }

}

