(function () {
  function traceDesktop(event, fields) {
    if (typeof window.SstDesktopUiTrace === "function") {
      window.SstDesktopUiTrace(event, fields);
    }
  }

  const URL_PARAMS = new URLSearchParams(window.location.search);
  const FORCED_DESKTOP_MODE = URL_PARAMS.get("desktop") === "1";
  const PYWEBVIEW_GUI = "edgechromium";
  const DEFAULT_CONTEXT = {
    desktop_mode: FORCED_DESKTOP_MODE,
    base_url: location.origin,
    dashboard_url: `${location.origin}/`,
    overlay_url: `${location.origin}/overlay`,
    browser_worker_url: `${location.origin}/google-asr`,
    worker_launch_browser: "auto",
    startup_mode: "local",
    web_speech_only: false,
    install_profile: "auto",
    remote_role: "disabled",
  };

  let cachedContext = { ...DEFAULT_CONTEXT };
  let contextPromise = null;
  let contextRefreshScheduled = false;

  function dispatchContext(context) {
    document.dispatchEvent(new CustomEvent("sst:desktop-context", { detail: context }));
  }

  function hasPywebviewApi() {
    return Boolean(window.pywebview?.api);
  }

  function waitForPywebviewApi(timeoutMs = 4000) {
    if (hasPywebviewApi()) {
      traceDesktop("pywebview_api_ready", { immediate: true, timeout_ms: timeoutMs });
      return Promise.resolve(true);
    }
    if (!FORCED_DESKTOP_MODE) {
      return Promise.resolve(false);
    }
    traceDesktop("pywebview_api_wait_begin", { timeout_ms: timeoutMs, forced_desktop: FORCED_DESKTOP_MODE });
    return new Promise((resolve) => {
      let settled = false;
      const finish = (value) => {
        if (settled) {
          return;
        }
        settled = true;
        document.removeEventListener("pywebviewready", onReady);
        clearTimeout(timer);
        traceDesktop(value ? "pywebview_api_ready" : "pywebview_api_timeout", {
          timeout_ms: timeoutMs,
          has_api: hasPywebviewApi(),
        });
        resolve(value);
      };
      const onReady = () => finish(hasPywebviewApi());
      const timer = setTimeout(() => finish(false), timeoutMs);
      document.addEventListener("pywebviewready", onReady);
    });
  }

  function immediateDesktopContext() {
    return { ...DEFAULT_CONTEXT, desktop_mode: FORCED_DESKTOP_MODE || cachedContext.desktop_mode };
  }

  function scheduleContextRefresh() {
    if (contextRefreshScheduled || hasPywebviewApi()) {
      return;
    }
    contextRefreshScheduled = true;
    void waitForPywebviewApi().then((ready) => {
      contextRefreshScheduled = false;
      if (!ready || !hasPywebviewApi()) {
        return;
      }
      contextPromise = null;
      void getContext();
    });
  }

  async function getContext() {
    if (!hasPywebviewApi()) {
      if (FORCED_DESKTOP_MODE) {
        scheduleContextRefresh();
      }
      return immediateDesktopContext();
    }
    if (contextPromise) {
      return contextPromise;
    }
    contextPromise = window.pywebview.api
      .get_launch_context()
      .then((payload) => {
        cachedContext = { ...DEFAULT_CONTEXT, ...(payload || {}), desktop_mode: true };
        traceDesktop("launch_context_loaded", {
          gui: payload?.pywebview_gui || PYWEBVIEW_GUI,
          storage_path: payload?.pywebview_storage_path || null,
          startup_mode: cachedContext.startup_mode,
          install_profile: cachedContext.install_profile,
        });
        dispatchContext(cachedContext);
        return cachedContext;
      })
      .catch((error) => {
        traceDesktop("launch_context_failed", {
          error: error instanceof Error ? error.message : String(error || ""),
        });
        return cachedContext;
      });
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
    /** True only when the Python launcher can open a specific browser exe for `/google-asr` or `/google-asr-edge` (not plain `start.bat` in a normal browser). */
    controlsWorkerBrowserLaunch() {
      return Boolean(hasPywebviewApi() && typeof window.pywebview.api.open_external_url === "function");
    },
    async openExternalUrl(url) {
      return openExternalUrl(url);
    },
    async requestRuntimeStart(deviceId, configPayload) {
      if (!hasPywebviewApi() || typeof window.pywebview.api.request_runtime_start !== "function") {
        return { ok: false, error: "native start unavailable" };
      }
      try {
        return await window.pywebview.api.request_runtime_start(deviceId ?? null, configPayload ?? null);
      } catch (error) {
        return { ok: false, error: error instanceof Error ? error.message : String(error) };
      }
    },
    async requestRuntimeStop() {
      if (!hasPywebviewApi() || typeof window.pywebview.api.request_runtime_stop !== "function") {
        return { ok: false, error: "native stop unavailable" };
      }
      try {
        return await window.pywebview.api.request_runtime_stop();
      } catch (error) {
        return { ok: false, error: error instanceof Error ? error.message : String(error) };
      }
    },
  };

  document.addEventListener("pywebviewready", () => {
    traceDesktop("pywebviewready", {
      gui: PYWEBVIEW_GUI,
      has_api: hasPywebviewApi(),
      href: String(location.href || ""),
    });
    void getContext();
  });

  traceDesktop("desktop_bridge_init", {
    forced_desktop: FORCED_DESKTOP_MODE,
    gui: PYWEBVIEW_GUI,
    has_api: hasPywebviewApi(),
    href: String(location.href || ""),
  });

  if (!hasPywebviewApi()) {
    dispatchContext(cachedContext);
    if (FORCED_DESKTOP_MODE) {
      scheduleContextRefresh();
    }
  }
})();
