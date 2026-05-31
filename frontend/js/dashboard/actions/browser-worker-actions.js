import { getCurrentLocale, isExperimentalBrowserRecognitionMode, t } from "../helpers.js";
import { buildPreviewPayload, getResolvedSubtitleStyle } from "../action-helpers.js";

export function createBrowserWorkerActions({ store, logger }) {
  function getPreviewPayload() {
    return buildPreviewPayload(store.getState(), { getResolvedSubtitleStyle });
  }

  function buildBrowserAsrUrl(mode) {
    const params = new URLSearchParams();
    params.set("autostart", "1");
    params.set("locale", getCurrentLocale());
    const path = isExperimentalBrowserRecognitionMode(mode) ? "/google-asr-experimental" : "/google-asr";
    const relativeUrl = `${path}?${params.toString()}`;
    try {
      return new URL(relativeUrl, window.location.href).toString();
    } catch (_error) {
      return relativeUrl;
    }
  }

  async function navigateBrowserAsrWindow() {
    const browserAsrUrl = buildBrowserAsrUrl(store.getState().config?.asr?.mode || "browser_google");
    if (window.DesktopBridge?.isDesktopMode?.()) {
      const opened = await window.DesktopBridge.openExternalUrl(browserAsrUrl);
      if (!opened) {
        logger(t("worker.open_external_failed_log"));
      }
      return;
    }
    const popup = window.open(browserAsrUrl, "browser_asr_worker");
    if (!popup) {
      logger("[browser-asr] popup blocked; allow popups for this local app");
      return;
    }
    popup.focus();
  }

  return {
    getPreviewPayload,
    navigateBrowserAsrWindow,
  };
}
