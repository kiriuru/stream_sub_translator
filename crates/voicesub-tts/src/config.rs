use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use thiserror::Error;
use tracing::{debug, info, warn};

use crate::subtitle_speech::TtsSpeechSettings;
use voicesub_twitch::TwitchTtsSettings;

#[derive(Debug, Error)]
pub enum TtsConfigError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),

    #[error("toml parse error: {0}")]
    Parse(#[from] toml::de::Error),

    #[error("toml serialize error: {0}")]
    Serialize(#[from] toml::ser::Error),
}

pub const TTS_PROVIDER_BROWSER_GOOGLE: &str = "browser_google";
pub const TTS_PROVIDER_PYTHON_STDLIB: &str = "python_stdlib";
pub const PLAYBACK_MODE_NATIVE: &str = "native";
pub const PLAYBACK_MODE_BROWSER: &str = "browser";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TtsConfig {
    #[serde(default = "default_enabled")]
    pub enabled: bool,
    /// `browser_google` (HTTP proxy + browser audio) or `python_stdlib` (urllib script).
    #[serde(default = "default_tts_provider")]
    pub tts_provider: String,
    /// Browser `MediaDeviceInfo.deviceId` from `selectAudioOutput`; empty = default.
    #[serde(default)]
    pub audio_output_device_id: String,
    #[serde(default)]
    pub audio_output_device_label: String,
    /// `native` (Rust/cpal) or `browser` (`HTMLAudioElement` fallback).
    #[serde(default = "default_playback_mode")]
    pub playback_mode: String,
    #[serde(default = "default_rate")]
    pub speech_rate: f32,
    #[serde(default = "default_volume")]
    pub speech_volume: f32,
    #[serde(default)]
    pub speech: TtsSpeechSettings,
    #[serde(default)]
    pub twitch: TwitchTtsSettings,
}

fn default_enabled() -> bool {
    true
}

fn default_tts_provider() -> String {
    TTS_PROVIDER_BROWSER_GOOGLE.to_string()
}

pub fn normalize_tts_provider(provider: &str) -> Option<String> {
    let trimmed = provider.trim();
    match trimmed {
        TTS_PROVIDER_BROWSER_GOOGLE | TTS_PROVIDER_PYTHON_STDLIB => Some(trimmed.to_string()),
        _ => None,
    }
}

fn default_playback_mode() -> String {
    PLAYBACK_MODE_NATIVE.to_string()
}

pub fn normalize_playback_mode(mode: &str) -> Option<String> {
    match mode.trim().to_ascii_lowercase().as_str() {
        PLAYBACK_MODE_NATIVE => Some(PLAYBACK_MODE_NATIVE.to_string()),
        PLAYBACK_MODE_BROWSER => Some(PLAYBACK_MODE_BROWSER.to_string()),
        _ => None,
    }
}

fn default_rate() -> f32 {
    1.0
}

fn default_volume() -> f32 {
    1.0
}

impl Default for TtsConfig {
    fn default() -> Self {
        Self {
            enabled: default_enabled(),
            tts_provider: default_tts_provider(),
            audio_output_device_id: String::new(),
            audio_output_device_label: String::new(),
            playback_mode: default_playback_mode(),
            speech_rate: default_rate(),
            speech_volume: default_volume(),
            speech: TtsSpeechSettings::default(),
            twitch: TwitchTtsSettings::default(),
        }
    }
}

pub struct TtsConfigStore {
    path: PathBuf,
}

impl TtsConfigStore {
    pub fn new(module_dir: impl Into<PathBuf>) -> Self {
        Self {
            path: module_dir.into().join("config.toml"),
        }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn load(&self) -> Result<TtsConfig, TtsConfigError> {
        if !self.path.is_file() {
            let config = TtsConfig::default();
            info!(
                target: "voicesub.tts",
                path = %self.path.display(),
                "tts config missing; writing defaults"
            );
            self.save(&config)?;
            return Ok(config);
        }
        let text = fs::read_to_string(&self.path)?;
        let config: TtsConfig = toml::from_str(&text)?;
        debug!(
            target: "voicesub.tts",
            path = %self.path.display(),
            enabled = config.enabled,
            "tts config loaded from disk"
        );
        Ok(config)
    }

    pub fn save(&self, config: &TtsConfig) -> Result<(), TtsConfigError> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }
        let text = toml::to_string_pretty(config)?;
        fs::write(&self.path, text)?;
        info!(path = %self.path.display(), "tts module config saved");
        Ok(())
    }

    pub fn update<F>(&self, mutate: F) -> Result<TtsConfig, TtsConfigError>
    where
        F: FnOnce(&mut TtsConfig),
    {
        let mut config = self.load().unwrap_or_else(|err| {
            warn!(error = %err, "tts config load failed; using defaults");
            TtsConfig::default()
        });
        mutate(&mut config);
        self.save(&config)?;
        Ok(config)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_twitch_ignore_users() {
        let dir = std::env::temp_dir().join(format!("voicesub-tts-ignore-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        let store = TtsConfigStore::new(&dir);
        let mut twitch = TwitchTtsSettings::default();
        twitch.ignore_users = vec!["nightbot".into(), "streamelements".into()];
        let config = TtsConfig {
            twitch,
            ..TtsConfig::default()
        };
        store.save(&config).expect("save");
        let loaded = store.load().expect("load");
        assert_eq!(
            loaded.twitch.ignore_users,
            vec!["nightbot".to_string(), "streamelements".to_string()]
        );
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn roundtrip_config() {
        let dir = std::env::temp_dir().join(format!("voicesub-tts-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        let store = TtsConfigStore::new(&dir);
        let config = TtsConfig {
            enabled: false,
            tts_provider: TTS_PROVIDER_PYTHON_STDLIB.to_string(),
            playback_mode: PLAYBACK_MODE_NATIVE.to_string(),
            audio_output_device_id: "{test-device}".to_string(),
            audio_output_device_label: "Speakers".to_string(),
            speech_rate: 1.1,
            speech_volume: 0.8,
            speech: TtsSpeechSettings {
                speak_source: true,
                speak_translations: false,
                translation_slots: vec!["translation_1".into()],
                min_chars: 4,
                max_queue_items: 4,
            },
            twitch: TwitchTtsSettings::default(),
        };
        store.save(&config).expect("save");
        let loaded = store.load().expect("load");
        assert_eq!(loaded, config);
        let _ = fs::remove_dir_all(&dir);
    }
}
