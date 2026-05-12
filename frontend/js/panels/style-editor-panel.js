import { subscribe } from "../core/store.js";
import { clone, getCurrentLocale, t } from "../dashboard/helpers.js";
import { applyUiThemeFromConfigPayload } from "../ui-theme.js";

const FALLBACK_LINE_SLOTS = [
  "source",
  "translation_1",
  "translation_2",
  "translation_3",
  "translation_4",
  "translation_5",
];

function normalizeStyle(config, presets) {
  return window.SubtitleStyleRenderer
    ? window.SubtitleStyleRenderer.normalizeStyleConfig(config || {}, presets || {})
    : (config || {});
}

function buildStyleFromPreset(presets, presetName) {
  return window.SubtitleStyleRenderer
    ? window.SubtitleStyleRenderer.buildStyleFromPreset(presets || {}, presetName)
    : {};
}

function getLineSlotNames() {
  if (window.SubtitleStyleRenderer?.LINE_SLOT_NAMES?.length) {
    return window.SubtitleStyleRenderer.LINE_SLOT_NAMES.slice();
  }
  return FALLBACK_LINE_SLOTS.slice();
}

function buildFontCatalogSignature(fontCatalog) {
  const entries = [];
  if (fontCatalog?.project_local?.length) {
    entries.push(...fontCatalog.project_local.map((item) => item?.id || item?.label || ""));
  }
  if (fontCatalog?.system?.length) {
    entries.push(...fontCatalog.system.map((item) => item?.id || item?.label || ""));
  }
  if (fontCatalog?.fallback?.length) {
    entries.push(...fontCatalog.fallback.map((item) => item?.id || item?.label || ""));
  }
  return entries.join("|");
}

function buildPresetCatalogSignature(presets) {
  const catalog = presets && typeof presets === "object" ? presets : {};
  return Object.keys(catalog).sort().join("|");
}

function setSelectOptions(select, options) {
  if (!select) {
    return;
  }
  const previousValue = select.value ?? "";
  select.innerHTML = "";
  options.forEach((optionConfig) => {
    const option = document.createElement("option");
    option.value = String(optionConfig.value ?? "");
    option.textContent = String(optionConfig.label ?? option.value);
    select.appendChild(option);
  });
  select.value = previousValue;
}

function styleSlotLabel(slotName) {
  const normalized = String(slotName || "").trim().toLowerCase();
  if (normalized === "source") {
    return t("common.source");
  }
  if (/^translation_[1-5]$/.test(normalized)) {
    return t(`obs.output.${normalized}`);
  }
  return slotName;
}

function inheritLabel() {
  return t("style.slots.inherit_base");
}

function normalizeOverrideFieldValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (value === "null") {
    return "";
  }
  return String(value);
}

function isStyleNumberInput(element) {
  return Boolean(element && element.type === "number");
}

