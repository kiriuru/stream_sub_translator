use std::net::SocketAddr;

use std::path::PathBuf;

use std::sync::{
    atomic::AtomicBool,
    Arc, RwLock as StdRwLock,
};

use tokio::sync::RwLock as TokioRwLock;

use axum::Router;

use tokio::sync::RwLock;

use tracing::{info, instrument};

use voicesub_browser::{
    structured_log_from_runtime_logger as browser_structured_log_from_runtime_logger, BrowserAsrGateway,
    BrowserAsrService, BrowserWorkerLauncher, StatusCallback, WorkerLifecycleCallback,
};

use voicesub_config::{
    base_url_from_socket, default_config_payload, worker_url_for_payload, AppConfig, ConfigStore,
    ProjectPaths,
};
use voicesub_export::ExportService;
use crate::http::{
    build_router, spawn_runtime_heartbeat, spawn_startup_check, HttpState, PartialEmitCoordinator,
    RuntimeMetricsCollector, RuntimeStatusBroadcaster, StylePresetsFn,
};
use voicesub_config::read_full_logging_enabled;
use voicesub_logging::{
    apply_logging_preferences, ensure_logs_dir, SessionLogManager, StructuredRuntimeLogger,
};
use voicesub_obs::{structured_log_from_runtime_logger as obs_structured_log_from_runtime_logger, ObsCaptionService};

use voicesub_subtitle::{
    structured_log_from_runtime_logger, ConfigGetter, OverlayBroadcaster, PublishCallback,
    SubtitleLog, SubtitleRouter,
};
use voicesub_ws::{
    shared_event_sequencer, ws_structured_log_from_runtime_logger, AsrWorkerHub, EventsHub,
    WsEventPublisher, WsLog,
};

use crate::trace::{structured_log_from_runtime_logger as runtime_pipeline_structured_log, RuntimePipelineLog};

use voicesub_translation::{
    arc_publish, arc_relevance, TranslationRuntimeController,
};

use crate::browser_event_builder::BrowserTranscriptEventBuilder;
use crate::browser_speech_source::{BrowserSpeechSource, SharedBrowserSpeechSource};
use crate::transcript_controller::TranscriptController;

use voicesub_tts::TwitchOAuthBridge;
use voicesub_types::PROJECT_VERSION;

#[derive(Debug, thiserror::Error)]

pub enum RuntimeError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),

    #[error("config error: {0}")]
    Config(#[from] voicesub_config::ConfigError),

    #[error("runtime server failed: {0}")]
    Server(String),
}

pub struct RuntimeHandle {
    pub bind_addr: SocketAddr,

    shutdown: Option<tokio::sync::oneshot::Sender<()>>,

    server_task: Option<tokio::task::JoinHandle<()>>,

    heartbeat_task: Option<tokio::task::JoinHandle<()>>,
}

impl RuntimeHandle {
    pub async fn shutdown(mut self) {
        if let Some(shutdown) = self.shutdown.take() {
            let _ = shutdown.send(());
        }
        let mut server_task = self
            .server_task
            .take()
            .expect("runtime server task missing");
        let abort_handle = server_task.abort_handle();
        match tokio::time::timeout(std::time::Duration::from_secs(5), &mut server_task).await {
            Ok(_) => {}
            Err(_) => {
                tracing::warn!("runtime server graceful shutdown timed out; aborting task");
                abort_handle.abort();
                let _ = server_task.await;
            }
        }
        if let Some(heartbeat_task) = self.heartbeat_task.take() {
            heartbeat_task.abort();
        }
    }
}

impl Drop for RuntimeHandle {
    fn drop(&mut self) {
        if let Some(shutdown) = self.shutdown.take() {
            let _ = shutdown.send(());
        }
        if let Some(heartbeat_task) = self.heartbeat_task.take() {
            heartbeat_task.abort();
        }
        if let Some(server_task) = self.server_task.take() {
            server_task.abort();
        }
    }
}

