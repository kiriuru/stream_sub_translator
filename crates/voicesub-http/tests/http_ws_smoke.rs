#![allow(clippy::await_holding_lock)]

mod common;

use std::time::Duration;

use common::{integration_lock, EphemeralRuntime, workspace_root as project_root};
use futures_util::{SinkExt, StreamExt};
use tokio_tungstenite::connect_async;
use tokio_tungstenite::tungstenite::Message;

#[tokio::test]
async fn http_responses_include_content_security_policy() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let client = reqwest::Client::new();
    let response = client
        .get(format!("http://{addr}/api/health"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("health request");
    let csp = response
        .headers()
        .get("content-security-policy")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    assert!(
        csp.contains("default-src 'self'"),
        "missing default-src directive: {csp}"
    );
    assert!(
        csp.contains("connect-src"),
        "missing connect-src directive: {csp}"
    );
    assert!(
        csp.contains("media-src 'self' blob:"),
        "missing media-src directive for TTS audio playback: {csp}"
    );

    handle.shutdown().await;
}

#[tokio::test]
async fn runtime_start_emits_preflight_and_runtime_updates() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let (mut socket, _) = connect_async(format!("ws://{addr}/ws/events"))
        .await
        .expect("connect events ws");
    let _ = tokio::time::timeout(Duration::from_secs(3), socket.next())
        .await
        .expect("hello timeout")
        .expect("frame")
        .expect("ok frame");

    let client = reqwest::Client::new();
    let start = client
        .post(format!("http://{addr}/api/runtime/start"))
        .json(&serde_json::json!({}))
        .timeout(Duration::from_secs(10))
        .send()
        .await
        .expect("runtime start");
    assert!(start.status().is_success());

    let mut saw_preflight = false;
    let mut saw_runtime = false;
    for _ in 0..12 {
        let frame = tokio::time::timeout(Duration::from_secs(3), socket.next()).await;
        let Ok(Some(Ok(Message::Text(text)))) = frame else {
            continue;
        };
        let json: serde_json::Value = serde_json::from_str(&text).unwrap_or(serde_json::Value::Null);
        let kind = json.get("type").and_then(|value| value.as_str()).unwrap_or("");
        if kind == "preflight_update" {
            saw_preflight = true;
        }
        if kind == "runtime_update" {
            let payload = json.get("payload").expect("runtime payload");
            assert!(
                payload.get("event_sequence").and_then(|v| v.as_u64()).unwrap_or(0) > 0,
                "runtime_update must include event_sequence"
            );
            saw_runtime = true;
        }
        if saw_preflight && saw_runtime {
            break;
        }
    }
    assert!(saw_preflight, "expected preflight_update after runtime start");
    assert!(saw_runtime, "expected runtime_update after runtime start");

    let _ = client
        .post(format!("http://{addr}/api/runtime/stop"))
        .timeout(Duration::from_secs(5))
        .send()
        .await;
    let _ = socket.close(None).await;
    handle.shutdown().await;
}

#[tokio::test]
async fn health_endpoint_returns_ok() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let client = reqwest::Client::new();
    let url = format!("http://{addr}/api/health");
    let response = client
        .get(&url)
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("health request");
    assert!(response.status().is_success());
    let body: serde_json::Value = response.json().await.expect("json");
    assert_eq!(body["status"], "ok");
    assert_eq!(body["version"], voicesub_types::PROJECT_VERSION);

    handle.shutdown().await;
}

#[tokio::test]
async fn ws_events_sends_hello() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let (mut socket, _) = connect_async(format!("ws://{addr}/ws/events"))
        .await
        .expect("connect events ws");
    let msg = tokio::time::timeout(Duration::from_secs(3), socket.next())
        .await
        .expect("timeout")
        .expect("frame")
        .expect("ok frame");
    let text = match msg {
        Message::Text(t) => t,
        other => panic!("unexpected frame: {other:?}"),
    };
    let json: serde_json::Value = serde_json::from_str(&text).expect("json");
    assert_eq!(json["type"], "hello");
    assert_eq!(json["message"], "connected");

    let _ = socket.close(None).await;
    handle.shutdown().await;
}

