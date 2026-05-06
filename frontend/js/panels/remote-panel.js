import { subscribe } from "../core/store.js";

export function mountRemotePanel(root, { store, actions, api, logger }) {
  const elements = {
    workerUrl: root.querySelector("#remote-worker-url"),
    sessionId: root.querySelector("#remote-session-id"),
    pairCode: root.querySelector("#remote-pair-code"),
    createPairBtn: root.querySelector("#remote-create-pair-btn"),
    refreshStateBtn: root.querySelector("#remote-refresh-state-btn"),
    workerSyncBtn: root.querySelector("#remote-worker-sync-btn"),
    workerHealthBtn: root.querySelector("#remote-worker-health-btn"),
    workerStatusBtn: root.querySelector("#remote-worker-status-btn"),
    prepareRunBtn: root.querySelector("#remote-prepare-run-btn"),
    workerStartBtn: root.querySelector("#remote-worker-start-btn"),
    workerStopBtn: root.querySelector("#remote-worker-stop-btn"),
    openWorkerBridgeBtn: root.querySelector("#remote-open-worker-bridge-btn"),
    openControllerBridgeBtn: root.querySelector("#remote-open-controller-bridge-btn"),
    stateText: root.querySelector("#remote-state-text"),
    workerText: root.querySelector("#remote-worker-text"),
  };

  function fillFromConfig(snapshot) {
    const remote = snapshot.config?.remote || {};
    if (elements.workerUrl && !elements.workerUrl.value) {
      elements.workerUrl.value = remote.controller?.worker_url || "";
    }
    if (elements.sessionId && !elements.sessionId.value) {
      elements.sessionId.value = remote.session_id || "";
    }
    if (elements.pairCode && !elements.pairCode.value) {
      elements.pairCode.value = remote.pair_code || "";
    }
  }

  async function applyRemoteConfig(role = "controller") {
    actions.mutateConfig((draft) => {
      draft.remote.enabled = true;
      draft.remote.role = role;
      draft.remote.session_id = String(elements.sessionId?.value || "").trim();
      draft.remote.pair_code = String(elements.pairCode?.value || "").trim();
      draft.remote.controller.worker_url = String(elements.workerUrl?.value || "").trim();
    });
    await actions.saveCurrentConfig();
  }

  async function refreshRemoteState() {
    const data = await api.getRemoteState();
    const remote = data?.remote || {};
    const pairing = data?.pairing || {};
    elements.stateText.textContent =
      `Remote state: enabled=${Boolean(remote.enabled)} role=${remote.effective_role || remote.configured_role || "disabled"} session=${pairing.session_id || remote.session_id || "none"} active=${Boolean(pairing.is_active)} controller_online=${Boolean(pairing.controller_online)} worker_online=${Boolean(pairing.worker_online)}`;
  }

  async function refreshWorkerStatus() {
    await applyRemoteConfig("controller");
    const data = await api.getRemoteWorkerRuntimeStatus();
    const runtime = data?.worker_runtime || {};
    elements.workerText.textContent = `Worker runtime: running=${Boolean(runtime.is_running)} status=${runtime.status || "unknown"}${runtime.status_message ? ` message=${runtime.status_message}` : ""}`;
  }

  elements.createPairBtn?.addEventListener("click", async () => {
    const data = await api.createRemotePair(43200);
    elements.sessionId.value = data.session_id || "";
    elements.pairCode.value = data.pair_code || "";
    await refreshRemoteState();
    logger("[remote] local pair created");
  });
  elements.refreshStateBtn?.addEventListener("click", refreshRemoteState);
  elements.workerHealthBtn?.addEventListener("click", async () => {
    await applyRemoteConfig("controller");
    const data = await api.getRemoteWorkerHealth();
    elements.workerText.textContent = `Worker health: status=${data?.health?.status || "unknown"} url=${data?.worker_url || "n/a"}`;
  });
  elements.workerSyncBtn?.addEventListener("click", async () => {
    await applyRemoteConfig("controller");
    const data = await api.syncRemoteWorkerSettings();
    elements.workerText.textContent = `Worker settings synced: translation=${Boolean(data?.worker_translation_enabled)} targets=${(data?.worker_target_languages || []).join(",") || "none"} asr_mode=${data?.worker_asr_mode || "local"}`;
    logger("[remote] worker settings synced from controller");
  });
  elements.workerStatusBtn?.addEventListener("click", refreshWorkerStatus);
  elements.workerStartBtn?.addEventListener("click", async () => {
    await applyRemoteConfig("controller");
    const data = await api.startRemoteWorkerRuntime();
    elements.workerText.textContent = `Worker start: status=${data?.worker_runtime?.status || "unknown"} running=${Boolean(data?.worker_runtime?.is_running)}`;
    logger("[remote] worker runtime start requested");
  });
  elements.workerStopBtn?.addEventListener("click", async () => {
    await applyRemoteConfig("controller");
    const data = await api.stopRemoteWorkerRuntime();
    elements.workerText.textContent = `Worker stop: status=${data?.worker_runtime?.status || "unknown"} running=${Boolean(data?.worker_runtime?.is_running)}`;
    logger("[remote] worker runtime stop requested");
  });
  elements.prepareRunBtn?.addEventListener("click", async () => {
    await applyRemoteConfig("controller");
    await api.syncRemoteWorkerSettings();
    await api.startRemoteWorkerRuntime();
    const url = `/remote/controller-bridge?worker_url=${encodeURIComponent(elements.workerUrl.value)}&session_id=${encodeURIComponent(elements.sessionId.value)}&pair_code=${encodeURIComponent(elements.pairCode.value)}`;
    await window.DesktopBridge?.openExternalUrl?.(url);
    logger("[remote] prepare remote run completed");
  });
  elements.openWorkerBridgeBtn?.addEventListener("click", async () => {
    await applyRemoteConfig("worker");
    const url = `/remote/worker-bridge?session_id=${encodeURIComponent(elements.sessionId.value)}&pair_code=${encodeURIComponent(elements.pairCode.value)}`;
    await window.DesktopBridge?.openExternalUrl?.(url);
  });
  elements.openControllerBridgeBtn?.addEventListener("click", async () => {
    await applyRemoteConfig("controller");
    const url = `/remote/controller-bridge?worker_url=${encodeURIComponent(elements.workerUrl.value)}&session_id=${encodeURIComponent(elements.sessionId.value)}&pair_code=${encodeURIComponent(elements.pairCode.value)}`;
    await window.DesktopBridge?.openExternalUrl?.(url);
  });

  fillFromConfig(store.getState());
  const unsubscribe = subscribe((snapshot) => fillFromConfig(snapshot));
  refreshRemoteState().catch(() => {
    if (elements.stateText) {
      elements.stateText.textContent = "Remote state: initial load failed.";
    }
  });
  return () => unsubscribe();
}
