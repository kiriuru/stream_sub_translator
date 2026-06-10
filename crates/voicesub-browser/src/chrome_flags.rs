use serde_json::{json, Value};

/// Chrome feature gates disabled for Web Speech stability (SST Appendix A).
pub const DISABLED_CHROME_FEATURES: &[&str] = &[    "CalculateNativeWinOcclusion",
    "HighEfficiencyModeAvailable",
    "HeuristicMemorySaver",
    "IntensiveWakeUpThrottling",
    "GlobalMediaControls",
];

pub fn disabled_chrome_features_csv() -> String {
    DISABLED_CHROME_FEATURES.join(",")
}

/// Shared Chromium args for classic browser worker launch.
pub const CHROME_ANTI_THROTTLE_FLAGS: &[&str] = &[
    "--new-window",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-default-apps",
    "--disable-session-crashed-bubble",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "--noerrdialogs",
    "--window-size=980,860",
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BrowserChromeLaunchConfig {
    pub launch_args: Vec<String>,
    pub disabled_features: Vec<String>,
    pub extra_args: Vec<String>,
    pub use_high_priority: bool,
}

impl Default for BrowserChromeLaunchConfig {
    fn default() -> Self {
        Self {
            launch_args: default_anti_throttle_args(),
            disabled_features: default_disabled_chrome_features(),
            extra_args: Vec::new(),
            use_high_priority: true,
        }
    }
}

impl BrowserChromeLaunchConfig {
    pub fn disabled_features_csv(&self) -> String {
        self.disabled_features.join(",")
    }

    pub fn launch_args_for_url(&self, profile_dir: &std::path::Path, worker_url: &str) -> Vec<String> {
        let mut args = self.launch_args.clone();
        args.extend(self.extra_args.clone());
        args.push(format!("--user-data-dir={}", profile_dir.display()));
        args.push(format!(
            "--disable-features={}",
            self.disabled_features_csv()
        ));
        args.push(worker_url.to_string());
        args
    }
}

pub fn default_anti_throttle_args() -> Vec<String> {
    CHROME_ANTI_THROTTLE_FLAGS
        .iter()
        .map(|flag| (*flag).to_string())
        .collect()
}

pub fn default_disabled_chrome_features() -> Vec<String> {
    DISABLED_CHROME_FEATURES
        .iter()
        .map(|feature| (*feature).to_string())
        .collect()
}

/// Default `asr.browser.chrome_launch` object for config seeding / normalization.
pub fn default_chrome_launch_value() -> Value {
    json!({
        "launch_args": default_anti_throttle_args(),
        "disabled_features": default_disabled_chrome_features(),
        "extra_args": [],
        "use_high_priority": true
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn disabled_features_match_roadmap_appendix_a() {
        let csv = disabled_chrome_features_csv();
        assert!(csv.contains("CalculateNativeWinOcclusion"));
        assert!(csv.contains("GlobalMediaControls"));
    }
}
