import { subscribe } from "../core/store.js";
import { escapeHtml, getCurrentLocale, getLanguageLabel, setElementVisibility, t } from "../dashboard/helpers.js";

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
  const note = document.createElement("p");
  note.className = "subtitle-stage-note";
  note.textContent = state.overlay?.payload
    ? (payload.completed_block_visible
        ? (getCurrentLocale() === "ru" ? `Живой блок субтитров${payload.sequence ? ` #${payload.sequence}` : ""}.` : `Live subtitle block${payload.sequence ? ` #${payload.sequence}` : ""}.`)
        : (getCurrentLocale() === "ru" ? "Предпросмотр live-partial." : "Live partial preview."))
    : (getCurrentLocale() === "ru"
        ? "Предпросмотр построен по текущему сохранённому порядку строк, схеме overlay и стилю субтитров."
        : "Preview built from the current saved subtitle output order, overlay layout, and subtitle style.");
  container.appendChild(note);
}

export function mountOverlayPanel(root, { store, actions, logger }) {
  const elements = {
    presetSelect: root.querySelector("#overlay-preset-select"),
    presetHint: root.querySelector("#overlay-preset-hint"),
    compactToggle: root.querySelector("#overlay-compact-toggle"),
    showSource: root.querySelector("#subtitle-show-source"),
    showTranslations: root.querySelector("#subtitle-show-translations"),
    maxTranslations: root.querySelector("#subtitle-max-translations"),
    displayOrder: root.querySelector("#subtitle-display-order"),
    orderUpBtn: root.querySelector("#subtitle-order-up-btn"),
    orderDownBtn: root.querySelector("#subtitle-order-down-btn"),
    preview: root.querySelector("#subtitle-output-preview"),
  };

  function syncConfig() {
    actions.mutateConfig((draft) => {
      draft.subtitle_output.show_source = Boolean(elements.showSource?.checked);
      draft.subtitle_output.show_translations = Boolean(elements.showTranslations?.checked);
      draft.subtitle_output.max_translation_languages = Number(elements.maxTranslations?.value || 0);
      draft.overlay.preset = elements.presetSelect?.value || "single";
      draft.overlay.compact = Boolean(elements.compactToggle?.checked);
    });
  }

  function render(snapshot) {
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
      elements.presetHint.textContent = preset === "single"
        ? (getCurrentLocale() === "ru"
            ? "Одна строка: все видимые элементы выводятся в одном физическом ряду слева направо по сохранённому порядку."
            : "Single: all visible subtitle items are rendered inside one physical row in the saved order.")
        : preset === "dual-line"
          ? (getCurrentLocale() === "ru"
              ? "Две строки: первый видимый элемент идёт в верхний ряд, остальные делят нижний ряд."
              : "Dual-line: the first visible item uses the top row, and the remaining visible items share the second row.")
          : (getCurrentLocale() === "ru"
              ? "Стопка: каждый видимый элемент получает собственный ряд."
              : "Stacked: each visible subtitle item gets its own row.");
    }
    if (elements.displayOrder) {
      elements.displayOrder.innerHTML = "";
      config.subtitle_output?.display_order?.forEach((code) => {
        const li = document.createElement("li");
        li.dataset.code = code;
        li.textContent = code === "source" ? t("common.source") : `${getLanguageLabel(code)} (${code})`;
        li.classList.toggle("active", code === snapshot.ui.selectedSubtitleOrderItem);
        li.addEventListener("click", () => actions.updateSubtitleSelection(code));
        elements.displayOrder.appendChild(li);
      });
    }
    renderPreview(elements.preview, actions.getPreviewPayload(), snapshot);
  }

  elements.presetSelect?.addEventListener("change", () => {
    syncConfig();
    logger(`[overlay] preset -> ${elements.presetSelect.value}`);
  });
  elements.compactToggle?.addEventListener("change", () => {
    syncConfig();
    logger(`[overlay] compact -> ${elements.compactToggle.checked ? "on" : "off"}`);
  });
  elements.showSource?.addEventListener("change", () => {
    syncConfig();
    logger(`[subtitle] source visibility -> ${elements.showSource.checked ? "on" : "off"}`);
  });
  elements.showTranslations?.addEventListener("change", () => {
    syncConfig();
    logger(`[subtitle] translation visibility -> ${elements.showTranslations.checked ? "on" : "off"}`);
  });
  elements.maxTranslations?.addEventListener("input", syncConfig);
  elements.orderUpBtn?.addEventListener("click", () => {
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
  elements.orderDownBtn?.addEventListener("click", () => {
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

  render(store.getState());
  const unsubscribe = subscribe(render);
  return () => unsubscribe();
}
