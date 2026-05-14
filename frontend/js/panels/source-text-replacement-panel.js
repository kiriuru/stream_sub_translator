import { subscribe } from "../core/store.js";
import { getCurrentLocale } from "../dashboard/helpers.js";

const MAX_PAIRS = 100;
const MAX_FIELD_LEN = 240;

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function trimField(raw) {
  return String(raw ?? "")
    .trim()
    .slice(0, MAX_FIELD_LEN);
}

export function mountSourceTextReplacementPanel(root, { store, actions, logger }) {
  const elements = {
    enabled: root.querySelector("#str-repl-enabled"),
    builtin: root.querySelector("#str-repl-builtin"),
    ci: root.querySelector("#str-repl-ci"),
    whole: root.querySelector("#str-repl-whole"),
    word: root.querySelector("#str-repl-word"),
    replace: root.querySelector("#str-repl-replace"),
    addBtn: root.querySelector("#str-repl-add"),
    removeSelectedBtn: root.querySelector("#str-repl-remove-selected"),
    list: root.querySelector("#str-repl-pairs-list"),
    empty: root.querySelector("#str-repl-pairs-empty"),
  };

  function ensureBlock(draft) {
    if (!draft.source_text_replacement || typeof draft.source_text_replacement !== "object") {
      draft.source_text_replacement = {};
    }
    const block = draft.source_text_replacement;
    if (!Array.isArray(block.pairs)) {
      block.pairs = [];
    }
    return block;
  }

  function syncFlagsFromDom() {
    actions.mutateConfig((draft) => {
      const block = ensureBlock(draft);
      block.enabled = Boolean(elements.enabled?.checked);
      block.include_builtin = Boolean(elements.builtin?.checked);
      block.case_insensitive = Boolean(elements.ci?.checked);
      block.whole_words = Boolean(elements.whole?.checked);
    });
  }

  function updateRemoveButtonState() {
    if (!elements.removeSelectedBtn || !elements.list) {
      return;
    }
    const anyChecked = Boolean(elements.list.querySelector(".str-repl-pair-select:checked"));
    elements.removeSelectedBtn.disabled = !anyChecked;
  }

  function renderPairList(pairs) {
    if (!elements.list) {
      return;
    }
    elements.list.replaceChildren();
    const list = Array.isArray(pairs) ? pairs : [];
    if (elements.empty) {
      elements.empty.hidden = list.length > 0;
    }
    list.forEach((p, index) => {
      const li = document.createElement("li");
      li.className = "str-repl-pair-row";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "str-repl-pair-select";
      cb.dataset.strReplIdx = String(index);
      cb.setAttribute("data-i18n-aria-label", "tools.source_replacement.pair_checkbox_aria");
      const textWrap = document.createElement("label");
      textWrap.className = "str-repl-pair-text mono";
      textWrap.htmlFor = cb.id = `str-repl-pair-cb-${index}`;
      const src = document.createElement("strong");
      src.textContent = String(p?.source ?? "").trim() || "—";
      const sep = document.createElement("span");
      sep.className = "muted";
      sep.textContent = " · ";
      const tgt = document.createElement("span");
      tgt.className = "muted";
      tgt.textContent = String(p?.target ?? "");
      textWrap.append(src, sep, tgt);
      li.append(cb, textWrap);
      elements.list.appendChild(li);
    });
    window.I18n?.apply?.(elements.list);
    updateRemoveButtonState();
  }

  function render(snapshot) {
    const cfg = snapshot.config;
    if (!isPlainObject(cfg)) {
      return;
    }
    const block = isPlainObject(cfg.source_text_replacement) ? cfg.source_text_replacement : {};
    if (elements.enabled) {
      elements.enabled.checked = Boolean(block.enabled);
    }
    if (elements.builtin) {
      elements.builtin.checked = block.include_builtin !== false;
    }
    if (elements.ci) {
      elements.ci.checked = block.case_insensitive !== false;
    }
    if (elements.whole) {
      elements.whole.checked = block.whole_words !== false;
    }
    renderPairList(block.pairs);
  }

  function addPair() {
    const w = trimField(elements.word?.value);
    if (!w) {
      return;
    }
    const t = trimField(elements.replace?.value);
    const snap = store.getState();
    const existing = snap.config?.source_text_replacement?.pairs;
    const current = Array.isArray(existing) ? existing : [];
    const dupIdx = current.findIndex((p) => String(p?.source ?? "").trim() === w);
    if (dupIdx < 0 && current.length >= MAX_PAIRS) {
      logger(
        getCurrentLocale() === "ru"
          ? `[source-text-replacement] не более ${MAX_PAIRS} своих пар`
          : `[source-text-replacement] at most ${MAX_PAIRS} custom pairs`
      );
      return;
    }
    actions.mutateConfig((draft) => {
      const block = ensureBlock(draft);
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
      const block = ensureBlock(draft);
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

  function onListChange(event) {
    if (event.target?.classList?.contains("str-repl-pair-select")) {
      updateRemoveButtonState();
    }
  }

  function onWordKeydown(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      addPair();
    }
  }

  function onReplaceKeydown(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      addPair();
    }
  }

  [elements.enabled, elements.builtin, elements.ci, elements.whole]
    .filter(Boolean)
    .forEach((element) => {
      element.addEventListener("change", () => {
        syncFlagsFromDom();
        logger("[source-text-replacement] updated locally");
      });
    });

  elements.addBtn?.addEventListener("click", addPair);
  elements.removeSelectedBtn?.addEventListener("click", removeSelectedPairs);
  elements.list?.addEventListener("change", onListChange);
  elements.word?.addEventListener("keydown", onWordKeydown);
  elements.replace?.addEventListener("keydown", onReplaceKeydown);

  render(store.getState());
  const unsubscribe = subscribe(render);

  return () => {
    unsubscribe();
    elements.addBtn?.removeEventListener("click", addPair);
    elements.removeSelectedBtn?.removeEventListener("click", removeSelectedPairs);
    elements.list?.removeEventListener("change", onListChange);
    elements.word?.removeEventListener("keydown", onWordKeydown);
    elements.replace?.removeEventListener("keydown", onReplaceKeydown);
  };
}
