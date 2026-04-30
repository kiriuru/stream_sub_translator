(function () {
  const workerUrlInput = document.getElementById("remote-worker-url");
  const sessionIdInput = document.getElementById("remote-session-id");
  const pairCodeInput = document.getElementById("remote-pair-code");
  const createPairBtn = document.getElementById("remote-create-pair-btn");
  const refreshStateBtn = document.getElementById("remote-refresh-state-btn");
  const workerSyncBtn = document.getElementById("remote-worker-sync-btn");
  const workerHealthBtn = document.getElementById("remote-worker-health-btn");
  const workerStatusBtn = document.getElementById("remote-worker-status-btn");
  const prepareRunBtn = document.getElementById("remote-prepare-run-btn");
  const workerStartBtn = document.getElementById("remote-worker-start-btn");
  const workerStopBtn = document.getElementById("remote-worker-stop-btn");
  const openWorkerBridgeBtn = document.getElementById("remote-open-worker-bridge-btn");
  const openControllerBridgeBtn = document.getElementById("remote-open-controller-bridge-btn");
  const remoteStateText = document.getElementById("remote-state-text");
  const remoteWorkerText = document.getElementById("remote-worker-text");

  if (!workerUrlInput || !sessionIdInput || !pairCodeInput || !remoteStateText || !remoteWorkerText) {
    return;
  }

  const STORE_KEYS = {
    workerUrl: "sst.remote.worker_url",
    sessionId: "sst.remote.session_id",
    pairCode: "sst.remote.pair_code",
  };
  const AUTO_POLL_INTERVAL_MS = 5000;
  const DEFAULT_PAIR_TTL_SECONDS = 43200;
  const state = {
    pollTimer: null,
    pollInFlight: false,
    lastAppliedConfigKey: "",
    remoteEnabled: false,
    lastKnownSessionId: "",
  };

  function shouldPollRemoteStatus() {
    return state.remoteEnabled || Boolean(state.lastKnownSessionId) || hasRequiredRemotePairingFields();
  }

  function appLog(message) {
    if (typeof window.__appLog === "function") {
      window.__appLog(message);
      return;
    }
    if (window.console && typeof window.console.log === "function") {
      window.console.log(message);
    }
  }

  function setRemoteStateText(message) {
    remoteStateText.textContent = message;
  }

  function setRemoteWorkerText(message) {
    remoteWorkerText.textContent = message;
  }

  function hasRequiredRemotePairingFields() {
    const workerUrl = String(workerUrlInput.value || "").trim();
    const sessionId = String(sessionIdInput.value || "").trim();
    const pairCode = String(pairCodeInput.value || "").trim();
    return Boolean(workerUrl && sessionId && pairCode);
  }

  function buildRemoteConfigKey({ role, sessionId, pairCode, workerUrl }) {
    return [
      String(role || "controller").trim().toLowerCase(),
      String(sessionId || "").trim(),
      String(pairCode || "").trim(),
      String(workerUrl || "").trim(),
    ].join("|");
  }

  function loadPersistedValues() {
    try {
      workerUrlInput.value = localStorage.getItem(STORE_KEYS.workerUrl) || workerUrlInput.value || "";
      sessionIdInput.value = localStorage.getItem(STORE_KEYS.sessionId) || sessionIdInput.value || "";
      pairCodeInput.value = localStorage.getItem(STORE_KEYS.pairCode) || pairCodeInput.value || "";
    } catch (_error) {
      // localStorage may be unavailable in restricted environments
    }
  }

  function persistValues() {
    try {
      localStorage.setItem(STORE_KEYS.workerUrl, String(workerUrlInput.value || "").trim());
      localStorage.setItem(STORE_KEYS.sessionId, String(sessionIdInput.value || "").trim());
      localStorage.setItem(STORE_KEYS.pairCode, String(pairCodeInput.value || "").trim());
    } catch (_error) {
      // ignore persistence failures
    }
  }

  async function openLocalUrl(url) {
    if (window.DesktopBridge && typeof window.DesktopBridge.openExternalUrl === "function") {
      try {
        const opened = await window.DesktopBridge.openExternalUrl(url);
        if (opened) {
          return true;
        }
      } catch (_error) {
        // fallback below
      }
    }
    window.open(url, "_blank", "noopener,noreferrer");
    return true;
  }

  async function refreshRemoteState() {
    if (!window.Api || typeof window.Api.getRemoteState !== "function") {
      setRemoteStateText("Remote state: API unavailable.");
      return;
    }
    try {
      const data = await window.Api.getRemoteState();
      const remote = data?.remote || {};
      const pairing = data?.pairing || {};
      const enabled = Boolean(remote.enabled);
      const role = String(remote.effective_role || remote.configured_role || "disabled");
      const sessionId = String(pairing.session_id || remote.session_id || "").trim();
      const active = Boolean(pairing.is_active);
      const controllerOnline = Boolean(pairing.controller_online);
      const workerOnline = Boolean(pairing.worker_online);
      state.remoteEnabled = enabled;
      state.lastKnownSessionId = enabled ? sessionId : "";
      if (sessionId && !sessionIdInput.value) {
        sessionIdInput.value = sessionId;
      }
      setRemoteStateText(
        `Remote state: enabled=${enabled} role=${role} session=${sessionId || "none"} active=${active} controller_online=${controllerOnline} worker_online=${workerOnline}`
      );
      persistValues();
    } catch (error) {
      setRemoteStateText(`Remote state: failed to load (${error}).`);
    }
  }

  async function createPair() {
    if (!window.Api || typeof window.Api.createRemotePair !== "function") {
      setRemoteStateText("Remote pair: API unavailable.");
      return;
    }
    try {
      const data = await window.Api.createRemotePair(DEFAULT_PAIR_TTL_SECONDS);
      if (!data || !data.ok) {
        setRemoteStateText("Remote pair: create failed.");
        return;
      }
      sessionIdInput.value = String(data.session_id || "").trim();
      pairCodeInput.value = String(data.pair_code || "").trim();
      persistValues();
      await refreshRemoteState();
      appLog("[remote] local pair created");
    } catch (error) {
      setRemoteStateText(`Remote pair: create failed (${error}).`);
    }
  }

  async function checkWorkerHealth(options = {}) {
    const silentErrors = options?.silentErrors === true;
    if (!window.Api || typeof window.Api.getRemoteWorkerHealth !== "function") {
      if (!silentErrors) {
        setRemoteWorkerText("Worker health: API unavailable.");
      }
      return;
    }
    try {
      await applyRemoteConfig({
        role: "controller",
        sessionId: String(sessionIdInput.value || "").trim(),
        pairCode: String(pairCodeInput.value || "").trim(),
        workerUrl: String(workerUrlInput.value || "").trim(),
      }, { quiet: true });
      const data = await window.Api.getRemoteWorkerHealth();
      if (!data || !data.ok) {
        if (!silentErrors) {
          setRemoteWorkerText(`Worker health: failed (${data?.error || "unknown error"}).`);
        }
        return;
      }
      const status = String((data.health || {}).status || "unknown");
      setRemoteWorkerText(`Worker health: status=${status} url=${data.worker_url || "n/a"}`);
    } catch (error) {
      if (!silentErrors) {
        setRemoteWorkerText(`Worker health: failed (${error}).`);
      }
    }
  }

  async function checkWorkerRuntimeStatus(options = {}) {
    const silentErrors = options?.silentErrors === true;
    if (!window.Api || typeof window.Api.getRemoteWorkerRuntimeStatus !== "function") {
      if (!silentErrors) {
        setRemoteWorkerText("Worker runtime: API unavailable.");
      }
      return;
    }
    try {
      await applyRemoteConfig({
        role: "controller",
        sessionId: String(sessionIdInput.value || "").trim(),
        pairCode: String(pairCodeInput.value || "").trim(),
        workerUrl: String(workerUrlInput.value || "").trim(),
      }, { quiet: true });
      const data = await window.Api.getRemoteWorkerRuntimeStatus();
      if (!data || !data.ok) {
        if (!silentErrors) {
          setRemoteWorkerText(`Worker runtime: failed (${data?.error || "unknown error"}).`);
        }
        return;
      }
      const runtime = data.worker_runtime || {};
      const running = Boolean(runtime.is_running);
      const status = String(runtime.status || "unknown");
      const message = String(runtime.status_message || runtime.last_error || "").trim();
      setRemoteWorkerText(
        `Worker runtime: running=${running} status=${status}${message ? ` message=${message}` : ""}`
      );
    } catch (error) {
      if (!silentErrors) {
        setRemoteWorkerText(`Worker runtime: failed (${error}).`);
      }
    }
  }

  async function syncWorkerSettings(options = {}) {
    const silentErrors = options?.silentErrors === true;
    const quiet = options?.quiet === true;
    if (!window.Api || typeof window.Api.syncRemoteWorkerSettings !== "function") {
      if (!silentErrors) {
        setRemoteWorkerText("Worker settings sync: API unavailable.");
      }
      return false;
    }
    try {
      await applyRemoteConfig({
        role: "controller",
        sessionId: String(sessionIdInput.value || "").trim(),
        pairCode: String(pairCodeInput.value || "").trim(),
        workerUrl: String(workerUrlInput.value || "").trim(),
      }, { quiet: true, force: options?.forceConfigApply === true });
      const data = await window.Api.syncRemoteWorkerSettings();
      if (!data || !data.ok) {
        if (!silentErrors) {
          setRemoteWorkerText(`Worker settings sync failed (${data?.error || "unknown error"}).`);
        }
        return false;
      }
      const translationEnabled = Boolean(data.worker_translation_enabled);
      const targets = Array.isArray(data.worker_target_languages)
        ? data.worker_target_languages.filter((item) => String(item || "").trim())
        : [];
      const asrMode = String(data.worker_asr_mode || "local");
      const targetsLabel = targets.length ? targets.join(",") : "none";
      setRemoteWorkerText(
        `Worker settings synced: translation=${translationEnabled} targets=${targetsLabel} asr_mode=${asrMode}`
      );
      if (!quiet) {
        appLog("[remote] worker settings synced from controller");
      }
      return true;
    } catch (error) {
      if (!silentErrors) {
        setRemoteWorkerText(`Worker settings sync failed (${error}).`);
      }
      return false;
    }
  }

  async function startWorkerRuntime(options = {}) {
    const skipSync = options?.skipSync === true;
    if (!window.Api || typeof window.Api.startRemoteWorkerRuntime !== "function") {
      setRemoteWorkerText("Worker start: API unavailable.");
      return false;
    }
    try {
      if (!skipSync) {
        const synced = await syncWorkerSettings({ quiet: true, silentErrors: false, forceConfigApply: true });
        if (!synced) {
          return false;
        }
      }
      await applyRemoteConfig({
        role: "controller",
        sessionId: String(sessionIdInput.value || "").trim(),
        pairCode: String(pairCodeInput.value || "").trim(),
        workerUrl: String(workerUrlInput.value || "").trim(),
      }, { force: true });
      const data = await window.Api.startRemoteWorkerRuntime();
      if (!data || !data.ok) {
        setRemoteWorkerText(`Worker start failed (${data?.error || "unknown error"}).`);
        return;
      }
      const runtime = data.worker_runtime || {};
      setRemoteWorkerText(`Worker start: status=${runtime.status || "unknown"} running=${Boolean(runtime.is_running)}`);
      appLog("[remote] worker runtime start requested");
      return true;
    } catch (error) {
      setRemoteWorkerText(`Worker start failed (${error}).`);
      return false;
    }
  }

  async function stopWorkerRuntime() {
    if (!window.Api || typeof window.Api.stopRemoteWorkerRuntime !== "function") {
      setRemoteWorkerText("Worker stop: API unavailable.");
      return false;
    }
    try {
      await applyRemoteConfig({
        role: "controller",
        sessionId: String(sessionIdInput.value || "").trim(),
        pairCode: String(pairCodeInput.value || "").trim(),
        workerUrl: String(workerUrlInput.value || "").trim(),
      }, { force: true });
      const data = await window.Api.stopRemoteWorkerRuntime();
      if (!data || !data.ok) {
        setRemoteWorkerText(`Worker stop failed (${data?.error || "unknown error"}).`);
        return;
      }
      const runtime = data.worker_runtime || {};
      setRemoteWorkerText(`Worker stop: status=${runtime.status || "unknown"} running=${Boolean(runtime.is_running)}`);
      appLog("[remote] worker runtime stop requested");
      return true;
    } catch (error) {
      setRemoteWorkerText(`Worker stop failed (${error}).`);
      return false;
    }
  }

  async function prepareRemoteRun() {
    if (!hasRequiredRemotePairingFields()) {
      setRemoteStateText("Prepare remote run: worker URL, session id, and pair code are required.");
      return false;
    }

    setRemoteStateText("Preparing remote run...");
    const synced = await syncWorkerSettings({ quiet: true, silentErrors: false, forceConfigApply: true });
    if (!synced) {
      setRemoteStateText("Prepare remote run failed: worker settings sync did not complete.");
      return false;
    }

    const started = await startWorkerRuntime({ skipSync: true });
    if (!started) {
      setRemoteStateText("Prepare remote run failed: worker runtime start was not successful.");
      return false;
    }

    await openControllerBridge();
    await checkWorkerRuntimeStatus({ silentErrors: true });
    setRemoteStateText("Remote run prepared. Keep worker bridge open on the remote machine, then click Start Stream in controller bridge.");
    appLog("[remote] prepare remote run completed");
    return true;
  }

  async function openWorkerBridge() {
    const sessionId = String(sessionIdInput.value || "").trim();
    const pairCode = String(pairCodeInput.value || "").trim();
    if (!sessionId || !pairCode) {
      setRemoteStateText("Open worker bridge: session id and pair code are required.");
      return;
    }
    await applyRemoteConfig({
      role: "worker",
      sessionId,
      pairCode,
      workerUrl: String(workerUrlInput.value || "").trim(),
    });
    const url = `/remote/worker-bridge?session_id=${encodeURIComponent(sessionId)}&pair_code=${encodeURIComponent(pairCode)}`;
    await openLocalUrl(url);
  }

  async function openControllerBridge() {
    const workerUrl = String(workerUrlInput.value || "").trim();
    const sessionId = String(sessionIdInput.value || "").trim();
    const pairCode = String(pairCodeInput.value || "").trim();
    if (!workerUrl || !sessionId || !pairCode) {
      setRemoteStateText("Open controller bridge: worker URL, session id, and pair code are required.");
      return;
    }
    await applyRemoteConfig({
      role: "controller",
      sessionId,
      pairCode,
      workerUrl,
    });
    const url = `/remote/controller-bridge?worker_url=${encodeURIComponent(workerUrl)}&session_id=${encodeURIComponent(
      sessionId
    )}&pair_code=${encodeURIComponent(pairCode)}`;
    await openLocalUrl(url);
  }

  async function applyRemoteConfig({ role, sessionId, pairCode, workerUrl }, options = {}) {
    const force = options?.force === true;
    const quiet = options?.quiet === true;
    if (!window.Api || typeof window.Api.loadSettings !== "function" || typeof window.Api.saveSettings !== "function") {
      return;
    }
    const configKey = buildRemoteConfigKey({ role, sessionId, pairCode, workerUrl });
    if (!force && configKey === state.lastAppliedConfigKey) {
      return;
    }
    try {
      const current = await window.Api.loadSettings();
      const payload = current?.payload && typeof current.payload === "object" ? current.payload : {};
      const remote = payload.remote && typeof payload.remote === "object" ? payload.remote : {};
      const controller = remote.controller && typeof remote.controller === "object" ? remote.controller : {};
      payload.remote = {
        ...remote,
        enabled: true,
        role: String(role || "controller"),
        session_id: String(sessionId || "").trim(),
        pair_code: String(pairCode || "").trim(),
        controller: {
          ...controller,
          worker_url: String(workerUrl || "").trim(),
        },
      };
      await window.Api.saveSettings(payload);
      state.lastAppliedConfigKey = configKey;
      if (!quiet) {
        appLog(`[remote] config applied for role=${role}`);
      }
    } catch (error) {
      if (!quiet) {
        appLog(`[remote] failed to apply config: ${error}`);
      }
    }
  }

  async function pollRemoteStatus() {
    if (document.hidden || state.pollInFlight || !shouldPollRemoteStatus()) {
      return;
    }
    state.pollInFlight = true;
    try {
      await refreshRemoteState();
      await checkWorkerRuntimeStatus({ silentErrors: true });
    } finally {
      state.pollInFlight = false;
    }
  }

  function startAutoPoll() {
    if (!shouldPollRemoteStatus()) {
      stopAutoPoll();
      return;
    }
    if (state.pollTimer !== null) {
      window.clearInterval(state.pollTimer);
    }
    state.pollTimer = window.setInterval(() => {
      pollRemoteStatus().catch(() => {
        // keep polling best-effort
      });
    }, AUTO_POLL_INTERVAL_MS);
  }

  function stopAutoPoll() {
    if (state.pollTimer !== null) {
      window.clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  [workerUrlInput, sessionIdInput, pairCodeInput].forEach((element) => {
    element.addEventListener("input", () => {
      persistValues();
      if (shouldPollRemoteStatus()) {
        startAutoPoll();
      } else {
        stopAutoPoll();
      }
    });
  });
  createPairBtn?.addEventListener("click", () => {
    createPair().catch((error) => {
      setRemoteStateText(`Remote pair: create failed (${error}).`);
    });
  });
  refreshStateBtn?.addEventListener("click", () => {
    refreshRemoteState().catch(() => {
      setRemoteStateText("Remote state: refresh failed.");
    });
  });
  workerHealthBtn?.addEventListener("click", () => {
    checkWorkerHealth().catch((error) => {
      setRemoteWorkerText(`Worker health failed (${error}).`);
    });
  });
  workerSyncBtn?.addEventListener("click", () => {
    syncWorkerSettings({ quiet: false, silentErrors: false, forceConfigApply: true }).catch((error) => {
      setRemoteWorkerText(`Worker settings sync failed (${error}).`);
    });
  });
  workerStatusBtn?.addEventListener("click", () => {
    checkWorkerRuntimeStatus().catch((error) => {
      setRemoteWorkerText(`Worker runtime status failed (${error}).`);
    });
  });
  prepareRunBtn?.addEventListener("click", () => {
    prepareRemoteRun().catch((error) => {
      setRemoteStateText(`Prepare remote run failed (${error}).`);
    });
  });
  workerStartBtn?.addEventListener("click", () => {
    startWorkerRuntime().catch((error) => {
      setRemoteWorkerText(`Worker start failed (${error}).`);
    });
  });
  workerStopBtn?.addEventListener("click", () => {
    stopWorkerRuntime().catch((error) => {
      setRemoteWorkerText(`Worker stop failed (${error}).`);
    });
  });
  openWorkerBridgeBtn?.addEventListener("click", () => {
    openWorkerBridge().catch((error) => {
      setRemoteStateText(`Open worker bridge failed (${error}).`);
    });
  });
  openControllerBridgeBtn?.addEventListener("click", () => {
    openControllerBridge().catch((error) => {
      setRemoteStateText(`Open controller bridge failed (${error}).`);
    });
  });

  loadPersistedValues();
  setRemoteWorkerText("Worker runtime: not loaded.");
  refreshRemoteState()
    .then(() => {
      startAutoPoll();
    })
    .catch(() => {
      setRemoteStateText("Remote state: initial load failed.");
      stopAutoPoll();
    });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      pollRemoteStatus().catch(() => {
        // keep UI stable on wake-up refresh failures
      });
    }
  });
  window.addEventListener("beforeunload", stopAutoPoll);
})();
