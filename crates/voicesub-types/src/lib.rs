//! Shared DTOs, enums, and WebSocket/API payload types (Layer 0).

pub mod asr;
pub mod version;
pub mod ws;

pub use asr::ExternalAsrUpdate;
pub use version::{
    build_version_info_payload, extract_latest_github_release, is_remote_version_newer,
    release_url_for, PROJECT_VERSION, RELEASE_TRACK,
};
pub use ws::{parse_worker_message_type, AsrWorkerHello, EventsHello, WsMessage, WsMessageType};
