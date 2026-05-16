export const DESKTOP_PROFILE_LOCK_BROWSER_SPEECH = "browser_speech";

export function isDesktopBrowserQuickStartLocked(config, desktopContext = null) {
  const lock = String(config?.asr?.desktop_profile_lock || "").toLowerCase();
  if (lock === DESKTOP_PROFILE_LOCK_BROWSER_SPEECH) {
    return true;
  }
  const desktop = desktopContext || (typeof window !== "undefined" ? window.AppState?.desktop : null) || {};
  if (!desktop.desktop_mode) {
    return false;
  }
  if (desktop.web_speech_only) {
    return true;
  }
  return String(desktop.startup_mode || "").toLowerCase() === "browser_google";
}

export function applyDesktopProfileLockToAsrConfig(config) {
  if (!config || typeof config !== "object") {
    return config;
  }
  if (!isDesktopBrowserQuickStartLocked(config)) {
    return config;
  }
  if (!config.asr || typeof config.asr !== "object") {
    config.asr = {};
  }
  if (config.asr.mode !== "browser_google" && config.asr.mode !== "browser_google_experimental") {
    config.asr.mode = "browser_google";
  }
  config.asr.desktop_profile_lock = DESKTOP_PROFILE_LOCK_BROWSER_SPEECH;
  return config;
}

export function syncRecognitionModeSelectLock(modeSelect, locked) {
  if (!modeSelect) {
    return;
  }
  let localOption = modeSelect.querySelector('option[value="local"]');
  if (locked) {
    if (localOption) {
      modeSelect.dataset.sstRemovedLocalOption = localOption.outerHTML;
      localOption.remove();
    }
    return;
  }
  if (!modeSelect.querySelector('option[value="local"]') && modeSelect.dataset.sstRemovedLocalOption) {
    modeSelect.insertAdjacentHTML("afterbegin", modeSelect.dataset.sstRemovedLocalOption);
    delete modeSelect.dataset.sstRemovedLocalOption;
  }
}
