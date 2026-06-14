use serde_json::{json, Map, Value};

/// TOML has no `null`; drop null object fields and array elements before persisting.
pub(crate) fn strip_null_values(value: Value) -> Value {
    match value {
        Value::Object(map) => {
            let mut out = Map::new();
            for (key, child) in map {
                if child.is_null() {
                    continue;
                }
                out.insert(key, strip_null_values(child));
            }
            Value::Object(out)
        }
        Value::Array(items) => Value::Array(
            items
                .into_iter()
                .filter(|item| !item.is_null())
                .map(strip_null_values)
                .collect(),
        ),
        other => other,
    }
}

use crate::defaults::CURRENT_CONFIG_VERSION;
use crate::logging_preferences::normalize_logging_config;
use crate::defaults::default_config_payload;
use crate::obs_normalize::normalize_obs_closed_captions;
use voicesub_types::{DEFAULT_GITHUB_REPO, LEGACY_GITHUB_REPO};
use crate::translation_normalize::normalize_translation_config;

fn as_object_mut(value: &mut Value) -> &mut Map<String, Value> {
    if !value.is_object() {
        *value = json!({});
    }
    value.as_object_mut().expect("object")
}

fn int_or(value: Option<&Value>, fallback: i64) -> i64 {
    value
        .and_then(|v| v.as_i64().or_else(|| v.as_u64().map(|n| n as i64)))
        .filter(|n| *n >= 0)
        .unwrap_or(fallback)
}

fn clamp_i64(value: i64, min: i64, max: i64) -> i64 {
    value.max(min).min(max)
}

fn bool_default_true(value: Option<&Value>) -> bool {
    value.and_then(|v| v.as_bool()).unwrap_or(true)
}

fn normalize_ui_language(raw: &str) -> String {
    let current = raw.trim().to_ascii_lowercase();
    if current.is_empty() {
        return String::new();
    }
    if ["en", "ru", "ja", "ko", "zh"].contains(&current.as_str()) {
        return current;
    }
    if current.starts_with("ru") {
        return "ru".into();
    }
    if current.starts_with("zh") {
        return "zh".into();
    }
    if current.starts_with("ja") {
        return "ja".into();
    }
    if current.starts_with("ko") {
        return "ko".into();
    }
    if current.starts_with("en") {
        return "en".into();
    }
    String::new()
}

pub(crate) fn canonical_translation_provider(raw: &str, fallback: &str) -> String {
    let provider = raw.trim();
    if provider.is_empty() || provider == "mymemory" {
        fallback.to_string()
    } else {
        provider.to_string()
    }
}

fn normalize_ui_config(root: &mut Map<String, Value>) {
    let ui_value = root
        .entry("ui".to_string())
        .or_insert_with(|| json!({}));
    let ui = as_object_mut(ui_value);
    let lang = ui
        .get("language")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    ui.insert("language".into(), json!(normalize_ui_language(lang)));
}

fn normalize_overlay_config(root: &mut Map<String, Value>) {
    let overlay_value = root
        .entry("overlay".to_string())
        .or_insert_with(|| json!({}));
    let overlay = as_object_mut(overlay_value);

    let mut preset = overlay
        .get("preset")
        .and_then(|v| v.as_str())
        .unwrap_or("single")
        .trim()
        .to_string();
    let mut compact = overlay
        .get("compact")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);

    if preset == "compact" {
        compact = true;
        preset = "stacked".into();
    }
    if !["single", "dual-line", "stacked"].contains(&preset.as_str()) {
        preset = "single".into();
    }

    overlay.insert("preset".into(), json!(preset));
    overlay.insert("compact".into(), json!(compact));
}

