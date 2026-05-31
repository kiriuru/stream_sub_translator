import { createEventBus, DASHBOARD_EVENTS } from "./core/events.js";
import { createApiClient, createDashboardApi } from "./core/api-client.js";
import * as store from "./core/store.js";
const { patchDesktopContext } = store;
import { WsClient } from "./core/ws-client.js";
import { createDashboardActions } from "./dashboard/actions.js";
import { createLogger } from "./dashboard/logging.js";
import { configureUiTrace, traceUi } from "./dashboard/ui-trace.js";
import { getCurrentLocale, t } from "./dashboard/helpers.js";
import { mountAsrPanel } from "./panels/asr-panel.js";
import { mountDiagnosticsPanel } from "./panels/diagnostics-panel.js";
import { mountSourceTextReplacementPanel } from "./panels/source-text-replacement-panel.js";
import { mountModelManagerPanel } from "./panels/model-manager-panel.js";
import { mountObsCaptionsPanel } from "./panels/obs-captions-panel.js";
import { mountOverlayPanel } from "./panels/overlay-panel.js";
import { mountProfilesPanel } from "./panels/profiles-panel.js";
import { mountRemotePanel } from "./panels/remote-panel.js";
import { mountRuntimePanel } from "./panels/runtime-panel.js";
import { mountStyleEditorPanel } from "./panels/style-editor-panel.js";
import { mountTranslationPanel } from "./panels/translation-panel.js";
import { mountLayoutController } from "./layout/layout-controller.js";
import { loadDashboardHelpContent } from "./shell/help-content-loader.js";
import { initializeHelpTopics } from "./shell/help-topics.js";
import { initializeLocaleSwitcher } from "./shell/locale-switcher.js";
import { initializeTabs } from "./shell/tabs.js";

let actionsRef = null;

function showBootstrapFailure(message) {
  const text = String(message || "Dashboard bootstrap failed.").trim();
  console.error(`[bootstrap] ${text}`);
  const target = document.querySelector("#save-status-text");
  if (target) {
    target.textContent = text;
    target.dataset.tone = "error";
  }
}

function mountDashboardPanels(actions, store, api, ws, logger, events) {
  const mounts = [];
  const mountSteps = [
    ["runtime", () => mountRuntimePanel(document, { store, actions, api, ws, logger, events })],
    ["asr", () => mountAsrPanel(document, { store, actions, api, ws, logger, events })],
    ["translation", () => mountTranslationPanel(document, { store, actions, api, ws, logger, events })],
    ["overlay", () => mountOverlayPanel(document, { store, actions, api, ws, logger, events })],
    ["obs-captions", () => mountObsCaptionsPanel(document, { store, actions, api, ws, logger, events })],
    ["diagnostics", () => mountDiagnosticsPanel(document, { store, actions, api, ws, logger, events })],
    ["source-text-replacement", () => mountSourceTextReplacementPanel(document, { store, actions, api, ws, logger, events })],
    ["style-editor", () => mountStyleEditorPanel(document, { store, actions, api, ws, logger, events })],
    ["profiles", () => mountProfilesPanel(document, { store, actions, api, ws, logger, events })],
    ["remote", () => mountRemotePanel(document, { store, actions, api, ws, logger, events })],
    ["model-manager", () => mountModelManagerPanel(document, { store, actions, api, ws, logger, events })],
  ];
  for (const [name, mount] of mountSteps) {
    try {
      mounts.push(mount());
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error || "");
      throw new Error(`Panel mount failed (${name}): ${detail}`);
    }
  }
  return mounts;
}

function applyDesktopContext(context) {
  if (!context || typeof context !== "object") {
    return;
  }
  patchDesktopContext(context);
}

async function bootstrap() {
  try {
    await bootstrapDashboard();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error || "");
    showBootstrapFailure(message);
    throw error;
  }
}