export function mountStyleEditorPanel(root, { store, actions, logger }) {
  const UI_THEME_PRESETS = [
    {
      id: "custom",
      label: () => getCurrentLocale() === "ru" ? "Пользовательский" : "Custom",
      theme: null,
      palette: null,
    },
    {
      id: "ocean",
      label: () => getCurrentLocale() === "ru" ? "Океан" : "Ocean",
      theme: "dark",
      palette: { accent: "#6cc7ff", accent_secondary: "#4fe3ff", accent_tertiary: "#7ce3ad" },
    },
    {
      id: "neon",
      label: () => getCurrentLocale() === "ru" ? "Неон" : "Neon",
      theme: "dark",
      palette: { accent: "#8bddff", accent_secondary: "#ff6ce6", accent_tertiary: "#ffd166" },
    },
    {
      id: "sunset",
      label: () => getCurrentLocale() === "ru" ? "Закат" : "Sunset",
      theme: "dark",
      palette: { accent: "#ffb703", accent_secondary: "#ff5c7a", accent_tertiary: "#6cc7ff" },
    },
    {
      id: "paper",
      label: () => getCurrentLocale() === "ru" ? "Бумага" : "Paper",
      theme: "light",
      palette: { accent: "#2563eb", accent_secondary: "#db2777", accent_tertiary: "#059669" },
    },
  ];

  const elements = {
    preset: root.querySelector("#subtitle-style-preset"),
    customName: root.querySelector("#subtitle-style-custom-name"),
    saveCustomBtn: root.querySelector("#subtitle-style-save-custom-btn"),
    deleteCustomBtn: root.querySelector("#subtitle-style-delete-custom-btn"),
    description: root.querySelector("#subtitle-style-preset-description"),
    status: root.querySelector("#subtitle-style-custom-status"),
    fontRefreshBtn: root.querySelector("#font-refresh-btn"),
    projectFontsDir: root.querySelector("#project-fonts-dir"),
    fontSourceStatus: root.querySelector("#font-source-status"),
    uiTheme: {
      preset: root.querySelector("#ui-theme-preset"),
      mode: root.querySelector("#ui-theme-mode"),
      accent: root.querySelector("#ui-palette-accent"),
      accentSecondary: root.querySelector("#ui-palette-accent-secondary"),
      accentTertiary: root.querySelector("#ui-palette-accent-tertiary"),
      status: root.querySelector("#ui-theme-status"),
    },
    fields: {
      font_family: root.querySelector("#style-font-family"),
      font_size_px: root.querySelector("#style-font-size"),
      font_weight: root.querySelector("#style-font-weight"),
      fill_color: root.querySelector("#style-fill-color"),
      stroke_color: root.querySelector("#style-stroke-color"),
      stroke_width_px: root.querySelector("#style-stroke-width"),
      shadow_color: root.querySelector("#style-shadow-color"),
      shadow_blur_px: root.querySelector("#style-shadow-blur"),
      shadow_offset_x_px: root.querySelector("#style-shadow-offset-x"),
      shadow_offset_y_px: root.querySelector("#style-shadow-offset-y"),
      background_color: root.querySelector("#style-background-color"),
      background_opacity: root.querySelector("#style-background-opacity"),
      background_padding_x_px: root.querySelector("#style-background-padding-x"),
      background_padding_y_px: root.querySelector("#style-background-padding-y"),
      background_radius_px: root.querySelector("#style-background-radius"),
      line_spacing_em: root.querySelector("#style-line-spacing"),
      letter_spacing_em: root.querySelector("#style-letter-spacing"),
      text_align: root.querySelector("#style-text-align"),
      line_gap_px: root.querySelector("#style-line-gap"),
      effect: root.querySelector("#style-effect"),
    },
    lineSlots: {
      enabled: root.querySelector("#style-line-slot-enabled"),
      tabs: root.querySelector("#style-line-slot-tabs"),
      description: root.querySelector("#style-line-slot-description"),
      fieldsContainer: root.querySelector("#style-line-slot-fields"),
      details: root.querySelector("#style-line-slot-details"),
      fields: {
        font_family: root.querySelector("#style-line-slot-font-family"),
        font_size_px: root.querySelector("#style-line-slot-font-size"),
        font_weight: root.querySelector("#style-line-slot-font-weight"),
        fill_color: root.querySelector("#style-line-slot-fill-color"),
        stroke_color: root.querySelector("#style-line-slot-stroke-color"),
        stroke_width_px: root.querySelector("#style-line-slot-stroke-width"),
        shadow_color: root.querySelector("#style-line-slot-shadow-color"),
        shadow_blur_px: root.querySelector("#style-line-slot-shadow-blur"),
        shadow_offset_x_px: root.querySelector("#style-line-slot-shadow-offset-x"),
        shadow_offset_y_px: root.querySelector("#style-line-slot-shadow-offset-y"),
        background_color: root.querySelector("#style-line-slot-background-color"),
        background_opacity: root.querySelector("#style-line-slot-background-opacity"),
        background_padding_x_px: root.querySelector("#style-line-slot-background-padding-x"),
        background_padding_y_px: root.querySelector("#style-line-slot-background-padding-y"),
        background_radius_px: root.querySelector("#style-line-slot-background-radius"),
        line_spacing_em: root.querySelector("#style-line-slot-line-spacing"),
        letter_spacing_em: root.querySelector("#style-line-slot-letter-spacing"),
        text_align: root.querySelector("#style-line-slot-text-align"),
        effect: root.querySelector("#style-line-slot-effect"),
      },
    },
  };

  let lastFontCatalogSignature = "";
  let lastPresetCatalogSignature = "";

  function updateStyle(mutator) {
    actions.mutateConfig((draft) => {
      const style = normalizeStyle(draft.subtitle_style, store.getState().subtitleStylePresets);
      const nextStyle = clone(style);
      mutator(nextStyle);
      draft.subtitle_style = normalizeStyle(nextStyle, store.getState().subtitleStylePresets);
    });
  }

  function ensureSlotTabs(snapshot) {
    const container = elements.lineSlots.tabs;
    if (!container) {
      return;
    }
    const activeSlot = snapshot.ui?.selectedStyleLineSlot || "source";
    if (!container.childElementCount) {
      getLineSlotNames().forEach((slotName) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "slot-tab";
        button.dataset.slot = slotName;
        button.textContent = styleSlotLabel(slotName);
        button.classList.toggle("active", slotName === activeSlot);
        button.addEventListener("click", () => {
          actions.updateStyleSlot(slotName);
        });
        container.appendChild(button);
      });
      return;
    }
    [...container.querySelectorAll("button[data-slot]")].forEach((button) => {
      const slotName = button.dataset.slot || "";
      button.textContent = styleSlotLabel(slotName);
      button.classList.toggle("active", slotName === activeSlot);
    });
  }

  function ensureFontPickers(snapshot, style) {
    const signature = buildFontCatalogSignature(snapshot.fontCatalog || {});
    if (signature === lastFontCatalogSignature && elements.fields.font_family?.options?.length) {
      return;
    }
    lastFontCatalogSignature = signature;
    const fontCatalog = snapshot.fontCatalog || {};
    const fontOptions = [
      ...(Array.isArray(fontCatalog.project_local) ? fontCatalog.project_local : []),
      ...(Array.isArray(fontCatalog.system) ? fontCatalog.system : []),
      ...(Array.isArray(fontCatalog.fallback) ? fontCatalog.fallback : []),
    ].filter((item) => item && item.family);

    const baseOptions = fontOptions.map((entry) => ({
      value: String(entry.family),
      label: `${entry.label || entry.family}${entry.source ? ` (${entry.source})` : ""}`,
    }));

    setSelectOptions(elements.fields.font_family, baseOptions);
    if (elements.fields.font_family && style.base?.font_family) {
      elements.fields.font_family.value = String(style.base.font_family);
    }

    const slotOptions = [{ value: "", label: inheritLabel() }, ...baseOptions];
    setSelectOptions(elements.lineSlots.fields.font_family, slotOptions);
  }

  function render(snapshot) {
    const presets = snapshot.subtitleStylePresets || {};
    const style = normalizeStyle(snapshot.config?.subtitle_style, presets);
    const ui = snapshot.config?.ui || {};
    const palette = ui?.palette || {};
    ensureSlotTabs(snapshot);
    ensureFontPickers(snapshot, style);
    if (elements.preset) {
      const presetSignature = buildPresetCatalogSignature(presets);
      const shouldRebuildPresets = !elements.preset.options.length || presetSignature !== lastPresetCatalogSignature;
      if (shouldRebuildPresets) {
        lastPresetCatalogSignature = presetSignature;
        const previousSelection = String(elements.preset.value || "").trim();
        elements.preset.innerHTML = "";
        Object.entries(presets).forEach(([presetName, preset]) => {
          const option = document.createElement("option");
          option.value = presetName;
          option.textContent = preset?.label || presetName;
          elements.preset.appendChild(option);
        });
        const desired = String(style.preset || "").trim() || "clean_default";
        const fallback =
          presets[desired] ? desired
            : presets[previousSelection] ? previousSelection
              : presets.clean_default ? "clean_default"
                : Object.keys(presets)[0] || "clean_default";
        elements.preset.value = fallback;
      } else {
        elements.preset.value = style.preset && presets[style.preset] ? style.preset : (elements.preset.value || "clean_default");
      }
    }
    if (elements.description) {
      elements.description.textContent = style.description || (getCurrentLocale() === "ru" ? "Выберите пресет и подстройте его локально." : "Choose a preset and tweak it locally.");
    }
    if (elements.status) {
      elements.status.textContent = style.built_in === false
        ? (getCurrentLocale() === "ru" ? `Редактируется пользовательский пресет "${style.label || style.preset}".` : `Editing custom preset "${style.label || style.preset}".`)
        : (getCurrentLocale() === "ru" ? `Редактируется встроенный пресет "${style.label || style.preset}".` : `Editing built-in preset "${style.label || style.preset}".`);
    }
    if (elements.projectFontsDir) {
      elements.projectFontsDir.textContent = snapshot.fontCatalog?.project_fonts_dir || "fonts";
    }
    if (elements.fontSourceStatus) {
      elements.fontSourceStatus.textContent = getCurrentLocale() === "ru"
        ? `Шрифтов проекта: ${snapshot.fontCatalog?.project_local?.length || 0}. Системных шрифтов: ${snapshot.fontCatalog?.system?.length || 0}.`
        : `Project-local fonts: ${snapshot.fontCatalog?.project_local?.length || 0}. System fonts: ${snapshot.fontCatalog?.system?.length || 0}.`;
    }
    if (elements.uiTheme.mode) {
      elements.uiTheme.mode.value = String(ui?.theme || "dark");
    }

    if (elements.uiTheme.preset) {
      if (!elements.uiTheme.preset.options.length) {
        const options = UI_THEME_PRESETS.map((preset) => ({
          value: preset.id,
          label: preset.label(),
        }));
        setSelectOptions(elements.uiTheme.preset, options);
      } else {
        [...elements.uiTheme.preset.options].forEach((option) => {
          const preset = UI_THEME_PRESETS.find((item) => item.id === option.value);
          if (preset) {
            option.textContent = preset.label();
          }
        });
      }
      if (!String(elements.uiTheme.preset.value || "").trim()) {
        elements.uiTheme.preset.value = "custom";
      }
    }
    if (elements.uiTheme.accent) {
      elements.uiTheme.accent.value = String(palette?.accent || "#6cc7ff");
    }
    if (elements.uiTheme.accentSecondary) {
      elements.uiTheme.accentSecondary.value = String(palette?.accent_secondary || "#ff6ce6");
    }
    if (elements.uiTheme.accentTertiary) {
      elements.uiTheme.accentTertiary.value = String(palette?.accent_tertiary || "#7ce3ad");
    }
    Object.entries(elements.fields).forEach(([key, element]) => {
      if (!element) {
        return;
      }
      if (isStyleNumberInput(element) && document.activeElement === element) {
        return;
      }
      element.value = String(style.base?.[key] ?? "");
    });

    const activeSlot = snapshot.ui?.selectedStyleLineSlot || "source";
    const slotStyle = style.line_slots?.[activeSlot] || { enabled: false };
    const slotEnabled = Boolean(slotStyle.enabled);
    if (elements.lineSlots.enabled) {
      elements.lineSlots.enabled.checked = slotEnabled;
    }
    if (elements.lineSlots.description) {
      elements.lineSlots.description.textContent = slotEnabled
        ? (
          getCurrentLocale() === "ru"
            ? `Выбран слот: ${styleSlotLabel(activeSlot)}. Пустое значение означает "наследовать базовый стиль".`
            : `Selected slot: ${styleSlotLabel(activeSlot)}. Empty values inherit from base.`
        )
        : (
          getCurrentLocale() === "ru"
            ? `Выбран слот: ${styleSlotLabel(activeSlot)}. Включите "Переопределить", чтобы показать настройки слота.`
            : `Selected slot: ${styleSlotLabel(activeSlot)}. Enable Override to reveal slot controls.`
        );
    }
    if (elements.lineSlots.fieldsContainer) {
      elements.lineSlots.fieldsContainer.hidden = !slotEnabled;
    }
    if (elements.lineSlots.details) {
      elements.lineSlots.details.hidden = !slotEnabled;
      if (!slotEnabled) {
        elements.lineSlots.details.removeAttribute("open");
      }
    }
    Object.entries(elements.lineSlots.fields).forEach(([key, element]) => {
      if (!element) {
        return;
      }
      if (isStyleNumberInput(element) && document.activeElement === element) {
        return;
      }
      const raw = slotStyle?.[key];
      element.value = normalizeOverrideFieldValue(raw);
      element.disabled = !slotEnabled;
    });
  }

  elements.preset?.addEventListener("change", () => {
    updateStyle((style) => {
      const nextStyle = buildStyleFromPreset(store.getState().subtitleStylePresets, elements.preset.value);
      nextStyle.custom_presets = style.custom_presets || {};
      Object.assign(style, nextStyle);
    });
    logger(`[subtitle-style] preset -> ${elements.preset.value}`);
  });
  Object.entries(elements.fields).forEach(([key, element]) => {
    if (!element) {
      return;
    }
    const applyFromControl = () => {
      updateStyle((style) => {
        style.base[key] = element.value;
      });
    };
    if (isStyleNumberInput(element)) {
      element.addEventListener("change", () => {
        applyFromControl();
        logger("[subtitle-style] updated locally");
      });
      element.addEventListener("blur", applyFromControl);
      return;
    }
    element.addEventListener("input", applyFromControl);
    element.addEventListener("change", () => {
      applyFromControl();
      logger("[subtitle-style] updated locally");
    });
  });

  elements.lineSlots.enabled?.addEventListener("change", () => {
    const enabled = Boolean(elements.lineSlots.enabled.checked);
    updateStyle((style) => {
      const activeSlot = store.getState().ui?.selectedStyleLineSlot || "source";
      if (!style.line_slots || typeof style.line_slots !== "object") {
        style.line_slots = {};
      }
      const current = style.line_slots[activeSlot] && typeof style.line_slots[activeSlot] === "object"
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
    if (!element) {
      return;
    }
    const apply = () => {
      updateStyle((style) => {
        const activeSlot = store.getState().ui?.selectedStyleLineSlot || "source";
        if (!style.line_slots || typeof style.line_slots !== "object") {
          style.line_slots = {};
        }
        const current = style.line_slots[activeSlot] && typeof style.line_slots[activeSlot] === "object"
          ? style.line_slots[activeSlot]
          : {};
        const raw = String(element.value ?? "");
        style.line_slots[activeSlot] = {
          ...current,
          [key]: raw.trim() === "" ? null : raw,
        };
      });
    };
    if (isStyleNumberInput(element)) {
      element.addEventListener("change", () => {
        apply();
        logger("[subtitle-style] slot updated locally");
      });
      element.addEventListener("blur", apply);
      return;
    }
    element.addEventListener("input", apply);
    element.addEventListener("change", () => {
      apply();
      logger("[subtitle-style] slot updated locally");
    });
  });

  elements.saveCustomBtn?.addEventListener("click", async () => {
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
  elements.deleteCustomBtn?.addEventListener("click", async () => {
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
  elements.fontRefreshBtn?.addEventListener("click", async () => {
    await actions.refreshSystemFonts();
    logger("[subtitle-style] system font refresh finished");
  });

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
    const preset = UI_THEME_PRESETS.find((item) => item.id === presetId) || UI_THEME_PRESETS[0];
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

  elements.uiTheme.preset?.addEventListener("change", () => {
    applyUiThemePreset(String(elements.uiTheme.preset.value || "custom"));
    logger(`[ui-theme] preset -> ${elements.uiTheme.preset.value || "custom"}`);
  });

  elements.uiTheme.mode?.addEventListener("change", () => {
    applyUiThemeDraft();
    logger("[ui-theme] mode updated locally");
  });
  elements.uiTheme.accent?.addEventListener("input", applyUiThemeDraft);
  elements.uiTheme.accentSecondary?.addEventListener("input", applyUiThemeDraft);
  elements.uiTheme.accentTertiary?.addEventListener("input", applyUiThemeDraft);

  render(store.getState());
  const unsubscribe = subscribe(render);
  const onLocaleChanged = () => {
    lastFontCatalogSignature = "";
    render(store.getState());
  };
  window.addEventListener("sst:locale-changed", onLocaleChanged);
  return () => {
    window.removeEventListener("sst:locale-changed", onLocaleChanged);
    unsubscribe();
  };
}
