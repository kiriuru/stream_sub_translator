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
        description: "",
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
    const effect = ["none", "fade", "subtle_pop", "slide_up", "zoom_in", "blur_in", "glow"].includes(String(current.effect || "").toLowerCase())
      ? String(current.effect).toLowerCase()
      : defaults.effect;

    return {
      font_family: String(current.font_family || defaults.font_family),
      font_size_px: clampInt(current.font_size_px, defaults.font_size_px, 12, 96),
      font_weight: clampInt(current.font_weight, defaults.font_weight, 300, 900),
      fill_color: normalizeColor(current.fill_color, defaults.fill_color),
      stroke_color: normalizeColor(current.stroke_color, defaults.stroke_color),
      stroke_width_px: Number(clampFloat(current.stroke_width_px, defaults.stroke_width_px, 0, 8).toFixed(2)),
      shadow_color: normalizeColor(current.shadow_color, defaults.shadow_color),
      shadow_blur_px: Number(clampFloat(current.shadow_blur_px, defaults.shadow_blur_px, 0, 32).toFixed(2)),
      shadow_offset_x_px: Number(clampFloat(current.shadow_offset_x_px, defaults.shadow_offset_x_px, -24, 24).toFixed(2)),
      shadow_offset_y_px: Number(clampFloat(current.shadow_offset_y_px, defaults.shadow_offset_y_px, -24, 24).toFixed(2)),
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
          entries: [{ kind: "source", text: activePartialText, style_slot: "source", transient: true }],
        },
      ];
    }

    if (!payload?.completed_block_visible || !visibleItems.length) {
      return [];
    }

    // When the backend lifecycle state is "completed_with_partial" — i.e. the
    // PREVIOUS phrase's completed translation is still visible while the
    // NEXT phrase is being typed — the presentation layer mixes the live
    // partial text into `visible_items[source]` instead of leaving the old
    // completed source there. Without explicitly marking that source entry
    // as transient here, the renderer treats every keystroke as a brand
    // new completed entry: the shape signature changes on every frame,
    // the fast path bails to the slow path, a fresh surface is created,
    // and the completion animation fires repeatedly. That's the
    // "когда появляется перевод, исходник постоянно перерендерится"
    // regression. Translations keep their completed semantics because
    // they appear once per phrase and don't need typewriter-incremental
    // treatment (matches the explicit user request to leave translations
    // on the old logic).
    const livePartialSourceInVisibleItems =
      payload?.lifecycle_state === "completed_with_partial"
      && activePartialText.length > 0;
    let translationIndex = 0;
    const entries = visibleItems.map((item) => {
      const slotName = inferStyleSlot(item, translationIndex);
      if (item.kind === "translation") {
        translationIndex += 1;
      }
      const isLivePartialSource =
        livePartialSourceInVisibleItems
        && item.kind === "source"
        && String(item.text || "") === activePartialText;
      return {
        kind: item.kind || "source",
        lang: item.lang || "",
        text: item.text || "",
        style_slot: slotName,
        transient: isLivePartialSource,
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
    const scaledStrokeWidth = Number(
      Math.max(0, Number(roleStyle.stroke_width_px || 0) * styleScale).toFixed(2)
    );
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
      "--subtitle-stroke-width": `${scaledStrokeWidth}px`,
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

  function effectClassName(effect) {
    const normalized = String(effect || "none").trim().toLowerCase().replace(/_/g, "-") || "none";
    return `effect-${normalized}`;
  }

  function renderEntrySignature(entry) {
    return [
      entry.transient ? "partial" : "completed",
      entry.style_slot || "source",
      entry.kind || "source",
      entry.lang || "",
      entry.text || "",
    ].join("\u001f");
  }

  function shouldAnimateEntry(entry, previousEntrySignatures) {
    if (entry.transient) {
      return false;
    }
    return !previousEntrySignatures.has(renderEntrySignature(entry));
  }

  function applyStyleMap(element, styleMap) {
    Object.entries(styleMap).forEach(([key, value]) => {
      element.style.setProperty(key, value);
    });
  }

  // Compute the longest character prefix two strings share. Used to split a
  // growing partial subtitle into "already-shown static prefix" and "freshly
  // appended characters that should run the chosen effect" — the existing
  // prefix must remain visually static across partial frames.
  function commonPrefixLength(current, previous) {
    const cur = String(current || "");
    const prev = String(previous || "");
    const limit = Math.min(cur.length, prev.length);
    let index = 0;
    while (index < limit && cur.charCodeAt(index) === prev.charCodeAt(index)) {
      index += 1;
    }
    return index;
  }

  // Classify a partial-frame transition between two consecutive partial texts
  // so the debug trace (and downstream flicker heuristics) can distinguish
  // healthy typewriter extensions from disruptive recogniser revisions.
  // Values:
  //   "initial"   - previous text was empty (first partial of a phrase)
  //   "identical" - text unchanged across frames (no fresh chars)
  //   "extension" - current text starts with previous text (pure append)
  //   "shrink"    - current text is a strict prefix of previous text (rollback)
  //   "revision"  - current text shares a non-empty prefix but is not a
  //                 simple extension/shrink (recogniser changed mid-word)
  //   "jump"      - current and previous share no prefix (full replacement)
  function classifyPartialTransition(currentText, previousText, sharedLength) {
    if (!previousText) {
      return "initial";
    }
    if (currentText === previousText) {
      return "identical";
    }
    if (sharedLength === previousText.length) {
      return "extension";
    }
    if (sharedLength === currentText.length && currentText.length < previousText.length) {
      return "shrink";
    }
    if (sharedLength === 0) {
      return "jump";
    }
    return "revision";
  }

  function appendTransientFragments(surface, entry, slotEffect, previousPartialText, options) {
    const currentText = String(entry.text || "");
    const sharedLength = commonPrefixLength(currentText, previousPartialText);
    const staticPart = currentText.slice(0, sharedLength);
    const freshPart = currentText.slice(sharedLength);
    // Always create the static span — even when empty on the very first
    // partial — so the next pure-extension frame can reuse this surface
    // via updateTransientSurfaceInPlace() instead of falling back to a
    // full DOM rebuild. The empty span has no animation and zero layout
    // impact; without it the in-place reuse fast-path was unreachable on
    // the second partial of every utterance, which produced the
    // "sometimes flickers" symptom reported against v0.4.2.
    const staticSpan = document.createElement("span");
    staticSpan.className = "subtitle-fragment-static";
    staticSpan.textContent = staticPart;
    surface.appendChild(staticSpan);
    if (freshPart) {
      const freshSpan = document.createElement("span");
      const effectClass = effectClassName(slotEffect || "none");
      freshSpan.className = `subtitle-fragment-fresh ${effectClass}`;
      freshSpan.textContent = freshPart;
      surface.appendChild(freshSpan);
    }
    if (options && typeof options.onTrace === "function") {
      try {
        options.onTrace({
          slot: entry.style_slot || "source",
          kind: entry.kind || "source",
          transient: true,
          effect: String(slotEffect || "none"),
          current_text_length: currentText.length,
          previous_text_length: String(previousPartialText || "").length,
          shared_length: sharedLength,
          static_chars: staticPart.length,
          fresh_chars: freshPart.length,
          transition: classifyPartialTransition(currentText, String(previousPartialText || ""), sharedLength),
        });
      } catch (_error) {
        // Tracing must never break rendering.
      }
    }
  }

  // Debug tracing hook: callers may pass `options.onRenderTrace = (event) => void`
  // (or `options.debugTrace`) to receive structured per-frame diagnostics. The
  // renderer emits three event types:
  //   { type: "partial_frame", slot, transition, shared_length, static_chars,
  //     fresh_chars, current_text_length, previous_text_length, effect }
  //   { type: "completed_frame", slot, text_length, effect, animated }
  //   { type: "render_summary", rows, partial_entries, completed_entries,
  //     state_carryover, ms_since_last_render, anomalies }
  // Anomalies array currently flags partial frames where transition is
  // "revision" or "jump" (most common cause of visible flicker when the ASR
  // back-end revises its hypothesis mid-utterance), and frames where the
  // per-container state was unexpectedly lost between calls.
  function _resolveTraceCallback(options) {
    if (!options) {
      return null;
    }
    const candidate = options.onRenderTrace || options.debugTrace || null;
    return typeof candidate === "function" ? candidate : null;
  }

  function _safeEmit(trace, event) {
    if (!trace) {
      return;
    }
    try {
      trace(event);
    } catch (_error) {
      // Tracing must never break rendering.
    }
  }

  // Update an *existing* transient surface element in place for a pure-extension
  // partial frame. Returns true when the in-place update succeeded; false when
  // the previous surface structure was unsuitable and the caller must fall back
  // to a full rebuild.
  //
  // Why this exists: the default render path wipes `container.innerHTML` and
  // recreates every node every frame. For partials that grow by one or two
  // characters at a time, that means even the "static" prefix span is a brand
  // new DOM node on each frame, which the browser may paint as a tiny layout
  // flash. By keeping the same `surface` + `staticSpan` DOM elements across
  // consecutive partial frames and only swapping in a new `fresh` span for the
  // newly-appended characters, we get:
  //   * static prefix that is byte-for-byte stable across frames (no flash)
  //   * fresh suffix as a brand-new DOM node, so its CSS animation fires once
  //     per growth step (and exactly on the new characters)
  function updateTransientSurfaceInPlace(surface, entry, slotEffect, previousText, options) {
    const currentText = String(entry.text || "");
    const sharedLength = commonPrefixLength(currentText, previousText);
    const isPureExtension =
      previousText.length > 0 && sharedLength === previousText.length;
    if (!isPureExtension && currentText !== previousText) {
      return false;
    }
    const staticSpan = surface.querySelector(".subtitle-fragment-static");
    if (!staticSpan) {
      return false;
    }
    const oldFreshSpan = surface.querySelector(".subtitle-fragment-fresh");
    const newStaticText = currentText.slice(0, sharedLength);
    const newFreshText = currentText.slice(sharedLength);
    if (staticSpan.textContent !== newStaticText) {
      staticSpan.textContent = newStaticText;
    }
    if (oldFreshSpan && oldFreshSpan.parentNode === surface) {
      surface.removeChild(oldFreshSpan);
    }
    if (newFreshText) {
      const freshSpan = document.createElement("span");
      const effectClass = effectClassName(slotEffect || "none");
      freshSpan.className = `subtitle-fragment-fresh ${effectClass}`;
      freshSpan.textContent = newFreshText;
      surface.appendChild(freshSpan);
    }
    if (options && typeof options.onTrace === "function") {
      try {
        options.onTrace({
          slot: entry.style_slot || "source",
          kind: entry.kind || "source",
          transient: true,
          effect: String(slotEffect || "none"),
          current_text_length: currentText.length,
          previous_text_length: previousText.length,
          shared_length: sharedLength,
          static_chars: newStaticText.length,
          fresh_chars: newFreshText.length,
          transition: classifyPartialTransition(currentText, previousText, sharedLength),
          reused_surface: true,
        });
      } catch (_error) {
        // Tracing must never break rendering.
      }
    }
    return true;
  }

  // Build a layout fingerprint that is stable across pure-extension partial
  // frames but changes whenever the *shape* of the render does — different
  // row count, different slot composition, different completed text, or a
  // transient ↔ completed switch. When two consecutive renders share the
  // same shape, we keep the existing wrapper/stage/row/content DOM nodes
  // and only mutate the per-entry surfaces in place. That eliminates the
  // `container.innerHTML = ""` wipe that was repainting the whole subtitle
  // container on every keystroke and producing the v0.4.2 flicker.
  function _shapeSignatureForEntry(entry) {
    if (entry.transient) {
      return [
        "T",
        entry.style_slot || "source",
        entry.kind || "source",
        entry.lang || "",
      ].join(":");
    }
    return [
      "C",
      entry.style_slot || "source",
      entry.kind || "source",
      entry.lang || "",
      String(entry.text || ""),
    ].join(":");
  }

  function _shapeSignatureForRows(rows, layoutPreset, compact, overlay) {
    const layoutTag = `${layoutPreset || "stacked"}|${compact ? "c" : "_"}|${overlay ? "o" : "_"}`;
    if (!rows.length) {
      return `0||${layoutTag}`;
    }
    const rowSigs = rows.map((rowConfig) => {
      const entrySigs = (rowConfig.entries || []).map(_shapeSignatureForEntry).join(",");
      return `${rowConfig.rowSlot || "source"}/${entrySigs}`;
    });
    return `${rows.length}||${rowSigs.join("|")}||${layoutTag}`;
  }

  // Apply the style map only when one of its values actually changed. CSS
  // variable writes that match the current value are still treated as
  // attribute mutations by some engines and can invalidate the parent
  // container's style cache — when the fast-path is updating a still-running
  // partial we want to touch as little as possible.
  function _applyStyleMapIfChanged(element, styleMap) {
    if (!element || !styleMap) {
      return;
    }
    const current = element.__sstAppliedStyleMap || {};
    let changed = false;
    Object.entries(styleMap).forEach(([key, value]) => {
      if (current[key] !== value) {
        element.style.setProperty(key, value);
        current[key] = value;
        changed = true;
      }
    });
    if (changed) {
      element.__sstAppliedStyleMap = current;
    }
  }

  function _setClassNameIfChanged(element, className) {
    if (!element) {
      return;
    }
    if (element.className !== className) {
      element.className = className;
    }
  }

  // Decide whether the new render is *just a finalization* of the previous
  // render: every entry is in the same position with the same slot/kind/lang
  // as last frame, and the only change is that one or more transient entries
  // have flipped to completed with text matching what was last shown as a
  // partial. In this case we can keep the existing wrapper/stage/row/content
  // DOM nodes — and, critically, reuse the partial surface element by simply
  // consolidating its `<span.static>...</span><span.fresh>...</span>` children
  // into plain text. No surface-level animation fires (the text was already
  // visible to the user), and no `container.innerHTML = ""` wipe happens.
  // This is the dominant finalization shape in practice: translations arrive
  // in a *later* frame (which falls through to the slow path because the row
  // count actually changes), so source finalization frames are
  // finalization-compatible.
  function _canFastPathFinalize(rows, previousDescriptors, previousPartialBySlot) {
    if (!Array.isArray(previousDescriptors) || rows.length === 0) {
      return false;
    }
    let totalEntries = 0;
    for (const rowConfig of rows) {
      totalEntries += (rowConfig.entries || []).length;
    }
    if (totalEntries !== previousDescriptors.length) {
      return false;
    }
    let idx = 0;
    for (const rowConfig of rows) {
      for (const entry of (rowConfig.entries || [])) {
        const prev = previousDescriptors[idx];
        idx += 1;
        if (!prev) {
          return false;
        }
        const slot = entry.style_slot || "source";
        const kind = entry.kind || "source";
        const lang = entry.lang || "";
        const text = String(entry.text || "");
        if (prev.slot !== slot || prev.kind !== kind || prev.lang !== lang) {
          return false;
        }
        if (prev.transient === Boolean(entry.transient)) {
          // Same transient state: shape-equal handles this branch, so any
          // text mismatch here means the *only* difference is text of a
          // completed entry. Bail to the slow path — completed text changes
          // are rare and old-logic translations expect a fresh render.
          if (!entry.transient && prev.text !== text) {
            return false;
          }
        } else if (prev.transient && !entry.transient) {
          // T → C finalization. Only compatible if the completed text matches
          // what was last shown as a partial in this slot. If they differ,
          // the user would see the text mutate at finalize time — that's
          // exactly the kind of jump we want the slow path to handle (with
          // its built-in completion animation).
          const lastPartial = String(previousPartialBySlot.get(slot) || "");
          if (lastPartial !== text) {
            return false;
          }
        } else {
          // C → T transitions are not a finalization. Defer to slow path.
          return false;
        }
      }
    }
    return true;
  }

  // Convert a previously-transient surface into a completed surface IN PLACE.
  // The surface DOM node is preserved (same identity, same children parent),
  // its <span.static>/<span.fresh> children are replaced with a single text
  // node, and the surface-level effect class is forced to `effect-none`
  // because the text was already visible — playing the completion animation
  // would just create the "full re-render" jump the user reported.
  function _finalizeTransientSurfaceInPlace(surface, entry, traceCallback) {
    const text = String(entry.text || "");
    while (surface.firstChild) {
      surface.removeChild(surface.firstChild);
    }
    surface.textContent = text;
    _setClassNameIfChanged(
      surface,
      `subtitle-line__surface subtitle-slot-${entry.style_slot} effect-none`
    );
    if (traceCallback) {
      try {
        traceCallback({
          type: "completed_frame",
          slot: entry.style_slot || "source",
          kind: entry.kind || "source",
          effect: "none",
          text_length: text.length,
          animated: false,
          finalized_in_place: true,
        });
      } catch (_error) {
        // Tracing must never break rendering.
      }
    }
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
    const traceCallback = _resolveTraceCallback(options);
    const renderStartedAt = (typeof performance !== "undefined" && performance && typeof performance.now === "function")
      ? performance.now()
      : Date.now();
    const hadPriorRenderState = Boolean(container.__subtitleStyleRenderState);
    const renderState = container.__subtitleStyleRenderState || {};
    const previousEntrySignatures = new Set(renderState.entrySignatures || []);
    const previousPartialBySlot = new Map(
      renderState.partialBySlot instanceof Map
        ? renderState.partialBySlot
        : Object.entries(renderState.partialBySlot || {})
    );
    const previousPartialSurfaceBySlot = renderState.partialSurfaceBySlot instanceof Map
      ? new Map(renderState.partialSurfaceBySlot)
      : new Map();
    const lastRenderedAt = Number.isFinite(renderState.lastRenderedAt) ? renderState.lastRenderedAt : null;
    const previousShape = typeof renderState.shapeSignature === "string" ? renderState.shapeSignature : null;
    const previousEntrySurfaces = Array.isArray(renderState.entrySurfaces) ? renderState.entrySurfaces : null;
    const previousEntryDescriptors = Array.isArray(renderState.entryDescriptors) ? renderState.entryDescriptors : null;
    const layoutPreset = payload?.preset || "stacked";
    const overlay = Boolean(options?.overlay);
    const compact = Boolean(payload?.compact);
    const shapeSignature = _shapeSignatureForRows(rows, layoutPreset, compact, overlay);
    const stageScale = compact ? 0.88 : 1;
    const nextEntrySignatures = [];
    const nextPartialBySlot = new Map();
    const nextPartialSurfaceBySlot = new Map();
    const nextEntrySurfaces = [];
    const nextEntryDescriptors = [];
    const traceFrameEvents = traceCallback ? [] : null;
    let partialEntryCount = 0;
    let completedEntryCount = 0;
    let reusedPartialSurfaceCount = 0;
    let finalizedInPlaceCount = 0;
    let usedFastPath = false;
    const exactShapeMatch = previousShape !== null && previousShape === shapeSignature;
    const finalizationCompatible = !exactShapeMatch
      && _canFastPathFinalize(rows, previousEntryDescriptors, previousPartialBySlot);

    // -----------------------------------------------------------------
    // Fast path: same wrapper as last frame; either the shape is identical
    // (pure partial extension / unchanged completed) OR the only change is
    // one or more partials finalizing with text matching what was already
    // shown. In both cases we mutate the existing surfaces in place and
    // leave the wrapper alone. This kills the full-block re-render at
    // finalization that the user reported, while letting translation rows
    // (which only appear once and *do* change the row count) fall through
    // to the slow path so they follow the old logic.
    // -----------------------------------------------------------------
    if (
      (exactShapeMatch || finalizationCompatible)
      && previousEntrySurfaces
      && renderState.wrapper
      && renderState.wrapper.parentNode === container
      && rows.length > 0
    ) {
      const totalEntries = rows.reduce((sum, rowConfig) => sum + (rowConfig.entries || []).length, 0);
      if (previousEntrySurfaces.length === totalEntries) {
        usedFastPath = true;
        let surfaceCursor = 0;
        rows.forEach((rowConfig) => {
          rowConfig.entries.forEach((entry) => {
            const cursorIdx = surfaceCursor;
            const surface = previousEntrySurfaces[surfaceCursor];
            const prevDescriptor = previousEntryDescriptors ? previousEntryDescriptors[surfaceCursor] : null;
            surfaceCursor += 1;
            if (!surface || !surface.isConnected) {
              usedFastPath = false;
              return;
            }
            const lineStyle = effectiveStyle.line_slots?.[entry.style_slot] || effectiveStyle.base || {};
            const slotEffect = lineStyle.effect || effectiveStyle.effect || "none";
            _applyStyleMapIfChanged(surface, buildCssVariables(lineStyle, stageScale));
            const wasTransient = Boolean(prevDescriptor && prevDescriptor.transient);
            if (entry.transient) {
              partialEntryCount += 1;
              const slotName = entry.style_slot || "source";
              const previousText = previousPartialBySlot.get(slotName) || "";
              const partialTraceHook = traceCallback
                ? (partialEvent) => {
                    const enriched = { type: "partial_frame", ...partialEvent };
                    traceFrameEvents.push(enriched);
                    _safeEmit(traceCallback, enriched);
                  }
                : null;
              _setClassNameIfChanged(
                surface,
                `subtitle-line__surface subtitle-slot-${entry.style_slot} effect-none`
              );
              const reused = updateTransientSurfaceInPlace(surface, entry, slotEffect, previousText, {
                onTrace: partialTraceHook,
              });
              if (!reused) {
                // Revision/jump within the same shape — wipe the surface and
                // re-render its fragments inside the same DOM node. We still
                // avoid the wrapper rebuild, but the fresh span will play its
                // animation on the whole replacement, which matches user
                // expectations (the recogniser changed the hypothesis).
                while (surface.firstChild) {
                  surface.removeChild(surface.firstChild);
                }
                appendTransientFragments(surface, entry, slotEffect, previousText, {
                  onTrace: partialTraceHook,
                });
              } else {
                reusedPartialSurfaceCount += 1;
              }
              nextPartialBySlot.set(slotName, String(entry.text || ""));
              nextPartialSurfaceBySlot.set(slotName, surface);
            } else if (wasTransient) {
              // T → C finalization at *the same position with matching text*.
              // Consolidate the static/fresh spans into plain text on the
              // *same DOM node* so the user sees zero visual change at
              // finalization. This is the load-bearing optimisation that
              // eliminates the "renders the whole block again" jump.
              completedEntryCount += 1;
              finalizedInPlaceCount += 1;
              const finalizationTraceHook = traceCallback
                ? (event) => {
                    traceFrameEvents.push(event);
                    _safeEmit(traceCallback, event);
                  }
                : null;
              _finalizeTransientSurfaceInPlace(surface, entry, finalizationTraceHook);
              nextEntrySignatures.push(renderEntrySignature(entry));
            } else {
              completedEntryCount += 1;
              // Completed text is part of the shape signature, so identical
              // shape means identical text — leave the surface untouched.
              // We still preserve its dataset so subsequent transitions can
              // dedupe animations correctly.
              if (surface.textContent !== entry.text) {
                surface.textContent = entry.text;
              }
              const animateCompleted = false;
              _setClassNameIfChanged(
                surface,
                `subtitle-line__surface subtitle-slot-${entry.style_slot} ${animateCompleted ? effectClassName(slotEffect) : "effect-none"}`
              );
              nextEntrySignatures.push(renderEntrySignature(entry));
              if (traceCallback) {
                const event = {
                  type: "completed_frame",
                  slot: entry.style_slot || "source",
                  kind: entry.kind || "source",
                  effect: String(slotEffect || "none"),
                  text_length: String(entry.text || "").length,
                  animated: animateCompleted,
                  reused_surface: true,
                };
                traceFrameEvents.push(event);
                _safeEmit(traceCallback, event);
              }
            }
            nextEntrySurfaces.push(surface);
            nextEntryDescriptors.push({
              slot: entry.style_slot || "source",
              kind: entry.kind || "source",
              lang: entry.lang || "",
              transient: Boolean(entry.transient),
              text: String(entry.text || ""),
            });
            void cursorIdx; // present for clarity in stack traces during debug.
          });
        });
      }
    }

    if (usedFastPath) {
      const renderFinishedAt = (typeof performance !== "undefined" && performance && typeof performance.now === "function")
        ? performance.now()
        : Date.now();
      container.__subtitleStyleRenderState = {
        entrySignatures: nextEntrySignatures,
        partialBySlot: Object.fromEntries(nextPartialBySlot.entries()),
        partialSurfaceBySlot: nextPartialSurfaceBySlot,
        entrySurfaces: nextEntrySurfaces,
        entryDescriptors: nextEntryDescriptors,
        shapeSignature,
        wrapper: renderState.wrapper,
        lastRenderedAt: renderFinishedAt,
      };
      if (traceCallback) {
        const anomalies = [];
        traceFrameEvents.forEach((event) => {
          if (event.type !== "partial_frame") {
            return;
          }
          if (event.transition === "revision" || event.transition === "jump") {
            anomalies.push({
              kind: "partial_revision",
              slot: event.slot,
              transition: event.transition,
              shared_length: event.shared_length,
              fresh_chars: event.fresh_chars,
              previous_text_length: event.previous_text_length,
              current_text_length: event.current_text_length,
            });
          }
        });
        _safeEmit(traceCallback, {
          type: "render_summary",
          overlay,
          rows: rows.length,
          partial_entries: partialEntryCount,
          completed_entries: completedEntryCount,
          reused_partial_surfaces: reusedPartialSurfaceCount,
          finalized_in_place: finalizedInPlaceCount,
          state_carryover: hadPriorRenderState,
          fast_path: true,
          fast_path_reason: exactShapeMatch ? "shape_equal" : "finalization_compatible",
          shape_signature: shapeSignature,
          ms_since_last_render: lastRenderedAt !== null ? Math.max(0, renderStartedAt - lastRenderedAt) : null,
          render_duration_ms: Math.max(0, renderFinishedAt - renderStartedAt),
          anomalies,
        });
      }
      return {
        empty: rows.length === 0,
        rowCount: rows.length,
        effectiveStyle,
        rows,
      };
    }

    // -----------------------------------------------------------------
    // Slow path: structural change (or first render). Rebuild the wrapper
    // top-down. We still reuse the per-slot partial surface where possible
    // so the static prefix span is preserved even when, for example, a new
    // translation row arrives.
    // -----------------------------------------------------------------
    const wrapper = document.createElement("div");
    wrapper.className = `subtitle-stage-shell${overlay ? " is-overlay-shell" : ""}`;
    const stage = document.createElement("div");
    stage.className = `subtitle-stage layout-${layoutPreset}${compact ? " is-compact" : ""}`;
    stage.style.setProperty("--subtitle-line-gap", `${Math.max(0, effectiveStyle.container?.line_gap_px || 0)}px`);

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
        const slotEffect = lineStyle.effect || effectiveStyle.effect || "none";
        // Transient (live partial) entries never animate the surface itself —
        // we add a per-fragment span animation below so the growing prefix
        // stays visually static while only freshly appended characters run
        // the configured effect. Completed entries keep the surface-level
        // animation gated by signature dedup so they fire exactly once per
        // distinct text+slot combination.
        const animateCompleted = !entry.transient && shouldAnimateEntry(entry, previousEntrySignatures);
        const surfaceEffectClass = animateCompleted
          ? effectClassName(slotEffect)
          : "effect-none";

        let surface = null;
        let reusedSurface = false;
        if (entry.transient) {
          partialEntryCount += 1;
          const slotName = entry.style_slot || "source";
          const previousText = previousPartialBySlot.get(slotName) || "";
          const previousSurface = previousPartialSurfaceBySlot.get(slotName) || null;
          const partialTraceHook = traceCallback
            ? (partialEvent) => {
                const enriched = { type: "partial_frame", ...partialEvent };
                traceFrameEvents.push(enriched);
                _safeEmit(traceCallback, enriched);
              }
            : null;
          if (previousSurface) {
            // Detach from any prior parent (will be moved into the new wrapper
            // when we appendChild below). DOM moves don't restart CSS
            // animations on existing children, so this preserves the static
            // prefix span untouched.
            if (previousSurface.parentNode) {
              previousSurface.parentNode.removeChild(previousSurface);
            }
            const reused = updateTransientSurfaceInPlace(
              previousSurface,
              entry,
              slotEffect,
              previousText,
              { onTrace: partialTraceHook },
            );
            if (reused) {
              surface = previousSurface;
              reusedSurface = true;
              reusedPartialSurfaceCount += 1;
              surface.dataset.row = String(rowIndex);
              surface.dataset.index = String(entryIndex);
              surface.className = `subtitle-line__surface subtitle-slot-${entry.style_slot} ${surfaceEffectClass}`;
              applyStyleMap(surface, buildCssVariables(lineStyle, stageScale));
            }
          }
          if (!surface) {
            surface = document.createElement("div");
            surface.className = `subtitle-line__surface subtitle-slot-${entry.style_slot} ${surfaceEffectClass}`;
            surface.dataset.slot = entry.style_slot || "source";
            surface.dataset.kind = entry.kind || "source";
            surface.dataset.row = String(rowIndex);
            surface.dataset.index = String(entryIndex);
            applyStyleMap(surface, buildCssVariables(lineStyle, stageScale));
            appendTransientFragments(surface, entry, slotEffect, previousText, {
              onTrace: partialTraceHook,
            });
          }
          nextPartialBySlot.set(slotName, String(entry.text || ""));
          nextPartialSurfaceBySlot.set(slotName, surface);
        } else {
          completedEntryCount += 1;
          // Slow-path completed reuse strategy. The wrapper is being
          // rebuilt here (because the shape changed — typically a new
          // translation row just arrived), but the SOURCE row's content
          // hasn't actually changed visually since the previous frame.
          // We look for an existing surface to reuse, in priority order:
          //   1. A *partial* surface in the same slot whose text matches
          //      the new completed text — classic "ASR just finalized"
          //      flow with no animation needed.
          //   2. A *completed* surface from the previous render with the
          //      same slot/kind/lang/text — handles "completed source
          //      persists while translation arrives in the next frame".
          //      Without this, the source re-animates each time a
          //      translation row is added/changed, which is exactly the
          //      'got worse for effects' regression.
          // Translation rows keep the old behaviour — fresh surface,
          // fresh animation — which matches the user's request that
          // translations follow the old logic since they appear once.
          const slotName = entry.style_slot || "source";
          const entryKind = entry.kind || "source";
          const entryLang = entry.lang || "";
          const entryText = String(entry.text || "");
          const partialSurfaceForSlot = previousPartialSurfaceBySlot.get(slotName) || null;
          const lastPartialTextForSlot = String(previousPartialBySlot.get(slotName) || "");
          const canReuseAsFinalization =
            partialSurfaceForSlot
            && lastPartialTextForSlot === entryText
            && previousPartialBySlot.has(slotName);
          let reusableCompletedSurface = null;
          if (!canReuseAsFinalization && previousEntryDescriptors && previousEntrySurfaces) {
            for (let i = 0; i < previousEntryDescriptors.length; i += 1) {
              const prev = previousEntryDescriptors[i];
              if (
                prev
                && prev.transient === false
                && prev.slot === slotName
                && prev.kind === entryKind
                && prev.lang === entryLang
                && prev.text === entryText
              ) {
                reusableCompletedSurface = previousEntrySurfaces[i] || null;
                break;
              }
            }
          }
          const reuseSurface = canReuseAsFinalization
            ? partialSurfaceForSlot
            : reusableCompletedSurface;
          if (reuseSurface) {
            // Detach from its old wrapper and (for the finalization case
            // only) flush <span.static>/<span.fresh> children to plain
            // text. The completed-reuse case is already plain text and
            // doesn't need a children wipe — but a defensive wipe is
            // cheap and keeps the behaviour identical between branches.
            if (reuseSurface.parentNode) {
              reuseSurface.parentNode.removeChild(reuseSurface);
            }
            surface = reuseSurface;
            reusedSurface = true;
            if (canReuseAsFinalization) {
              finalizedInPlaceCount += 1;
            }
            while (surface.firstChild) {
              surface.removeChild(surface.firstChild);
            }
            surface.className = `subtitle-line__surface subtitle-slot-${entry.style_slot} effect-none`;
            surface.dataset.slot = entry.style_slot || "source";
            surface.dataset.kind = entry.kind || "source";
            surface.dataset.row = String(rowIndex);
            surface.dataset.index = String(entryIndex);
            applyStyleMap(surface, buildCssVariables(lineStyle, stageScale));
            surface.textContent = entry.text;
            nextEntrySignatures.push(renderEntrySignature(entry));
            if (traceCallback) {
              const event = {
                type: "completed_frame",
                slot: entry.style_slot || "source",
                kind: entry.kind || "source",
                effect: "none",
                text_length: entryText.length,
                animated: false,
                finalized_in_place: Boolean(canReuseAsFinalization),
                reused_completed_surface: Boolean(reusableCompletedSurface && !canReuseAsFinalization),
              };
              traceFrameEvents.push(event);
              _safeEmit(traceCallback, event);
            }
          } else {
            surface = document.createElement("div");
            surface.className = `subtitle-line__surface subtitle-slot-${entry.style_slot} ${surfaceEffectClass}`;
            surface.dataset.slot = entry.style_slot || "source";
            surface.dataset.kind = entry.kind || "source";
            surface.dataset.row = String(rowIndex);
            surface.dataset.index = String(entryIndex);
            applyStyleMap(surface, buildCssVariables(lineStyle, stageScale));
            surface.textContent = entry.text;
            nextEntrySignatures.push(renderEntrySignature(entry));
            if (traceCallback) {
              const event = {
                type: "completed_frame",
                slot: entry.style_slot || "source",
                kind: entry.kind || "source",
                effect: String(slotEffect || "none"),
                text_length: entryText.length,
                animated: animateCompleted,
              };
              traceFrameEvents.push(event);
              _safeEmit(traceCallback, event);
            }
          }
        }
        content.appendChild(surface);
        nextEntrySurfaces.push(surface);
        nextEntryDescriptors.push({
          slot: entry.style_slot || "source",
          kind: entry.kind || "source",
          lang: entry.lang || "",
          transient: Boolean(entry.transient),
          text: String(entry.text || ""),
        });
        void reusedSurface; // referenced in trace metrics above.
      });

      row.appendChild(content);
      stage.appendChild(row);
    });

    wrapper.appendChild(stage);
    container.innerHTML = "";
    container.appendChild(wrapper);
    const renderFinishedAt = (typeof performance !== "undefined" && performance && typeof performance.now === "function")
      ? performance.now()
      : Date.now();
    container.__subtitleStyleRenderState = {
      entrySignatures: nextEntrySignatures,
      partialBySlot: Object.fromEntries(nextPartialBySlot.entries()),
      partialSurfaceBySlot: nextPartialSurfaceBySlot,
      entrySurfaces: nextEntrySurfaces,
      entryDescriptors: nextEntryDescriptors,
      shapeSignature,
      wrapper,
      lastRenderedAt: renderFinishedAt,
    };
    if (traceCallback) {
      const anomalies = [];
      // Detect the common "fresh suffix is most of the line because the ASR
      // back-end revised its hypothesis" case — this is the dominant cause of
      // visible flicker when the renderer otherwise looks healthy.
      traceFrameEvents.forEach((event) => {
        if (event.type !== "partial_frame") {
          return;
        }
        if (event.transition === "revision" || event.transition === "jump") {
          anomalies.push({
            kind: "partial_revision",
            slot: event.slot,
            transition: event.transition,
            shared_length: event.shared_length,
            fresh_chars: event.fresh_chars,
            previous_text_length: event.previous_text_length,
            current_text_length: event.current_text_length,
          });
        }
      });
      if (!hadPriorRenderState && partialEntryCount > 0) {
        anomalies.push({
          kind: "state_carryover_missing",
          partial_entries: partialEntryCount,
          detail: "Container had no prior __subtitleStyleRenderState when a partial entry was rendered — the previous-text prefix is unavailable, so the whole partial will animate.",
        });
      }
      const summary = {
        type: "render_summary",
        overlay: Boolean(options?.overlay),
        rows: rows.length,
        partial_entries: partialEntryCount,
        completed_entries: completedEntryCount,
        reused_partial_surfaces: reusedPartialSurfaceCount,
        finalized_in_place: finalizedInPlaceCount,
        state_carryover: hadPriorRenderState,
        fast_path: false,
        shape_signature: shapeSignature,
        previous_shape_signature: previousShape,
        ms_since_last_render: lastRenderedAt !== null ? Math.max(0, renderStartedAt - lastRenderedAt) : null,
        render_duration_ms: Math.max(0, renderFinishedAt - renderStartedAt),
        anomalies,
      };
      _safeEmit(traceCallback, summary);
    }
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
    effectClassName,
    commonPrefixLength,
    classifyPartialTransition,
    updateTransientSurfaceInPlace,
    _shapeSignatureForRows,
    _shapeSignatureForEntry,
    _canFastPathFinalize,
    _finalizeTransientSurfaceInPlace,
    render,
  };
})();
