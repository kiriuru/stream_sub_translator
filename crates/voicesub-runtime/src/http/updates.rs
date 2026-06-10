use std::sync::Arc;

use axum::extract::State;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::Value;

use super::state::HttpState;
use super::update_service::check_now;

pub async fn check_updates(State(state): State<Arc<HttpState>>) -> Response {
    Json(check_now(&state, true).await).into_response()
}

pub async fn version_info(State(state): State<Arc<HttpState>>) -> Response {
    let config = state.config.read().await.payload().clone();
    let payload: Value = voicesub_types::build_version_info_payload(Some(&config));
    Json(payload).into_response()
}
