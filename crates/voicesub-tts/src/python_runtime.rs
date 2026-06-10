use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Duration;

use base64::Engine as _;

use serde::Serialize;
use tokio::io::AsyncWriteExt;
use tokio::process::Command;
use tokio::time::sleep;
use tracing::debug;

pub const SCRIPT_NAME: &str = "google_tts_fetch.py";
const TEXT_ENV_B64: &str = "VOICESUB_TTS_TEXT_B64";
pub const EMBEDDED_BINARY_NAME: &str = "google_tts_fetch";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PythonRuntimeKind {
    Embedded,
    /// Dev-only fallback when module runtime is not built yet.
    SystemScript,
}

#[derive(Debug, Clone, Serialize)]
pub struct PythonRuntimeStatus {
    pub available: bool,
    pub kind: String,
    pub command: String,
    pub version: String,
    pub script_found: bool,
    pub embedded_found: bool,
    pub script_path: String,
    pub embedded_path: String,
    pub runtime_dir: String,
    pub build_hint: String,
}

pub fn script_path(tts_module_dir: &Path) -> PathBuf {
    tts_module_dir.join(SCRIPT_NAME)
}

pub fn runtime_platform_dir() -> &'static str {
    if cfg!(windows) {
        "win-x64"
    } else if cfg!(target_os = "macos") {
        if cfg!(target_arch = "aarch64") {
            "macos-arm64"
        } else {
            "macos-x64"
        }
    } else {
        "linux-x64"
    }
}

pub fn normalize_tts_lang(lang: &str) -> String {
    let trimmed = lang.trim().to_lowercase();
    if trimmed.is_empty() {
        return "en".to_string();
    }
    trimmed
        .split('-')
        .next()
        .unwrap_or("en")
        .split('_')
        .next()
        .unwrap_or("en")
        .to_string()
}

pub fn embedded_binary_path(tts_module_dir: &Path) -> PathBuf {
    let file_name = if cfg!(windows) {
        format!("{EMBEDDED_BINARY_NAME}.exe")
    } else {
        EMBEDDED_BINARY_NAME.to_string()
    };
    tts_module_dir
        .join("runtime")
        .join(runtime_platform_dir())
        .join(file_name)
}

fn build_hint(_tts_module_dir: &Path) -> String {
    "Reinstall VoiceSub or restore bin/modules/tts/runtime/{platform}/google_tts_fetch.exe from the release package.".to_string()
}

fn system_python_invocations() -> Vec<Vec<String>> {
    if cfg!(windows) {
        vec![
            vec!["py".into(), "-3".into()],
            vec!["python".into()],
            vec!["python3".into()],
        ]
    } else {
        vec![vec!["python3".into()], vec!["python".into()]]
    }
}

fn allow_system_python_fallback() -> bool {
    std::env::var("VOICESUB_TTS_ALLOW_SYSTEM_PYTHON")
        .map(|value| matches!(value.trim(), "1" | "true" | "yes" | "on"))
        .unwrap_or(cfg!(debug_assertions))
}

async fn run_fetch_command(
    program: &str,
    args: &[String],
    lang: &str,
    text: &str,
) -> Result<Vec<u8>, String> {
    let mut command = Command::new(program);
    for arg in args {
        command.arg(arg);
    }
    let text_b64 = base64::engine::general_purpose::STANDARD.encode(text.as_bytes());
    command
        .arg(lang)
        .env(TEXT_ENV_B64, &text_b64)
        .env("PYTHONUTF8", "1")
        .env("PYTHONIOENCODING", "utf-8")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = command
        .spawn()
        .map_err(|err| format!("{program} {}: {err}", args.join(" ")))?;

    if let Some(mut stdin) = child.stdin.take() {
        stdin
            .write_all(text.as_bytes())
            .await
            .map_err(|err| format!("fetcher stdin write failed: {err}"))?;
    }

    let output = child
        .wait_with_output()
        .await
        .map_err(|err| format!("fetcher wait failed: {err}"))?;

    if output.status.success() && !output.stdout.is_empty() {
        debug!(
            target: "voicesub.tts.python",
            program,
            args = %args.join(" "),
            bytes = output.stdout.len(),
            "embedded python tts fetch ok"
        );
        return Ok(output.stdout);
    }

    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    if stderr.is_empty() {
        Err(format!(
            "{program} {} exited with {} (stdout {} bytes)",
            args.join(" "),
            output.status,
            output.stdout.len()
        ))
    } else {
        Err(format!("{program} {}: {stderr}", args.join(" ")))
    }
}

fn is_retryable_fetch_error(message: &str) -> bool {
    let lower = message.to_ascii_lowercase();
    lower.contains("ssl")
        || lower.contains("unexpected_eof")
        || lower.contains("timed out")
        || lower.contains("timeout")
        || lower.contains("connection reset")
        || lower.contains("connection aborted")
        || lower.contains("temporarily unavailable")
}

async fn run_fetch_with_retries(
    program: &str,
    args: &[String],
    lang: &str,
    text: &str,
) -> Result<Vec<u8>, String> {
    const MAX_ATTEMPTS: usize = 3;
    let mut last_error = String::from("fetch failed");
    for attempt in 1..=MAX_ATTEMPTS {
        match run_fetch_command(program, args, lang, text).await {
            Ok(bytes) => return Ok(bytes),
            Err(err) => {
                last_error = err;
                if attempt >= MAX_ATTEMPTS || !is_retryable_fetch_error(&last_error) {
                    break;
                }
                sleep(Duration::from_millis(300 * attempt as u64)).await;
            }
        }
    }
    Err(last_error)
}

