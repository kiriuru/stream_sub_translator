use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use thiserror::Error;
use tracing::{info, instrument, warn};

use crate::chrome_flags::BrowserChromeLaunchConfig;
use crate::ecoqos::opt_out_chrome_power_throttling;

#[derive(Debug, Error)]
pub enum BrowserLaunchError {
    #[error("chrome executable not found")]
    ChromeNotFound,
    #[error("failed to create profile directory: {0}")]
    ProfileDir(std::io::Error),
    #[error("failed to spawn chrome: {0}")]
    Spawn(std::io::Error),
}

#[derive(Debug, Clone)]
pub struct LaunchResult {
    pub chrome_path: PathBuf,
    pub profile_dir: PathBuf,
    pub pid: u32,
    pub args: Vec<String>,
}

pub struct BrowserWorkerLauncher {
    runtime_root: PathBuf,
}

impl BrowserWorkerLauncher {
    pub fn new(runtime_root: impl Into<PathBuf>) -> Self {
        Self {
            runtime_root: runtime_root.into(),
        }
    }

    pub fn profile_dir(&self, _worker_url: &str, chrome_path: &Path) -> PathBuf {
        let variant = "classic";
        let engine = chrome_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("chromium")
            .to_ascii_lowercase();
        let safe_engine: String = engine
            .chars()
            .filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
            .collect();
        let safe_engine = if safe_engine.is_empty() {
            "chromium".to_string()
        } else {
            safe_engine
        };
        self.runtime_root
            .join(format!("browser-worker-profile-{variant}-{safe_engine}"))
    }

    #[instrument(skip(self, chrome_launch))]
    pub fn launch_worker(
        &self,
        worker_url: &str,
        chrome_launch: &BrowserChromeLaunchConfig,
    ) -> Result<LaunchResult, BrowserLaunchError> {
        let chrome_path = find_chrome_executable().ok_or(BrowserLaunchError::ChromeNotFound)?;
        let profile_dir = self.profile_dir(worker_url, &chrome_path);
        std::fs::create_dir_all(&profile_dir).map_err(BrowserLaunchError::ProfileDir)?;

        let chrome_args = chrome_launch.launch_args_for_url(&profile_dir, worker_url);
        let mut args = vec![chrome_path.display().to_string()];
        args.extend(chrome_args.clone());

        let child = spawn_chrome_process(&chrome_path, &chrome_args, chrome_launch.use_high_priority)?;
        let pid = child.id();

        opt_out_chrome_power_throttling(pid);

        info!(
            chrome = %chrome_path.display(),
            profile = %profile_dir.display(),
            pid,
            high_priority = chrome_launch.use_high_priority,
            "browser worker launched"
        );

        Ok(LaunchResult {
            chrome_path,
            profile_dir,
            pid,
            args,
        })
    }

    /// Best-effort terminate a launched browser worker process tree.
    pub fn terminate_worker(pid: u32) -> bool {
        if pid == 0 {
            return false;
        }
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            std::process::Command::new("taskkill")
                .args(["/PID", &pid.to_string(), "/T", "/F"])
                .creation_flags(CREATE_NO_WINDOW)
                .status()
                .map(|status| status.success())
                .unwrap_or(false)
        }
        #[cfg(not(windows))]
        {
            let _ = pid;
            false
        }
    }
}

fn is_access_denied(err: &std::io::Error) -> bool {
    err.raw_os_error() == Some(5)
}

fn spawn_chrome_process(
    chrome_path: &Path,
    chrome_args: &[String],
    use_high_priority: bool,
) -> Result<std::process::Child, BrowserLaunchError> {
    match try_spawn_chrome(chrome_path, chrome_args, use_high_priority) {
        Ok(child) => Ok(child),
        Err(err) if use_high_priority && matches!(&err, BrowserLaunchError::Spawn(io) if is_access_denied(io)) => {
            warn!(
                "chrome launch: HIGH_PRIORITY_CLASS denied (ERROR_ACCESS_DENIED); retrying without priority boost"
            );
            try_spawn_chrome(chrome_path, chrome_args, false)
        }
        Err(err) => Err(err),
    }
}

