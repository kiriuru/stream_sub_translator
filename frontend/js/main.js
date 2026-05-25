import { createEventBus, DASHBOARD_EVENTS } from "./core/events.js";
import { createApiClient, createDashboardApi } from "./core/api-client.js";
import * as store from "./core/store.js";
import { WsClient } from "./core/ws-client.js";
import { createDashboardActions } from "./dashboard/actions.js";
import { createLogger } from "./dashboard/logging.js";
import { configureUiTrace, traceUi } from "./dashboard/ui-trace.js";
import { getCurrentLocale } from "./dashboard/helpers.js";
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

async function bootstrap() {
  const events = createEventBus();
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
  void window.DesktopBridge?.getContext?.().then((context) => {
    traceUi("dashboard", "ui", "bootstrap", {
      desktop_mode: Boolean(context?.desktop_mode),
      startup_mode: context?.startup_mode || null,
      install_profile: context?.install_profile || null,
    });
  });

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

  const mounts = [
    mountRuntimePanel(document, { store, actions, api, ws, logger, events }),
    mountAsrPanel(document, { store, actions, api, ws, logger, events }),
    mountTranslationPanel(document, { store, actions, api, ws, logger, events }),
    mountOverlayPanel(document, { store, actions, api, ws, logger, events }),
    mountObsCaptionsPanel(document, { store, actions, api, ws, logger, events }),
    mountDiagnosticsPanel(document, { store, actions, api, ws, logger, events }),
    mountSourceTextReplacementPanel(document, { store, actions, api, ws, logger, events }),
    mountStyleEditorPanel(document, { store, actions, api, ws, logger, events }),
    mountProfilesPanel(document, { store, actions, api, ws, logger, events }),
    mountRemotePanel(document, { store, actions, api, ws, logger, events }),
    mountModelManagerPanel(document, { store, actions, api, ws, logger, events }),
  ];

  void (async () => {
    try {
      await loadDashboardHelpContent();
      events.emit(DASHBOARD_EVENTS.HELP_CONTENT_LOADED);
      destroyHelpTopics = initializeHelpTopics();
    } catch (error) {
      const root = document.querySelector("[data-help-content-mount]");
      if (root) {
        root.innerHTML = `<p class="muted">${getCurrentLocale() === "ru" ? "Не удалось загрузить справку." : "Failed to load help content."}</p>`;
      }
      logger(`[help] load failed -> ${error instanceof Error ? error.message : String(error)}`);
    }
  })();

  void window.DesktopBridge?.getContext?.()
    .then((context) => {
      if (context && window.AppState) {
        window.AppState.desktop = { ...window.AppState.desktop, ...context };
      }
      if (context?.desktop_mode) {
        logger(
          getCurrentLocale() === "ru"
            ? `[desktop] desktop launcher активен | startup=${context.startup_mode || "local"} | remote_role=${context.remote_role || "disabled"}`
            : `[desktop] desktop launcher active | startup=${context.startup_mode || "local"} | remote_role=${context.remote_role || "disabled"}`,
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
    .catch(() => null);

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

bootstrap().catch((error) => {
  console.error(error);
});