pub struct RuntimeService {
    pub config: AppConfig,

    pub paths: ProjectPaths,

    config_store: Arc<RwLock<ConfigStore>>,

    config_snapshot: Arc<StdRwLock<serde_json::Value>>,

    bind_addr: Arc<TokioRwLock<Option<SocketAddr>>>,

    events: EventsHub,

    ws_publisher: WsEventPublisher,

    runtime_broadcaster: Arc<RuntimeStatusBroadcaster>,

    pipeline_log: RuntimePipelineLog,

    subtitle: Arc<SubtitleRouter>,

    translation: Arc<tokio::sync::Mutex<TranslationRuntimeController>>,

    browser_asr: Arc<BrowserAsrService>,

    asr_worker: AsrWorkerHub,

    obs_captions: Arc<ObsCaptionService>,

    runtime_metrics: Arc<RuntimeMetricsCollector>,

    partial_emit: Arc<tokio::sync::Mutex<PartialEmitCoordinator>>,

    runtime_running: Arc<AtomicBool>,

    browser_speech: Arc<SharedBrowserSpeechSource>,

    twitch_oauth: Arc<TwitchOAuthBridge>,

    structured_runtime_logger: Arc<StructuredRuntimeLogger>,
}

impl RuntimeService {
    pub fn new(project_root: impl Into<PathBuf>) -> Self {
        Self::with_config(
            project_root,
            AppConfig::default(),
            Arc::new(TwitchOAuthBridge::default()),
        )
    }

    pub fn with_config(
        project_root: impl Into<PathBuf>,
        config: AppConfig,
        twitch_oauth: Arc<TwitchOAuthBridge>,
    ) -> Self {
        Self::build(ProjectPaths::discover(project_root), config, twitch_oauth)
    }

    /// Workspace assets with an isolated `user-data` + `logs` tree (integration tests).
    pub fn with_config_isolated_user_data(
        project_root: impl Into<PathBuf>,
        user_data_dir: impl Into<PathBuf>,
        config: AppConfig,
        twitch_oauth: Arc<TwitchOAuthBridge>,
    ) -> Self {
        let project_root = project_root.into();
        let user_data_dir = user_data_dir.into();
        let mut paths = ProjectPaths::discover(&project_root);
        paths.user_data_dir = user_data_dir.clone();
        paths.logs_dir = user_data_dir.join("logs");
        Self::build(paths, config, twitch_oauth)
    }

