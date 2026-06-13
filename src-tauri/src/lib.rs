mod shell;
mod tts;

#[cfg(windows)]
mod webview2_gate;
mod webview_memory;

use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tauri::{Emitter, LogicalSize, Manager, State, WebviewWindow, WindowEvent};
use voicesub_audio::PlaybackHub;
use tracing::{info, warn};
use voicesub_config::{
    discover_project_root, ensure_runtime_data_dirs, http_bind_from_env,
    read_full_logging_enabled_from_user_data, AppConfig, ProjectPaths,
};
use serde_json::json;
use voicesub_logging::{
    complete_graceful_shutdown, init_tracing_backbone, install_lifecycle_hooks, log_shutdown_begin,
    log_shutdown_step, set_config_full_logging_enabled,
};
use voicesub_runtime::{RuntimeHandle, RuntimeService};
use voicesub_tts::{TtsModuleService, TTS_WINDOW_LABEL, TwitchOAuthBridge};

use crate::tts::TtsState;
use crate::webview_memory::{SharedWebviewMemoryManager, WebviewMemoryManager};

struct AppState {
    runtime: Arc<RuntimeService>,
    handle: Mutex<Option<RuntimeHandle>>,
    bind_addr: SocketAddr,
    project_root: PathBuf,
    /// Keeps the tokio runtime alive for the embedded HTTP server task.
    _http_runtime: tokio::runtime::Runtime,
}

#[tauri::command]
fn voicesub_version() -> String {
    voicesub_types::PROJECT_VERSION.to_string()
}

#[tauri::command]
fn set_dashboard_layout(window: WebviewWindow, compact: bool) -> Result<(), String> {
    if compact {
        window
            .set_size(LogicalSize::new(390.0, 844.0))
            .map_err(|e| e.to_string())?;
        window
            .set_min_size(Some(LogicalSize::new(360.0, 640.0)))
            .map_err(|e| e.to_string())?;
        window
            .set_max_size(Some(LogicalSize::new(430.0, 932.0)))
            .map_err(|e| e.to_string())?;
    } else {
        window.set_max_size(None::<LogicalSize<f64>>).map_err(|e| e.to_string())?;
        window
            .set_min_size(Some(LogicalSize::new(960.0, 640.0)))
            .map_err(|e| e.to_string())?;
        window
            .set_size(LogicalSize::new(1280.0, 900.0))
            .map_err(|e| e.to_string())?;
    }
    window.center().map_err(|e| e.to_string())?;
    info!(compact, "dashboard window layout applied");
    Ok(())
}

#[tauri::command]
async fn launch_browser_worker(state: State<'_, AppState>) -> Result<String, String> {
    let result = state
        .runtime
        .launch_browser_worker()
        .await
        .map_err(|err| err.to_string())?;
    info!(pid = result.pid, %state.bind_addr, "browser worker launched via IPC");
    Ok(format!("pid={}", result.pid))
}

async fn stop_runtime_session(bind_addr: SocketAddr) {
    let stop_url = format!("http://{bind_addr}/api/runtime/stop");
    match reqwest::Client::new().post(&stop_url).send().await {
        Ok(response) if response.status().is_success() => {
            info!(%bind_addr, "runtime stop requested before desktop exit");
        }
        Ok(response) => {
            tracing::warn!(
                %bind_addr,
                status = %response.status(),
                "runtime stop returned non-success before desktop exit"
            );
        }
        Err(err) => {
            tracing::warn!(%bind_addr, error = %err, "runtime stop request failed before desktop exit");
        }
    }
    tokio::time::sleep(Duration::from_millis(120)).await;
}

