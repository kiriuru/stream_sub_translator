import { createPanelMount } from "../core/panel-mount.js";
import { clone } from "../dashboard/helpers.js";
import { applyUiThemeFromConfigPayload } from "../ui-theme.js";
import {
  bindStyleColorPickerEvents,
  buildStyleFromPreset,
  getUiThemePresets,
  isStyleColorInput,
  isStyleNumberInput,
  normalizeStyle,
} from "./style/style-editor-panel-shared.js";
import { collectStyleEditorElements, renderStyleEditorPanel } from "./style/style-editor-panel-render.js";

function bindStyleEditorEvents(elements, { store, actions, logger }, catalogState, rerender) {
  function updateStyle(mutator) {
    actions.mutateConfig((draft) => {
      const style = normalizeStyle(draft.subtitle_style, store.getState().subtitleStylePresets);
      const nextStyle = clone(style);
      mutator(nextStyle);
      draft.subtitle_style = normalizeStyle(nextStyle, store.getState().subtitleStylePresets);
    });
  }

  const applyUiThemeDraft = () => {
    actions.mutateConfig((draft) => {
      if (!draft.ui || typeof draft.ui !== "object") {
        draft.ui = {};
      }
      draft.ui.theme = String(elements.uiTheme.mode?.value || "dark") === "light" ? "light" : "dark";
      if (!draft.ui.palette || typeof draft.ui.palette !== "object") {
        draft.ui.palette = {};
      }
      draft.ui.palette.accent = String(elements.uiTheme.accent?.value || "#6cc7ff");
      draft.ui.palette.accent_secondary = String(elements.uiTheme.accentSecondary?.value || "#ff6ce6");
      draft.ui.palette.accent_tertiary = String(elements.uiTheme.accentTertiary?.value || "#7ce3ad");
    });
    applyUiThemeFromConfigPayload(store.getState().config || {});
  };

  const applyUiThemePreset = (presetId) => {
    const preset = getUiThemePresets().find((item) => item.id === presetId) || getUiThemePresets()[0];
    if (!preset || preset.id === "custom") {
      applyUiThemeDraft();
      return;
    }
    if (elements.uiTheme.mode && preset.theme) {
      elements.uiTheme.mode.value = preset.theme;
    }
    if (elements.uiTheme.accent && preset.palette?.accent) {
      elements.uiTheme.accent.value = preset.palette.accent;
    }
    if (elements.uiTheme.accentSecondary && preset.palette?.accent_secondary) {
      elements.uiTheme.accentSecondary.value = preset.palette.accent_secondary;
    }
    if (elements.uiTheme.accentTertiary && preset.palette?.accent_tertiary) {
      elements.uiTheme.accentTertiary.value = preset.palette.accent_tertiary;
    }
    applyUiThemeDraft();
  };

  const handlers = [];
  const add = (element, event, handler) => {
    if (!element) {
      return;
    }
    element.addEventListener(event, handler);
    handlers.push(() => element.removeEventListener(event, handler));
  };

  add(elements.preset, "change", () => {
    updateStyle((style) => {
      const nextStyle = buildStyleFromPreset(store.getState().subtitleStylePresets, elements.preset.value);
      nextStyle.custom_presets = style.custom_presets || {};
      Object.assign(style, nextStyle);
    });
    logger(`[subtitle-style] preset -> ${elements.preset.value}`);
  });

  const bindBaseOrSlotField = (element, key, applyValue) => {
    if (!element) {
      return;
    }
    const applyFromControl = () => {
      applyValue(key, element.value);
    };
    if (isStyleNumberInput(element)) {
      add(element, "change", () => {
        applyFromControl();
        logger("[subtitle-style] updated locally");
      });
      add(element, "blur", applyFromControl);
      return;
    }
    if (isStyleColorInput(element)) {
      bindStyleColorPickerEvents(element, add, () => {
        applyFromControl();
        logger("[subtitle-style] updated locally");
      });
      return;
    }
    add(element, "input", applyFromControl);
    add(element, "change", () => {
      applyFromControl();
      logger("[subtitle-style] updated locally");
    });
  };

  Object.entries(elements.fields).forEach(([key, element]) => {
    bindBaseOrSlotField(element, key, (fieldKey, value) => {
      updateStyle((style) => {
        style.base[fieldKey] = value;
      });
    });
  });

  add(elements.lineSlots.enabled, "change", () => {
    const enabled = Boolean(elements.lineSlots.enabled.checked);
    updateStyle((style) => {
      const activeSlot = store.getState().ui?.selectedStyleLineSlot || "source";
      if (!style.line_slots || typeof style.line_slots !== "object") {
        style.line_slots = {};
      }
      const current =
        style.line_slots[activeSlot] && typeof style.line_slots[activeSlot] === "object"
          ? style.line_slots[activeSlot]
          : {};
      if (enabled && current.enabled !== true) {
        const next = { ...current, enabled: true };
        const base = style.base && typeof style.base === "object" ? style.base : {};
        Object.entries(base).forEach(([key, value]) => {
          if (key === "effect" && value == null) {
            return;
          }
          if (next[key] === null || next[key] === undefined || next[key] === "") {
            next[key] = value;
          }
        });
        style.line_slots[activeSlot] = next;
        return;
      }
      style.line_slots[activeSlot] = { ...current, enabled };
    });
    logger(`[subtitle-style] slot ${enabled ? "override on" : "override off"}`);
  });

  Object.entries(elements.lineSlots.fields).forEach(([key, element]) => {
    bindBaseOrSlotField(element, key, (fieldKey, value) => {
      updateStyle((style) => {
        const activeSlot = store.getState().ui?.selectedStyleLineSlot || "source";
        if (!style.line_slots || typeof style.line_slots !== "object") {
          style.line_slots = {};
        }
        const current =
          style.line_slots[activeSlot] && typeof style.line_slots[activeSlot] === "object"
            ? style.line_slots[activeSlot]
            : {};
        const raw = String(value ?? "");
        style.line_slots[activeSlot] = {
          ...current,
          [fieldKey]: raw.trim() === "" ? null : raw,
        };
      });
      logger("[subtitle-style] slot updated locally");
    });
  });

  // "Apply preset to this slot" — copy the chosen preset's base style into
  // the currently selected line slot as a one-shot override. The slot keeps
  // its enabled=true flag, all base fields are pushed into the slot, and
  // the selector is reset to the placeholder so users see this as an
  // action button rather than a binding (the slot is a free-form override
  // afterwards and can be tweaked further). The base preset selector is
  // unaffected, so users can still mix and match (e.g. base preset =
  // clean_default, source slot copied from cyberpunk_pulse).
  add(elements.lineSlots.applyPreset, "change", () => {
    const presetName = String(elements.lineSlots.applyPreset.value || "").trim();
    if (!presetName) {
      return;
    }
    const presets = store.getState().subtitleStylePresets || {};
    const sourceStyle = buildStyleFromPreset(presets, presetName);
    const sourceBase = sourceStyle?.base || {};
    if (!Object.keys(sourceBase).length) {
      elements.lineSlots.applyPreset.value = "";
      return;
    }
    updateStyle((style) => {
      const activeSlot = store.getState().ui?.selectedStyleLineSlot || "source";
      if (!style.line_slots || typeof style.line_slots !== "object") {
        style.line_slots = {};
      }
      const current =
        style.line_slots[activeSlot] && typeof style.line_slots[activeSlot] === "object"
          ? style.line_slots[activeSlot]
          : {};
      const next = { ...current, enabled: true };
      Object.entries(sourceBase).forEach(([key, value]) => {
        // Coerce all values to strings so they match how the slot field
        // bindings persist user-entered values (later normalisation in
        // the renderer/router handles the parse-back to numbers etc.).
        next[key] = value === null || value === undefined ? null : String(value);
      });
      style.line_slots[activeSlot] = next;
    });
    elements.lineSlots.applyPreset.value = "";
    logger(`[subtitle-style] slot preset applied -> ${presetName}`);
  });

  add(elements.saveCustomBtn, "click", async () => {
    const name = String(elements.customName?.value || "").trim();
    if (!name) {
      return;
    }
    updateStyle((style) => {
      const key = `custom_${name.toLowerCase().replace(/[^a-z0-9]+/g, "_")}`;
      const customPresets = clone(style.custom_presets || {});
      customPresets[key] = {
        ...style,
        preset: key,
        label: name,
        built_in: false,
        custom_presets: {},
      };
      style.custom_presets = customPresets;
      style.preset = key;
      style.label = name;
      style.built_in = false;
    });
    await actions.saveCurrentConfig();
    logger("[subtitle-style] custom preset saved and persisted");
  });

  add(elements.deleteCustomBtn, "click", async () => {
    updateStyle((style) => {
      if (!style.custom_presets?.[style.preset]) {
        return;
      }
      const customPresets = clone(style.custom_presets);
      delete customPresets[style.preset];
      const nextStyle = buildStyleFromPreset(store.getState().subtitleStylePresets, "clean_default");
      Object.assign(style, nextStyle, { custom_presets: customPresets });
    });
    await actions.saveCurrentConfig();
    logger("[subtitle-style] custom preset deleted and persisted");
  });

  add(elements.fontRefreshBtn, "click", async () => {
    await actions.refreshSystemFonts();
    logger("[subtitle-style] system font refresh finished");
  });

  add(elements.uiTheme.preset, "change", () => {
    applyUiThemePreset(String(elements.uiTheme.preset.value || "custom"));
    logger(`[ui-theme] preset -> ${elements.uiTheme.preset.value || "custom"}`);
  });
  add(elements.uiTheme.mode, "change", () => {
    applyUiThemeDraft();
    logger("[ui-theme] mode updated locally");
  });
  [elements.uiTheme.accent, elements.uiTheme.accentSecondary, elements.uiTheme.accentTertiary].forEach((element) => {
    bindStyleColorPickerEvents(element, add, applyUiThemeDraft);
  });

  const onLocaleChanged = () => {
    catalogState.lastFontCatalogSignature = "";
    rerender(store.getState());
  };
  window.addEventListener("sst:locale-changed", onLocaleChanged);

  return () => {
    window.removeEventListener("sst:locale-changed", onLocaleChanged);
    handlers.forEach((off) => off());
  };
}

export function mountStyleEditorPanel(root, context) {
  const catalogState = { lastFontCatalogSignature: "", lastPresetCatalogSignature: "" };
  const mountImpl = createPanelMount({
    collectElements: collectStyleEditorElements,
    render: (snapshot, elements) => renderStyleEditorPanel(snapshot, elements, context, catalogState),
    bindEvents: (elements, ctx, rerender) => bindStyleEditorEvents(elements, ctx, catalogState, rerender),
  });
  return mountImpl(root, context);
}