    fn build(
        paths: ProjectPaths,
        config: AppConfig,
        twitch_oauth: Arc<TwitchOAuthBridge>,
    ) -> Self {
        let config_store = Arc::new(RwLock::new(ConfigStore::new(paths.config_toml_path())));

        let config_snapshot = Arc::new(StdRwLock::new(default_config_payload()));

        let structured_runtime_logger =
            Arc::new(StructuredRuntimeLogger::new(&paths.logs_dir));
        let runtime_metrics = Arc::new(RuntimeMetricsCollector::new());
        let pipeline_log = RuntimePipelineLog::new(Some(runtime_pipeline_structured_log(
            structured_runtime_logger.clone(),
        )));
        let ws_log = WsLog::new(Some(ws_structured_log_from_runtime_logger(
            structured_runtime_logger.clone(),
        )));
        let events = EventsHub::with_log(ws_log);
        let ws_publisher = WsEventPublisher::new(events.clone(), shared_event_sequencer());
        let runtime_broadcaster = Arc::new(RuntimeStatusBroadcaster::new(
            ws_publisher.clone(),
            1_000,
            pipeline_log.clone(),
            runtime_metrics.clone(),
        ));
        let subtitle_structured_log =
            structured_log_from_runtime_logger(structured_runtime_logger.clone());
        let subtitle_log = SubtitleLog::new(Some(subtitle_structured_log.clone()));

        let publisher_for_overlay = ws_publisher.clone();
        let overlay_broadcaster = Arc::new(OverlayBroadcaster::new(
            Arc::new({
                let publisher = publisher_for_overlay.clone();
                move |message| {
                    let channel = message
                        .get("type")
                        .and_then(|value| value.as_str())
                        .unwrap_or("overlay_update")
                        .to_string();
                    let body = message.get("payload").cloned().unwrap_or(message);
                    publisher.broadcast_overlay_body_now(&channel, "overlay_update", body);
                }
            }),
            subtitle_log,
        ));

        let publisher_for_publish = ws_publisher.clone();
        let publish: PublishCallback = Arc::new(move |payload| {
            let overlay = overlay_broadcaster.clone();
            let publisher = publisher_for_publish.clone();
            overlay.publish(&payload);
            let subtitle_body = serde_json::to_value(&payload).unwrap_or_default();
            publisher.broadcast_overlay_body_now(
                "subtitle_payload_update",
                "overlay_update",
                subtitle_body,
            );
        });

        let config_getter: ConfigGetter = {
            let snapshot = config_snapshot.clone();

            Arc::new(move || snapshot.read().unwrap_or_else(|e| e.into_inner()).clone())
        };

        let obs_structured_log =
            obs_structured_log_from_runtime_logger(structured_runtime_logger.clone());
        let obs_captions =
            ObsCaptionService::new(config_getter.clone(), Some(obs_structured_log));

        let obs_for_publish = obs_captions.clone();
        let base_publish = publish.clone();
        let publish_with_obs: PublishCallback = Arc::new(move |payload| {
            obs_for_publish.publish_payload(payload.clone());
            base_publish(payload);
        });

        let subtitle = SubtitleRouter::new(
            config_getter.clone(),
            publish_with_obs,
            Some(subtitle_structured_log),
        );

        let subtitle_for_translation_publish = subtitle.clone();

        let publisher_for_translation = ws_publisher.clone();

        let translation_publish = arc_publish(move |event| {
            let subtitle = subtitle_for_translation_publish.clone();

            let publisher = publisher_for_translation.clone();

            async move {
                let relevant = subtitle
                    .is_sequence_relevant_for_presentation(event.sequence)
                    .await;
                subtitle.handle_translation(event.clone()).await;

                if relevant {
                    let body = serde_json::to_value(&event).unwrap_or_default();

                    publisher.broadcast_channel_now(
                        "translation_update",
                        "translation_update",
                        body,
                    );
                }
            }
        });

        let subtitle_for_relevance = subtitle.clone();

        let translation_relevance = arc_relevance(move |sequence| {
            let subtitle = subtitle_for_relevance.clone();

            async move {
                subtitle
                    .is_sequence_relevant_for_translation(sequence)
                    .await
            }
        });

        let translation_cache_dir = paths.user_data_dir.join("cache");
        let translation = Arc::new(tokio::sync::Mutex::new(TranslationRuntimeController::new(
            config_getter,
            translation_publish,
            translation_relevance,
            Some(translation_cache_dir),
        )));

        let partial_emit = Arc::new(tokio::sync::Mutex::new(PartialEmitCoordinator::default()));

        let runtime_running = Arc::new(AtomicBool::new(false));

        let transcript_controller = Arc::new(TranscriptController::new(
            subtitle.clone(),
            translation.clone(),
            obs_captions.clone(),
            ws_publisher.clone(),
            config_snapshot.clone(),
            pipeline_log.clone(),
            runtime_metrics.clone(),
        ));

        let event_builder = Arc::new(BrowserTranscriptEventBuilder::new(
            runtime_running.clone(),
            partial_emit.clone(),
            pipeline_log.clone(),
        ));

        let browser_structured_log =
            browser_structured_log_from_runtime_logger(structured_runtime_logger.clone());
        let browser_asr_gateway = Arc::new(std::sync::Mutex::new(BrowserAsrGateway::new(Some(
            browser_structured_log,
        ))));

        let browser_speech = SharedBrowserSpeechSource::new(BrowserSpeechSource::new(
            runtime_running.clone(),
            event_builder,
            transcript_controller,
            config_snapshot.clone(),
            browser_asr_gateway.clone(),
            runtime_metrics.clone(),
        ));

        let gateway_for_status = browser_asr_gateway.clone();
        let on_status_update: StatusCallback = Arc::new(move |payload| {
            if let Ok(mut gateway) = gateway_for_status.lock() {
                gateway.update_status(&payload);
            }
        });

        let gateway_for_connected = browser_asr_gateway.clone();
        let on_worker_connected: WorkerLifecycleCallback = Arc::new(move || {
            if let Ok(mut gateway) = gateway_for_connected.lock() {
                gateway.worker_connected();
            }
        });

        let gateway_for_disconnect = browser_asr_gateway.clone();
        let subtitle_for_disconnect = subtitle.clone();
        let partial_emit_for_disconnect = partial_emit.clone();
        let on_worker_disconnected: WorkerLifecycleCallback = Arc::new(move || {
            if let Ok(mut gateway) = gateway_for_disconnect.lock() {
                gateway.worker_disconnected();
            }
            let subtitle = subtitle_for_disconnect.clone();
            let partial_emit = partial_emit_for_disconnect.clone();
            if let Ok(handle) = tokio::runtime::Handle::try_current() {
                handle.spawn(async move {
                    subtitle.clear_active_partial().await;
                    partial_emit
                        .lock()
                        .await
                        .segment_state
                        .cleanup_on_browser_worker_disconnect();
                });
            }
        });

        let browser_speech_for_ingest = browser_speech.clone();
        let browser_asr = Arc::new(BrowserAsrService::with_hooks(
            Arc::new(move |update| {
                let speech = browser_speech_for_ingest.clone();
                tokio::spawn(async move {
                    speech.ingest(update).await;
                });
            }),
            Some(on_worker_connected),
            Some(on_worker_disconnected),
            Some(on_status_update),
        ));

        let asr_worker = AsrWorkerHub::new(browser_asr.clone());

        Self {
            config,

            paths,

            config_store,

            config_snapshot,

            bind_addr: Arc::new(TokioRwLock::new(None)),

            events,

            ws_publisher,

            runtime_broadcaster,
            pipeline_log,

            subtitle,

            translation,

            browser_asr,

            asr_worker,

            obs_captions,

            runtime_metrics,

            partial_emit,
            runtime_running,
            browser_speech,
            twitch_oauth,
            structured_runtime_logger,
        }
    }