fn normalize_asr_browser_config(root: &mut Map<String, Value>) {
    let Some(asr) = root.get_mut("asr").and_then(|v| v.as_object_mut()) else {
        return;
    };
    let browser_value = asr
        .entry("browser".to_string())
        .or_insert_with(|| json!({}));
    let browser = as_object_mut(browser_value);
    let mut launch = browser
        .get("worker_launch_browser")
        .and_then(|v| v.as_str())
        .unwrap_or("auto")
        .trim()
        .to_ascii_lowercase();
    if launch == "chromium" || !["auto", "google_chrome"].contains(&launch.as_str()) {
        launch = "auto".into();
    }
    browser.insert("worker_launch_browser".into(), json!(launch));

    let chrome_defaults = default_config_payload()
        .get("asr")
        .and_then(|v| v.get("browser"))
        .and_then(|v| v.get("chrome_launch"))
        .cloned()
        .unwrap_or_else(|| json!({}));
    let chrome_value = browser
        .entry("chrome_launch".to_string())
        .or_insert(chrome_defaults.clone());
    if let Some(chrome) = chrome_value.as_object_mut() {
        if let Some(defaults) = chrome_defaults.as_object() {
            for (key, value) in defaults {
                chrome.entry(key.clone()).or_insert_with(|| value.clone());
            }
        }
        if let Some(args) = chrome.get_mut("launch_args") {
            if args.as_array().is_none_or(|items| items.is_empty()) {
                *args = chrome_defaults["launch_args"].clone();
            }
        }
        if let Some(features) = chrome.get_mut("disabled_features") {
            if features.as_array().is_none_or(|items| items.is_empty()) {
                *features = chrome_defaults["disabled_features"].clone();
            }
        }
    }
}

fn normalize_translation_section(root: &mut Map<String, Value>) {
    let defaults = default_config_payload()
        .get("translation")
        .cloned()
        .unwrap_or(Value::Null);
    let fallback_targets = root
        .get("translation")
        .and_then(|v| v.get("target_languages"))
        .cloned()
        .unwrap_or_else(|| json!(["en"]));
    let current = root
        .get("translation")
        .cloned()
        .unwrap_or(Value::Null);
    let normalized = normalize_translation_config(&current, &defaults, &fallback_targets);
    root.insert("translation".into(), normalized);
}

fn normalize_subtitle_lifecycle(root: &mut Map<String, Value>) {
    let rt_pause_default = int_or(
        root.get("asr")
            .and_then(|v| v.get("realtime"))
            .and_then(|v| v.get("finalization_hold_ms")),
        350,
    );
    let rt_hard_max_default = int_or(
        root.get("asr")
            .and_then(|v| v.get("realtime"))
            .and_then(|v| v.get("max_segment_ms")),
        5500,
    );

    let lifecycle_value = root
        .entry("subtitle_lifecycle".to_string())
        .or_insert_with(|| json!({}));
    let lifecycle = as_object_mut(lifecycle_value);

    let block_ttl = clamp_i64(int_or(lifecycle.get("completed_block_ttl_ms"), 4500), 500, 3_600_000);
    let source_ttl = clamp_i64(
        int_or(lifecycle.get("completed_source_ttl_ms"), block_ttl),
        500,
        3_600_000,
    );
    let translation_ttl = clamp_i64(
        int_or(lifecycle.get("completed_translation_ttl_ms"), block_ttl),
        500,
        3_600_000,
    );
    lifecycle.insert("completed_source_ttl_ms".into(), json!(source_ttl));
    lifecycle.insert(
        "completed_translation_ttl_ms".into(),
        json!(translation_ttl),
    );
    lifecycle.insert(
        "completed_block_ttl_ms".into(),
        json!(source_ttl.max(translation_ttl)),
    );

    let pause = clamp_i64(
        int_or(lifecycle.get("pause_to_finalize_ms"), rt_pause_default),
        120,
        60_000,
    );
    lifecycle.insert("pause_to_finalize_ms".into(), json!(pause));

    lifecycle.insert(
        "allow_early_replace_on_next_final".into(),
        json!(bool_default_true(lifecycle.get("allow_early_replace_on_next_final"))),
    );
    lifecycle.insert(
        "sync_source_and_translation_expiry".into(),
        json!(bool_default_true(lifecycle.get("sync_source_and_translation_expiry"))),
    );
    lifecycle.insert(
        "keep_completed_translation_during_active_partial".into(),
        json!(bool_default_true(
            lifecycle.get("keep_completed_translation_during_active_partial")
        )),
    );

    let hard_max = clamp_i64(
        int_or(lifecycle.get("hard_max_phrase_ms"), rt_hard_max_default),
        1000,
        120_000,
    );
    lifecycle.insert("hard_max_phrase_ms".into(), json!(hard_max));

    if let Some(asr) = root.get_mut("asr").and_then(|v| v.as_object_mut()) {
        let realtime = asr
            .entry("realtime".to_string())
            .or_insert_with(|| json!({}));
        if let Some(rt) = realtime.as_object_mut() {
            rt.insert("finalization_hold_ms".into(), json!(pause));
            rt.insert("max_segment_ms".into(), json!(hard_max));
        }
    }
}

