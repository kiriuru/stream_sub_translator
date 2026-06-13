//! Product version and GitHub release comparison (SST parity).

use serde_json::{json, Value};

/// Product version — single source until crate-only policy is enforced.
pub const PROJECT_VERSION: &str = "0.5.1";
pub const RELEASE_TRACK: &str = "stable";
pub const DEFAULT_UPDATE_PROVIDER: &str = "github_releases";
pub const DEFAULT_RELEASE_CHANNEL: &str = "stable";
/// Canonical GitHub repo for update checks and release download links.
pub const DEFAULT_GITHUB_REPO: &str = "kiriuru/VoiceSub";
/// Legacy SST repo slug — migrated on config load.
pub const LEGACY_GITHUB_REPO: &str = "kiriuru/stream_sub_translator";

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct SemVer {
    major: u32,
    minor: u32,
    patch: u32,
    build: u32,
}

fn parse_semver(value: &str) -> Option<SemVer> {
    let text = value.trim().trim_start_matches('v');
    if text.is_empty() {
        return None;
    }
    let (core, _) = text.split_once(['-', '+']).unwrap_or((text, ""));
    let mut parts = core.split('.');
    let major = parts.next()?.parse().ok()?;
    let minor = parts.next()?.parse().ok()?;
    let patch = parts.next()?.parse().ok()?;
    let build = parts
        .next()
        .and_then(|part| part.parse().ok())
        .unwrap_or(0);
    Some(SemVer {
        major,
        minor,
        patch,
        build,
    })
}

fn format_semver(semver: &SemVer) -> String {
    if semver.build > 0 {
        return format!(
            "{}.{}.{}.{}",
            semver.major, semver.minor, semver.patch, semver.build
        );
    }
    format!("{}.{}.{}", semver.major, semver.minor, semver.patch)
}

/// Returns true when `remote_version` is strictly newer than `local_version`.
pub fn is_remote_version_newer(local_version: &str, remote_version: &str) -> bool {
    match (parse_semver(local_version), parse_semver(remote_version)) {
        (Some(local), Some(remote)) => remote > local,
        _ => false,
    }
}

/// Pick the highest semver from a GitHub Releases API payload.
pub fn extract_latest_github_release(
    releases_payload: &Value,
    release_channel: &str,
) -> (Option<String>, String, Option<String>) {
    let channel = release_channel.trim().to_ascii_lowercase();
    let channel = if channel == "prerelease" {
        "prerelease"
    } else {
        "stable"
    };

    let Some(items) = releases_payload.as_array() else {
        return (
            None,
            "GitHub releases payload was not a list.".to_string(),
            None,
        );
    };

    let mut best: Option<SemVer> = None;
    let mut best_raw: Option<String> = None;
    let mut best_url: Option<String> = None;
    let mut scanned = 0usize;

    for item in items {
        let Some(obj) = item.as_object() else {
            continue;
        };
        scanned += 1;
        if obj.get("draft").and_then(Value::as_bool).unwrap_or(false) {
            continue;
        }
        let is_prerelease = obj
            .get("prerelease")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        if channel == "stable" && is_prerelease {
            continue;
        }
        let tag = obj
            .get("tag_name")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(str::to_string)
            .or_else(|| {
                obj.get("name")
                    .and_then(Value::as_str)
                    .map(str::trim)
                    .filter(|value| !value.is_empty())
                    .map(str::to_string)
            });
        let Some(tag) = tag else {
            continue;
        };
        let Some(semver) = parse_semver(&tag) else {
            continue;
        };
        if best.as_ref().is_none_or(|current| semver > *current) {
            best = Some(semver);
            best_raw = Some(tag);
            best_url = obj
                .get("html_url")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .map(str::to_string);
        }
    }

    let Some(best) = best else {
        return (
            None,
            format!("No usable release versions found (scanned {scanned} releases)."),
            None,
        );
    };

    let formatted = format_semver(&best);
    let raw = best_raw
        .as_deref()
        .unwrap_or("")
        .trim()
        .trim_start_matches('v')
        .to_string();
    let message = if !raw.is_empty() && raw != formatted {
        format!("Latest release tag: {raw} (normalized to {formatted}).")
    } else {
        format!("Latest release version: {formatted}.")
    };
    (Some(formatted), message, best_url)
}

pub fn release_url_for(github_repo: &str, version: &str) -> String {
    let repo = github_repo.trim().trim_matches('/');
    let version = version.trim().trim_start_matches('v');
    format!("https://github.com/{repo}/releases/tag/v{version}")
}