pub async fn run_google_tts_fetch(
    tts_module_dir: &Path,
    lang: &str,
    text: &str,
) -> Result<(Vec<u8>, PythonRuntimeKind), String> {
    let tl = normalize_tts_lang(lang);
    let embedded = embedded_binary_path(tts_module_dir);
    if embedded.is_file() {
        let bytes = run_fetch_with_retries(
            &embedded.display().to_string(),
            &[],
            &tl,
            text,
        )
        .await?;
        return Ok((bytes, PythonRuntimeKind::Embedded));
    }

    if !allow_system_python_fallback() {
        return Err(format!(
            "embedded TTS runtime missing at {}. {}",
            embedded.display(),
            build_hint(tts_module_dir)
        ));
    }

    let script = script_path(tts_module_dir);
    if !script.is_file() {
        return Err(format!(
            "embedded runtime missing and script not found: {}",
            script.display()
        ));
    }

    let mut last_error = String::from("system python not found (dev fallback)");
    for prefix in system_python_invocations() {
        let program = &prefix[0];
        let mut args: Vec<String> = prefix.iter().skip(1).cloned().collect();
        args.push(script.display().to_string());
        match run_fetch_with_retries(program, &args, &tl, text).await {
            Ok(bytes) => return Ok((bytes, PythonRuntimeKind::SystemScript)),
            Err(err) => last_error = err,
        }
    }

    Err(last_error)
}

pub async fn probe_python_runtime(tts_module_dir: &Path) -> PythonRuntimeStatus {
    let script = script_path(tts_module_dir);
    let embedded = embedded_binary_path(tts_module_dir);
    let script_found = script.is_file();
    let embedded_found = embedded.is_file();
    let script_path = script.display().to_string();
    let embedded_path = embedded.display().to_string();
    let runtime_dir = tts_module_dir
        .join("runtime")
        .join(runtime_platform_dir())
        .display()
        .to_string();
    let build_hint = build_hint(tts_module_dir);

    if embedded_found {
        return PythonRuntimeStatus {
            available: true,
            kind: "embedded".to_string(),
            command: embedded_path.clone(),
            version: "nuitka-onefile".to_string(),
            script_found,
            embedded_found,
            script_path,
            embedded_path,
            runtime_dir,
            build_hint,
        };
    }

    if !allow_system_python_fallback() {
        return PythonRuntimeStatus {
            available: false,
            kind: "embedded_missing".to_string(),
            command: String::new(),
            version: String::new(),
            script_found,
            embedded_found,
            script_path,
            embedded_path,
            runtime_dir,
            build_hint,
        };
    }

    if !script_found {
        return PythonRuntimeStatus {
            available: false,
            kind: "missing".to_string(),
            command: String::new(),
            version: String::new(),
            script_found,
            embedded_found,
            script_path,
            embedded_path,
            runtime_dir,
            build_hint,
        };
    }

    for prefix in system_python_invocations() {
        let mut command = Command::new(&prefix[0]);
        for arg in prefix.iter().skip(1) {
            command.arg(arg);
        }
        command
            .arg("--version")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let Ok(output) = command.output().await else {
            continue;
        };
        if !output.status.success() {
            continue;
        }
        let version = String::from_utf8_lossy(&output.stdout)
            .trim()
            .to_string();
        let version = if version.is_empty() {
            String::from_utf8_lossy(&output.stderr).trim().to_string()
        } else {
            version
        };
        return PythonRuntimeStatus {
            available: true,
            kind: "system_dev_fallback".to_string(),
            command: prefix.join(" "),
            version,
            script_found,
            embedded_found,
            script_path,
            embedded_path,
            runtime_dir,
            build_hint,
        };
    }

    PythonRuntimeStatus {
        available: false,
        kind: "system_dev_fallback_missing".to_string(),
        command: String::new(),
        version: String::new(),
        script_found,
        embedded_found,
        script_path,
        embedded_path,
        runtime_dir,
        build_hint,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_path_uses_platform_dir() {
        let tts_module = PathBuf::from(if cfg!(windows) {
            r"C:\project\bin\modules\tts"
        } else {
            "/project/bin/modules/tts"
        });
        let path = embedded_binary_path(&tts_module);
        let parts: Vec<_> = path
            .components()
            .map(|c| c.as_os_str().to_string_lossy().into_owned())
            .collect();
        assert!(parts.windows(3).any(|w| w == ["modules", "tts", "runtime"]));
        assert!(parts.iter().any(|p| p == runtime_platform_dir()));
        #[cfg(windows)]
        assert_eq!(parts.last().map(String::as_str), Some("google_tts_fetch.exe"));
        #[cfg(not(windows))]
        assert_eq!(parts.last().map(String::as_str), Some("google_tts_fetch"));
    }

    #[test]
    fn normalize_lang_strips_region() {
        assert_eq!(normalize_tts_lang("ru-RU"), "ru");
        assert_eq!(normalize_tts_lang("en"), "en");
        assert_eq!(normalize_tts_lang(""), "en");
    }

    #[test]
    fn system_fallback_disabled_in_release_by_default() {
        if cfg!(debug_assertions) {
            assert!(allow_system_python_fallback());
        } else {
            assert!(!allow_system_python_fallback());
        }
    }

    #[test]
    fn retryable_errors_include_ssl_eof() {
        assert!(is_retryable_fetch_error(
            "SSL: UNEXPECTED_EOF_WHILE_READING EOF occurred in violation of protocol"
        ));
        assert!(!is_retryable_fetch_error("empty text"));
    }
}
