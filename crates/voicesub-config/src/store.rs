use std::fs;
use std::path::{Path, PathBuf};

use serde_json::{json, Value};
use thiserror::Error;
use tracing::{info, warn};

use crate::atomic_io::atomic_write;
use crate::defaults::CURRENT_CONFIG_VERSION;
use crate::document::ConfigDocument;
use crate::migrate::{apply_voicesub_import_rules, import_sst_json_value, migrate_sst_payload};
use crate::normalize::{
    normalize_config_payload, repair_legacy_keep_completed_false, strip_null_values,
};

#[derive(Debug, Error)]
pub enum ConfigError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("toml parse error: {0}")]
    TomlParse(#[from] toml::de::Error),
    #[error("toml serialize error: {0}")]
    TomlSerialize(#[from] toml::ser::Error),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("invalid configuration: {0}")]
    Invalid(String),
}

pub struct ConfigStore {
    path: PathBuf,
    document: ConfigDocument,
}

impl ConfigStore {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self {
            path: path.into(),
            document: ConfigDocument::with_defaults(),
        }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn document(&self) -> &ConfigDocument {
        &self.document
    }

    pub fn payload(&self) -> &Value {
        self.document.payload()
    }

    pub fn load_or_create(&mut self) -> Result<&ConfigDocument, ConfigError> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }
        if !self.path.is_file() {
            let legacy_json = self
                .path
                .parent()
                .map(|dir| dir.join(crate::paths::LEGACY_SST_CONFIG_JSON))
                .filter(|path| path.is_file());
            if let Some(legacy_json) = legacy_json {
                info!(
                    legacy = %legacy_json.display(),
                    target = %self.path.display(),
                    "migrating legacy SST config.json into config.toml"
                );
                match self.import_sst_json_file(&legacy_json) {
                    Ok(()) => return Ok(&self.document),
                    Err(err) => {
                        warn!(
                            error = %err,
                            legacy = %legacy_json.display(),
                            "legacy SST config.json import failed; creating defaults"
                        );
                        self.document = ConfigDocument::with_defaults();
                        self.save()?;
                        return Ok(&self.document);
                    }
                }
            }
            info!(path = %self.path.display(), "creating default config.toml");
            self.document = ConfigDocument::with_defaults();
            self.save()?;
            return Ok(&self.document);
        }

        let raw = fs::read_to_string(&self.path)?;
        match Self::parse_toml_str(&raw) {
            Ok(payload) => {
                let normalized = Self::normalize_loaded_payload(payload.clone());
                let changed = normalized != payload;
                self.document =
                    ConfigDocument::from_payload(normalized, self.path.display().to_string());
                if changed {
                    self.save()?;
                }
            }
            Err(err) => {
                warn!(error = %err, path = %self.path.display(), "config.toml corrupt; using defaults");
                self.document = ConfigDocument::with_defaults();
                self.save()?;
            }
        }
        Ok(&self.document)
    }

    pub fn save(&self) -> Result<(), ConfigError> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }
        let payload = strip_null_values(self.document.payload().clone());
        let toml_value: toml::Value = serde_json::from_value(payload)?;
        let rendered = toml::to_string_pretty(&toml_value)?;
        atomic_write(&self.path, &rendered)?;
        Ok(())
    }

    pub fn apply_save_payload(&mut self, incoming: &Value) -> Result<(), ConfigError> {
        let normalized = normalize_config_payload(incoming.clone());
        self.document.merge_save_request(&normalized);
        self.save()
    }

    /// Persist only `updates.latest_known_version` and `updates.last_checked_utc`.
    pub fn patch_updates_metadata(
        &mut self,
        latest_version: &str,
        checked_utc: &str,
    ) -> Result<(), ConfigError> {
        let mut payload = self.document.payload().clone();
        let root = payload
            .as_object_mut()
            .ok_or_else(|| ConfigError::Invalid("config root is not an object".into()))?;
        let updates = root
            .entry("updates")
            .or_insert_with(|| json!({}));
        let updates_obj = updates
            .as_object_mut()
            .ok_or_else(|| ConfigError::Invalid("updates is not an object".into()))?;
        updates_obj.insert(
            "latest_known_version".into(),
            Value::String(latest_version.to_string()),
        );
        updates_obj.insert(
            "last_checked_utc".into(),
            Value::String(checked_utc.to_string()),
        );
        let normalized = normalize_config_payload(payload);
        self.document = ConfigDocument::from_payload(
            normalized,
            self.document.loaded_from().to_string(),
        );
        self.save()
    }

    pub fn import_sst_json_file(&mut self, json_path: impl AsRef<Path>) -> Result<(), ConfigError> {
        let raw = fs::read_to_string(json_path.as_ref())?;
        let payload: Value = serde_json::from_str(&raw)?;
        let migrated = import_sst_json_value(payload);
        self.document = ConfigDocument::from_payload(
            migrated,
            format!("import:{}", json_path.as_ref().display()),
        );
        self.save()?;
        Ok(())
    }

    fn parse_toml_str(raw: &str) -> Result<Value, ConfigError> {
        let toml_value: toml::Value = toml::from_str(raw)?;
        Ok(serde_json::to_value(toml_value)?)
    }

    fn normalize_loaded_payload(payload: Value) -> Value {
        let source_version = payload
            .get("config_version")
            .and_then(|v| v.as_i64().or_else(|| v.as_u64().map(|n| n as i64)))
            .unwrap_or(0);
        let migrated = if source_version < CURRENT_CONFIG_VERSION {
            migrate_sst_payload(payload)
        } else {
            payload
        };
        let mut imported = apply_voicesub_import_rules(migrated);
        repair_legacy_keep_completed_false(&mut imported, source_version);
        normalize_config_payload(imported)
    }
}
