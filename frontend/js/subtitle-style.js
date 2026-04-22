(function () {
  const LINE_SLOT_NAMES = [
    "source",
    "translation_1",
    "translation_2",
    "translation_3",
    "translation_4",
    "translation_5",
  ];

  const DEFAULT_BASE_STYLE = {
    font_family: '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif',
    font_size_px: 30,
    font_weight: 700,
    fill_color: "#ffffff",
    stroke_color: "#000000",
    stroke_width_px: 2,
    shadow_color: "#000000",
    shadow_blur_px: 10,
    shadow_offset_x_px: 0,
    shadow_offset_y_px: 3,
    background_color: "#000000",
    background_opacity: 0,
    background_padding_x_px: 12,
    background_padding_y_px: 4,
    background_radius_px: 10,
    line_spacing_em: 1.15,
    letter_spacing_em: 0,
    text_align: "center",
    line_gap_px: 8,
    effect: "none",
  };

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function buildEmptyLineSlots() {
    return LINE_SLOT_NAMES.reduce((accumulator, slotName) => {
      accumulator[slotName] = { enabled: false };
      return accumulator;
    }, {});
  }

  function fallbackPresets() {
    return {
      clean_default: {
        preset: "clean_default",
        label: "Clean Default",
        description: "Balanced white subtitles with readable outline and no extra effects.",
        built_in: true,
        base: clone(DEFAULT_BASE_STYLE),
        line_slots: buildEmptyLineSlots(),
      },
    };
  }

  function getPresetCatalog(presets) {
    return presets && typeof presets === "object" && Object.keys(presets).length ? presets : fallbackPresets();
  }

  function buildStyleFromPreset(presets, presetName) {
    const catalog = getPresetCatalog(presets);
    const current = catalog[presetName] || catalog.clean_default || Object.values(catalog)[0];
    return {
      preset: current.preset || presetName || "clean_default",
      label: current.label || "Subtitle Style",
      description: current.description || "",
      built_in: current.built_in !== false,
      recommended_max_visible_lines: current.recommended_max_visible_lines || null,
      base: clone(current.base || {}),
      line_slots: normalizeLineSlots(current.line_slots || {}),
      custom_presets: clone(current.custom_presets || {}),
    };
  }

  function clampInt(value, fallback, min, max) {
    const parsed = Number.parseInt(String(value), 10);
    const normalized = Number.isFinite(parsed) ? parsed : fallback;
    return Math.max(min, Math.min(max, normalized));
  }

  function clampFloat(value, fallback, min, max) {
    const parsed = Number.parseFloat(String(value));
    const normalized = Number.isFinite(parsed) ? parsed : fallback;
    return Math.max(min, Math.min(max, normalized));
  }

  function normalizeColor(value, fallback) {
    const normalized = String(value || "").trim();
    return normalized || fallback;
  }

  function normalizeBaseStyle(rawBase) {
    const defaults = DEFAULT_BASE_STYLE;
    const current = rawBase && typeof rawBase === "object" ? rawBase : {};
    const textAlign = ["left", "center", "right"].includes(String(current.text_align || "").toLowerCase())
      ? String(current.text_align).toLowerCase()
      : defaults.text_align;
    const effect = ["none", "fade", "subtle_pop"].includes(String(current.effect || "").toLowerCase())
      ? String(current.effect).toLowerCase()
      : defaults.effect;

    return {
      font_family: String(current.font_family || defaults.font_family),
      font_size_px: clampInt(current.font_size_px, defaults.font_size_px, 12, 96),
      font_weight: clampInt(current.font_weight, defaults.font_weight, 300, 900),
      fill_color: normalizeColor(current.fill_color, defaults.fill_color),
      stroke_color: normalizeColor(current.stroke_color, defaults.stroke_color),
      stroke_width_px: clampInt(current.stroke_width_px, defaults.stroke_width_px, 0, 8),
      shadow_color: normalizeColor(current.shadow_color, defaults.shadow_color),
      shadow_blur_px: clampInt(current.shadow_blur_px, defaults.shadow_blur_px, 0, 32),
      shadow_offset_x_px: clampInt(current.shadow_offset_x_px, defaults.shadow_offset_x_px, -24, 24),
      shadow_offset_y_px: clampInt(current.shadow_offset_y_px, defaults.shadow_offset_y_px, -24, 24),
      background_color: normalizeColor(current.background_color, defaults.background_color),
      background_opacity: clampInt(current.background_opacity, defaults.background_opacity, 0, 100),
      background_padding_x_px: clampInt(current.background_padding_x_px, defaults.background_padding_x_px, 0, 40),
      background_padding_y_px: clampInt(current.background_padding_y_px, defaults.background_padding_y_px, 0, 24),
      background_radius_px: clampInt(current.background_radius_px, defaults.background_radius_px, 0, 40),
      line_spacing_em: Number(clampFloat(current.line_spacing_em, defaults.line_spacing_em, 0.8, 2.2).toFixed(2)),
      letter_spacing_em: Number(clampFloat(current.letter_spacing_em, defaults.letter_spacing_em, -0.08, 0.2).toFixed(3)),
      text_align: textAlign,
      line_gap_px: clampInt(current.line_gap_px, defaults.line_gap_px, 0, 40),
      effect,
    };
  }

  function normalizeOverrideStyle(rawOverride) {
    const current = rawOverride && typeof rawOverride === "object" ? rawOverride : {};
    const normalizedBase = normalizeBaseStyle(current);
    const normalized = { enabled: Boolean(current.enabled) };
    Object.keys(normalizedBase).forEach((key) => {
      normalized[key] = current[key] === "" || current[key] == null ? null : normalizedBase[key];
    });
    return normalized;
  }

  function normalizeLineSlots(rawLineSlots, presetLineSlots, legacySourceOverride, legacyTranslationOverride) {
    const current = rawLineSlots && typeof rawLineSlots === "object" ? rawLineSlots : {};
    const presetSlots = presetLineSlots && typeof presetLineSlots === "object" ? presetLineSlots : {};
    const normalized = buildEmptyLineSlots();
    LINE_SLOT_NAMES.forEach((slotName) => {
      let source = current[slotName];
      if (source == null) {
        source = presetSlots[slotName];
      }
      if (source == null && slotName === "source" && legacySourceOverride && typeof legacySourceOverride === "object") {
        source = legacySourceOverride;
      }
      if (
        source == null &&
        slotName.startsWith("translation_") &&
        legacyTranslationOverride &&
        typeof legacyTranslationOverride === "object"
      ) {
        source = legacyTranslationOverride;
      }
      normalized[slotName] = normalizeOverrideStyle(source || {});
    });
    return normalized;
  }

  function normalizeCustomPresets(rawCustomPresets) {
    const current = rawCustomPresets && typeof rawCustomPresets === "object" ? rawCustomPresets : {};
    const normalized = {};
    Object.entries(current).forEach(([presetName, presetPayload]) => {
      normalized[presetName] = normalizeStyleConfig(
        {
          ...(presetPayload || {}),
          preset: presetName,
        },
        { ...fallbackPresets(), ...normalized }
      );
      normalized[presetName].built_in = false;
      normalized[presetName].label = presetPayload?.label || presetName;
      normalized[presetName].description = presetPayload?.description || "User-created local subtitle style.";
    });
    return normalized;
  }

  function normalizeStyleConfig(rawStyle, presets) {
    const current = rawStyle && typeof rawStyle === "object" ? rawStyle : {};
    const customPresets = normalizeCustomPresets(current.custom_presets || {});
    const catalog = {
      ...getPresetCatalog(presets),
      ...customPresets,
    };
    const presetName = String(current.preset || "clean_default");
    const presetStyle = buildStyleFromPreset(catalog, presetName);
    return {
      preset: presetStyle.preset,
      label: current.label || presetStyle.label,
      description: current.description || presetStyle.description,
      built_in: presetStyle.built_in !== false,
      recommended_max_visible_lines: current.recommended_max_visible_lines || presetStyle.recommended_max_visible_lines || null,
      base: normalizeBaseStyle(current.base || presetStyle.base),
      line_slots: normalizeLineSlots(
        current.line_slots,
        presetStyle.line_slots,
        current.source_override,
        current.translation_override
      ),
      custom_presets: customPresets,
    };
  }

  function mergeLineStyle(baseStyle, overrideStyle) {
    if (!overrideStyle?.enabled) {
      return clone(baseStyle);
    }
    const merged = clone(baseStyle);
    Object.keys(baseStyle).forEach((key) => {
      if (overrideStyle[key] !== null && overrideStyle[key] !== undefined && overrideStyle[key] !== "") {
        merged[key] = overrideStyle[key];
      }
    });
    return merged;
  }

  function resolveEffectiveStyle(rawStyle, presets) {
    const normalized = normalizeStyleConfig(rawStyle, presets);
    const base = clone(normalized.base);
    const lineSlots = {};
    LINE_SLOT_NAMES.forEach((slotName) => {
      lineSlots[slotName] = mergeLineStyle(base, normalized.line_slots?.[slotName] || { enabled: false });
    });
    return {
      preset: normalized.preset,
      label: normalized.label,
      description: normalized.description,
      built_in: normalized.built_in !== false,
      recommended_max_visible_lines: normalized.recommended_max_visible_lines || null,
      effect: base.effect,
      container: {
        text_align: base.text_align,
        line_gap_px: base.line_gap_px,
      },
      base,
      line_slots: lineSlots,
      roles: {
        source: lineSlots.source,
        translation: lineSlots.translation_1,
      },
    };
  }

  function colorToRgba(color, opacityPercent) {
    const normalized = String(color || "").trim();
    const alpha = Math.max(0, Math.min(1, Number(opacityPercent || 0) / 100));
    if (!normalized || alpha <= 0) {
      return "transparent";
    }
    const hex = normalized.replace("#", "");
    if (/^[0-9a-fA-F]{3}$/.test(hex)) {
      const r = Number.parseInt(`${hex[0]}${hex[0]}`, 16);
      const g = Number.parseInt(`${hex[1]}${hex[1]}`, 16);
      const b = Number.parseInt(`${hex[2]}${hex[2]}`, 16);
      return `rgba(${r}, ${g}, ${b}, ${alpha.toFixed(2)})`;
    }
    if (/^[0-9a-fA-F]{6}$/.test(hex)) {
      const r = Number.parseInt(hex.slice(0, 2), 16);
      const g = Number.parseInt(hex.slice(2, 4), 16);
      const b = Number.parseInt(hex.slice(4, 6), 16);
      return `rgba(${r}, ${g}, ${b}, ${alpha.toFixed(2)})`;
    }
    return alpha >= 1 ? normalized : "transparent";
  }

  function inferStyleSlot(item, translationIndex) {
    if (item?.style_slot) {
      return item.style_slot;
    }
    if (item?.kind === "translation") {
      return `translation_${Math.max(1, Math.min(5, translationIndex + 1))}`;
    }
    return "source";
  }

  function composeRenderRows(payload) {
    const visibleItems = Array.isArray(payload?.visible_items)
      ? payload.visible_items.filter((item) => item && item.text)
      : [];
    const activePartialText = String(payload?.active_partial_text || "");
    const allowSourcePartialPreview = payload?.show_source !== false;

    if (!payload?.completed_block_visible && allowSourcePartialPreview && activePartialText) {
      return [
        {
          rowSlot: "source",
          entries: [{ kind: "source", text: activePartialText, style_slot: "source" }],
        },
      ];
    }

    if (!payload?.completed_block_visible || !visibleItems.length) {
      return [];
    }

    let translationIndex = 0;
    const entries = visibleItems.map((item) => {
      const slotName = inferStyleSlot(item, translationIndex);
      if (item.kind === "translation") {
        translationIndex += 1;
      }
      return {
        kind: item.kind || "source",
        lang: item.lang || "",
        text: item.text || "",
        style_slot: slotName,
      };
    });

    if (payload.preset === "single") {
      return [{ rowSlot: entries[0]?.style_slot || "source", entries }];
    }

    if (payload.preset === "dual-line") {
      const firstEntry = entries[0] ? [{ ...entries[0] }] : [];
      const remainingEntries = entries.slice(1);
      return [
        firstEntry.length ? { rowSlot: firstEntry[0].style_slot, entries: firstEntry } : null,
        remainingEntries.length ? { rowSlot: remainingEntries[0].style_slot, entries: remainingEntries } : null,
      ].filter(Boolean);
    }

    return entries.map((entry) => ({
      rowSlot: entry.style_slot,
      entries: [entry],
    }));
  }

  function buildCssVariables(roleStyle, scale) {
    const styleScale = Number.isFinite(scale) ? scale : 1;
    const shadow = roleStyle.shadow_blur_px > 0
      ? `${roleStyle.shadow_offset_x_px}px ${roleStyle.shadow_offset_y_px}px ${roleStyle.shadow_blur_px}px ${colorToRgba(
          roleStyle.shadow_color,
          100
        )}`
      : "none";
    return {
      "--subtitle-font-family": roleStyle.font_family,
      "--subtitle-font-size": `${Math.max(12, Math.round(roleStyle.font_size_px * styleScale))}px`,
      "--subtitle-font-weight": String(roleStyle.font_weight),
      "--subtitle-fill": roleStyle.fill_color,
      "--subtitle-stroke": roleStyle.stroke_color,
      "--subtitle-stroke-width": `${Math.max(0, Math.round(roleStyle.stroke_width_px * styleScale))}px`,
      "--subtitle-shadow": shadow,
      "--subtitle-background": colorToRgba(roleStyle.background_color, roleStyle.background_opacity),
      "--subtitle-radius": `${Math.max(0, Math.round(roleStyle.background_radius_px * styleScale))}px`,
      "--subtitle-padding-x": `${Math.max(0, Math.round(roleStyle.background_padding_x_px * styleScale))}px`,
      "--subtitle-padding-y": `${Math.max(0, Math.round(roleStyle.background_padding_y_px * styleScale))}px`,
      "--subtitle-line-height": String(roleStyle.line_spacing_em),
      "--subtitle-letter-spacing": `${roleStyle.letter_spacing_em}em`,
      "--subtitle-text-align": roleStyle.text_align,
    };
  }

  function applyStyleMap(element, styleMap) {
    Object.entries(styleMap).forEach(([key, value]) => {
      element.style.setProperty(key, value);
    });
  }

  function render(container, payload, options) {
    if (!container) {
      return { empty: true };
    }
    const presets = options?.presets || null;
    const effectiveStyle = payload?.style && Object.keys(payload.style).length
      ? payload.style
      : resolveEffectiveStyle(options?.styleConfig || null, presets);
    const rows = composeRenderRows(payload);
    const wrapper = document.createElement("div");
    wrapper.className = `subtitle-stage-shell${options?.overlay ? " is-overlay-shell" : ""}`;
    const stage = document.createElement("div");
    const layoutPreset = payload?.preset || "stacked";
    stage.className = `subtitle-stage layout-${layoutPreset}${payload?.compact ? " is-compact" : ""}`;
    stage.style.setProperty("--subtitle-line-gap", `${Math.max(0, effectiveStyle.container?.line_gap_px || 0)}px`);

    const stageScale = payload?.compact ? 0.88 : 1;
    rows.forEach((rowConfig, rowIndex) => {
      const row = document.createElement("div");
      row.className = "subtitle-line";
      row.dataset.slot = rowConfig.rowSlot || "source";
      row.style.setProperty(
        "--subtitle-text-align",
        effectiveStyle.line_slots?.[rowConfig.rowSlot]?.text_align ||
          effectiveStyle.container?.text_align ||
          "center"
      );
      const content = document.createElement("div");
      content.className = `subtitle-line__content subtitle-line__content--${layoutPreset}`;

      rowConfig.entries.forEach((entry, entryIndex) => {
        const lineStyle = effectiveStyle.line_slots?.[entry.style_slot] || effectiveStyle.base || {};
        const surface = document.createElement("div");
        surface.className = `subtitle-line__surface subtitle-slot-${entry.style_slot} effect-${
          lineStyle.effect || effectiveStyle.effect || "none"
        }`;
        surface.dataset.slot = entry.style_slot || "source";
        surface.dataset.kind = entry.kind || "source";
        surface.dataset.row = String(rowIndex);
        surface.dataset.index = String(entryIndex);
        applyStyleMap(surface, buildCssVariables(lineStyle, stageScale));
        surface.textContent = entry.text;
        content.appendChild(surface);
      });

      row.appendChild(content);
      stage.appendChild(row);
    });

    wrapper.appendChild(stage);
    container.innerHTML = "";
    container.appendChild(wrapper);
    return {
      empty: rows.length === 0,
      rowCount: rows.length,
      effectiveStyle,
      rows,
    };
  }

  window.SubtitleStyleRenderer = {
    LINE_SLOT_NAMES,
    buildStyleFromPreset,
    normalizeStyleConfig,
    resolveEffectiveStyle,
    composeRenderRows,
    render,
  };
})();