    pub fn config_store(&self) -> Arc<RwLock<ConfigStore>> {
        self.config_store.clone()
    }

    pub fn asr_worker(&self) -> AsrWorkerHub {
        self.asr_worker.clone()
    }

    pub fn browser_asr_service(&self) -> Arc<BrowserAsrService> {
        self.browser_asr.clone()
    }

    pub fn subtitle_router(&self) -> Arc<SubtitleRouter> {
        self.subtitle.clone()
    }

    pub fn translation_controller(&self) -> Arc<tokio::sync::Mutex<TranslationRuntimeController>> {
        self.translation.clone()
    }

    pub fn obs_captions(&self) -> Arc<ObsCaptionService> {
        self.obs_captions.clone()
    }

    pub fn events_hub(&self) -> EventsHub {
        self.events.clone()
    }

    pub fn ws_publisher(&self) -> WsEventPublisher {
        self.ws_publisher.clone()
    }

    pub fn http_state(&self) -> Arc<HttpState> {
        let session_log = Arc::new(SessionLogManager::new(&self.paths.logs_dir));
        let structured_runtime_logger = self.structured_runtime_logger.clone();
        let export_service = Arc::new(ExportService::from_paths(&self.paths, PROJECT_VERSION));

        let style_presets: StylePresetsFn = Arc::new(|subtitle_style| {
            voicesub_subtitle::subtitle_style_presets(subtitle_style)
        });
        HttpState::new(
            self.paths.clone(),
            self.events.clone(),
            self.runtime_broadcaster.clone(),
            self.pipeline_log.clone(),
            self.asr_worker.clone(),
            self.config_store.clone(),
            self.config_snapshot.clone(),
            self.config.clone(),
            self.bind_addr.clone(),
            session_log,
            structured_runtime_logger,
            export_service,
            self.translation.clone(),
            self.subtitle.clone(),
            self.obs_captions.clone(),
            self.runtime_metrics.clone(),
            self.partial_emit.clone(),
            self.runtime_running.clone(),
            self.browser_speech.clone(),
            self.twitch_oauth.clone(),
            style_presets,
            PROJECT_VERSION,
        )
    }

