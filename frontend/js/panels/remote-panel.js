import { collectElements } from "../core/dom.js";
import { createPanelMount } from "../core/panel-mount.js";
import { subscribeSelector } from "../core/store.js";
import { selectConfig } from "../core/selectors.js";
import { t } from "../dashboard/helpers.js";

function fillRemoteFieldsFromConfig(elements, config) {
  const remote = config?.remote || {};
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

function renderRemotePanel(snapshot, elements) {
  fillRemoteFieldsFromConfig(elements, snapshot.config);
}

const collectRemoteElements = (root) =>
  collectElements(root, {
    workerUrl: "#remote-worker-url",
    sessionId: "#remote-session-id",
    pairCode: "#remote-pair-code",
    createPairBtn: "#remote-create-pair-btn",
    refreshStateBtn: "#remote-refresh-state-btn",
    workerSyncBtn: "#remote-worker-sync-btn",
    workerHealthBtn: "#remote-worker-health-btn",
    workerStatusBtn: "#remote-worker-status-btn",
    prepareRunBtn: "#remote-prepare-run-btn",
    workerStartBtn: "#remote-worker-start-btn",
    workerStopBtn: "#remote-worker-stop-btn",
    openWorkerBridgeBtn: "#remote-open-worker-bridge-btn",
    openControllerBridgeBtn: "#remote-open-controller-bridge-btn",
    stateText: "#remote-state-text",
    workerText: "#remote-worker-text",
  });

function bindRemoteEvents(elements, { store, actions, api, logger }) {
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
    if (elements.stateText) {
      elements.stateText.textContent = t("remote.tools.state.template", {
        enabled: Boolean(remote.enabled),
        role: remote.effective_role || remote.configured_role || "disabled",
        session: pairing.session_id || remote.session_id || "none",
        active: Boolean(pairing.is_active),
        controller_online: Boolean(pairing.controller_online),
        worker_online: Boolean(pairing.worker_online),
      });
    }
  }

  async function refreshWorkerStatus() {
    await applyRemoteConfig("controller");
    const data = await api.getRemoteWorkerRuntimeStatus();
    const runtime = data?.worker_runtime || {};
    if (elements.workerText) {
      elements.workerText.textContent = t("remote.tools.worker.status_template", {
        running: Boolean(runtime.is_running),
        status: runtime.status || "unknown",
        message: runtime.status_message ? ` message=${runtime.status_message}` : "",
      });
    }
  }

  const handlers = [];
  const add = (element, event, handler) => {
    if (!element) {
      return;
    }
    element.addEventListener(event, handler);
    handlers.push(() => element.removeEventListener(event, handler));
  };

  add(elements.createPairBtn, "click", async () => {
    const data = await api.createRemotePair(43200);
    elements.sessionId.value = data.session_id || "";
    elements.pairCode.value = data.pair_code || "";
    await refreshRemoteState();
    logger("[remote] local pair created");
  });
  add(elements.refreshStateBtn, "click", () => refreshRemoteState());
  add(elements.workerHealthBtn, "click", async () => {
    await applyRemoteConfig("controller");
    const data = await api.getRemoteWorkerHealth();
    if (elements.workerText) {
      elements.workerText.textContent = t("remote.tools.worker.health_template", {
        status: data?.health?.status || "unknown",
        url: data?.worker_url || "n/a",
      });
    }
  });
  add(elements.workerSyncBtn, "click", async () => {
    await applyRemoteConfig("controller");
    const data = await api.syncRemoteWorkerSettings();
    if (elements.workerText) {
      elements.workerText.textContent = t("remote.tools.worker.sync_template", {
        translation: Boolean(data?.worker_translation_enabled),
        targets: (data?.worker_target_languages || []).join(",") || "none",
        asr_mode: data?.worker_asr_mode || "local",
      });
    }
    logger("[remote] worker settings synced from controller");
  });
  add(elements.workerStatusBtn, "click", refreshWorkerStatus);
  add(elements.workerStartBtn, "click", async () => {
    await applyRemoteConfig("controller");
    const data = await api.startRemoteWorkerRuntime();
    if (elements.workerText) {
      elements.workerText.textContent = t("remote.tools.worker.start_template", {
        status: data?.worker_runtime?.status || "unknown",
        running: Boolean(data?.worker_runtime?.is_running),
      });
    }
    logger("[remote] worker runtime start requested");
  });
  add(elements.workerStopBtn, "click", async () => {
    await applyRemoteConfig("controller");
    const data = await api.stopRemoteWorkerRuntime();
    if (elements.workerText) {
      elements.workerText.textContent = t("remote.tools.worker.stop_template", {
        status: data?.worker_runtime?.status || "unknown",
        running: Boolean(data?.worker_runtime?.is_running),
      });
    }
    logger("[remote] worker runtime stop requested");
  });
  add(elements.prepareRunBtn, "click", async () => {
    await applyRemoteConfig("controller");
    await api.syncRemoteWorkerSettings();
    await api.startRemoteWorkerRuntime();
    const url = `/remote/controller-bridge?worker_url=${encodeURIComponent(elements.workerUrl.value)}&session_id=${encodeURIComponent(elements.sessionId.value)}&pair_code=${encodeURIComponent(elements.pairCode.value)}`;
    await window.DesktopBridge?.openExternalUrl?.(url);
    logger("[remote] prepare remote run completed");
  });
  add(elements.openWorkerBridgeBtn, "click", async () => {
    await applyRemoteConfig("worker");
    const url = `/remote/worker-bridge?session_id=${encodeURIComponent(elements.sessionId.value)}&pair_code=${encodeURIComponent(elements.pairCode.value)}`;
    await window.DesktopBridge?.openExternalUrl?.(url);
  });
  add(elements.openControllerBridgeBtn, "click", async () => {
    await applyRemoteConfig("controller");
    const url = `/remote/controller-bridge?worker_url=${encodeURIComponent(elements.workerUrl.value)}&session_id=${encodeURIComponent(elements.sessionId.value)}&pair_code=${encodeURIComponent(elements.pairCode.value)}`;
    await window.DesktopBridge?.openExternalUrl?.(url);
  });

  const unsubscribeConfig = subscribeSelector(selectConfig, (config) => fillRemoteFieldsFromConfig(elements, config));

  refreshRemoteState().catch(() => {
    if (elements.stateText) {
      elements.stateText.textContent = t("remote.tools.state.failed");
    }
  });

  return () => {
    handlers.forEach((off) => off());
    unsubscribeConfig();
  };
}

const mountRemotePanelImpl = createPanelMount({
  collectElements: collectRemoteElements,
  render: renderRemotePanel,
  bindEvents: bindRemoteEvents,
});

export function mountRemotePanel(root, context) {
  return mountRemotePanelImpl(root, context);
}
