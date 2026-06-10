use std::path::PathBuf;
use std::sync::Arc;

use axum::{
    extract::{State, WebSocketUpgrade},
    http::{header, HeaderValue},
    response::{Html, IntoResponse, Response},
    routing::{get, post},
    Router,
};
use tower_http::services::ServeDir;
use tower_http::set_header::SetResponseHeaderLayer;
use voicesub_config::build_project_fonts_stylesheet;

use super::devices::audio_inputs;
use super::exports::{export_diagnostics, list_exports};
use super::logs::{logs_client_event, logs_ui_trace};
use super::openai::{list_models, recommended_models, usable_models};
use super::profiles::{delete_profile, list_profiles, load_profile, save_profile};
use super::runtime::{obs_url, runtime_start, runtime_status, runtime_stop};
use super::settings::{settings_load, settings_save};
use super::state::HttpState;
use super::tts_proxy::google_tts_proxy;
use super::tts_python::{python_tts_proxy, python_tts_status};
use super::twitch_oauth::{twitch_oauth_complete, twitch_oauth_open, twitch_oauth_pending};
use super::updates::{check_updates, version_info};

pub fn build_router(state: Arc<HttpState>) -> Router {
    let paths = state.paths.clone();
    let no_cache = SetResponseHeaderLayer::overriding(
        header::CACHE_CONTROL,
        HeaderValue::from_static("no-store, no-cache, must-revalidate, max-age=0"),
    );
    let csp = SetResponseHeaderLayer::if_not_present(
        header::CONTENT_SECURITY_POLICY,
        HeaderValue::from_static(
            "default-src 'self'; base-uri 'self'; connect-src 'self' http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:* wss://127.0.0.1:* wss://localhost:* https:; media-src 'self' blob:; img-src 'self' data: blob: https:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'self'",
        ),
    );

    let overlay_static = ServeDir::new(paths.overlay_root.clone());
    let legacy_static = ServeDir::new(paths.overlay_root.join("shared"));
    let worker_static = ServeDir::new(paths.worker_dist.clone());
    let dashboard_assets = ServeDir::new(paths.dashboard_dist.join("assets"));
    let tts_static = ServeDir::new(paths.tts_dist.clone());
    let project_fonts_static = ServeDir::new(paths.fonts_dir.clone());

    Router::new()
        .route("/api/health", get(health))
        .route("/api/version", get(version_info_route))
        .route("/api/devices/audio-inputs", get(audio_inputs))
        .route("/api/openai/recommended-models", get(recommended_models))
        .route("/api/openai/models", post(list_models))
        .route("/api/openai/usable-models", post(usable_models))
        .route("/api/updates/check", post(check_updates))
        .route("/api/settings/load", get(settings_load))
        .route("/api/settings/save", post(settings_save))
        .route("/api/logs/client-event", post(logs_client_event))
        .route("/api/logs/ui-trace", post(logs_ui_trace))
        .route("/api/tts/google", get(google_tts_proxy))
        .route("/api/tts/python", get(python_tts_proxy))
        .route("/api/tts/python/status", get(python_tts_status))
        .route("/api/tts/twitch/oauth-complete", post(twitch_oauth_complete))
        .route("/api/tts/twitch/oauth-open", post(twitch_oauth_open))
        .route("/api/tts/twitch/oauth-pending", get(twitch_oauth_pending))
        .route("/api/exports", get(list_exports))
        .route("/api/exports/diagnostics", get(export_diagnostics))
        .route("/api/profiles", get(list_profiles))
        .route(
            "/api/profiles/{name}",
            get(load_profile).post(save_profile).delete(delete_profile),
        )
        .route("/api/runtime/start", post(runtime_start))
        .route("/api/runtime/stop", post(runtime_stop))
        .route("/api/runtime/status", get(runtime_status))
        .route("/api/obs/url", get(obs_url))
        .route("/", get(dashboard_index))
        .route("/google-asr", get(google_asr_page))
        .route("/google-asr-edge", get(google_asr_edge_page))
        .route("/tts", get(tts_page))
        .route("/overlay", get(overlay_page))
        .route("/project-fonts.css", get(project_fonts_css))
        .route("/ws/events", get(ws_events))
        .route("/ws/asr_worker", get(ws_asr_worker))
        .nest_service("/overlay-assets", overlay_static)
        .nest_service("/static", legacy_static)
        .nest_service("/worker-assets", worker_static)
        .nest_service("/assets", dashboard_assets)
        .nest_service("/tts-assets", tts_static)
        .nest_service("/project-fonts", project_fonts_static)
        .layer(csp)
        .layer(no_cache)
        .with_state(state)
}

async fn health(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    let diag = state.events.diagnostics();
    let snap = state.asr_worker.snapshot().await;
    axum::Json(serde_json::json!({
        "status": "ok",
        "version": state.version,
        "ws_events_connections_active": diag.connections_active,
        "browser_worker_connected": snap.worker_connected,
    }))
}

async fn version_info_route(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    version_info(State(state)).await
}

async fn dashboard_index(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    serve_html_candidate(
        state.paths.dashboard_dist.join("index.html"),
        "<!doctype html><html><head><title>VoiceSub</title></head><body><h1>VoiceSub dashboard</h1><p>Run <code>npm run build</code> for Svelte bundle.</p></body></html>",
    )
}

async fn google_asr_page(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    serve_worker_page(&state.paths)
}

async fn google_asr_edge_page(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    serve_worker_page(&state.paths)
}

async fn tts_page(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    serve_html_candidate(
        state.paths.tts_dist.join("index.html"),
        "<!doctype html><html><body><h1>VoiceSub TTS module (run npm run build:tts)</h1></body></html>",
    )
}

async fn project_fonts_css(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    let css = build_project_fonts_stylesheet(&state.paths.fonts_dir);
    ([(header::CONTENT_TYPE, "text/css; charset=utf-8")], css)
}

/// OBS overlay HTML is read from `bin/overlay/` (Tauri `bundle.resources`), not `include_str!`.
async fn overlay_page(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    serve_html_candidate(
        state.paths.overlay_root.join("overlay.html"),
        "<!doctype html><html><body>overlay missing</body></html>",
    )
}

async fn ws_events(State(state): State<Arc<HttpState>>, ws: WebSocketUpgrade) -> impl IntoResponse {
    let hub = state.events.clone();
    ws.on_upgrade(move |socket| async move {
        hub.serve_connection(socket).await;
    })
}

async fn ws_asr_worker(
    State(state): State<Arc<HttpState>>,
    ws: WebSocketUpgrade,
) -> impl IntoResponse {
    let hub = state.asr_worker.clone();
    ws.on_upgrade(move |socket| async move {
        hub.serve_connection(socket).await;
    })
}

fn serve_worker_page(paths: &voicesub_config::ProjectPaths) -> Response {
    serve_html_candidate(
        paths.worker_dist.join("index.html"),
        "<!doctype html><html><body><h1>VoiceSub Web Speech worker (run npm run build)</h1></body></html>",
    )
}

fn serve_html_candidate(path: PathBuf, fallback: &str) -> Response {
    if path.is_file() {
        if let Ok(bytes) = std::fs::read(path) {
            if let Ok(text) = String::from_utf8(bytes) {
                return Html(text).into_response();
            }
        }
    }
    Html(fallback.to_string()).into_response()
}
