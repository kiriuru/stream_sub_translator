import { collectElements } from "../core/dom.js";
import { createPanelMount } from "../core/panel-mount.js";
import { getCurrentLocale, t } from "../dashboard/helpers.js";

function renderObsCaptionsPanel(snapshot, elements) {
  const config = snapshot.config?.obs_closed_captions;
  const diagnostics = snapshot.diagnostics?.obs || {};
  if (!config) {
    return;
  }
  elements.enabled.checked = Boolean(config.enabled);
  elements.host.value = config.connection?.host || "127.0.0.1";
  elements.port.value = String(config.connection?.port ?? 4455);
  elements.password.value = config.connection?.password || "";
  elements.outputMode.value = config.output_mode || "disabled";
  elements.debugEnabled.checked = Boolean(config.debug_mirror?.enabled);
  elements.debugInputName.value = config.debug_mirror?.input_name || "CC_DEBUG";
  elements.debugSendPartials.checked = config.debug_mirror?.send_partials !== false;
  elements.sendPartials.checked = config.timing?.send_partials !== false;
  elements.partialThrottle.value = String(config.timing?.partial_throttle_ms ?? 250);
  elements.minPartialDelta.value = String(config.timing?.min_partial_delta_chars ?? 3);
  elements.finalReplaceDelay.value = String(config.timing?.final_replace_delay_ms ?? 0);
  elements.clearAfter.value = String(config.timing?.clear_after_ms ?? 2500);
  elements.avoidDuplicates.checked = config.timing?.avoid_duplicate_text !== false;
  if (!elements.statusText) {
    return;
  }
  if (!diagnostics.enabled) {
    elements.statusText.textContent =
      getCurrentLocale() === "ru"
        ? "OBS Closed Captions выключены. На browser overlay это не влияет."
        : "OBS Closed Captions are disabled. The browser overlay remains unchanged.";
  } else if (diagnostics.connection_state === "connected") {
    elements.statusText.textContent =
      getCurrentLocale() === "ru"
        ? `OBS websocket подключён, режим: ${diagnostics.output_mode || config.output_mode}.`
        : `Connected to OBS websocket, mode: ${diagnostics.output_mode || config.output_mode}.`;
  } else if (diagnostics.last_error) {
    elements.statusText.textContent =
      getCurrentLocale() === "ru"
        ? `OBS captions включены, но не подключены: ${diagnostics.last_error}`
        : `OBS captions are enabled but not connected: ${diagnostics.last_error}`;
  } else {
    elements.statusText.textContent =
      getCurrentLocale() === "ru"
        ? "OBS captions включены и ждут подключение к OBS websocket."
        : "OBS captions are enabled and waiting for the OBS websocket connection.";
  }
}

const collectObsCaptionsElements = (root) =>
  collectElements(root, {
    enabled: "#obs-cc-enabled",
    host: "#obs-cc-host",
    port: "#obs-cc-port",
    password: "#obs-cc-password",
    passwordToggle: "#obs-cc-password-toggle",
    outputMode: "#obs-cc-output-mode",
    debugEnabled: "#obs-cc-debug-enabled",
    debugInputName: "#obs-cc-debug-input-name",
    debugSendPartials: "#obs-cc-debug-send-partials",
    sendPartials: "#obs-cc-send-partials",
    partialThrottle: "#obs-cc-partial-throttle",
    minPartialDelta: "#obs-cc-min-partial-delta",
    finalReplaceDelay: "#obs-cc-final-replace-delay",
    clearAfter: "#obs-cc-clear-after",
    avoidDuplicates: "#obs-cc-avoid-duplicates",
    statusText: "#obs-cc-status-text",
  });

function bindObsCaptionsEvents(elements, { actions, logger }) {
  function syncConfig() {
    actions.mutateConfig((draft) => {
      const obs = draft.obs_closed_captions;
      obs.enabled = Boolean(elements.enabled?.checked);
      obs.output_mode = elements.outputMode?.value || "disabled";
      obs.connection.host = (elements.host?.value || "127.0.0.1").trim() || "127.0.0.1";
      obs.connection.port = Number(elements.port?.value || 4455);
      obs.connection.password = elements.password?.value || "";
      obs.debug_mirror.enabled = Boolean(elements.debugEnabled?.checked);
      obs.debug_mirror.input_name = (elements.debugInputName?.value || "CC_DEBUG").trim() || "CC_DEBUG";
      obs.debug_mirror.send_partials = Boolean(elements.debugSendPartials?.checked);
      obs.timing.send_partials = Boolean(elements.sendPartials?.checked);
      obs.timing.partial_throttle_ms = Number(elements.partialThrottle?.value || 250);
      obs.timing.min_partial_delta_chars = Number(elements.minPartialDelta?.value || 3);
      obs.timing.final_replace_delay_ms = Number(elements.finalReplaceDelay?.value || 0);
      obs.timing.clear_after_ms = Number(elements.clearAfter?.value || 2500);
      obs.timing.avoid_duplicate_text = Boolean(elements.avoidDuplicates?.checked);
    });
  }

  const handlers = [];
  const add = (element, event, handler) => {
    if (!element) {
      return;
    }
    element.addEventListener(event, handler);
    handlers.push(() => element.removeEventListener(event, handler));
  };

  add(elements.passwordToggle, "click", () => {
    elements.password.type = elements.password.type === "password" ? "text" : "password";
    elements.passwordToggle.textContent =
      elements.password.type === "password" ? t("security.show") : t("security.hide");
  });

  [
    elements.enabled,
    elements.host,
    elements.port,
    elements.password,
    elements.outputMode,
    elements.debugEnabled,
    elements.debugInputName,
    elements.debugSendPartials,
    elements.sendPartials,
    elements.partialThrottle,
    elements.minPartialDelta,
    elements.finalReplaceDelay,
    elements.clearAfter,
    elements.avoidDuplicates,
  ]
    .filter(Boolean)
    .forEach((element) => {
      const eventName = element.type === "checkbox" || element.tagName === "SELECT" ? "change" : "input";
      add(element, eventName, syncConfig);
      add(element, "change", () => {
        syncConfig();
        logger("[obs-cc] updated locally");
      });
    });

  return () => handlers.forEach((off) => off());
}

const mountObsCaptionsPanelImpl = createPanelMount({
  collectElements: collectObsCaptionsElements,
  render: renderObsCaptionsPanel,
  bindEvents: bindObsCaptionsEvents,
});

export function mountObsCaptionsPanel(root, context) {
  return mountObsCaptionsPanelImpl(root, context);
}
