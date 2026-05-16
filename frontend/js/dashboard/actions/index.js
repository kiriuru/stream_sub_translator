import { createBrowserWorkerActions } from "./browser-worker-actions.js";
import { createConfigActions } from "./config-actions.js";
import { createDataActions } from "./data-actions.js";
import { createRuntimeActions } from "./runtime-actions.js";
import { createUiActions } from "./ui-actions.js";
import { createWsHandlers } from "./ws-handlers.js";

export function createDashboardActions({ store, api, logger, events }) {
  const runtimeActions = createRuntimeActions({ store, api, logger, events });
  const configActions = createConfigActions({ store, api, logger, events });
  const dataActions = createDataActions({ store, api, logger, configActions });
  const uiActions = createUiActions({ store, events });
  const browserWorkerActions = createBrowserWorkerActions({ store, logger });
  const wsHandlers = createWsHandlers({ store, runtimeActions, events });

  return {
    ...dataActions,
    ...configActions,
    ...runtimeActions,
    ...uiActions,
    ...browserWorkerActions,
    ...wsHandlers,
  };
}