fn try_spawn_chrome(
    chrome_path: &Path,
    chrome_args: &[String],
    use_high_priority: bool,
) -> Result<std::process::Child, BrowserLaunchError> {
    let mut command = Command::new(chrome_path);
    command
        .args(chrome_args)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NEW_PROCESS_GROUP: u32 = 0x00000200;
        const DETACHED_PROCESS: u32 = 0x00000008;
        const HIGH_PRIORITY_CLASS: u32 = 0x00000080;
        let mut flags = CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS;
        if use_high_priority {
            flags |= HIGH_PRIORITY_CLASS;
        }
        command.creation_flags(flags);
    }

    command.spawn().map_err(BrowserLaunchError::Spawn)
}

fn find_chrome_executable() -> Option<PathBuf> {
    if let Some(path) = find_chrome_from_registry() {
        return Some(path);
    }
    if let Some(path) = which_chrome("chrome.exe") {
        return Some(path);
    }
    probe_common_install_paths()
}

#[cfg(windows)]
fn find_chrome_from_registry() -> Option<PathBuf> {
    use winreg::enums::{HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, KEY_READ};
    use winreg::RegKey;

    const SUBKEY: &str = r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe";
    for hive in [HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE] {
        let root = RegKey::predef(hive);
        if let Ok(key) = root.open_subkey_with_flags(SUBKEY, KEY_READ) {
            if let Ok(value) = key.get_value::<String, _>("") {
                let candidate = PathBuf::from(value.trim().trim_matches('"'));
                if is_supported_chrome(&candidate) {
                    return Some(candidate);
                }
            }
        }
    }
    None
}

#[cfg(not(windows))]
fn find_chrome_from_registry() -> Option<PathBuf> {
    None
}

fn which_chrome(name: &str) -> Option<PathBuf> {
    std::env::var_os("PATH").and_then(|paths| {
        std::env::split_paths(&paths).find_map(|dir| {
            let candidate = dir.join(name);
            if is_supported_chrome(&candidate) {
                Some(candidate)
            } else {
                None
            }
        })
    })
}

fn probe_common_install_paths() -> Option<PathBuf> {
    let roots = [
        std::env::var_os("LOCALAPPDATA"),
        std::env::var_os("ProgramFiles"),
        std::env::var_os("ProgramFiles(x86)"),
    ];
    let relatives = [
        ["Google", "Chrome", "Application", "chrome.exe"],
        ["Google", "Chrome", "Application", "chrome.exe"],
    ];
    for root in roots.into_iter().flatten() {
        for parts in &relatives {
            let mut candidate = PathBuf::from(&root);
            for part in *parts {
                candidate.push(part);
            }
            if is_supported_chrome(&candidate) {
                return Some(candidate);
            }
        }
    }
    None
}

fn is_supported_chrome(path: &Path) -> bool {
    if !path.is_file() {
        return false;
    }
    let lower = path.to_string_lossy().to_ascii_lowercase();
    if lower.contains("windowsapps") {
        return false;
    }
    path.file_name()
        .and_then(|n| n.to_str())
        .map(|n| n.eq_ignore_ascii_case("chrome.exe"))
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::chrome_flags::BrowserChromeLaunchConfig;

    #[test]
    fn profile_dir_uses_classic_variant() {
        let launcher = BrowserWorkerLauncher::new("user-data");
        let chrome = Path::new("C:/Program Files/Google/Chrome/Application/chrome.exe");
        let dir = launcher.profile_dir("http://127.0.0.1:8765/google-asr", chrome);
        assert!(dir.to_string_lossy().contains("classic"));
    }

    #[test]
    fn launch_args_include_configured_flags() {
        let config = BrowserChromeLaunchConfig::default();
        assert!(config
            .launch_args
            .contains(&"--disable-background-timer-throttling".to_string()));
    }

    #[test]
    fn access_denied_detection_matches_win32_code_5() {
        let err = std::io::Error::from_raw_os_error(5);
        assert!(is_access_denied(&err));
    }
}
