const state = {
  config: null,
  runtime: null,
  diagnostics: null,
  model: null,
  translation: null,
  overlay: null,
  transcript: {
    partial: "",
    finals: [],
  },
  profiles: [],
  audioDevices: [],
  versionInfo: null,
  subtitleStylePresets: {},
  fontCatalog: {
    project_local: [],
    fallback: [],
    system: [],
    project_fonts_dir: "fonts",
  },
  remote: null,
  desktop: null,
  ui: {
    activeTab: "runtime",
    saving: false,
    runtimeBusy: false,
    preflightRunning: false,
    modelRepairRunning: false,
    saveStatus: "",
    saveTone: "info",
    wsConnected: false,
    logs: [],
    selectedAudioInputId: null,
    selectedTranslationLanguage: null,
    selectedSubtitleOrderItem: null,
    selectedStyleLineSlot: "source",
    uiLanguage: "en",
  },
};

const listeners = new Set();

function clone(value) {
  if (typeof structuredClone === "function") {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
}

function emit() {
  const snapshot = getState();
  // Iterate over a snapshot so listeners that unsubscribe during dispatch
  // don't skip later subscribers. Wrap each call so a thrown listener does
  // not silently halt the rest of the panel/diagnostics tree (e.g. a typo
  // in one panel must not freeze runtime status or transcript updates in
  // every other panel).
  Array.from(listeners).forEach((listener) => {
    try {
      listener(snapshot);
    } catch (error) {
      try {
        console.error("[store] listener error", error);
      } catch (_logError) {
        // last-resort: swallow logging error so we never bubble out of emit.
      }
    }
  });
}

export function getState() {
  return clone(state);
}

export function updateState(patch) {
  if (!patch || typeof patch !== "object") {
    return;
  }
  const nextPatch = { ...patch };
  if (nextPatch.ui && typeof nextPatch.ui === "object") {
    nextPatch.ui = { ...state.ui, ...nextPatch.ui };
  }
  Object.assign(state, nextPatch);
  emit();
}

export function replaceState(nextState) {
  Object.keys(state).forEach((key) => {
    delete state[key];
  });
  Object.assign(state, clone(nextState || {}));
  emit();
}

export function mutateState(mutator) {
  if (typeof mutator !== "function") {
    return;
  }
  mutator(state);
  emit();
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * Subscribe to a derived slice; skips listener when selector result is unchanged (Object.is).
 */
export function subscribeSelector(selector, listener) {
  let previous = selector(getState());
  listener(previous, getState());
  return subscribe((snapshot) => {
    const next = selector(snapshot);
    if (Object.is(previous, next)) {
      return;
    }
    previous = next;
    listener(next, snapshot);
  });
}

export function patchUi(patch) {
  if (!patch || typeof patch !== "object") {
    return;
  }
  updateState({ ui: patch });
}

export function patchDesktopContext(patch) {
  if (!patch || typeof patch !== "object") {
    return;
  }
  state.desktop = { ...(state.desktop || {}), ...patch };
  emit();
}
