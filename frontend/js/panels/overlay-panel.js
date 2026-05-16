import { collectElements } from "../core/dom.js";
import { createPanelMount } from "../core/panel-mount.js";
import { escapeHtml, getCurrentLocale, setElementVisibility, t } from "../dashboard/helpers.js";
import { renderSubtitleDisplayOrder } from "./overlay/overlay-display-order-view.js";

function renderPreview(container, payload, state) {
  if (!container) {
    return;
  }
  if (!payload) {
    container.innerHTML = `<p class="muted">${escapeHtml(getCurrentLocale() === "ru" ? "Предпросмотр стиля субтитров появится после загрузки config." : "Subtitle style preview is unavailable until config loads.")}</p>`;
    return;
  }
  if (!window.SubtitleStyleRenderer) {
    container.innerHTML = `<p class="muted">${escapeHtml(getCurrentLocale() === "ru" ? "SubtitleStyleRenderer недоступен." : "SubtitleStyleRenderer unavailable.")}</p>`;
    return;
  }
  const result = window.SubtitleStyleRenderer.render(container, payload, {
    styleConfig: state.config?.subtitle_style || {},
    presets: state.subtitleStylePresets || {},
  });
  if (result.empty) {
    container.innerHTML = `<p class="muted">${escapeHtml(getCurrentLocale() === "ru" ? "По текущим настройкам сейчас нет видимых строк субтитров." : "No visible subtitle lines for the current settings yet.")}</p>`;
    return;
  }
  if (state.overlay?.payload) {
    const note = document.createElement("p");
    note.className = "subtitle-stage-note";
    note.textContent = payload.completed_block_visible
      ? getCurrentLocale() === "ru"
        ? `Живой блок субтитров${payload.sequence ? ` #${payload.sequence}` : ""}.`
        : `Live subtitle block${payload.sequence ? ` #${payload.sequence}` : ""}.`
      : getCurrentLocale() === "ru"
        ? "Предпросмотр live-partial."
        : "Live partial preview.";
    container.appendChild(note);
  }
}

function renderOverlayPanel(snapshot, elements, { actions }) {
  const config = snapshot.config;
  if (!config) {
    return;
  }
  if (elements.presetSelect) {
    elements.presetSelect.value = config.overlay?.preset || "single";
  }
  if (elements.compactToggle) {
    elements.compactToggle.checked = Boolean(config.overlay?.compact);
  }
  if (elements.showSource) {
    elements.showSource.checked = config.subtitle_output?.show_source !== false;
  }
  if (elements.showTranslations) {
    elements.showTranslations.checked = config.subtitle_output?.show_translations !== false;
  }
  if (elements.maxTranslations) {
    elements.maxTranslations.value = String(config.subtitle_output?.max_translation_languages ?? 0);
  }
  if (elements.presetHint) {
    const preset = config.overlay?.preset || "single";
    elements.presetHint.textContent =
      preset === "single"
        ? getCurrentLocale() === "ru"
          ? "Одна строка: все видимые элементы выводятся в одном физическом ряду слева направо по сохранённому порядку."
          : "Single: all visible subtitle items are rendered inside one physical row in the saved order."
        : preset === "dual-line"
          ? getCurrentLocale() === "ru"
            ? "Две строки: первый видимый элемент идёт в верхний ряд, остальные делят нижний ряд."
            : "Dual-line: the first visible item uses the top row, and the remaining visible items share the second row."
          : getCurrentLocale() === "ru"
            ? "Стопка: каждый видимый элемент получает собственный ряд."
            : "Stacked: each visible subtitle item gets its own row.";
  }
  renderSubtitleDisplayOrder(elements.displayOrder, snapshot, {
    onSelect: (code) => actions.updateSubtitleSelection(code),
  });
  renderPreview(elements.preview, actions.getPreviewPayload(), snapshot);
}

const collectOverlayElements = (root) =>
  collectElements(root, {
    presetSelect: "#overlay-preset-select",
    presetHint: "#overlay-preset-hint",
    compactToggle: "#overlay-compact-toggle",
    showSource: "#subtitle-show-source",
    showTranslations: "#subtitle-show-translations",
    maxTranslations: "#subtitle-max-translations",
    displayOrder: "#subtitle-display-order",
    orderUpBtn: "#subtitle-order-up-btn",
    orderDownBtn: "#subtitle-order-down-btn",
    preview: "#subtitle-output-preview",
  });

function bindOverlayEvents(elements, { store, actions, logger }) {
  function syncConfig() {
    actions.mutateConfig((draft) => {
      draft.subtitle_output.show_source = Boolean(elements.showSource?.checked);
      draft.subtitle_output.show_translations = Boolean(elements.showTranslations?.checked);
      draft.subtitle_output.max_translation_languages = Number(elements.maxTranslations?.value || 0);
      draft.overlay.preset = elements.presetSelect?.value || "single";
      draft.overlay.compact = Boolean(elements.compactToggle?.checked);
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

  add(elements.presetSelect, "change", () => {
    syncConfig();
    logger(`[overlay] preset -> ${elements.presetSelect.value}`);
  });
  add(elements.compactToggle, "change", () => {
    syncConfig();
    logger(`[overlay] compact -> ${elements.compactToggle.checked ? "on" : "off"}`);
  });
  add(elements.showSource, "change", () => {
    syncConfig();
    logger(`[subtitle] source visibility -> ${elements.showSource.checked ? "on" : "off"}`);
  });
  add(elements.showTranslations, "change", () => {
    syncConfig();
    logger(`[subtitle] translation visibility -> ${elements.showTranslations.checked ? "on" : "off"}`);
  });
  add(elements.maxTranslations, "input", syncConfig);
  add(elements.orderUpBtn, "click", () => {
    const selected = store.getState().ui.selectedSubtitleOrderItem;
    if (!selected) {
      return;
    }
    actions.mutateConfig((draft) => {
      const items = draft.subtitle_output.display_order;
      const index = items.indexOf(selected);
      if (index > 0) {
        [items[index - 1], items[index]] = [items[index], items[index - 1]];
      }
    });
    logger("[subtitle] moved display item up");
  });
  add(elements.orderDownBtn, "click", () => {
    const selected = store.getState().ui.selectedSubtitleOrderItem;
    if (!selected) {
      return;
    }
    actions.mutateConfig((draft) => {
      const items = draft.subtitle_output.display_order;
      const index = items.indexOf(selected);
      if (index >= 0 && index < items.length - 1) {
        [items[index + 1], items[index]] = [items[index], items[index + 1]];
      }
    });
    logger("[subtitle] moved display item down");
  });

  return () => handlers.forEach((off) => off());
}

const mountOverlayPanelImpl = createPanelMount({
  collectElements: collectOverlayElements,
  render: renderOverlayPanel,
  bindEvents: bindOverlayEvents,
});

export function mountOverlayPanel(root, context) {
  return mountOverlayPanelImpl(root, context);
}
