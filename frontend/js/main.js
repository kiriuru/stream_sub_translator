import { createEventBus } from "./core/events.js";
import { createApiClient, createDashboardApi } from "./core/api-client.js";
import * as store from "./core/store.js";
import { WsClient } from "./core/ws-client.js";
import { createDashboardActions } from "./dashboard/actions.js";
import { createLogger } from "./dashboard/logging.js";
import { getCurrentLocale } from "./dashboard/helpers.js";
import { mountAsrPanel } from "./panels/asr-panel.js";
import { mountDiagnosticsPanel } from "./panels/diagnostics-panel.js";
import { mountModelManagerPanel } from "./panels/model-manager-panel.js";
import { mountObsCaptionsPanel } from "./panels/obs-captions-panel.js";
import { mountOverlayPanel } from "./panels/overlay-panel.js";
import { mountProfilesPanel } from "./panels/profiles-panel.js";
import { mountRemotePanel } from "./panels/remote-panel.js";
import { mountRuntimePanel } from "./panels/runtime-panel.js";
import { mountStyleEditorPanel } from "./panels/style-editor-panel.js";
import { mountTranslationPanel } from "./panels/translation-panel.js";

let actionsRef = null;

function initializeLocaleSwitcher(actions) {
  const select = document.querySelector("#ui-language-select");
  if (!select) {
    return () => {};
  }

  const applyCurrentLocale = () => {
    select.value = getCurrentLocale();
  };

  const onChange = () => {
    actions.setUiLanguage(select.value || "en");
  };

  select.addEventListener("change", onChange);
  applyCurrentLocale();

  return () => {
    select.removeEventListener("change", onChange);
  };
}

function initializeTabs(actions) {
  const buttons = [...document.querySelectorAll("[data-tab-target]")];
  const panels = [...document.querySelectorAll("[data-tab-panel]")];
  const availableTabs = new Set(panels.map((panel) => panel.dataset.tabPanel));
  const initialTab = availableTabs.has(store.getState().ui.activeTab)
    ? store.getState().ui.activeTab
    : panels[0]?.dataset.tabPanel
      || "translation";

  function applyActiveTab(tabName) {
    buttons.forEach((button) => {
      const active = button.dataset.tabTarget === tabName;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    panels.forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.tabPanel === tabName);
    });
    actions.setActiveTab(tabName);
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      applyActiveTab(button.dataset.tabTarget);
    });
  });
  applyActiveTab(initialTab);
}

async function bootstrap() {
  const events = createEventBus();
  const client = createApiClient({
    onBusyChange(busyKey, isBusy) {
      actionsRef?.updateBusyState?.(busyKey, isBusy);
    },
  });
  const api = createDashboardApi(client);
  const logger = createLogger({ store, events, api });
  const actions = createDashboardActions({ store, api, logger });
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
  initializeTabs(actions);

  const mounts = [
    mountRuntimePanel(document, { store, actions, api, ws, logger, events }),
    mountAsrPanel(document, { store, actions, api, ws, logger, events }),
    mountTranslationPanel(document, { store, actions, api, ws, logger, events }),
    mountOverlayPanel(document, { store, actions, api, ws, logger, events }),
    mountObsCaptionsPanel(document, { store, actions, api, ws, logger, events }),
    mountDiagnosticsPanel(document, { store, actions, api, ws, logger, events }),
    mountStyleEditorPanel(document, { store, actions, api, ws, logger, events }),
    mountProfilesPanel(document, { store, actions, api, ws, logger, events }),
    mountRemotePanel(document, { store, actions, api, ws, logger, events }),
    mountModelManagerPanel(document, { store, actions, api, ws, logger, events }),
  ];

  window.addEventListener("sst:locale-changed", () => {
    const localeSelect = document.querySelector("#ui-language-select");
    if (localeSelect) {
      localeSelect.value = getCurrentLocale();
    }
    store.updateState({ ui: { uiLanguage: getCurrentLocale() } });
  });

  try {
    const context = await window.DesktopBridge?.getContext?.();
    if (context?.desktop_mode) {
      logger(
        getCurrentLocale() === "ru"
          ? `[desktop] desktop launcher активен | startup=${context.startup_mode || "local"} | remote_role=${context.remote_role || "disabled"}`
          : `[desktop] desktop launcher active | startup=${context.startup_mode || "local"} | remote_role=${context.remote_role || "disabled"}`
      );
    }
  } catch (_error) {
    // desktop bridge is optional
  }

  await actions.loadInitialData();
  actions.refreshSystemFonts().catch(() => {
    // keep font picker usable with project-local + fallback fonts
  });
  await actions.pollRuntimeStatus().catch(() => null);
  window.setInterval(() => {
    actions.pollRuntimeStatus().catch(() => null);
  }, 1200);
  ws.connect();

  window.addEventListener("beforeunload", () => {
    destroyLocaleSwitcher();
    mounts.forEach((destroy) => destroy?.());
    ws.disconnect();
  });
}

bootstrap().catch((error) => {
  console.error(error);
});
