//! Core Audio helpers for optional VoiceSub modules (TTS output routing).

mod error;
mod playback;
mod sonic_speed;
mod trace;

#[cfg(windows)]
mod policy_config;

#[cfg(windows)]
mod platform;

pub use error::AudioError;
pub use playback::{
    PlaybackFinished, PlaybackHub, CHANNEL_SPEECH, CHANNEL_TWITCH, resolve_output_device,
};
#[cfg(windows)]
pub use platform::is_per_process_routing_enabled;

#[cfg(not(windows))]
pub fn is_per_process_routing_enabled() -> bool {
    false
}

/// Render endpoint visible to the module UI and config store.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct AudioOutputDevice {
    /// Stable endpoint id (WASAPI). Empty string means system default.
    pub id: String,
    pub label: String,
    /// `true` for the synthetic "Default" entry.
    #[serde(default)]
    pub is_default: bool,
}

/// List active render endpoints. Always includes a synthetic default row first.
pub fn list_output_devices() -> Result<Vec<AudioOutputDevice>, AudioError> {
    tracing::debug!(target: "voicesub.tts.audio", "list_output_devices");
    let result = {
        #[cfg(windows)]
        {
            platform::list_output_devices()
        }
        #[cfg(not(windows))]
        {
            Ok(vec![AudioOutputDevice {
                id: String::new(),
                label: "Default".to_string(),
                is_default: true,
            }])
        }
    };
    match &result {
        Ok(devices) => {
            tracing::info!(
                target: "voicesub.tts.audio",
                count = devices.len(),
                "output devices enumerated"
            );
            trace::trace(
                "platform",
                "devices_enumerated",
                serde_json::json!({
                    "count": devices.len(),
                    "labels": devices.iter().map(|d| &d.label).collect::<Vec<_>>(),
                }),
            );
        }
        Err(err) => {
            tracing::warn!(target: "voicesub.tts.audio", error = %err, "device enumeration failed");
            trace::trace(
                "platform",
                "devices_enumerate_failed",
                serde_json::json!({ "error": err.to_string() }),
            );
        }
    }
    result
}

/// Enumerate WASAPI endpoints on a dedicated thread so IPC handlers never block.
pub fn list_output_devices_on_thread() -> Result<Vec<AudioOutputDevice>, AudioError> {
    std::thread::Builder::new()
        .name("voicesub-audio-enum".into())
        .spawn(list_output_devices)
        .map_err(|err| AudioError::PlaybackFailed(format!("audio enum thread spawn failed: {err}")))?
        .join()
        .map_err(|_| AudioError::PlaybackFailed("audio enum thread panicked".into()))?
}

/// Route render output for `pid` to `device_id`. Empty `device_id` clears per-process override.
pub fn set_process_output_device(pid: u32, device_id: &str) -> Result<(), AudioError> {
    if pid == 0 {
        tracing::warn!(target: "voicesub.tts.audio", pid, "reject routing for zero pid");
        return Err(AudioError::InvalidProcessId);
    }
    trace::trace(
        "routing",
        "route_requested",
        serde_json::json!({
            "pid": pid,
            "device_id": trace::device_id_field(device_id),
        }),
    );
    let result = {
        #[cfg(windows)]
        {
            platform::set_process_output_device(pid, device_id)
        }
        #[cfg(not(windows))]
        {
            let _ = device_id;
            tracing::warn!(target: "voicesub.tts.audio", pid, "audio routing is only supported on Windows");
            Ok(())
        }
    };
    if let Err(err) = &result {
        tracing::warn!(
            target: "voicesub.tts.audio",
            pid,
            device_id = if device_id.is_empty() { "default" } else { device_id },
            error = %err,
            "per-process audio routing failed"
        );
        trace::trace(
            "routing",
            "route_failed",
            serde_json::json!({
                "pid": pid,
                "device_id": trace::device_id_field(device_id),
                "error": err.to_string(),
            }),
        );
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn list_devices_includes_default_row() {
        let devices = list_output_devices().expect("list_output_devices");
        assert!(!devices.is_empty());
        assert!(devices.iter().any(|d| d.is_default));
    }

    #[test]
    fn zero_pid_is_rejected() {
        let err = set_process_output_device(0, "").unwrap_err();
        assert!(matches!(err, AudioError::InvalidProcessId));
    }
}