pub fn run() {
    #[cfg(windows)]
    if !webview2_gate::ensure_runtime_available() {
        return;
    }

    voicesub_twitch::init_crypto_provider();
    let project_root = discover_project_root();
    let paths = ProjectPaths::discover(&project_root);
    ensure_runtime_data_dirs(&paths).expect("failed to ensure runtime user-data/logs directories");
    set_config_full_logging_enabled(read_full_logging_enabled_from_user_data(
        &paths.user_data_dir,
    ));
    init_tracing_backbone(&project_root);
    install_lifecycle_hooks(&project_root, voicesub_types::PROJECT_VERSION);
    let mut config = AppConfig::default();
    config.http.host = http_bind_from_env(None);
    if voicesub_config::allow_lan_from_env() {
        warn!("VOICESUB_ALLOW_LAN is enabled — HTTP API binds without localhost restriction");
    }
    let oauth_bridge = Arc::new(TwitchOAuthBridge::default());
    let runtime_service = Arc::new(RuntimeService::with_config(
        &project_root,
        config.clone(),
        oauth_bridge.clone(),
    ));

    let http_runtime = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .thread_name("voicesub-http")
        .build()
        .expect("failed to build HTTP tokio runtime");

    let handle = http_runtime
        .block_on(runtime_service.start())
        .expect("failed to start VoiceSub runtime");

    let bind_addr = handle.bind_addr;
    info!(%bind_addr, "runtime started for Tauri shell");

    let http_handle = http_runtime.handle().clone();
    let ws_publisher = runtime_service.ws_publisher();
    let publisher_for_tts = ws_publisher.clone();
    let broadcaster_handle = http_handle.clone();
    let tts_broadcaster: voicesub_twitch::EventBroadcaster = Arc::new(move |message| {
        let publisher = publisher_for_tts.clone();
        let handle = broadcaster_handle.clone();
        handle.spawn(async move {
            let channel = message
                .get("type")
                .and_then(|value| value.as_str())
                .unwrap_or("event")
                .to_string();
            let payload = message.get("payload").cloned().unwrap_or(message);
            publisher
                .broadcast_channel(&channel, &channel, payload)
                .await;
        });
    });
    let tts_service = Arc::new(TtsModuleService::with_broadcaster(
        project_root.join("user-data"),
        tts_broadcaster,
        oauth_bridge,
        http_handle,
    ));

    let (playback_hub, completion_rx) = PlaybackHub::spawn();
    let playback_hub = Arc::new(playback_hub);
    let webview_memory = Mutex::new(WebviewMemoryManager::default());

    tauri::Builder::default()
        .manage(AppState {
            runtime: runtime_service,
            handle: Mutex::new(Some(handle)),
            bind_addr,
            project_root: project_root.clone(),
            _http_runtime: http_runtime,
        })
        .manage(TtsState {
            service: tts_service.clone(),
            bind_addr,
            playback: playback_hub.clone(),
        })
        .manage(webview_memory)
        .invoke_handler(tauri::generate_handler![
            voicesub_version,
            launch_browser_worker,
            set_dashboard_layout,
            tts::tts_get_config,
            tts::tts_set_provider,
            tts::tts_set_enabled,
            tts::tts_set_audio_device,
            tts::tts_set_channel_audio_device,
            tts::tts_set_playback_mode,
            tts::tts_play_audio,
            tts::tts_stop_channel,
            tts::tts_list_output_devices,
            tts::tts_get_audio_routing,
            tts::tts_bind_window_audio,
            tts::tts_update_speech_settings,
            tts::tts_update_voice_settings,
            tts::tts_plan_subtitle_speech,
            tts::tts_reset_subtitle_planner,
            tts::tts_channel_enqueue,
            tts::tts_channel_begin_next,
            tts::tts_channel_finish,
            tts::tts_channel_clear,
            tts::tts_channel_snapshot,
            tts::tts_channel_force_idle,
            tts::tts_get_resource_telemetry,
            tts::tts_enqueue,
            tts::tts_twitch_get_status,
            tts::tts_twitch_connect,
            tts::tts_twitch_disconnect,
            tts::tts_update_twitch_settings,
            tts::tts_sync_source_text_replacement,
            tts::tts_open_window,
            tts::tts_open_system_url,
            tts::tts_report_webview_activity,
            shell::open_external_https_url,
            shell::open_local_http_url,
        ])
        .setup(move |app| {
            let url = format!("http://{}:{}/", bind_addr.ip(), bind_addr.port());
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.eval(format!("window.location.replace('{url}');"));
                if let Ok(mut guard) = app.state::<SharedWebviewMemoryManager>().lock() {
                    guard.set_main_focused(true);
                    guard.set_tts_visible(false);
                }
                crate::webview_memory::refresh_from_state(
                    &app.handle(),
                    app.state::<SharedWebviewMemoryManager>().inner(),
                );
            }
            let tts_state = app.state::<TtsState>();
            tts::sync_playback_devices(&tts_state);
            let app_handle = app.handle().clone();
            std::thread::Builder::new()
                .name("voicesub-tts-playback-events".into())
                .spawn(move || {
                    while let Ok(finished) = completion_rx.recv() {
                        let _ = app_handle.emit("playback-finished", finished);
                    }
                })
                .expect("spawn playback completion event thread");
            Ok(())
        })
        .on_window_event(|window, event| {
            match event {
                WindowEvent::Focused(focused) => {
                    let memory = window.state::<SharedWebviewMemoryManager>();
                    if let Ok(mut guard) = memory.lock() {
                        match window.label() {
                            "main" => guard.set_main_focused(*focused),
                            "tts" => guard.set_tts_focused(*focused),
                            _ => {}
                        }
                    }
                    if window.label() == "tts" {
                        crate::webview_memory::sync_tts_window_visibility(
                            &window.app_handle(),
                            memory.inner(),
                        );
                    } else {
                        crate::webview_memory::refresh_from_state(
                            &window.app_handle(),
                            memory.inner(),
                        );
                    }
                }
                WindowEvent::CloseRequested { .. } if window.label() == TTS_WINDOW_LABEL => {
                    tts::recover_tts_after_window_closed(window.state::<TtsState>().inner());
                    let memory = window.state::<SharedWebviewMemoryManager>();
                    if let Ok(mut guard) = memory.lock() {
                        guard.set_tts_visible(false);
                        guard.set_tts_focused(false);
                    }
                    crate::webview_memory::refresh_from_state(
                        &window.app_handle(),
                        memory.inner(),
                    );
                }
                WindowEvent::CloseRequested { api, .. } if window.label() == "main" => {
                    api.prevent_close();
                    let bind_addr = window.state::<AppState>().bind_addr;
                    let app = window.app_handle().clone();
                    let window = window.clone();
                    let tts_service = app.state::<TtsState>().service.clone();
                    tauri::async_runtime::spawn(async move {
                        let project_root = window.state::<AppState>().project_root.clone();
                        log_shutdown_begin("user_close");
                        log_shutdown_step("tts_shutdown", json!({}));
                        tts_service.shutdown();
                        log_shutdown_step("tts_window_close", json!({}));
                        tts::close_tts_window(&app);
                        log_shutdown_step("runtime_stop_request", json!({ "bind_addr": bind_addr.to_string() }));
                        stop_runtime_session(bind_addr).await;
                        let shutdown_handle = window
                            .state::<AppState>()
                            .handle
                            .lock()
                            .ok()
                            .and_then(|mut guard| guard.take());
                        if let Some(handle) = shutdown_handle {
                            log_shutdown_step("runtime_shutdown", json!({}));
                            handle.shutdown().await;
                        } else {
                            log_shutdown_step("runtime_shutdown_skipped", json!({ "reason": "handle_missing" }));
                        }
                        complete_graceful_shutdown(&project_root, "user_close");
                        let _ = window.destroy();
                    });
                }
                _ => {}
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running VoiceSub");
}
