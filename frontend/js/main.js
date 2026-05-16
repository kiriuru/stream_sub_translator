import { createEventBus } from "./core/events.js";
import { createApiClient, createDashboardApi } from "./core/api-client.js";
import * as store from "./core/store.js";
import { WsClient } from "./core/ws-client.js";
import { createDashboardActions } from "./dashboard/actions.js";
import { createLogger } from "./dashboard/logging.js";
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

let actionsRef = null;

function initializeLocaleSwitcher(actions) {
  const selects = [...document.querySelectorAll("#ui-language-select, #ui-language-select-settings")];
  if (!selects.length) {
    return () => {};
  }

  const applyCurrentLocale = () => {
    const locale = getCurrentLocale();
    selects.forEach((select) => {
      select.value = locale;
    });
  };

  const onChange = (event) => {
    actions.setUiLanguage(event.target?.value || "en");
    actions.saveCurrentConfig();
  };

  selects.forEach((select) => select.addEventListener("change", onChange));
  applyCurrentLocale();

  return () => {
    selects.forEach((select) => select.removeEventListener("change", onChange));
  };
}

function initializeTabs(actions) {
  const buttons = [...document.querySelectorAll("[data-tab-target]")];
  const panels = [...document.querySelectorAll("[data-tab-panel]")];
  const availableTabs = new Set(panels.map((panel) => panel.dataset.tabPanel));
  const preferredTab = store.getState().ui.activeTab;
  const initialTab = availableTabs.has(preferredTab)
    ? preferredTab
    : availableTabs.has("translation")
      ? "translation"
      : panels.find((panel) => panel.dataset.tabPanel !== "recognition")?.dataset.tabPanel
        || panels[0]?.dataset.tabPanel
        || "translation";

  function applyActiveTab(tabName) {
    if (!availableTabs.has(tabName)) {
      return;
    }
    actions.setActiveTab(tabName);
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      applyActiveTab(button.dataset.tabTarget);
    });
  });
  applyActiveTab(initialTab);
}

function initializeHelpTopics() {
  const buttons = [...document.querySelectorAll("[data-help-topic-target]")];
  const panels = [...document.querySelectorAll("[data-help-topic-panel]")];
  if (!buttons.length || !panels.length) {
    return () => {};
  }

  const availableTopics = new Set(panels.map((panel) => panel.dataset.helpTopicPanel));
  let activeTopic = buttons.find((button) => button.classList.contains("active"))?.dataset.helpTopicTarget;
  if (!availableTopics.has(activeTopic)) {
    activeTopic = panels[0]?.dataset.helpTopicPanel || "";
  }

  function applyHelpLocale() {
    const locale = getCurrentLocale();
    panels.forEach((panel) => {
      const localizedBlocks = [...panel.querySelectorAll("[data-help-locale]")];
      localizedBlocks.forEach((block) => {
        const active = block.dataset.helpLocale === locale;
        block.classList.toggle("active", active);
      });
      if (localizedBlocks.length && !localizedBlocks.some((block) => block.classList.contains("active"))) {
        localizedBlocks[0].classList.add("active");
      }
    });
  }

  function applyHelpTopic(topicName) {
    activeTopic = availableTopics.has(topicName) ? topicName : activeTopic;
    buttons.forEach((button) => {
      const active = button.dataset.helpTopicTarget === activeTopic;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    panels.forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.helpTopicPanel === activeTopic);
    });
    applyHelpLocale();
  }

  const listeners = buttons.map((button) => {
    const onClick = () => applyHelpTopic(button.dataset.helpTopicTarget);
    button.addEventListener("click", onClick);
    return () => button.removeEventListener("click", onClick);
  });
  const onLocaleChanged = () => applyHelpLocale();
  window.addEventListener("sst:locale-changed", onLocaleChanged);

  applyHelpTopic(activeTopic);

  return () => {
    listeners.forEach((destroy) => destroy());
    window.removeEventListener("sst:locale-changed", onLocaleChanged);
  };
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
  const destroyLayoutController = mountLayoutController(document, { actions });
  const destroyHelpTopics = initializeHelpTopics();

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

  void window.DesktopBridge?.getContext?.()
    .then((context) => {
      if (context && window.AppState) {
        window.AppState.desktop = { ...window.AppState.desktop, ...context };
      }
      if (context?.desktop_mode) {
        logger(
          getCurrentLocale() === "ru"
            ? `[desktop] desktop launcher активен | startup=${context.startup_mode || "local"} | remote_role=${context.remote_role || "disabled"}`
            : `[desktop] desktop launcher active | startup=${context.startup_mode || "local"} | remote_role=${context.remote_role || "disabled"}`
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