/// Build `/api/version` and `/api/updates/check` payload from config `updates` section.
pub fn build_version_info_payload(config: Option<&Value>) -> Value {
    let payload = config
        .filter(|value| value.is_object())
        .unwrap_or(&Value::Null);
    let updates = payload.get("updates").and_then(Value::as_object);
    let updates = updates.cloned().unwrap_or_default();

    let provider = updates
        .get("provider")
        .and_then(Value::as_str)
        .unwrap_or(DEFAULT_UPDATE_PROVIDER)
        .trim()
        .to_ascii_lowercase();
    let provider = if provider == "github_releases" {
        "github_releases"
    } else {
        DEFAULT_UPDATE_PROVIDER
    };

    let github_repo = updates
        .get("github_repo")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_string();
    let release_channel = updates
        .get("release_channel")
        .and_then(Value::as_str)
        .unwrap_or(DEFAULT_RELEASE_CHANNEL)
        .trim()
        .to_ascii_lowercase();
    let release_channel = if release_channel == "prerelease" {
        "prerelease"
    } else {
        DEFAULT_RELEASE_CHANNEL
    };

    let latest_known_version = updates
        .get("latest_known_version")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string);
    let last_checked_utc = updates
        .get("last_checked_utc")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string);
    let enabled = updates
        .get("enabled")
        .and_then(Value::as_bool)
        .unwrap_or(false);

    let update_available = latest_known_version
        .as_deref()
        .is_some_and(|latest| is_remote_version_newer(PROJECT_VERSION, latest));
    let check_supported = !github_repo.is_empty();
    let message = if enabled && check_supported {
        "Update check is available via /api/updates/check."
    } else {
        "Update checks are disabled or not configured."
    };

    let release_url = latest_known_version
        .as_deref()
        .filter(|_| update_available && !github_repo.is_empty())
        .map(|version| release_url_for(&github_repo, version));

    json!({
        "ok": true,
        "current_version": PROJECT_VERSION,
        "version": PROJECT_VERSION,
        "product": "VoiceSub",
        "release_track": RELEASE_TRACK,
        "sync": {
            "provider": provider,
            "enabled": enabled,
            "github_repo": if github_repo.is_empty() { Value::Null } else { json!(github_repo) },
            "release_channel": release_channel,
            "latest_known_version": latest_known_version,
            "last_checked_utc": last_checked_utc,
            "update_available": update_available,
            "check_supported": check_supported,
            "check_active": false,
            "release_url": release_url,
            "message": message
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_semver_accepts_four_part_versions() {
        assert_eq!(
            parse_semver("0.2.9.0"),
            Some(SemVer {
                major: 0,
                minor: 2,
                patch: 9,
                build: 0
            })
        );
        assert_eq!(
            parse_semver("v2.8.3"),
            Some(SemVer {
                major: 2,
                minor: 8,
                patch: 3,
                build: 0
            })
        );
    }

    #[test]
    fn update_check_compares_four_part_versions() {
        assert!(is_remote_version_newer("0.2.8.9", "0.2.9.0"));
        assert!(!is_remote_version_newer("0.2.9.0", "0.2.9.0"));
    }

    #[test]
    fn voicesub_patch_and_minor_bumps_trigger_update() {
        assert!(is_remote_version_newer("0.5.1", "0.5.2"));
        assert!(is_remote_version_newer("0.5.1", "0.6.0"));
        assert!(!is_remote_version_newer("0.5.1", "0.5.1"));
        assert!(!is_remote_version_newer("0.5.1", "0.5.0"));
        assert!(!is_remote_version_newer(PROJECT_VERSION, PROJECT_VERSION));
    }

    #[test]
    fn build_version_payload_no_update_when_github_behind_local() {
        let payload = build_version_info_payload(Some(&json!({
            "updates": {
                "enabled": true,
                "provider": "github_releases",
                "github_repo": DEFAULT_GITHUB_REPO,
                "latest_known_version": "0.5.0"
            }
        })));
        assert_eq!(payload["current_version"], PROJECT_VERSION);
        assert_eq!(payload["sync"]["update_available"], false);
    }

    #[test]
    fn github_releases_pick_highest_0_5_x_and_trigger_update() {
        let releases = json!([
            {
                "tag_name": "v0.5.0",
                "draft": false,
                "prerelease": false,
                "html_url": "https://github.com/kiriuru/VoiceSub/releases/tag/v0.5.0"
            },
            {
                "tag_name": "v0.5.2",
                "draft": false,
                "prerelease": false,
                "html_url": "https://github.com/kiriuru/VoiceSub/releases/tag/v0.5.2"
            }
        ]);
        let (latest, _, url) = extract_latest_github_release(&releases, "stable");
        assert_eq!(latest.as_deref(), Some("0.5.2"));
        assert_eq!(
            url.as_deref(),
            Some("https://github.com/kiriuru/VoiceSub/releases/tag/v0.5.2")
        );
        assert!(is_remote_version_newer(PROJECT_VERSION, latest.as_deref().unwrap()));

        let payload = build_version_info_payload(Some(&json!({
            "updates": {
                "enabled": true,
                "provider": "github_releases",
                "github_repo": DEFAULT_GITHUB_REPO,
                "latest_known_version": latest
            }
        })));
        assert_eq!(payload["sync"]["update_available"], true);
        assert_eq!(
            payload["sync"]["release_url"],
            "https://github.com/kiriuru/VoiceSub/releases/tag/v0.5.2"
        );
    }

    #[test]
    fn build_version_payload_exposes_update_available() {
        let payload = build_version_info_payload(Some(&json!({
            "updates": {
                "enabled": true,
                "provider": "github_releases",
                "github_repo": "example/repo",
                "latest_known_version": "0.5.2"
            }
        })));
        assert_eq!(payload["current_version"], "0.5.1");
        assert_eq!(payload["sync"]["update_available"], true);
    }

    #[test]
    fn extract_latest_release_prefers_highest_semver() {
        let releases = json!([
            {"tag_name": "v0.3.2", "draft": false, "prerelease": false},
            {"tag_name": "v0.4.1", "draft": false, "prerelease": true},
            {"tag_name": "0.3.10", "draft": false, "prerelease": false}
        ]);
        let (latest, _, _) = extract_latest_github_release(&releases, "stable");
        assert_eq!(latest.as_deref(), Some("0.3.10"));
    }

    #[test]
    fn extract_latest_release_allows_prereleases() {
        let releases = json!([
            {"tag_name": "0.3.2", "draft": false, "prerelease": false},
            {"tag_name": "0.4.1", "draft": false, "prerelease": true, "html_url": "https://example/prerelease"}
        ]);
        let (latest, _, url) = extract_latest_github_release(&releases, "prerelease");
        assert_eq!(latest.as_deref(), Some("0.4.1"));
        assert_eq!(url.as_deref(), Some("https://example/prerelease"));
    }
}
