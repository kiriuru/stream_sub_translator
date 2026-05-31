import { collectElements, setCheckedIfChanged, setInputValueIfChanged } from "../core/dom.js";
import { createPanelMount } from "../core/panel-mount.js";
import { t } from "../dashboard/helpers.js";

function renderObsCaptionsPanel(snapshot, elements) {
  const config = snapshot.config?.obs_closed_captions;
  const diagnostics = snapshot.diagnostics?.obs || {};
  if (!config) {
    return;
  }
  setCheckedIfChanged(elements.enabled, Boolean(config.enabled));
  setInputValueIfChanged(elements.host, config.connection?.host || "127.0.0.1");
  setInputValueIfChanged(elements.port, config.connection?.port ?? 4455);
  setInputValueIfChanged(elements.password, config.connection?.password || "");
  setInputValueIfChanged(elements.outputMode, config.output_mode || "disabled");
  setCheckedIfChanged(elements.debugEnabled, Boolean(config.debug_mirror?.enabled));
  setInputValueIfChanged(elements.debugInputName, config.debug_mirror?.input_name || "CC_DEBUG");
  setCheckedIfChanged(elements.debugSendPartials, config.debug_mirror?.send_partials !== false);
  setCheckedIfChanged(elements.sendPartials, config.timing?.send_partials !== false);
  setInputValueIfChanged(elements.partialThrottle, config.timing?.partial_throttle_ms ?? 250);
  setInputValueIfChanged(elements.minPartialDelta, config.timing?.min_partial_delta_chars ?? 3);
  setInputValueIfChanged(elements.finalReplaceDelay, config.timing?.final_replace_delay_ms ?? 0);
  setInputValueIfChanged(elements.clearAfter, config.timing?.clear_after_ms ?? 2500);
  setCheckedIfChanged(elements.avoidDuplicates, config.timing?.avoid_duplicate_text !== false);
  if (!elements.statusText) {
    return;
  }
  if (!diagnostics.enabled) {
    elements.statusText.textContent = t("obs.cc.status.disabled");
  } else if (diagnostics.connection_state === "connected") {
    elements.statusText.textContent = t("obs.cc.status.connected", {
      mode: diagnostics.output_mode || config.output_mode,
    });
  } else if (diagnostics.last_error) {
    elements.statusText.textContent = t("obs.cc.status.error", { error: diagnostics.last_error });
  } else {
    elements.statusText.textContent = t("obs.cc.status.waiting");
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
      const isCheckboxOrSelect = element.type === "checkbox" || element.tagName === "SELECT";
      // Checkbox/select fire "change" only — binding both an `eventName` and
      // a separate "change" listener would mutate the store twice on every
      // toggle. Text/number inputs still need the live "input" sync plus a
      // committed "change" tick that also logs.
      if (isCheckboxOrSelect) {
        add(element, "change", () => {
          syncConfig();
          logger("[obs-cc] updated locally");
        });
        return;
      }
      add(element, "input", syncConfig);
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
