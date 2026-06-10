use tracing::info;

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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allows_github_release_urls() {
        assert!(validate_external_https_url(
            "https://github.com/kiriuru/stream_sub_translator/releases/tag/v0.5.1"
        )
        .is_ok());
    }

    #[test]
    fn rejects_non_https_and_unknown_hosts() {
        assert!(validate_external_https_url("http://github.com/foo").is_err());
        assert!(validate_external_https_url("https://evil.example/").is_err());
    }
}
