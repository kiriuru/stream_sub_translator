//! Chrome supervisor for Browser Speech worker (SST `browser_worker_launcher.py` port).

mod chrome_flags;
mod launch_config;
mod ecoqos;
mod gateway;
mod launcher;
mod operational_fsm;
mod service;
mod trace;
mod webview2_messages;
mod webview2_runtime;

pub use chrome_flags::{
    default_chrome_launch_value, disabled_chrome_features_csv, BrowserChromeLaunchConfig,
    CHROME_ANTI_THROTTLE_FLAGS,
};
pub use launch_config::chrome_launch_from_config;
pub use launcher::{BrowserLaunchError, BrowserWorkerLauncher, LaunchResult};
pub use gateway::{BrowserAsrGateway, GatewayDiagnostics};
pub use operational_fsm::{BrowserAsrOperationalFsm, BrowserOperationalPhase};
pub use trace::{structured_log_from_runtime_logger, BrowserAsrLog, StructuredLogFn};
pub use service::{
    BrowserAsrDiagnostics, BrowserAsrService, IngestCallback, IngestedAsrUpdate, StatusCallback,
    WorkerLifecycleCallback,
};
pub use webview2_messages::{
    normalize_supported_ui_language, system_supported_ui_language, webview2_missing_dialog_copy,
    WebView2MissingDialogCopy,
};
pub use webview2_runtime::{
    installed_webview2_version, WEBVIEW2_APP_GUID, WEBVIEW2_DOWNLOAD_URL,
};