#[tokio::test]
async fn google_asr_served_from_svelte_worker() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let client = reqwest::Client::new();
    let response = client
        .get(format!("http://{addr}/google-asr"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("google-asr");
    assert!(response.status().is_success());
    let body = response.text().await.expect("body");
    assert!(body.contains("Web Speech Worker"));

    let dist_worker = project_root().join("bin/worker/index.html");
    if dist_worker.is_file() {
        assert!(
            body.contains("/worker-assets/"),
            "built worker index should reference /worker-assets/"
        );
    }

    handle.shutdown().await;
}

#[tokio::test]
async fn settings_load_stub_ok() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let response = reqwest::Client::new()
        .get(format!("http://{addr}/api/settings/load"))
        .send()
        .await
        .expect("settings load");
    assert!(response.status().is_success());
    let body: serde_json::Value = response.json().await.expect("json");
    assert_eq!(body["ok"], true);
    assert_eq!(body["payload"]["asr"]["mode"], "browser_google");
    assert!(body["loaded_from"].is_string());
    let presets = body["subtitle_style_presets"]
        .as_object()
        .expect("subtitle_style_presets object");
    assert!(presets.len() >= 15, "expected 15 built-in presets");
    assert!(presets.contains_key("clean_default"));
    let font_catalog = &body["font_catalog"];
    assert!(font_catalog["project_fonts_dir"].is_string());
    assert!(
        font_catalog["fallback"]
            .as_array()
            .map(|a| a.len())
            .unwrap_or(0)
            >= 8
    );

    handle.shutdown().await;
}

