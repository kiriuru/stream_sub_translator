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
  listeners.forEach((listener) => {
    listener(snapshot);
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
