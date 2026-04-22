(function () {
  const URL_PARAMS = new URLSearchParams(window.location.search);
  const FORCED_DESKTOP_MODE = URL_PARAMS.get("desktop") === "1";
  const DEFAULT_CONTEXT = {
    desktop_mode: FORCED_DESKTOP_MODE,
    base_url: location.origin,
    dashboard_url: `${location.origin}/`,
    overlay_url: `${location.origin}/overlay`,
    browser_worker_url: `${location.origin}/google-asr`,
    startup_mode: "local",
    install_profile: "auto",
  };

  let cachedContext = { ...DEFAULT_CONTEXT };
  let contextPromise = null;

  function dispatchContext(context) {
    document.dispatchEvent(new CustomEvent("sst:desktop-context", { detail: context }));
  }

  function hasPywebviewApi() {
    return Boolean(window.pywebview?.api);
  }

  async function getContext() {
    if (!hasPywebviewApi()) {
      return cachedContext;
    }
    if (contextPromise) {
      return contextPromise;
    }
    contextPromise = window.pywebview.api
      .get_launch_context()
      .then((payload) => {
        cachedContext = { ...DEFAULT_CONTEXT, ...(payload || {}), desktop_mode: true };
        if (window.AppState) {
          window.AppState.desktop = cachedContext;
        }
        dispatchContext(cachedContext);
        return cachedContext;
      })
      .catch(() => cachedContext);
    return contextPromise;
  }

  async function openExternalUrl(url) {
    const target = String(url || "").trim();
    if (!target) {
      return false;
    }
    if (hasPywebviewApi() && typeof window.pywebview.api.open_external_url === "function") {
      try {
        return Boolean(await window.pywebview.api.open_external_url(target));
      } catch (_error) {
        return false;
      }
    }
    if (FORCED_DESKTOP_MODE || cachedContext.desktop_mode) {
      return false;
    }
    const popup = window.open(target, "_blank", "noopener,noreferrer");
    return Boolean(popup);
  }

  window.DesktopBridge = {
    async getContext() {
      return getContext();
    },
    isDesktopMode() {
      return Boolean(cachedContext.desktop_mode || hasPywebviewApi() || FORCED_DESKTOP_MODE);
    },
    async openExternalUrl(url) {
      return openExternalUrl(url);
    },
  };

  document.addEventListener("pywebviewready", () => {
    void getContext();
  });

  if (!hasPywebviewApi()) {
    dispatchContext(cachedContext);
  }
})();