const CANONICAL_SLOT_IDS: [&str; 5] = [
    "translation_1",
    "translation_2",
    "translation_3",
    "translation_4",
    "translation_5",
];

fn enabled_slot_ids(translation_lines: &[Value]) -> Vec<String> {
    translation_lines
        .iter()
        .filter_map(|line| {
            let obj = line.as_object()?;
            if !obj.get("enabled").and_then(|v| v.as_bool()).unwrap_or(true) {
                return None;
            }
            let slot = obj.get("slot_id")?.as_str()?.trim().to_ascii_lowercase();
            if slot.is_empty() {
                None
            } else {
                Some(slot)
            }
        })
        .collect()
}

fn legacy_language_to_slot(translation_lines: &[Value]) -> std::collections::HashMap<String, String> {
    let mut mapping = std::collections::HashMap::new();
    for line in translation_lines {
        let Some(obj) = line.as_object() else {
            continue;
        };
        if !obj.get("enabled").and_then(|v| v.as_bool()).unwrap_or(true) {
            continue;
        }
        let target_lang = obj
            .get("target_lang")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim()
            .to_ascii_lowercase();
        let slot_id = obj
            .get("slot_id")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim()
            .to_ascii_lowercase();
        if !target_lang.is_empty() && !slot_id.is_empty() {
            mapping.entry(target_lang).or_insert(slot_id);
        }
    }
    mapping
}

/// Maps legacy language codes (`ja`, `en`) in display order to `translation_N` slots.
pub fn normalize_display_order(display_order: &[Value], translation_lines: &[Value]) -> Vec<Value> {
    let enabled_slots = enabled_slot_ids(translation_lines);
    let language_to_slot = legacy_language_to_slot(translation_lines);
    let mut normalized: Vec<String> = Vec::new();

    for item in display_order {
        let value = item
            .as_str()
            .unwrap_or("")
            .trim()
            .to_ascii_lowercase();
        if value.is_empty() {
            continue;
        }
        if value == "source" {
            if !normalized.contains(&value) {
                normalized.push(value);
            }
            continue;
        }
        if CANONICAL_SLOT_IDS.contains(&value.as_str()) && enabled_slots.contains(&value) {
            if !normalized.contains(&value) {
                normalized.push(value);
            }
            continue;
        }
        if let Some(mapped) = language_to_slot.get(&value) {
            if !normalized.contains(mapped) {
                normalized.push(mapped.clone());
            }
        }
    }

    if !normalized.contains(&"source".to_string()) {
        normalized.push("source".into());
    }
    for slot_id in enabled_slots {
        if !normalized.contains(&slot_id) {
            normalized.push(slot_id);
        }
    }

    normalized.into_iter().map(Value::String).collect()
}

fn normalize_subtitle_output(root: &mut Map<String, Value>) {
    let translation_lines = root
        .get("translation")
        .and_then(|v| v.get("lines"))
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    let output_value = root
        .entry("subtitle_output".to_string())
        .or_insert_with(|| json!({}));
    let output = as_object_mut(output_value);

    if output.get("show_source").and_then(|v| v.as_bool()).is_none() {
        output.insert("show_source".into(), json!(true));
    }
    if output.get("show_translations").and_then(|v| v.as_bool()).is_none() {
        output.insert("show_translations".into(), json!(true));
    }
    let max_langs = clamp_i64(int_or(output.get("max_translation_languages"), 2), 0, 5);
    output.insert("max_translation_languages".into(), json!(max_langs));

    let display_order = output
        .get("display_order")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_else(|| vec![json!("source"), json!("translation_1")]);
    let normalized = normalize_display_order(&display_order, &translation_lines);
    output.insert("display_order".into(), Value::Array(normalized));
}

/// Configs saved before v8 could carry `keep_completed=false` without any UI control.
pub fn repair_legacy_keep_completed_false(payload: &mut Value, source_version: i64) {
    if source_version >= CURRENT_CONFIG_VERSION {
        return;
    }
    let Some(root) = payload.as_object_mut() else {
        return;
    };
    let Some(lifecycle) = root.get_mut("subtitle_lifecycle").and_then(|v| v.as_object_mut()) else {
        return;
    };
    if lifecycle
        .get("keep_completed_translation_during_active_partial")
        .and_then(|v| v.as_bool())
        == Some(false)
    {
        lifecycle.insert(
            "keep_completed_translation_during_active_partial".into(),
            json!(true),
        );
    }
}