    pub fn router(state: Arc<HttpState>) -> Router {
        build_router(state)
    }

    #[instrument(skip(self))]

    pub async fn start(&self) -> Result<RuntimeHandle, RuntimeError> {
        voicesub_config::ensure_runtime_data_dirs(&self.paths)
            .map_err(|err| RuntimeError::Server(err.to_string()))?;
        let _ = ensure_logs_dir(&self.paths.project_root)?;

        {
            let mut store = self.config_store.write().await;

            store.load_or_create()?;

            if let Ok(mut snapshot) = self.config_snapshot.write() {
                *snapshot = store.payload().clone();
            }
            apply_logging_preferences(
                &self.paths.logs_dir,
                read_full_logging_enabled(store.payload()),
            );
        }

        let addr = self.config.http.socket_addr();

        let state = self.http_state();
        let heartbeat_task = spawn_runtime_heartbeat(self.runtime_broadcaster.clone(), state.clone());
        spawn_startup_check(state.clone());
        let router = Self::router(state);

        let listener = tokio::net::TcpListener::bind(addr)
            .await
            .map_err(|err| RuntimeError::Server(err.to_string()))?;

        let bound = listener
            .local_addr()
            .map_err(|err| RuntimeError::Server(err.to_string()))?;

        *self.bind_addr.write().await = Some(bound);

        let (shutdown_tx, shutdown_rx) = tokio::sync::oneshot::channel::<()>();

        let server_task = tokio::spawn(async move {
            let server = axum::serve(listener, router).with_graceful_shutdown(async {
                let _ = shutdown_rx.await;

                info!("http server shutdown requested");
            });

            if let Err(err) = server.await {
                tracing::error!(error = %err, "http server exited with error");
            }
        });

        info!(%bound, "VoiceSub runtime listening");

        Ok(RuntimeHandle {
            bind_addr: bound,

            shutdown: Some(shutdown_tx),

            server_task: Some(server_task),

            heartbeat_task: Some(heartbeat_task),
        })
    }

    pub async fn launch_browser_worker(
        &self,
    ) -> Result<voicesub_browser::LaunchResult, voicesub_browser::BrowserLaunchError> {
        let base = if let Some(addr) = *self.bind_addr.read().await {
            base_url_from_socket(addr)
        } else {
            self.config.http.base_url()
        };

        let store = self.config_store.read().await;
        let payload = store.payload().clone();
        let url = worker_url_for_payload(&base, &payload);
        let chrome_launch = voicesub_browser::chrome_launch_from_config(&payload);

        let launcher = BrowserWorkerLauncher::new(&self.paths.user_data_dir);

        launcher.launch_worker(&url, &chrome_launch)
    }
}

#[cfg(test)]
mod tests {

    use super::*;

    #[test]

    fn runtime_service_builds_router() {
        let service = RuntimeService::new(".");

        let _router = RuntimeService::router(service.http_state());
    }
}