#[tokio::test]
async fn dashboard_assets_served_when_built() {
    let dist_assets = project_root().join("bin/dashboard/assets");
    if !dist_assets.is_dir() {
        return;
    }
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let entries: Vec<_> = std::fs::read_dir(&dist_assets)
        .expect("read dist/assets")
        .filter_map(|e| e.ok())
        .filter(|e| e.path().is_file())
        .map(|e| e.file_name().to_string_lossy().to_string())
        .collect();
    assert!(
        !entries.is_empty(),
        "bin/dashboard/assets should contain built files"
    );

    let first = &entries[0];
    let response = reqwest::Client::new()
        .get(format!("http://{addr}/assets/{first}"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("asset fetch");
    assert!(response.status().is_success());
    // Drain the body so the client connection closes before graceful shutdown.
    let _ = response.bytes().await.expect("asset body");

    handle.shutdown().await;
}

#[tokio::test]
async fn worker_page_and_assets() {
    let dist_worker = project_root().join("bin/worker");
    if !dist_worker.join("index.html").is_file() {
        return;
    }
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let index = std::fs::read_to_string(dist_worker.join("index.html")).expect("read index");
    assert!(
        index.contains("/worker-assets/"),
        "bin/worker index must reference /worker-assets/ base"
    );

    let page = reqwest::Client::new()
        .get(format!("http://{addr}/google-asr"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("svelte worker page");
    assert!(page.status().is_success());
    let _ = page.bytes().await.expect("svelte worker page body");

    let asset_name = index
        .lines()
        .find_map(|line| {
            let line = line.trim();
            line.strip_prefix("<script")
                .and_then(|_| line.split("src=\"").nth(1))
                .and_then(|rest| rest.split('"').next())
                .map(str::to_string)
        })
        .expect("bin/worker index must contain script src");
    let asset = reqwest::Client::new()
        .get(format!("http://{addr}{asset_name}"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("svelte worker js");
    assert!(asset.status().is_success());
    let _ = asset.bytes().await.expect("svelte worker js body");

    handle.shutdown().await;
}

#[tokio::test]
async fn tts_module_page_and_assets() {
    let dist_tts = project_root().join("bin/tts");
    if !dist_tts.join("index.html").is_file() {
        return;
    }
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let index = std::fs::read_to_string(dist_tts.join("index.html")).expect("read tts index");
    assert!(
        index.contains("/tts-assets/"),
        "bin/tts index must reference /tts-assets/ base"
    );

    let page = reqwest::Client::new()
        .get(format!("http://{addr}/tts"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("tts page");
    assert!(page.status().is_success());

    let asset_name = index
        .lines()
        .find_map(|line| {
            let line = line.trim();
            line.strip_prefix("<script")
                .and_then(|_| line.split("src=\"").nth(1))
                .and_then(|rest| rest.split('"').next())
                .map(str::to_string)
        })
        .expect("bin/tts index must contain script src");
    let asset = reqwest::Client::new()
        .get(format!("http://{addr}{asset_name}"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("tts js asset");
    assert!(asset.status().is_success());

    handle.shutdown().await;
}

#[tokio::test]
async fn google_tts_proxy_rejects_empty_query() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let resp = reqwest::Client::new()
        .get(format!("http://{addr}/api/tts/google?q=&tl=ru"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("google tts proxy");
    assert_eq!(resp.status(), reqwest::StatusCode::BAD_REQUEST);

    handle.shutdown().await;
}

#[tokio::test]
async fn python_tts_status_reports_script() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let resp = reqwest::Client::new()
        .get(format!("http://{addr}/api/tts/python/status"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("python tts status");
    assert!(resp.status().is_success());
    let body: serde_json::Value = resp.json().await.expect("json");
    assert_eq!(body["script_found"], true);
    assert!(body.get("embedded_found").is_some());
    assert!(body.get("build_hint").is_some());

    handle.shutdown().await;
}

#[tokio::test]
async fn obs_url_points_to_overlay() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let body: serde_json::Value = reqwest::Client::new()
        .get(format!("http://{addr}/api/obs/url"))
        .send()
        .await
        .expect("obs url")
        .json()
        .await
        .expect("json");
    assert!(body["overlay_url"].as_str().unwrap().ends_with("/overlay"));

    handle.shutdown().await;
}

#[tokio::test]
async fn subtitle_style_renderer_assets_served() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;
    let client = reqwest::Client::new();

    for path in [
        "/static/js/subtitle-style.js",
        "/overlay-assets/shared/js/subtitle-style.js",
    ] {
        let response = client
            .get(format!("http://{addr}{path}"))
            .timeout(Duration::from_secs(3))
            .send()
            .await
            .unwrap_or_else(|err| panic!("fetch {path}: {err}"));
        assert!(response.status().is_success(), "{path} status");
        let body = response
            .text()
            .await
            .unwrap_or_else(|err| panic!("read {path}: {err}"));
        assert!(
            body.contains("SubtitleStyleRenderer"),
            "{path} should expose renderer"
        );
    }

    handle.shutdown().await;
}

#[tokio::test]
async fn runtime_status_starts_idle() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;

    let body: serde_json::Value = reqwest::Client::new()
        .get(format!("http://{addr}/api/runtime/status"))
        .send()
        .await
        .expect("runtime status")
        .json()
        .await
        .expect("json");
    assert_eq!(body["phase"], "idle");
    assert_eq!(body["is_running"], false);
    assert_eq!(body["asr"]["active_mode"], "browser_google");
    assert!(body.get("obs_caption_diagnostics").is_some());
    assert!(body.get("obs_captions").is_some());
    assert!(body.get("translation_diagnostics").is_some());
    assert!(body.get("asr_diagnostics").is_some());
    let metrics = &body["metrics"];
    assert_eq!(metrics["partial_updates_emitted"], 0);
    assert_eq!(metrics["finals_emitted"], 0);
    assert_eq!(metrics["browser_transcripts_received"], 0);
    assert_eq!(metrics["ws_events_connections_active"], 0);

    handle.shutdown().await;
}

#[tokio::test]
async fn devices_audio_inputs_ok() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;
    let body: serde_json::Value = reqwest::Client::new()
        .get(format!("http://{addr}/api/devices/audio-inputs"))
        .send()
        .await
        .expect("devices")
        .json()
        .await
        .expect("json");
    assert!(body["devices"].is_array());
    handle.shutdown().await;
}

#[tokio::test]
async fn openai_recommended_models_ok() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;
    let body: serde_json::Value = reqwest::Client::new()
        .get(format!("http://{addr}/api/openai/recommended-models"))
        .send()
        .await
        .expect("openai models")
        .json()
        .await
        .expect("json");
    assert!(body["models"].as_array().unwrap().len() >= 3);
    handle.shutdown().await;
}

#[tokio::test]
async fn updates_check_ok() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;
    let body: serde_json::Value = reqwest::Client::new()
        .post(format!("http://{addr}/api/updates/check"))
        .send()
        .await
        .expect("updates")
        .json()
        .await
        .expect("json");
    assert_eq!(body["version"], voicesub_types::PROJECT_VERSION);
    assert_eq!(body["current_version"], voicesub_types::PROJECT_VERSION);
    assert_eq!(body["sync"]["enabled"], true);
    let latest = body["sync"]["latest_known_version"]
        .as_str()
        .unwrap_or("");
    assert!(!latest.is_empty(), "expected cached latest_known_version from GitHub");
    let update_available = body["sync"]["update_available"].as_bool().unwrap_or(false);
    assert_eq!(
        update_available,
        voicesub_types::is_remote_version_newer(voicesub_types::PROJECT_VERSION, latest),
        "update_available must track semver vs live GitHub latest ({latest})"
    );
    handle.shutdown().await;
}

#[tokio::test]
async fn profiles_api_roundtrip() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;
    let client = reqwest::Client::new();

    let list: serde_json::Value = client
        .get(format!("http://{addr}/api/profiles"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("list profiles")
        .json()
        .await
        .expect("json");
    let profiles = list["profiles"].as_array().expect("profiles array");
    assert!(profiles.iter().any(|item| item.as_str() == Some("default")));

    let save: serde_json::Value = client
        .post(format!("http://{addr}/api/profiles/stream"))
        .timeout(Duration::from_secs(3))
        .json(&serde_json::json!({ "payload": { "translation": { "enabled": true } } }))
        .send()
        .await
        .expect("save profile")
        .json()
        .await
        .expect("json");
    assert_eq!(save["name"], "stream");
    assert_eq!(save["payload"]["profile"], "stream");

    let load: serde_json::Value = client
        .get(format!("http://{addr}/api/profiles/stream"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("load profile")
        .json()
        .await
        .expect("json");
    assert_eq!(load["payload"]["translation"]["enabled"], true);

    let delete: serde_json::Value = client
        .delete(format!("http://{addr}/api/profiles/stream"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("delete profile")
        .json()
        .await
        .expect("json");
    assert_eq!(delete["deleted"], true);

    handle.shutdown().await;
}

/// Automated substitute for Phase 0 manual soak checklist (roadmap §5, PoC report).
/// Full 30 min OBS-over-window soak remains a manual operator step.
#[tokio::test]
async fn phase0_soak_checklist_automated() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;
    let client = reqwest::Client::new();
    let base = format!("http://{addr}");

    let dashboard = client
        .get(&base)
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("dashboard");
    assert!(dashboard.status().is_success());

    let worker = client
        .get(format!("{base}/google-asr"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("browser worker");
    assert!(worker.status().is_success());

    let overlay = client
        .get(format!("{base}/overlay"))
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .expect("overlay");
    assert!(overlay.status().is_success());
    let overlay_body = overlay.text().await.expect("overlay body");
    assert!(
        overlay_body.to_ascii_lowercase().contains("overlay")
            || overlay_body.contains("/ws/events"),
        "overlay page should reference overlay surface or events websocket"
    );

    let (mut events, _) = connect_async(format!("ws://{addr}/ws/events"))
        .await
        .expect("events ws");
    let hello = tokio::time::timeout(Duration::from_secs(3), events.next())
        .await
        .expect("events hello timeout")
        .expect("events frame")
        .expect("events ok");
    let hello_text = match hello {
        Message::Text(text) => text.to_string(),
        other => panic!("unexpected events frame: {other:?}"),
    };
    let hello_json: serde_json::Value = serde_json::from_str(&hello_text).expect("events hello json");
    assert_eq!(hello_json["type"], "hello");

    let start = client
        .post(format!("{base}/api/runtime/start"))
        .json(&serde_json::json!({}))
        .timeout(Duration::from_secs(10))
        .send()
        .await
        .expect("runtime start");
    assert!(start.status().is_success(), "runtime start failed: {}", start.status());

    let (mut worker, _) = connect_async(format!("ws://{addr}/ws/asr_worker"))
        .await
        .expect("worker ws");
    let worker_hello = tokio::time::timeout(Duration::from_secs(3), worker.next())
        .await
        .expect("worker hello timeout")
        .expect("worker frame")
        .expect("worker ok");
    let worker_hello_text = match worker_hello {
        Message::Text(text) => text.to_string(),
        other => panic!("unexpected worker frame: {other:?}"),
    };
    let worker_hello_json: serde_json::Value =
        serde_json::from_str(&worker_hello_text).expect("worker hello json");
    assert_eq!(worker_hello_json["type"], "hello");

    let partial = serde_json::json!({
        "type": "external_asr_update",
        "session_id": "phase0-soak",
        "generation_id": 1,
        "partial": "phase zero soak",
        "is_final": false
    });
    worker
        .send(Message::Text(partial.to_string().into()))
        .await
        .expect("send partial");

    let mut saw_live_update = false;
    for _ in 0..10 {
        let frame = tokio::time::timeout(Duration::from_secs(3), events.next()).await;
        let Ok(Some(Ok(Message::Text(text)))) = frame else {
            continue;
        };
        let json: serde_json::Value = serde_json::from_str(&text).unwrap_or(serde_json::Value::Null);
        let kind = json.get("type").and_then(|value| value.as_str()).unwrap_or("");
        if matches!(kind, "transcript_update" | "overlay_update") {
            if kind == "transcript_update" {
                let payload = json.get("payload").expect("transcript payload");
                assert!(
                    payload.get("event_sequence").and_then(|v| v.as_u64()).unwrap_or(0) > 0,
                    "transcript_update must include monotonic event_sequence"
                );
                assert!(
                    payload.get("created_at_ms").and_then(|v| v.as_u64()).unwrap_or(0) > 0,
                    "transcript_update must include created_at_ms"
                );
            }
            saw_live_update = true;
            break;
        }
    }
    assert!(
        saw_live_update,
        "expected transcript_update or overlay_update after worker partial ingest"
    );

    let final_update = serde_json::json!({
        "type": "external_asr_update",
        "session_id": "phase0-soak",
        "generation_id": 1,
        "final": "phase zero soak final",
        "is_final": true
    });
    worker
        .send(Message::Text(final_update.to_string().into()))
        .await
        .expect("send final");

    let _ = worker.close(None).await;
    let _ = events.close(None).await;
    handle.shutdown().await;
}

#[tokio::test]
async fn source_text_replacement_applies_on_asr_final_ingest() {
    let _guard = integration_lock();
    let runtime = EphemeralRuntime::new();
    let handle = runtime.start().await;
    let addr = handle.bind_addr;
    let client = reqwest::Client::new();

    let mut payload = voicesub_config::default_config_payload();
    payload["source_text_replacement"] = serde_json::json!({
        "enabled": true,
        "include_builtin_profanity": true,
        "whole_word_only": true,
        "pairs": [{"source": "badword", "target": "REPLACED"}]
    });
    let save = client
        .post(format!("http://{addr}/api/settings/save"))
        .json(&serde_json::json!({ "payload": payload }))
        .timeout(Duration::from_secs(5))
        .send()
        .await
        .expect("settings save");
    assert!(save.status().is_success(), "settings save failed: {}", save.status());

    let start = client
        .post(format!("http://{addr}/api/runtime/start"))
        .json(&serde_json::json!({}))
        .timeout(Duration::from_secs(10))
        .send()
        .await
        .expect("runtime start");
    assert!(start.status().is_success());

    let (mut events, _) = connect_async(format!("ws://{addr}/ws/events"))
        .await
        .expect("events ws");
    let _ = tokio::time::timeout(Duration::from_secs(3), events.next())
        .await
        .expect("hello timeout")
        .expect("frame")
        .expect("ok frame");

    let (mut worker, _) = connect_async(format!("ws://{addr}/ws/asr_worker"))
        .await
        .expect("worker ws");
    let _ = tokio::time::timeout(Duration::from_secs(3), worker.next())
        .await
        .expect("worker hello timeout")
        .expect("frame")
        .expect("ok frame");

    worker
        .send(Message::Text(
            serde_json::json!({
                "type": "external_asr_update",
                "session_id": "replacement-test",
                "generation_id": 1,
                "final": "BADWORD hello",
                "is_final": true
            })
            .to_string()
            .into(),
        ))
        .await
        .expect("send final");

    let mut saw_replaced = false;
    for _ in 0..20 {
        let frame = tokio::time::timeout(Duration::from_secs(3), events.next()).await;
        let Ok(Some(Ok(Message::Text(text)))) = frame else {
            continue;
        };
        let json: serde_json::Value = serde_json::from_str(&text).unwrap_or(serde_json::Value::Null);
        if json.get("type").and_then(|value| value.as_str()) != Some("transcript_update") {
            continue;
        }
        let payload = json.get("payload").cloned().unwrap_or_default();
        let body_text = payload
            .get("text")
            .and_then(|value| value.as_str())
            .unwrap_or("");
        if body_text.contains("REPLACED") {
            saw_replaced = true;
            break;
        }
    }

    assert!(
        saw_replaced,
        "expected transcript_update with replaced source text"
    );

    let _ = worker.close(None).await;
    let _ = events.close(None).await;
    handle.shutdown().await;
}