fn normalize_updates_config(root: &mut Map<String, Value>) {
    let defaults = default_config_payload()
        .get("updates")
        .and_then(|value| value.as_object())
        .cloned()
        .unwrap_or_default();

    let updates_value = root
        .entry("updates".to_string())
        .or_insert_with(|| json!({}));
    let updates = as_object_mut(updates_value);

    for (key, default_value) in defaults {
        match key.as_str() {
            "latest_known_version" | "last_checked_utc" => {
                if !updates.contains_key(&key) {
                    updates.insert(key.clone(), default_value.clone());
                }
            }
            "enabled" => {
                if updates.get("enabled").and_then(|v| v.as_bool()).is_none() {
                    updates.insert("enabled".into(), default_value.clone());
                }
            }
            "github_repo" => {
                let current = updates
                    .get("github_repo")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim();
                if current.is_empty() {
                    updates.insert("github_repo".into(), default_value.clone());
                } else if current == LEGACY_GITHUB_REPO {
                    updates.insert(
                        "github_repo".into(),
                        Value::String(DEFAULT_GITHUB_REPO.to_string()),
                    );
                }
            }
            _ => {
                if !updates.contains_key(&key) {
                    updates.insert(key.clone(), default_value.clone());
                }
            }
        }
    }

    // SST shipped updates.enabled=false by default; enable VoiceSub release checks when the
    // section still has virgin metadata (never polled) on the canonical VoiceSub repo.
    let github_repo = updates
        .get("github_repo")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim()
        .to_string();
    let never_checked = updates
        .get("last_checked_utc")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim()
        .is_empty()
        && updates
            .get("latest_known_version")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim()
            .is_empty();
    let voice_sub_repo = github_repo == DEFAULT_GITHUB_REPO || github_repo == LEGACY_GITHUB_REPO;
    if updates.get("enabled").and_then(|v| v.as_bool()) == Some(false)
        && never_checked
        && voice_sub_repo
    {
        updates.insert("enabled".into(), json!(true));
    }

    let release_channel = updates
        .get("release_channel")
        .and_then(|v| v.as_str())
        .unwrap_or("stable")
        .trim()
        .to_ascii_lowercase();
    let release_channel = if release_channel == "prerelease" {
        "prerelease"
    } else {
        "stable"
    };
    updates.insert("release_channel".into(), json!(release_channel));
    updates.insert(
        "check_interval_hours".into(),
        json!(clamp_i64(
            int_or(updates.get("check_interval_hours"), 12),
            1,
            168
        )),
    );
}

fn normalize_source_text_replacement(root: &mut Map<String, Value>) {
    let section_value = root
        .entry("source_text_replacement".to_string())
        .or_insert_with(|| json!({}));
    let section = as_object_mut(section_value);

    if section.get("enabled").and_then(|v| v.as_bool()).is_none() {
        section.insert("enabled".into(), json!(false));
    }
    let include_builtin = section
        .get("include_builtin")
        .and_then(|v| v.as_bool())
        .or_else(|| {
            section
                .get("include_builtin_profanity")
                .and_then(|v| v.as_bool())
        })
        .unwrap_or(true);
    section.insert("include_builtin".into(), json!(include_builtin));
    section.insert("include_builtin_profanity".into(), json!(include_builtin));
    if section.get("case_insensitive").and_then(|v| v.as_bool()).is_none() {
        section.insert("case_insensitive".into(), json!(true));
    }
    let whole_words = match (
        section.get("whole_words").and_then(|v| v.as_bool()),
        section.get("whole_word_only").and_then(|v| v.as_bool()),
    ) {
        (Some(false), _) | (_, Some(false)) => false,
        (Some(true), _) | (_, Some(true)) => true,
        _ => true,
    };
    section.insert("whole_words".into(), json!(whole_words));
    section.insert("whole_word_only".into(), json!(whole_words));
    if section.get("pairs").and_then(|v| v.as_array()).is_none() {
        section.insert("pairs".into(), json!([]));
    }
}

