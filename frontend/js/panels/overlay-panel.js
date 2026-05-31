import { collectElements, setCheckedIfChanged, setInputValueIfChanged } from "../core/dom.js";
import { createPanelMount } from "../core/panel-mount.js";
import { escapeHtml, setElementVisibility, t } from "../dashboard/helpers.js";
import { traceUi } from "../dashboard/ui-trace.js";
import { renderSubtitleDisplayOrder } from "./overlay/overlay-display-order-view.js";

// Subtitle-effect debug trace toggle for the dashboard preview surface.
// Persistent so it survives reloads/relaunches in the desktop shell. Enable
// from DevTools with:
//   localStorage.setItem("sst_debug_subtitles", "1"); location.reload();
const SUBTITLE_DEBUG_STORAGE_KEY = "sst_debug_subtitles";
const SUBTITLE_TRACE_RING_LIMIT = 200;

function isSubtitleDebugEnabled() {
  try {
    return window.localStorage && window.localStorage.getItem(SUBTITLE_DEBUG_STORAGE_KEY) === "1";
  } catch (_error) {
    return false;
  }
}

function getSubtitleTraceRing() {
  if (!Array.isArray(window.__sstDashboardSubtitleTrace)) {
    window.__sstDashboardSubtitleTrace = [];
  }
  return window.__sstDashboardSubtitleTrace;
}

function handleSubtitleRenderTraceForDashboard(event) {
  if (!event || typeof event !== "object") {
    return;
  }
  const ring = getSubtitleTraceRing();
  const enriched = { ts: Date.now(), ...event };
  ring.push(enriched);
  if (ring.length > SUBTITLE_TRACE_RING_LIMIT) {
    ring.splice(0, ring.length - SUBTITLE_TRACE_RING_LIMIT);
  }
  if (event.type === "partial_frame") {
    console.debug(
      `[dashboard-subtitles] partial slot=${event.slot} transition=${event.transition} `
        + `shared=${event.shared_length} fresh=${event.fresh_chars} prev_len=${event.previous_text_length} `
        + `cur_len=${event.current_text_length} effect=${event.effect}`
    );
  } else if (event.type === "completed_frame") {
    console.debug(
      `[dashboard-subtitles] completed slot=${event.slot} animated=${event.animated} text_len=${event.text_length}`
    );
  } else if (event.type === "render_summary") {
    const anomalyTags = (event.anomalies || []).map((a) => a.kind).join(",") || "none";
    console.debug(
      `[dashboard-subtitles] summary rows=${event.rows} partials=${event.partial_entries} `
        + `completed=${event.completed_entries} state_carryover=${event.state_carryover} `
        + `since_last_ms=${event.ms_since_last_render} anomalies=${anomalyTags}`
    );
    // Backend persistence: anomalies only, to keep ui-trace.jsonl readable.
    if (event.anomalies && event.anomalies.length) {
      traceUi("dashboard", "subtitle_render", "anomaly", {
        overlay: event.overlay,
        rows: event.rows,
        partial_entries: event.partial_entries,
        completed_entries: event.completed_entries,
        state_carryover: event.state_carryover,
        ms_since_last_render: event.ms_since_last_render,
        render_duration_ms: event.render_duration_ms,
        anomalies: event.anomalies,
      });
    }
  }
}

function renderPreview(container, payload, state) {
  if (!container) {
    return;
  }
  if (!payload) {
    window.SubtitleStyleRenderer?.disposeRenderContainer?.(container);
    container.innerHTML = `<p class="muted">${escapeHtml(t("overlay.preview.config_not_loaded"))}</p>`;
    return;
  }
  if (!window.SubtitleStyleRenderer) {
    container.innerHTML = `<p class="muted">${escapeHtml(t("overlay.preview.renderer_unavailable"))}</p>`;
    return;
  }
  const subtitleDebug = isSubtitleDebugEnabled();
  const result = window.SubtitleStyleRenderer.render(container, payload, {
    styleConfig: state.config?.subtitle_style || {},
    presets: state.subtitleStylePresets || {},
    onRenderTrace: subtitleDebug ? handleSubtitleRenderTraceForDashboard : null,
  });
  if (result.empty) {
    window.SubtitleStyleRenderer?.disposeRenderContainer?.(container);
    container.innerHTML = `<p class="muted">${escapeHtml(t("overlay.preview.no_visible_lines"))}</p>`;
    return;
  }
  // The renderer owns the `.subtitle-stage-shell` wrapper inside `container`
  // and only mutates it. Anything else this function appends as a sibling
  // (notes, hints, etc.) MUST be cleaned up by us — previously the renderer's
  // implicit `container.innerHTML = ""` wipe on every frame did that for us,
  // but the new in-place fast path leaves stale siblings in place. Without
  // this cleanup the dashboard accumulates one duplicate note per partial
  // frame ("Живой блок субтитров #N." stacked dozens of times).
  const staleNotes = container.querySelectorAll(".subtitle-stage-note");
  staleNotes.forEach((node) => node.remove());
  if (state.overlay?.payload) {
    const noteText = payload.completed_block_visible
      ? t("overlay.preview.live_block", {
          suffix: payload.sequence ? ` #${payload.sequence}` : "",
        })
      : t("overlay.preview.live_partial");
    const note = document.createElement("p");
    note.className = "subtitle-stage-note";
    note.textContent = noteText;
    container.appendChild(note);
  }
}

function renderOverlayPanel(snapshot, elements, { actions }) {
  const config = snapshot.config;
  if (!config) {
    return;
  }
  setInputValueIfChanged(elements.presetSelect, config.overlay?.preset || "single");
  setCheckedIfChanged(elements.compactToggle, Boolean(config.overlay?.compact));
  setCheckedIfChanged(elements.showSource, config.subtitle_output?.show_source !== false);
  setCheckedIfChanged(elements.showTranslations, config.subtitle_output?.show_translations !== false);
  setInputValueIfChanged(elements.maxTranslations, config.subtitle_output?.max_translation_languages ?? 0);
  if (elements.presetHint) {
    const preset = config.overlay?.preset || "single";
    elements.presetHint.textContent =
      preset === "single"
        ? t("overlay.preset_hint.single")
        : preset === "dual-line"
          ? t("overlay.preset_hint.dual_line")
          : t("overlay.preset_hint.stacked");
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
  const destroyPanel = mountOverlayPanelImpl(root, context);
  const preview = root.querySelector("#subtitle-output-preview");
  return () => {
    window.SubtitleStyleRenderer?.disposeRenderContainer?.(preview);
    destroyPanel();
  };
}