async function bootstrapDashboard() {
  const events = createEventBus();
  document.addEventListener("sst:desktop-context", (event) => {
    applyDesktopContext(event?.detail);
  });
  const client = createApiClient({
    onBusyChange(busyKey, isBusy) {
      actionsRef?.updateBusyState?.(busyKey, isBusy);
    },
  });
  const api = createDashboardApi(client);
  configureUiTrace((payload) => api.postUiTrace(payload));
  const logger = createLogger({ store, events, api });
  const actions = createDashboardActions({ store, api, logger, events });
  actionsRef = actions;

  const ws = new WsClient({
    onMessage(message) {
      actions.handleWsMessage(message);
    },
    onStatus(status) {
      store.updateState({ ui: { wsConnected: status === "connected" } });
    },
    logger,
  });

  window.Api = api;
  window.__appLog = logger;
  window.__persistDashboardLog = logger;
  const destroyLocaleSwitcher = initializeLocaleSwitcher(actions);
  initializeTabs(actions, store);
  const destroyLayoutController = mountLayoutController(document, { actions });

  let destroyHelpTopics = () => {};

  window.addEventListener("sst:locale-changed", () => {
    const localeSelect = document.querySelector("#ui-language-select");
    if (localeSelect) {
      localeSelect.value = getCurrentLocale();
    }
    store.updateState({ ui: { uiLanguage: getCurrentLocale() } });
  });

  const mounts = mountDashboardPanels(actions, store, api, ws, logger, events);

  void (async () => {
    try {
      await loadDashboardHelpContent();
      events.emit(DASHBOARD_EVENTS.HELP_CONTENT_LOADED);
      destroyHelpTopics = initializeHelpTopics();
    } catch (error) {
      const root = document.querySelector("[data-help-content-mount]");
      if (root) {
        root.innerHTML = `<p class="muted">${t("help.load_failed")}</p>`;
      }
      logger(`[help] load failed -> ${error instanceof Error ? error.message : String(error)}`);
    }
  })();

  void window.DesktopBridge?.getContext?.()
    .then((context) => {
      traceUi("dashboard", "ui", "bootstrap", {
        desktop_mode: Boolean(context?.desktop_mode),
        startup_mode: context?.startup_mode || null,
        install_profile: context?.install_profile || null,
      });
      applyDesktopContext(context);
      if (context?.desktop_mode) {
        logger(
          t("log.desktop.launcher_active", {
            startup: context.startup_mode || "local",
            remoteRole: context.remote_role || "disabled",
          }),
          {
            source: "desktop",
            details: {
              install_profile: context.install_profile || null,
              web_speech_only: Boolean(context.web_speech_only),
              profile_name: context.profile_name || null,
              base_url: context.base_url || null,
              project_root: context.project_root || null,
              data_dir: context.data_dir || null,
              worker_launch_browser: context.worker_launch_browser || null,
            },
          }
        );
      }
    })
    .catch(() => {
      // desktop bridge is optional
    });

  void actions
    .loadInitialData()
    .then(() => window.SstLayout?.syncDesktopWindowSize?.())
    .then(() => actions.pollRuntimeStatus())
    .catch((error) => {
      const message = error instanceof Error ? error.message : String(error || "");
      store.patchUi({
        saveStatus: t("bootstrap.load_dashboard_failed", { message }),
        saveTone: "error",
      });
      logger(`[bootstrap] ${message}`);
    });

  actions.refreshSystemFonts().catch(() => {
    // keep font picker usable with project-local + fallback fonts
  });
  window.setInterval(() => {
    actions.pollRuntimeStatus().catch(() => null);
  }, 1200);
  ws.connect();

  window.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "s")) {
      return;
    }
    event.preventDefault();
    void actions.stopRuntime();
  });

  window.addEventListener("beforeunload", () => {
    destroyLocaleSwitcher();
    destroyLayoutController?.();
    destroyHelpTopics();
    mounts.forEach((destroy) => destroy?.());
    ws.disconnect();
  });
}

window.addEventListener("error", (event) => {
  const message = event?.error instanceof Error ? event.error.message : String(event?.message || "");
  if (message) {
    showBootstrapFailure(message);
  }
});

window.addEventListener("unhandledrejection", (event) => {
  const reason = event?.reason;
  const message = reason instanceof Error ? reason.message : String(reason || "");
  if (message) {
    showBootstrapFailure(message);
  }
});

bootstrap().catch((error) => {
  const message = error instanceof Error ? error.message : String(error || "");
  showBootstrapFailure(message);
});
