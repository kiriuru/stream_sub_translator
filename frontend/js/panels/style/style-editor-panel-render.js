import { getCurrentLocale, t } from "../../dashboard/helpers.js";
import {
  buildFontCatalogSignature,
  buildPresetCatalogSignature,
  extractPrimaryFontFamily,
  getLineSlotNames,
  getUiThemePresets,
  inheritLabel,
  shouldSkipStyleControlRenderSync,
  normalizeOverrideFieldValue,
  normalizeStyle,
  setSelectOptions,
  styleSlotLabel,
} from "./style-editor-panel-shared.js";

export function collectStyleEditorElements(root) {
  return {
    preset: root.querySelector("#subtitle-style-preset"),
    customName: root.querySelector("#subtitle-style-custom-name"),
    saveCustomBtn: root.querySelector("#subtitle-style-save-custom-btn"),
    deleteCustomBtn: root.querySelector("#subtitle-style-delete-custom-btn"),
    description: root.querySelector("#subtitle-style-preset-description"),
    status: root.querySelector("#subtitle-style-custom-status"),
    // The Fonts surface lives in the Settings tab (separate root) so we look it
    // up against the document. IDs are unique app-wide; resolved references stay
    // stable for the lifetime of the panel.
    fontRefreshBtn: document.querySelector("#font-refresh-btn"),
    projectFontsDir: document.querySelector("#project-fonts-dir"),
    fontSourceStatus: document.querySelector("#font-source-status"),
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
      applyPreset: root.querySelector("#style-line-slot-apply-preset"),
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
}

function ensureSlotTabs(elements, snapshot, actions) {
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

function ensureFontPickers(elements, snapshot, style, catalogState) {
  const signature = buildFontCatalogSignature(snapshot.fontCatalog || {});
  if (signature === catalogState.lastFontCatalogSignature && elements.fields.font_family?.options?.length) {
    return;
  }
  catalogState.lastFontCatalogSignature = signature;
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
    // The preset's font_family is a full chain ("Mochiy Pop One Regular",
    // "Comfortaa Bold", ...) but each dropdown option is a single quoted
    // family. Pick the first name in the chain so the dropdown actually
    // reflects what the preset asked for; otherwise it stays blank and
    // the user can't tell which font is in use.
    elements.fields.font_family.value = extractPrimaryFontFamily(style.base.font_family);
  }

  const slotOptions = [{ value: "", label: inheritLabel() }, ...baseOptions];
  setSelectOptions(elements.lineSlots.fields.font_family, slotOptions);
}

export function renderStyleEditorPanel(snapshot, elements, { actions }, catalogState) {
  const presets = snapshot.subtitleStylePresets || {};
  const style = normalizeStyle(snapshot.config?.subtitle_style, presets);
  const ui = snapshot.config?.ui || {};
  const palette = ui?.palette || {};
  const uiThemePresets = getUiThemePresets();

  ensureSlotTabs(elements, snapshot, actions);
  ensureFontPickers(elements, snapshot, style, catalogState);

  if (elements.preset) {
    const presetSignature = buildPresetCatalogSignature(presets);
    const shouldRebuildPresets = !elements.preset.options.length || presetSignature !== catalogState.lastPresetCatalogSignature;
    if (shouldRebuildPresets) {
      catalogState.lastPresetCatalogSignature = presetSignature;
      const previousSelection = String(elements.preset.value || "").trim();
      elements.preset.innerHTML = "";
      Object.entries(presets).forEach(([presetName, preset]) => {
        const option = document.createElement("option");
        option.value = presetName;
        option.textContent = preset?.label || presetName;
        elements.preset.appendChild(option);
      });
      const desired = String(style.preset || "").trim() || "clean_default";
      const fallback = presets[desired]
        ? desired
        : presets[previousSelection]
          ? previousSelection
          : presets.clean_default
            ? "clean_default"
            : Object.keys(presets)[0] || "clean_default";
      elements.preset.value = fallback;
    } else {
      elements.preset.value = style.preset && presets[style.preset] ? style.preset : elements.preset.value || "clean_default";
    }
  }
  if (elements.description) {
    elements.description.textContent =
      style.description ||
      t("style.preset.default_description");
  }
  if (elements.status) {
    elements.status.textContent =
      style.built_in === false
        ? t("style.preset.editing_custom", { name: style.label || style.preset })
        : t("style.preset.editing_builtin", { name: style.label || style.preset });
  }
  if (elements.projectFontsDir) {
    elements.projectFontsDir.textContent = snapshot.fontCatalog?.project_fonts_dir || "fonts";
  }
  if (elements.fontSourceStatus) {
    elements.fontSourceStatus.textContent = t("style.font_catalog.counts", {
      projectCount: snapshot.fontCatalog?.project_local?.length || 0,
      systemCount: snapshot.fontCatalog?.system?.length || 0,
    });
  }
  if (elements.uiTheme.mode) {
    elements.uiTheme.mode.value = String(ui?.theme || "dark");
  }

  if (elements.uiTheme.preset) {
    if (!elements.uiTheme.preset.options.length) {
      const options = uiThemePresets.map((preset) => ({
        value: preset.id,
        label: preset.label(),
      }));
      setSelectOptions(elements.uiTheme.preset, options);
    } else {
      [...elements.uiTheme.preset.options].forEach((option) => {
        const preset = uiThemePresets.find((item) => item.id === option.value);
        if (preset) {
          option.textContent = preset.label();
        }
      });
    }
    if (!String(elements.uiTheme.preset.value || "").trim()) {
      elements.uiTheme.preset.value = "custom";
    }
  }
  if (elements.uiTheme.accent && !shouldSkipStyleControlRenderSync(elements.uiTheme.accent)) {
    elements.uiTheme.accent.value = String(palette?.accent || "#6cc7ff");
  }
  if (elements.uiTheme.accentSecondary && !shouldSkipStyleControlRenderSync(elements.uiTheme.accentSecondary)) {
    elements.uiTheme.accentSecondary.value = String(palette?.accent_secondary || "#ff6ce6");
  }
  if (elements.uiTheme.accentTertiary && !shouldSkipStyleControlRenderSync(elements.uiTheme.accentTertiary)) {
    elements.uiTheme.accentTertiary.value = String(palette?.accent_tertiary || "#7ce3ad");
  }
  Object.entries(elements.fields).forEach(([key, element]) => {
    if (!element) {
      return;
    }
    if (shouldSkipStyleControlRenderSync(element)) {
      return;
    }
    if (key === "font_family") {
      // Mirror ensureFontPickers: collapse the preset's font-family chain
      // down to its primary family so the dropdown option that represents
      // the *registered* face actually matches and gets highlighted.
      element.value = extractPrimaryFontFamily(style.base?.font_family);
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
      ? t("style.slot.enabled_hint", { slotLabel: styleSlotLabel(activeSlot) })
      : t("style.slot.disabled_hint", { slotLabel: styleSlotLabel(activeSlot) });
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
    if (shouldSkipStyleControlRenderSync(element)) {
      return;
    }
    const raw = slotStyle?.[key];
    if (key === "font_family") {
      // Slot overrides can also carry a full chain (when "Apply preset to
      // this slot" is used). Normalise to the primary family so the slot
      // dropdown matches one of its registered options instead of
      // silently going blank.
      element.value = raw ? extractPrimaryFontFamily(raw) : "";
    } else {
      element.value = normalizeOverrideFieldValue(raw);
    }
    element.disabled = !slotEnabled;
  });

  // Build the "Apply preset to this slot" dropdown. It mirrors the base
  // preset list (so users can copy any preset's base style onto a single
  // line slot) and stays disabled while the slot override itself is off.
  if (elements.lineSlots.applyPreset) {
    const slotPresetSignature = buildPresetCatalogSignature(presets);
    const slotPresetSignatureKey = `slot:${slotPresetSignature}`;
    if (catalogState.lastLineSlotPresetSignature !== slotPresetSignatureKey) {
      catalogState.lastLineSlotPresetSignature = slotPresetSignatureKey;
      const placeholderLabel = t("style.slot.pick_preset_placeholder");
      const presetOptions = [
        { value: "", label: placeholderLabel },
        ...Object.entries(presets).map(([presetName, preset]) => ({
          value: presetName,
          label: preset?.label || presetName,
        })),
      ];
      setSelectOptions(elements.lineSlots.applyPreset, presetOptions);
    }
    // The selector is one-shot: applying a preset writes its base into the
    // slot, then we reset it back to the placeholder so the field doesn't
    // pretend the slot is "bound" to that preset (the slot is a free-form
    // override after application).
    elements.lineSlots.applyPreset.value = "";
    elements.lineSlots.applyPreset.disabled = !slotEnabled;
  }
}
