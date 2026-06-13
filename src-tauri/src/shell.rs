use tracing::info;
use url::Host;

/// Allow local overlay / worker preview pages opened from the dashboard shell.
pub fn validate_local_http_url(url: &str) -> Result<(), String> {
    let trimmed = url.trim();
    if trimmed.is_empty() {
        return Err("url is empty".into());
    }
    let parsed = url::Url::parse(trimmed).map_err(|err| err.to_string())?;
    if parsed.scheme() != "http" {
        return Err("only http URLs are allowed".into());
    }
    let host = parsed.host().ok_or_else(|| "missing host".to_string())?;
    if !is_loopback_host(&host) {
        return Err(format!("host is not loopback: {host}"));
    }
    Ok(())
}

fn is_loopback_host(host: &Host<&str>) -> bool {
    match host {
        Host::Domain(name) => name.eq_ignore_ascii_case("localhost"),
        Host::Ipv4(ip) => ip.is_loopback(),
        Host::Ipv6(ip) => ip.is_loopback(),
    }
}

/// Allow HTTPS release / OAuth pages opened from the dashboard shell.
pub fn validate_external_https_url(url: &str) -> Result<(), String> {
    let trimmed = url.trim();
    if trimmed.is_empty() {
        return Err("url is empty".into());
    }
    if !trimmed.starts_with("https://") {
        return Err("only https URLs are allowed".into());
    }
    let host = trimmed
        .strip_prefix("https://")
        .and_then(|rest| rest.split('/').next())
        .unwrap_or("")
        .split(':')
        .next()
        .unwrap_or("")
        .trim()
        .to_ascii_lowercase();
    let allowed = matches!(
        host.as_str(),
        "github.com" | "www.github.com" | "id.twitch.tv"
    );
    if !allowed {
        return Err(format!("host is not allowed: {host}"));
    }
    Ok(())
}

#[tauri::command]
pub fn open_external_https_url(url: String) -> Result<(), String> {
    validate_external_https_url(&url)?;
    let trimmed = url.trim();
    info!(target: "voicesub.shell", url = %trimmed, "opening external https url");
    open::that(trimmed).map_err(|err| err.to_string())
}

#[tauri::command]
pub fn open_local_http_url(url: String) -> Result<(), String> {
    validate_local_http_url(&url)?;
    let trimmed = url.trim();
    info!(target: "voicesub.shell", url = %trimmed, "opening local http url");
    open::that(trimmed).map_err(|err| err.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allows_github_release_urls() {
        assert!(validate_external_https_url(
            "https://github.com/kiriuru/VoiceSub/releases/tag/v0.5.1"
        )
        .is_ok());
    }

    #[test]
    fn rejects_non_https_and_unknown_hosts() {
        assert!(validate_external_https_url("http://github.com/foo").is_err());
        assert!(validate_external_https_url("https://evil.example/").is_err());
    }

    #[test]
    fn allows_loopback_overlay_urls() {
        assert!(validate_local_http_url("http://127.0.0.1:8765/overlay").is_ok());
        assert!(validate_local_http_url("http://localhost:8765/overlay?foo=1").is_ok());
        assert!(validate_local_http_url("http://[::1]:8765/overlay").is_ok());
    }

    #[test]
    fn rejects_non_loopback_local_http_urls() {
        assert!(validate_local_http_url("https://127.0.0.1:8765/overlay").is_err());
        assert!(validate_local_http_url("http://192.168.1.10:8765/overlay").is_err());
        assert!(validate_local_http_url("http://evil.example/overlay").is_err());
    }
}
