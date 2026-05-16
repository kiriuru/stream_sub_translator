import { createPanelMount } from "../core/panel-mount.js";
import {
  MAX_PAIRS,
  collectSourceTextReplacementElements,
  ensureReplacementBlock,
  logPairLimit,
  renderSourceTextReplacementPanel,
  trimReplacementField,
  updateRemoveButtonState,
} from "./source-text-replacement/source-text-replacement-panel-render.js";

function bindSourceTextReplacementEvents(elements, { store, actions, logger }) {
  function syncFlagsFromDom() {
    actions.mutateConfig((draft) => {
      const block = ensureReplacementBlock(draft);
      block.enabled = Boolean(elements.enabled?.checked);
      block.include_builtin = Boolean(elements.builtin?.checked);
      block.case_insensitive = Boolean(elements.ci?.checked);
      block.whole_words = Boolean(elements.whole?.checked);
    });
  }

  function addPair() {
    const w = trimReplacementField(elements.word?.value);
    if (!w) {
      return;
    }
    const t = trimReplacementField(elements.replace?.value);
    const snap = store.getState();
    const existing = snap.config?.source_text_replacement?.pairs;
    const current = Array.isArray(existing) ? existing : [];
    const dupIdx = current.findIndex((p) => String(p?.source ?? "").trim() === w);
    if (dupIdx < 0 && current.length >= MAX_PAIRS) {
      logPairLimit(logger);
      return;
    }
    actions.mutateConfig((draft) => {
      const block = ensureReplacementBlock(draft);
      const pairs = Array.isArray(block.pairs) ? [...block.pairs] : [];
      const idx = pairs.findIndex((p) => String(p?.source ?? "").trim() === w);
      const entry = { source: w, target: t };
      if (idx >= 0) {
        pairs[idx] = entry;
      } else {
        pairs.push(entry);
      }
      block.pairs = pairs.slice(0, MAX_PAIRS);
    });
    if (elements.word) {
      elements.word.value = "";
    }
    if (elements.replace) {
      elements.replace.value = "";
    }
    elements.word?.focus?.();
    logger("[source-text-replacement] updated locally");
  }

  function removeSelectedPairs() {
    if (!elements.list) {
      return;
    }
    const checked = [...elements.list.querySelectorAll(".str-repl-pair-select:checked")];
    const indices = checked
      .map((el) => Number.parseInt(String(el.dataset.strReplIdx || ""), 10))
      .filter((n) => Number.isFinite(n) && n >= 0);
    if (!indices.length) {
      return;
    }
    const uniqueDesc = [...new Set(indices)].sort((a, b) => b - a);
    actions.mutateConfig((draft) => {
      const block = ensureReplacementBlock(draft);
      if (!Array.isArray(block.pairs)) {
        return;
      }
      uniqueDesc.forEach((idx) => {
        if (idx < block.pairs.length) {
          block.pairs.splice(idx, 1);
        }
      });
    });
    logger("[source-text-replacement] updated locally");
  }

  const handlers = [];
  const add = (element, event, handler) => {
    if (!element) {
      return;
    }
    element.addEventListener(event, handler);
    handlers.push(() => element.removeEventListener(event, handler));
  };

  [elements.enabled, elements.builtin, elements.ci, elements.whole]
    .filter(Boolean)
    .forEach((element) => {
      add(element, "change", () => {
        syncFlagsFromDom();
        logger("[source-text-replacement] updated locally");
      });
    });

  add(elements.addBtn, "click", addPair);
  add(elements.removeSelectedBtn, "click", removeSelectedPairs);
  add(elements.list, "change", (event) => {
    if (event.target?.classList?.contains("str-repl-pair-select")) {
      updateRemoveButtonState(elements);
    }
  });
  add(elements.word, "keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addPair();
    }
  });
  add(elements.replace, "keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addPair();
    }
  });

  return () => handlers.forEach((off) => off());
}

const mountSourceTextReplacementPanelImpl = createPanelMount({
  collectElements: collectSourceTextReplacementElements,
  render: renderSourceTextReplacementPanel,
  bindEvents: bindSourceTextReplacementEvents,
});

export function mountSourceTextReplacementPanel(root, context) {
  return mountSourceTextReplacementPanelImpl(root, context);
}
