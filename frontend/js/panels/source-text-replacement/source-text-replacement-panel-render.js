import { collectElements } from "../../core/dom.js";
import { t } from "../../dashboard/helpers.js";

export const MAX_PAIRS = 100;
export const MAX_FIELD_LEN = 240;

export const collectSourceTextReplacementElements = (root) =>
  collectElements(root, {
    enabled: "#str-repl-enabled",
    builtin: "#str-repl-builtin",
    ci: "#str-repl-ci",
    whole: "#str-repl-whole",
    word: "#str-repl-word",
    replace: "#str-repl-replace",
    addBtn: "#str-repl-add",
    removeSelectedBtn: "#str-repl-remove-selected",
    list: "#str-repl-pairs-list",
    empty: "#str-repl-pairs-empty",
  });

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function trimReplacementField(raw) {
  return String(raw ?? "")
    .trim()
    .slice(0, MAX_FIELD_LEN);
}

export function renderPairList(elements, pairs) {
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
}

export function updateRemoveButtonState(elements) {
  if (!elements.removeSelectedBtn || !elements.list) {
    return;
  }
  const anyChecked = Boolean(elements.list.querySelector(".str-repl-pair-select:checked"));
  elements.removeSelectedBtn.disabled = !anyChecked;
}

export function renderSourceTextReplacementPanel(snapshot, elements) {
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
  renderPairList(elements, block.pairs);
  updateRemoveButtonState(elements);
}

export function ensureReplacementBlock(draft) {
  if (!draft.source_text_replacement || typeof draft.source_text_replacement !== "object") {
    draft.source_text_replacement = {};
  }
  const block = draft.source_text_replacement;
  if (!Array.isArray(block.pairs)) {
    block.pairs = [];
  }
  return block;
}

export function logPairLimit(logger) {
  logger(t("source_text_replacement.pair_limit_log", { max: MAX_PAIRS }));
}