/// Canonical VoiceSub config normalization (mirrors `src/lib/config-normalize.ts`).
pub fn normalize_config_payload(mut payload: Value) -> Value {
    let logging = normalize_logging_config(&payload);
    let root = as_object_mut(&mut payload);

    normalize_subtitle_lifecycle(root);
    normalize_subtitle_output(root);
    normalize_source_text_replacement(root);
    normalize_obs_closed_captions(root);
    normalize_overlay_config(root);
    normalize_asr_browser_config(root);
    normalize_ui_config(root);
    normalize_translation_section(root);
    normalize_updates_config(root);
    root.insert("logging".into(), logging);

    root.insert("config_version".into(), json!(CURRENT_CONFIG_VERSION));
    payload
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_source_text_replacement_field_aliases() {
        let out = normalize_config_payload(json!({
            "source_text_replacement": {
                "enabled": true,
                "include_builtin_profanity": false,
                "whole_word_only": false,
                "pairs": [{"source": "bad", "target": "X"}]
            }
        }));
        let block = &out["source_text_replacement"];
        assert_eq!(block["enabled"], true);
        assert_eq!(block["include_builtin"], false);
        assert_eq!(block["include_builtin_profanity"], false);
        assert_eq!(block["whole_words"], false);
        assert_eq!(block["whole_word_only"], false);
    }

    #[test]
    fn strip_null_values_removes_null_fields_for_toml() {
        let stripped = strip_null_values(json!({
            "audio": { "input_device_id": null, "gain": 1.0 },
            "targets": [null, "en"]
        }));
        assert!(stripped["audio"].get("input_device_id").is_none());
        assert_eq!(stripped["audio"]["gain"], 1.0);
        assert_eq!(stripped["targets"].as_array().unwrap().len(), 1);
    }

    #[test]
    fn normalizes_keep_completed_default_true() {
        let out = normalize_config_payload(json!({
            "config_version": 7,
            "subtitle_lifecycle": {}
        }));
        assert_eq!(
            out["subtitle_lifecycle"]["keep_completed_translation_during_active_partial"],
            true
        );
    }

    #[test]
    fn normalizes_updates_defaults_for_legacy_configs() {
        let out = normalize_config_payload(json!({
            "config_version": CURRENT_CONFIG_VERSION,
            "source_lang": "ru"
        }));
        assert_eq!(out["updates"]["enabled"], true);
        assert_eq!(
            out["updates"]["github_repo"],
            DEFAULT_GITHUB_REPO
        );
        assert_eq!(out["updates"]["provider"], "github_releases");
    }

    #[test]
    fn migrates_legacy_github_repo_slug() {
        let out = normalize_config_payload(json!({
            "config_version": CURRENT_CONFIG_VERSION,
            "updates": { "github_repo": LEGACY_GITHUB_REPO }
        }));
        assert_eq!(out["updates"]["github_repo"], DEFAULT_GITHUB_REPO);
    }

    #[test]
    fn preserves_explicit_updates_disabled() {
        let out = normalize_config_payload(json!({
            "updates": {
                "enabled": false,
                "github_repo": "example/repo"
            }
        }));
        assert_eq!(out["updates"]["enabled"], false);
        assert_eq!(out["updates"]["github_repo"], "example/repo");
    }

    #[test]
    fn enables_voice_sub_updates_for_sst_default_disabled_state() {
        let out = normalize_config_payload(json!({
            "updates": {
                "enabled": false,
                "github_repo": DEFAULT_GITHUB_REPO,
                "last_checked_utc": "",
                "latest_known_version": ""
            }
        }));
        assert_eq!(out["updates"]["enabled"], true);
    }

    #[test]
    fn normalizes_logging_defaults() {
        let out = normalize_config_payload(json!({}));
        assert_eq!(out["logging"]["full_enabled"], false);
        let enabled = normalize_config_payload(json!({
            "logging": { "full_enabled": true }
        }));
        assert_eq!(enabled["logging"]["full_enabled"], true);
    }

    #[test]
    fn preserves_explicit_false_on_current_version() {
        let out = normalize_config_payload(json!({
            "config_version": CURRENT_CONFIG_VERSION,
            "subtitle_lifecycle": {
                "keep_completed_translation_during_active_partial": false
            }
        }));
        assert_eq!(
            out["subtitle_lifecycle"]["keep_completed_translation_during_active_partial"],
            false
        );
    }

    #[test]
    fn repairs_legacy_keep_completed_false() {
        let mut payload = json!({
            "config_version": 7,
            "subtitle_lifecycle": {
                "keep_completed_translation_during_active_partial": false
            }
        });
        repair_legacy_keep_completed_false(&mut payload, 7);
        let out = normalize_config_payload(payload);
        assert_eq!(
            out["subtitle_lifecycle"]["keep_completed_translation_during_active_partial"],
            true
        );
    }

    #[test]
    fn migrates_legacy_display_order_language_codes_to_slots() {
        let out = normalize_config_payload(json!({
            "config_version": 5,
            "translation": {
                "enabled": true,
                "provider": "google_translate_v2",
                "target_languages": ["en", "ja"],
                "lines": [
                    { "slot_id": "translation_1", "enabled": true, "target_lang": "en", "provider": "google_translate_v2", "label": "EN" },
                    { "slot_id": "translation_2", "enabled": true, "target_lang": "ja", "provider": "google_translate_v2", "label": "JA" }
                ]
            },
            "subtitle_output": {
                "display_order": ["ja", "source", "en"]
            }
        }));
        assert_eq!(
            out["subtitle_output"]["display_order"],
            json!(["translation_2", "source", "translation_1"])
        );
    }

    #[test]
    fn overlay_compact_preset_normalizes_to_stacked_plus_compact_flag() {
        let out = normalize_config_payload(json!({
            "config_version": 7,
            "overlay": { "preset": "compact" }
        }));
        assert_eq!(out["overlay"]["preset"], "stacked");
        assert_eq!(out["overlay"]["compact"], true);
    }

    #[test]
    fn worker_launch_browser_invalid_value_maps_to_auto() {
        let out = normalize_config_payload(json!({
            "config_version": 7,
            "asr": { "browser": { "worker_launch_browser": "safari" } }
        }));
        assert_eq!(out["asr"]["browser"]["worker_launch_browser"], "auto");
    }

    #[test]
    fn worker_launch_browser_chromium_maps_to_auto() {
        let out = normalize_config_payload(json!({
            "config_version": 7,
            "asr": { "browser": { "worker_launch_browser": "chromium" } }
        }));
        assert_eq!(out["asr"]["browser"]["worker_launch_browser"], "auto");
    }

    #[test]
    fn removed_mymemory_provider_falls_back_to_google_translate_v2() {
        let out = normalize_config_payload(json!({
            "config_version": 7,
            "translation": {
                "enabled": true,
                "provider": "mymemory",
                "target_languages": ["en"]
            }
        }));
        assert_eq!(out["translation"]["provider"], "google_translate_v2");
    }

    #[test]
    fn ui_language_round_trips_and_invalid_normalizes_to_empty() {
        let saved = normalize_config_payload(json!({
            "config_version": 7,
            "ui": { "language": "ru" }
        }));
        assert_eq!(saved["ui"]["language"], "ru");

        let invalid = normalize_config_payload(json!({
            "config_version": 7,
            "ui": { "language": "de" }
        }));
        assert_eq!(invalid["ui"]["language"], "");
    }

    #[test]
    fn clamps_ttl_and_syncs_realtime_pause() {
        let out = normalize_config_payload(json!({
            "config_version": 7,
            "subtitle_lifecycle": {
                "completed_source_ttl_ms": 100,
                "completed_translation_ttl_ms": 9000,
                "pause_to_finalize_ms": 400
            },
            "asr": { "realtime": { "finalization_hold_ms": 100 } }
        }));
        assert_eq!(out["subtitle_lifecycle"]["completed_source_ttl_ms"], 500);
        assert_eq!(out["subtitle_lifecycle"]["completed_translation_ttl_ms"], 9000);
        assert_eq!(out["asr"]["realtime"]["finalization_hold_ms"], 400);
        assert_eq!(out["asr"]["realtime"]["max_segment_ms"], 5500);
    }

    #[test]
    fn lifecycle_pause_and_hard_max_fallback_to_realtime() {
        let out = normalize_config_payload(json!({
            "config_version": 7,
            "asr": {
                "realtime": {
                    "finalization_hold_ms": 420,
                    "max_segment_ms": 6200
                }
            }
        }));
        assert_eq!(out["subtitle_lifecycle"]["pause_to_finalize_ms"], 420);
        assert_eq!(out["subtitle_lifecycle"]["hard_max_phrase_ms"], 6200);
        assert_eq!(out["asr"]["realtime"]["finalization_hold_ms"], 420);
        assert_eq!(out["asr"]["realtime"]["max_segment_ms"], 6200);
    }
}
