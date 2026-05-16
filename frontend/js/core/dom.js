import { escapeHtml } from "../dashboard/helpers.js";

/**
 * Safe HTML: string must already be escaped, or use setText.
 */
export function setHtml(element, html) {
  if (!element) {
    return;
  }
  element.innerHTML = html;
}

export function setText(element, text) {
  if (!element) {
    return;
  }
  element.textContent = String(text ?? "");
}

export function clearElement(element) {
  if (!element) {
    return;
  }
  element.replaceChildren();
}

export function replaceChildren(element, nodes) {
  if (!element) {
    return;
  }
  element.replaceChildren(...(Array.isArray(nodes) ? nodes : [nodes]));
}

export function htmlToNodes(html) {
  const template = document.createElement("template");
  template.innerHTML = String(html || "").trim();
  return [...template.content.childNodes];
}

export function setHtmlFromTemplate(element, html) {
  if (!element) {
    return;
  }
  clearElement(element);
  htmlToNodes(html).forEach((node) => element.appendChild(node));
}

export function setSafeHtml(element, html) {
  setHtmlFromTemplate(element, escapeHtml(String(html ?? "")));
}

/** For static markup (e.g. optgroups) built in code with escaped labels. */
export function setSelectMarkup(select, html, { selectedValue } = {}) {
  if (!select) {
    return;
  }
  const previous = selectedValue !== undefined ? String(selectedValue) : String(select.value || "");
  setHtmlFromTemplate(select, html);
  if (previous && [...select.options].some((option) => option.value === previous)) {
    select.value = previous;
  }
}

export function fillSelectOptions(
  select,
  items,
  {
    getValue = (item) => item?.value ?? item,
    getLabel = (item) => item?.label ?? item,
    getDataset,
    selectedValue,
  } = {}
) {
  if (!select) {
    return;
  }
  const previous = selectedValue !== undefined ? String(selectedValue) : String(select.value || "");
  clearElement(select);
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = String(getValue(item) ?? "");
    option.textContent = String(getLabel(item) ?? "");
    const dataset = typeof getDataset === "function" ? getDataset(item) : null;
    if (dataset && typeof dataset === "object") {
      Object.entries(dataset).forEach(([key, value]) => {
        if (value != null) {
          option.dataset[key] = String(value);
        }
      });
    }
    select.appendChild(option);
  });
  if (previous && [...select.options].some((option) => option.value === previous)) {
    select.value = previous;
  }
}

export function collectElements(root, selectorsByKey) {
  const elements = {};
  Object.entries(selectorsByKey).forEach(([key, selector]) => {
    if (typeof selector === "string") {
      elements[key] = root.querySelector(selector);
      return;
    }
    if (Array.isArray(selector)) {
      elements[key] = [...root.querySelectorAll(selector[0])];
      return;
    }
    elements[key] = selector(root);
  });
  return elements;
}

/**
 * Two-way bind: DOM input events write via onWrite; store subscription refreshes display.
 */
export function bindControlledField(element, { read, write, events = ["input", "change"] }) {
  if (!element || typeof read !== "function" || typeof write !== "function") {
    return () => {};
  }
  const syncFromStore = () => {
    const next = read();
    if (element.type === "checkbox") {
      element.checked = Boolean(next);
      return;
    }
    const normalized = next == null ? "" : String(next);
    if (element.value !== normalized) {
      element.value = normalized;
    }
  };
  const handlers = events.map((eventName) => {
    const handler = () => {
      if (element.type === "checkbox") {
        write(element.checked);
        return;
      }
      write(element.value);
    };
    element.addEventListener(eventName, handler);
    return () => element.removeEventListener(eventName, handler);
  });
  syncFromStore();
  return () => {
    handlers.forEach((off) => off());
  };
}
