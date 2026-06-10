use std::fs;
use std::path::PathBuf;

use serde_json::json;
use voicesub_config::{import_sst_json_value, ConfigStore};

#[test]
fn patch_updates_metadata_persists_only_updates_section() {
    let dir = std::env::temp_dir().join(format!("voicesub-cfg-upd-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    let path = dir.join("config.toml");

    let mut store = ConfigStore::new(&path);
    store.load_or_create().expect("load");
    let before_lang = store.payload()["ui"]["language"].clone();
    store
        .patch_updates_metadata("0.9.9", "2026-06-10T12:00:00+00:00")
        .expect("patch");

    let mut reloaded = ConfigStore::new(&path);
    reloaded.load_or_create().expect("reload");
    assert_eq!(
        reloaded.payload()["updates"]["latest_known_version"],
        "0.9.9"
    );
    assert_eq!(
        reloaded.payload()["updates"]["last_checked_utc"],
        "2026-06-10T12:00:00+00:00"
    );
    assert_eq!(reloaded.payload()["ui"]["language"], before_lang);

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn toml_roundtrip_preserves_browser_google_mode() {
    let dir = std::env::temp_dir().join(format!("voicesub-cfg-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    let path = dir.join("config.toml");

    let mut store = ConfigStore::new(&path);
    store.load_or_create().expect("load");
    assert_eq!(store.payload()["asr"]["mode"], "browser_google");
    store.save().expect("save");
    assert!(path.is_file());

    let mut reloaded = ConfigStore::new(&path);
    reloaded.load_or_create().expect("reload");
    assert_eq!(reloaded.payload()["asr"]["mode"], "browser_google");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn load_normalizes_legacy_local_asr_in_toml() {
    let dir = std::env::temp_dir().join(format!("voicesub-cfg-local-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    let path = dir.join("config.toml");
    fs::write(
        &path,
        r#"
config_version = 7

[asr]
mode = "local"
"#,
    )
    .unwrap();

    let mut store = ConfigStore::new(&path);
    store.load_or_create().expect("load");
    assert_eq!(store.payload()["asr"]["mode"], "browser_google");
    assert!(store.payload().get("remote").is_none());

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn load_fixes_project_user_data_keep_completed_false() {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(2)
        .expect("workspace root")
        .join("user-data/config.toml");
    if !path.is_file() {
        return;
    }
    let mut store = ConfigStore::new(&path);
    store.load_or_create().expect("load project config");
    assert_eq!(
        store.payload()["subtitle_lifecycle"]["keep_completed_translation_during_active_partial"],
        true
    );
}

#[test]
fn load_fixes_legacy_keep_completed_false() {
    let dir = std::env::temp_dir().join(format!("voicesub-cfg-keep-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    let path = dir.join("config.toml");
    fs::write(
        &path,
        r#"
config_version = 7

[subtitle_lifecycle]
keep_completed_translation_during_active_partial = false
completed_source_ttl_ms = 4500
completed_translation_ttl_ms = 7000
"#,
    )
    .unwrap();

    let mut store = ConfigStore::new(&path);
    store.load_or_create().expect("load");
    assert_eq!(
        store.payload()["subtitle_lifecycle"]["keep_completed_translation_during_active_partial"],
        true
    );
    assert_eq!(store.payload()["config_version"], 8);

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn load_recovers_from_corrupt_toml() {
    let dir = std::env::temp_dir().join(format!("voicesub-cfg-corrupt-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    let path = dir.join("config.toml");
    fs::write(&path, "{not: json").unwrap();

    let mut store = ConfigStore::new(&path);
    store.load_or_create().expect("recover corrupt config");
    assert_eq!(
        store.payload()["config_version"].as_i64().unwrap_or(0),
        voicesub_config::CURRENT_CONFIG_VERSION
    );
    assert!(path.is_file());

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn load_or_create_imports_legacy_sst_config_json_with_null_fields() {
    let dir = std::env::temp_dir().join(format!("voicesub-cfg-null-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    let json_path = dir.join("config.json");
    let toml_path = dir.join("config.toml");
    fs::write(
        &json_path,
        serde_json::to_string_pretty(&json!({
            "config_version": 7,
            "audio": { "input_device_id": null },
            "asr": { "mode": "local" },
            "translation": { "enabled": true, "provider": "google_translate_v2" }
        }))
        .unwrap(),
    )
    .unwrap();

    let mut store = ConfigStore::new(&toml_path);
    store
        .load_or_create()
        .expect("import legacy json with null fields");
    assert!(toml_path.is_file());
    let saved = fs::read_to_string(&toml_path).unwrap();
    assert!(!saved.contains("null"));
    assert_eq!(store.payload()["asr"]["mode"], "browser_google");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn load_or_create_imports_legacy_sst_config_json_when_toml_missing() {
    let dir = std::env::temp_dir().join(format!("voicesub-cfg-legacy-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    let json_path = dir.join("config.json");
    let toml_path = dir.join("config.toml");
    fs::write(
        &json_path,
        serde_json::to_string_pretty(&json!({
            "config_version": 7,
            "asr": { "mode": "local" },
            "translation": { "enabled": true, "provider": "google_translate_v2" }
        }))
        .unwrap(),
    )
    .unwrap();

    let mut store = ConfigStore::new(&toml_path);
    store.load_or_create().expect("import legacy json");
    assert!(toml_path.is_file());
    assert_eq!(store.payload()["asr"]["mode"], "browser_google");
    assert_eq!(store.payload()["config_version"], 8);

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn import_sst_json_maps_local_to_browser_google() {
    let migrated = import_sst_json_value(json!({
        "config_version": 3,
        "asr": { "mode": "local", "provider_preference": "official_eu_parakeet_low_latency" },
        "remote": { "enabled": true }
    }));
    assert_eq!(migrated["asr"]["mode"], "browser_google");
    assert!(migrated.get("remote").is_none());
    assert!(migrated["asr"].get("provider_preference").is_none());
}
