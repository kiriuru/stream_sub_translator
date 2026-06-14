use std::sync::Arc;
use std::time::Duration;

use chrono::{DateTime, Utc};
use serde_json::{json, Value};
use tracing::info;
use voicesub_types::{
    build_version_info_payload, extract_latest_github_release, is_remote_version_newer,
    release_url_for, PROJECT_VERSION,
};

use super::state::HttpState;

fn now_utc_iso() -> String {
    Utc::now().to_rfc3339()
}

fn parse_checked_time(value: Option<&str>) -> Option<DateTime<Utc>> {
    let text = value.unwrap_or("").trim();
    if text.is_empty() {
        return None;
    }
    DateTime::parse_from_rfc3339(text)
        .ok()
        .map(|parsed| parsed.with_timezone(&Utc))
        .or_else(|| text.parse::<DateTime<Utc>>().ok())
}

fn patch_updates_in_value(payload: &mut Value, latest_version: &str, checked_utc: &str) {
    let Some(root) = payload.as_object_mut() else {
        return;
    };
    let updates = root
        .entry("updates")
        .or_insert_with(|| json!({}));
    if let Some(obj) = updates.as_object_mut() {
        obj.insert(
            "latest_known_version".into(),
            Value::String(latest_version.to_string()),
        );
        obj.insert(
            "last_checked_utc".into(),
            Value::String(checked_utc.to_string()),
        );
    }
}

async fn persist_updates(
    state: &HttpState,
    latest_version: Option<&str>,
    checked_utc: &str,
) -> Result<Value, String> {
    let latest = latest_version.unwrap_or("");
    {
        let mut store = state.config.write().await;
        store
            .patch_updates_metadata(latest, checked_utc)
            .map_err(|err| err.to_string())?;
    }
    if let Ok(mut snapshot) = state.config_snapshot.write() {
        patch_updates_in_value(&mut snapshot, latest, checked_utc);
    }
    let store = state.config.read().await;
    Ok(store.payload().clone())
}

/// Poll GitHub Releases when enabled and interval elapsed.
pub async fn check_now(state: &Arc<HttpState>, force: bool) -> Value {
    let config = state.config.read().await.payload().clone();
    let updates = config.get("updates").cloned().unwrap_or_else(|| json!({}));
    let enabled = updates
        .get("enabled")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let github_repo = updates
        .get("github_repo")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_string();
    let release_channel = updates
        .get("release_channel")
        .and_then(Value::as_str)
        .unwrap_or("stable")
        .trim()
        .to_ascii_lowercase();
    let release_channel = if release_channel == "prerelease" {
        "prerelease"
    } else {
        "stable"
    };
    let interval_hours = updates
        .get("check_interval_hours")
        .and_then(Value::as_i64)
        .unwrap_or(12)
        .clamp(1, 168) as i64;

    let mut payload = build_version_info_payload(Some(&config));
    if !enabled {
        info!("update check skipped: updates.enabled=false in config");
        payload["sync"]["message"] = json!("Update checks are disabled in settings.");
        return payload;
    }
    if github_repo.is_empty() {
        payload["sync"]["message"] =
            json!("Update checks are enabled, but updates.github_repo is not configured.");
        return payload;
    }

    let latest_known = updates
        .get("latest_known_version")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_string();
    // After a local upgrade the cached GitHub latest can lag behind PROJECT_VERSION
    // (e.g. cache 0.5.1 while running 0.5.2). Do not let the interval gate hide newer tags.
    let cache_stale = !latest_known.is_empty()
        && is_remote_version_newer(&latest_known, PROJECT_VERSION);

    let last_checked = updates
        .get("last_checked_utc")
        .and_then(Value::as_str)
        .and_then(|value| parse_checked_time(Some(value)));
    let now = Utc::now();
    if !force {
        if let Some(last_checked) = last_checked {
            let due_at = last_checked + chrono::Duration::hours(interval_hours);
            if now < due_at && !cache_stale {
                payload["sync"]["message"] = json!("Update check skipped (interval not reached yet).");
                return payload;
            }
        }
    }

    let checked_utc = now_utc_iso();
    payload["sync"]["check_active"] = json!(true);
    payload["sync"]["message"] = json!("Checking GitHub Releases...");

    let api_url = format!(
        "https://api.github.com/repos/{github_repo}/releases?per_page=20"
    );
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(6))
        .connect_timeout(Duration::from_secs(3))
        .build()
        .unwrap_or_else(|_| reqwest::Client::new());

    let releases = match client
        .get(&api_url)
        .header("Accept", "application/vnd.github+json")
        .header("User-Agent", format!("VoiceSub/{PROJECT_VERSION}"))
        .send()
        .await
    {
        Ok(response) => match response.error_for_status() {
            Ok(ok) => match ok.json::<Value>().await {
                Ok(body) => body,
                Err(err) => {
                    payload["sync"]["check_active"] = json!(false);
                    payload["sync"]["message"] =
                        json!(format!("Update check failed: {}: {}", err, "invalid JSON"));
                    return payload;
                }
            },
            Err(err) => {
                payload["sync"]["check_active"] = json!(false);
                payload["sync"]["message"] =
                    json!(format!("Update check failed: reqwest: {err}"));
                return payload;
            }
        },
        Err(err) => {
            payload["sync"]["check_active"] = json!(false);
            payload["sync"]["message"] = json!(format!("Update check failed: reqwest: {err}"));
            return payload;
        }
    };

    let (latest_version, selection_message, release_url) =
        extract_latest_github_release(&releases, release_channel);
    let active_payload = match persist_updates(
        state,
        latest_version.as_deref(),
        &checked_utc,
    )
    .await
    {
        Ok(payload) => payload,
        Err(message) => {
            payload["sync"]["check_active"] = json!(false);
            payload["sync"]["message"] = json!(format!("Update check failed: {message}"));
            return payload;
        }
    };

    let mut payload = build_version_info_payload(Some(&active_payload));
    payload["sync"]["check_active"] = json!(false);
    payload["sync"]["message"] = json!(selection_message);
    if payload["sync"]["update_available"].as_bool() == Some(true) {
        let url = release_url.or_else(|| {
            latest_version
                .as_deref()
                .map(|version| release_url_for(&github_repo, version))
        });
        if let Some(url) = url {
            payload["sync"]["release_url"] = json!(url);
        }
    }
    payload
}

pub fn spawn_startup_check(state: Arc<HttpState>) {
    tokio::spawn(async move {
        let _ = check_now(&state, true).await;
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cache_stale_when_local_version_ahead_of_cached_latest() {
        assert!(is_remote_version_newer("0.5.1", "0.5.2"));
        assert!(!is_remote_version_newer("0.5.3", "0.5.2"));
    }
}
