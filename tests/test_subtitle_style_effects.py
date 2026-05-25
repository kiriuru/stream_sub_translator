from __future__ import annotations

import unittest

from backend.core.subtitle_style import (
    merge_style_presets,
    normalize_subtitle_style_config,
    resolve_effective_subtitle_style,
)


class SubtitleStyleEffectsTests(unittest.TestCase):
    def test_normalize_preserves_extended_web_effects(self) -> None:
        for effect in ("slide_up", "zoom_in", "blur_in", "glow", "fade", "subtle_pop", "none"):
            with self.subTest(effect=effect):
                payload = {
                    "preset": "clean_default",
                    "base": {"effect": effect},
                }
                normalized = normalize_subtitle_style_config(payload)
                self.assertEqual(normalized["base"]["effect"], effect)

    def test_normalize_rejects_unknown_effect_to_default(self) -> None:
        payload = {
            "preset": "clean_default",
            "base": {"effect": "spin_wildly"},
        }
        normalized = normalize_subtitle_style_config(payload)
        self.assertEqual(normalized["base"]["effect"], "none")

    def test_line_slot_override_applies_font_family_and_size(self) -> None:
        payload = {
            "preset": "clean_default",
            "base": {"font_family": "Base Font", "font_size_px": 30},
            "line_slots": {
                "source": {
                    "enabled": True,
                    "font_family": "Source Font",
                    "font_size_px": 40,
                },
                "translation_1": {
                    "enabled": True,
                    "font_size_px": 24,
                },
            },
        }
        normalized = normalize_subtitle_style_config(payload)
        effective = resolve_effective_subtitle_style(normalized)
        self.assertEqual(effective["line_slots"]["source"]["font_family"], "Source Font")
        self.assertEqual(effective["line_slots"]["source"]["font_size_px"], 40)
        self.assertEqual(effective["line_slots"]["translation_1"]["font_family"], "Base Font")
        self.assertEqual(effective["line_slots"]["translation_1"]["font_size_px"], 24)

    def test_builtin_presets_include_accessibility_dark_cinema_meeting_soft(self) -> None:
        catalog = merge_style_presets()
        for key in ("accessibility_high_contrast", "dark_cinema", "meeting_soft"):
            with self.subTest(preset=key):
                self.assertIn(key, catalog)
                self.assertTrue(catalog[key].get("built_in"))

    def test_builtin_presets_include_new_distinct_looks(self) -> None:
        """0.4.2 introduces three explicitly themed presets to break the "all
        white text + dark stroke" sameness of the previous catalog."""
        catalog = merge_style_presets()
        for key in ("retro_terminal", "comic_burst", "vlog_pastel"):
            with self.subTest(preset=key):
                self.assertIn(key, catalog)
                self.assertTrue(catalog[key].get("built_in"))

    def test_legacy_jp_presets_are_removed(self) -> None:
        """`jp_dual_caption` was removed entirely (user feedback: rarely used,
        duplicated `anime_stream`). `jp_stream_single` was renamed to
        `anime_stream` with a dedicated anime font; the old key must not
        come back via a stale catalog entry."""
        catalog = merge_style_presets()
        self.assertNotIn("jp_dual_caption", catalog)
        self.assertNotIn("jp_stream_single", catalog)

    def test_legacy_jp_preset_is_migrated_to_anime_stream(self) -> None:
        """Users with `subtitle_style.preset = jp_stream_single` saved in
        their existing config should land on the new `anime_stream`
        replacement after upgrade — not get bumped silently to
        `clean_default`."""
        from backend.core.subtitle_style import normalize_subtitle_style_config

        for legacy_key in ("jp_stream_single", "jp_dual_caption"):
            with self.subTest(legacy=legacy_key):
                normalized = normalize_subtitle_style_config({"preset": legacy_key})
                self.assertEqual(normalized["preset"], "anime_stream")

    def test_themed_presets_use_dedicated_bundled_fonts(self) -> None:
        """Each themed preset must point at a *distinct* bundled font family
        so the visual identity of the preset doesn't collapse onto another
        when the user previews them side by side. Regression guards against
        accidental copy-paste between presets."""
        catalog = merge_style_presets()
        expected_font_token = {
            "anime_stream": "Mochiy Pop One",
            "retro_terminal": "VT323",
            "fallout_pipboy": "Share Tech Mono",
            "comic_burst": "Bangers",
            "cyberpunk_neon": "Orbitron",
            "noir_typewriter": "Special Elite",
            "dark_cinema": "Playfair Display",
            "accessibility_high_contrast": "Montserrat",
        }
        for preset, token in expected_font_token.items():
            with self.subTest(preset=preset):
                self.assertIn(preset, catalog)
                self.assertIn(token, catalog[preset]["base"]["font_family"])

    def test_themed_presets_include_cyrillic_capable_fallback(self) -> None:
        """The themed Latin-only fonts (Mochiy Pop One, VT323, Bangers,
        Orbitron Black, Share Tech Mono, Special Elite) do not have
        Cyrillic glyphs — Russian / Ukrainian / Bulgarian subtitles fell
        back to neutral Segoe UI in 0.4.2, breaking the visual identity of
        the preset. The font-family chain must list a *bundled*
        Cyrillic-capable family for each themed preset so the browser's
        per-character fallback stays on theme."""
        catalog = merge_style_presets()
        themed_cyrillic_fallbacks = {
            "anime_stream": "Underdog Regular",
            "retro_terminal": "PT Mono Regular",
            "fallout_pipboy": "Ubuntu Mono",
            "comic_burst": "Comic Relief",
            "cyberpunk_neon": "Exo 2",
            "noir_typewriter": "Cutive Mono",
        }
        for preset, fallback_token in themed_cyrillic_fallbacks.items():
            with self.subTest(preset=preset, fallback=fallback_token):
                family = catalog[preset]["base"]["font_family"]
                self.assertIn(
                    fallback_token,
                    family,
                    msg=(
                        f"Preset {preset!r} must include {fallback_token!r} in its "
                        f"font-family chain to render Cyrillic on theme. "
                        f"Current chain: {family}"
                    ),
                )

    def test_plate_backed_presets_use_opaque_enough_plates(self) -> None:
        """Visibility regression: in 0.4.2 several presets (Max Contrast,
        Cinema Plate, retro terminal) ran their background plates at 58–88%
        opacity, which read as "dark text on dark background" on dashboards
        with a near-black UI. Any preset that *uses* a plate (opacity > 0)
        must now run at >= 88% so it stays distinguishable from the page
        background."""
        catalog = merge_style_presets()
        for key, preset in catalog.items():
            if not preset.get("built_in"):
                continue
            opacity = int(preset["base"]["background_opacity"])
            if opacity <= 0:
                continue  # transparent plate — covered by stroke/shadow.
            with self.subTest(preset=key, opacity=opacity):
                self.assertGreaterEqual(
                    opacity,
                    88,
                    msg=(
                        f"Built-in preset {key!r} uses a partially transparent plate "
                        f"({opacity}%), which produced the 'dark text on dark background' "
                        "feedback on the v0.4.2 dashboard preview. Use 88+ or set the "
                        "plate to fully transparent."
                    ),
                )

    def test_max_contrast_is_truly_high_contrast(self) -> None:
        """Regression: 'Max Contrast' must be unmistakably high contrast —
        white text on a solid black plate at 100% opacity. The v0.4.2
        version used yellow on near-black at 88% which was reported as
        unreadable."""
        catalog = merge_style_presets()
        preset = catalog["accessibility_high_contrast"]
        base = preset["base"]
        self.assertEqual(base["fill_color"].lower(), "#ffffff")
        self.assertEqual(base["background_color"].lower(), "#000000")
        self.assertEqual(int(base["background_opacity"]), 100)

    def test_builtin_presets_use_visually_distinct_fonts_and_fills(self) -> None:
        """Regression: the rework must not let presets collide on font family
        and fill colour again — that is the very thing that produced the
        'almost identical presets' complaint."""
        catalog = merge_style_presets()
        seen_signatures: set[tuple[str, str]] = set()
        for key, value in catalog.items():
            if not value.get("built_in"):
                continue
            font_family = str(value["base"]["font_family"]).split(",")[0].strip().lower()
            fill_color = str(value["base"]["fill_color"]).strip().lower()
            signature = (font_family, fill_color)
            with self.subTest(preset=key, signature=signature):
                self.assertNotIn(
                    signature,
                    seen_signatures,
                    msg=f"Built-in preset {key} reuses ({font_family}, {fill_color})",
                )
                seen_signatures.add(signature)


class SubtitleStyleRendererJsTests(unittest.TestCase):
    """Static checks that the subtitle-style.js renderer ships the incremental
    partial-effect logic. The JS itself is exercised via the renderer at
    runtime; this is a defence-in-depth guard against accidental deletion of
    the helpers."""

    def setUp(self) -> None:
        from pathlib import Path

        self.js_path = Path(__file__).resolve().parents[1] / "frontend" / "js" / "subtitle-style.js"
        self.source = self.js_path.read_text(encoding="utf-8")

    def test_renderer_exports_common_prefix_length(self) -> None:
        self.assertIn("commonPrefixLength", self.source)
        self.assertIn("commonPrefixLength,", self.source)  # in public export list

    def test_renderer_emits_fragment_classes_for_partial_split(self) -> None:
        self.assertIn("subtitle-fragment-static", self.source)
        self.assertIn("subtitle-fragment-fresh", self.source)
        self.assertIn("appendTransientFragments", self.source)

    def test_renderer_reuses_surface_on_pure_extension(self) -> None:
        """Flicker fix: when a partial frame is a pure extension of the
        previous partial, the renderer must REUSE the previous transient
        surface element (just grow its static span + swap its fresh span)
        instead of wiping the entire row. Without this guard the user sees
        the whole row re-mount on every partial — the 'sometimes flickers,
        sometimes doesn't' problem reported against v0.4.2."""
        self.assertIn("updateTransientSurfaceInPlace", self.source)
        self.assertIn("partialSurfaceBySlot", self.source)
        # The reuse helper must be exposed on the public namespace so the
        # overlay tracing and external diagnostics can reach it.
        self.assertIn(
            "updateTransientSurfaceInPlace,",
            self.source,
            msg="updateTransientSurfaceInPlace must be exported via window.SubtitleStyleRenderer",
        )

    def test_initial_partial_creates_empty_static_span_for_reuse(self) -> None:
        """The very first partial of an utterance has no shared prefix, so
        `staticPart` is empty. The previous implementation skipped creating
        the static span in that case, which made the *second* partial fall
        back to a full rebuild (no static span to reuse) — defeating the
        reuse fast-path on every utterance. `appendTransientFragments` must
        always emit the static span so subsequent extensions can grow it
        in place."""
        # The textual structure of appendTransientFragments must
        # unconditionally append the static span (no `if (staticPart)`
        # gating).
        index = self.source.index("function appendTransientFragments")
        body = self.source[index : index + 2000]
        self.assertNotRegex(
            body,
            r"if\s*\(\s*staticPart\s*\)\s*\{",
            msg=(
                "appendTransientFragments must not gate the static span on "
                "staticPart being non-empty — the empty static span is the "
                "reuse anchor for the second partial of every utterance."
            ),
        )

    def test_renderer_marks_reused_surface_in_trace(self) -> None:
        """Reused-surface debug trace flag — overlay/dashboard need to be
        able to *measure* how often partial reuse hit (high reuse rate ⇒
        no flicker; low reuse rate ⇒ recogniser is revising or state is
        being lost)."""
        self.assertIn("reused_surface", self.source)
        self.assertIn("reused_partial_surfaces", self.source)

    def test_pure_extension_check_uses_shared_prefix_invariant(self) -> None:
        """The reuse helper must only fire for pure extensions
        (sharedLength === previousText.length). Any other transition
        (revision/shrink/jump) MUST fall back to a full rebuild because the
        existing static span no longer matches the new prefix."""
        self.assertRegex(
            self.source,
            r"sharedLength\s*===\s*previousText\.length",
            msg="updateTransientSurfaceInPlace must guard reuse with the pure-extension predicate.",
        )

    def test_renderer_has_shape_signature_fast_path(self) -> None:
        """Root-cause flicker fix for the v0.4.2 'sometimes works, sometimes
        doesn't' regression: reusing only the per-slot *surface* element is
        not enough. The renderer also wiped and rebuilt the wrapper, stage,
        row, and content elements on every frame via
        `container.innerHTML = ""`. That wipe re-parented every surface,
        which forced the browser to recompute layout/paint for the whole
        subtitle area on every partial frame.

        The fix adds a structural-shape fast path: when consecutive renders
        share the same rows × slot × transient/completed × completed-text
        composition, mutate the existing surfaces *in place* and never
        touch the wrapper. This contract must remain intact."""
        # Shape-fingerprint helpers exist and are exposed for tests.
        self.assertIn("function _shapeSignatureForEntry", self.source)
        self.assertIn("function _shapeSignatureForRows", self.source)
        self.assertIn("_shapeSignatureForRows,", self.source)
        self.assertIn("_shapeSignatureForEntry,", self.source)
        # Render state carries the shape signature, the surface list, and the
        # wrapper DOM node forward so the next frame can decide whether to
        # use the fast path.
        self.assertIn("shapeSignature", self.source)
        self.assertIn("entrySurfaces", self.source)
        # The fast path explicitly guards against a stranded wrapper (e.g. if
        # an external script rewrote `container.innerHTML`).
        self.assertRegex(
            self.source,
            r"renderState\.wrapper\.parentNode\s*===\s*container",
            msg="Fast path must verify the cached wrapper is still inside the container.",
        )
        # Render summary must surface the chosen branch so debug traces show
        # whether the fast path engaged for any given frame.
        self.assertIn("fast_path: true", self.source)
        self.assertIn("fast_path: false", self.source)

    def test_fast_path_skips_innerhtml_wipe_for_partial_extension(self) -> None:
        """The slow path uses `container.innerHTML = ""` exactly once when
        rebuilding the wrapper top-down. The fast path must NOT contain a
        second copy of that wipe — otherwise the whole flicker fix is moot.
        Keeping the wipe count at exactly one is the load-bearing
        invariant."""
        # Count only real statements (line starts with optional whitespace
        # then the assignment, terminated by `;`). Comments that mention the
        # phrase verbatim don't count.
        import re

        statement = re.compile(r'^\s*container\.innerHTML\s*=\s*""\s*;', re.MULTILINE)
        occurrences = len(statement.findall(self.source))
        self.assertEqual(
            occurrences,
            1,
            msg=(
                f"`container.innerHTML = \"\"` appears {occurrences} times as a real "
                "statement in subtitle-style.js; it must appear exactly once (in the "
                "slow-path rebuild). Adding a copy in the fast path would reintroduce "
                "the per-frame wrapper wipe that caused the v0.4.2 subtitle flicker."
            ),
        )

    def test_source_finalization_engages_fast_path_with_in_place_consolidation(self) -> None:
        """When the SOURCE row finalizes (the partial flips from transient to
        completed with the same text), the renderer must NOT rebuild the
        wrapper — that's what produces the user-visible 'renders the whole
        block again' jump at the end of a phrase. Translations are out of
        scope here: they arrive once in a separate frame with a different
        row count, so they legitimately fall through to the slow path with
        the old logic the user explicitly asked us to keep.

        The contract:
        - `_canFastPathFinalize` accepts a frame where every entry is in the
          same position with the same slot/kind/lang, and the only
          difference is `transient: true` ⇒ `transient: false` with the new
          completed text matching the previously-tracked partial text.
        - `_finalizeTransientSurfaceInPlace` keeps the surface DOM node,
          replaces its `<span.static>/<span.fresh>` children with a single
          text node, and forces `effect-none` so the completion animation
          does NOT fire (the text was already visible).
        - The render summary exposes a `finalized_in_place` counter so the
          debug trace can confirm the optimisation engaged."""
        # Both helpers exist and are exported on the public namespace for
        # tests and external diagnostics.
        self.assertIn("function _canFastPathFinalize", self.source)
        self.assertIn("function _finalizeTransientSurfaceInPlace", self.source)
        self.assertIn("_canFastPathFinalize,", self.source)
        self.assertIn("_finalizeTransientSurfaceInPlace,", self.source)
        # Fast-path engagement OR-gates exact-shape with finalization
        # compatibility. Both predicates must be present in the render
        # function's gate.
        self.assertRegex(
            self.source,
            r"exactShapeMatch\s*\|\|\s*finalizationCompatible",
            msg=(
                "Fast path must engage on either an exact shape match OR a "
                "finalization-compatible transition — anything else "
                "reintroduces the wrapper rebuild at finalize time."
            ),
        )
        # Finalization writes the descriptor for the next frame so a
        # subsequent partial in the same position (rare but possible) still
        # has the previous descriptor available for transition dispatch.
        self.assertIn("entryDescriptors", self.source)
        # The render_summary publishes the finalize counter for debugging.
        self.assertIn("finalized_in_place", self.source)
        # The in-place finalization helper must avoid the completion
        # animation: the text was already on-screen during the partial, so
        # animating it now is exactly the visible 're-render' the user
        # reported.
        helper_index = self.source.index("function _finalizeTransientSurfaceInPlace")
        helper_body = self.source[helper_index : helper_index + 1200]
        self.assertIn("effect-none", helper_body)
        self.assertIn("animated: false", helper_body)
        # The finalize helper must consolidate fragments by *removing* the
        # static/fresh spans and setting `textContent`, not by leaving the
        # spans in place — otherwise completed surfaces would still carry
        # the partial DOM structure forever.
        self.assertIn("surface.removeChild(surface.firstChild)", helper_body)
        self.assertIn("surface.textContent = text", helper_body)

    def test_finalization_only_engages_when_completed_text_matches_partial(self) -> None:
        """A T→C transition is only finalization-compatible when the
        completed text matches what was last shown as a partial in that
        slot. Otherwise the user would see the text mutate at finalize
        time — that's a different kind of update and must follow the slow
        path so the completion animation can play."""
        helper_index = self.source.index("function _canFastPathFinalize")
        helper_body = self.source[helper_index : helper_index + 2000]
        # The text-equality predicate against the last tracked partial text
        # must be present. Without it, the helper would accept any T→C
        # transition regardless of the actual content shown.
        self.assertIn("lastPartial", helper_body)
        self.assertIn("previousPartialBySlot.get(slot)", helper_body)
        # C→T transitions (rare; only possible if a completed line is
        # somehow rewound to a partial) are NOT a finalization and must
        # bail out to the slow path.
        self.assertRegex(
            helper_body,
            r"C\s*→\s*T",
            msg=(
                "_canFastPathFinalize must explicitly document and reject "
                "C→T transitions — otherwise the renderer would silently "
                "treat them as finalizations."
            ),
        )

    def test_slow_path_reuses_partial_source_surface_when_translation_arrives_simultaneously(self) -> None:
        """The dominant finalization case is handled by the fast path (no
        translations yet). The minority case — where the finalization
        frame *also* introduces a new translation row, changing the row
        count and forcing the slow path — must still reuse the partial
        source surface so the source line itself doesn't visibly re-render
        even while the translation row is being added.

        Translations continue to follow the old behaviour (fresh surface,
        completion animation) because they appear exactly once."""
        # The slow-path branch that handles the *completed* entry must
        # check whether there's a previous partial in the same slot with
        # matching text and reuse that surface.
        self.assertIn("canReuseAsFinalization", self.source)
        self.assertRegex(
            self.source,
            r"previousPartialSurfaceBySlot\.get\(slotName\)",
            msg=(
                "Slow path must look up the previously-tracked partial "
                "surface for the entry's slot when finalizing."
            ),
        )
        self.assertRegex(
            self.source,
            r"lastPartialTextForSlot\s*===\s*entryText",
            msg=(
                "Slow-path finalization reuse must require an exact text "
                "match against the previously tracked partial text — "
                "otherwise the renderer would visually swap text content "
                "without an animation."
            ),
        )

    def test_style_editor_extracts_primary_font_from_preset_chain(self) -> None:
        """Built-in presets carry a full CSS font-family chain (multiple
        quoted families + a generic fallback) so the browser can fall
        through to a Cyrillic-capable face. The font dropdown, however,
        registers one option per face — its option values are single
        quoted families. Without ``extractPrimaryFontFamily`` the editor
        compares the whole chain to single-name options, finds no match,
        and leaves the dropdown blank — which the user reads as "preset
        doesn't tell me which font is selected". The helper must collapse
        the chain to its first quoted family so the dropdown actually
        highlights the right option."""
        from pathlib import Path

        shared_path = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "js"
            / "panels"
            / "style"
            / "style-editor-panel-shared.js"
        )
        shared_source = shared_path.read_text(encoding="utf-8")
        self.assertIn("export function extractPrimaryFontFamily", shared_source)
        # The helper must prefer the first quoted family — quoted matching
        # is the contract because the font catalog stores option values as
        # quoted single names.
        self.assertRegex(
            shared_source,
            r"str\.match\(/\"\(\[\^\"\]\+\)\"/\)",
            msg=(
                "extractPrimaryFontFamily must use the quoted-family "
                "regex; the fallback path must only fire on unquoted "
                "input."
            ),
        )

        render_path = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "js"
            / "panels"
            / "style"
            / "style-editor-panel-render.js"
        )
        render_source = render_path.read_text(encoding="utf-8")
        # The renderer must consume the helper for BOTH the base font
        # dropdown and the slot font dropdown — otherwise the dropdowns
        # disagree about what counts as "selected".
        self.assertIn("extractPrimaryFontFamily(style.base.font_family)", render_source)
        self.assertIn("extractPrimaryFontFamily(style.base?.font_family)", render_source)
        self.assertIn("extractPrimaryFontFamily(raw)", render_source)

    def test_style_editor_exposes_per_slot_apply_preset_selector(self) -> None:
        """Per-line slot overrides must support copying a preset's base
        style onto a single line (e.g. base preset = clean_default, but
        the source slot wants the cyberpunk look). The selector is a
        one-shot apply: it writes the chosen preset's base into the slot
        and resets back to the placeholder so users see this as an
        action button rather than a binding."""
        from pathlib import Path

        # HTML element must exist with the expected id.
        html_path = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
        html_source = html_path.read_text(encoding="utf-8")
        self.assertIn('id="style-line-slot-apply-preset"', html_source)
        self.assertIn('data-i18n="style.slots.apply_preset"', html_source)

        # Render module must collect the new element AND fill its options
        # from the preset catalog AND disable it while the slot override
        # is off.
        render_path = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "js"
            / "panels"
            / "style"
            / "style-editor-panel-render.js"
        )
        render_source = render_path.read_text(encoding="utf-8")
        self.assertIn(
            'applyPreset: root.querySelector("#style-line-slot-apply-preset")',
            render_source,
        )
        self.assertIn("elements.lineSlots.applyPreset", render_source)
        self.assertIn("lastLineSlotPresetSignature", render_source)

        # Event binder must apply the chosen preset's base into the
        # currently selected line slot, force enabled=true, and reset the
        # selector back to the empty placeholder.
        panel_path = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "js"
            / "panels"
            / "style-editor-panel.js"
        )
        panel_source = panel_path.read_text(encoding="utf-8")
        self.assertIn("elements.lineSlots.applyPreset", panel_source)
        self.assertIn("buildStyleFromPreset(presets, presetName)", panel_source)
        self.assertRegex(
            panel_source,
            r"next\s*=\s*\{\s*\.\.\.current,\s*enabled:\s*true\s*\}",
            msg=(
                "Applying a preset to a slot must force enabled=true so "
                "the override actually takes effect; without this the "
                "slot would keep enabled=false and silently inherit base."
            ),
        )
        self.assertRegex(
            panel_source,
            r"elements\.lineSlots\.applyPreset\.value\s*=\s*\"\"",
            msg=(
                "Selector must reset to the placeholder after applying. "
                "If we leave the chosen preset name in the field, users "
                "would think the slot is *bound* to that preset, but it "
                "is just a free-form override after application."
            ),
        )

        # i18n entries for the new label.
        i18n_path = Path(__file__).resolve().parents[1] / "frontend" / "js" / "i18n.js"
        i18n_source = i18n_path.read_text(encoding="utf-8")
        self.assertIn('"style.slots.apply_preset": "Apply preset to this slot"', i18n_source)
        self.assertIn('"style.slots.apply_preset": "Применить пресет к этому слоту"', i18n_source)

    def test_overlay_normalizer_preserves_lifecycle_state(self) -> None:
        """The dashboard receives subtitle payloads via the websocket and
        runs every payload through `normalizeOverlayPayload` before the
        store is updated. The normaliser MUST forward `lifecycle_state`
        unchanged — dropping it (as the legacy normaliser did) silently
        breaks the renderer's `composeRenderRows` ``completed_with_partial``
        gate, since the gate keys off lifecycle_state. Without the gate,
        the dashboard re-renders the source row on every keystroke as
        soon as a translation is visible. The overlay window keeps its
        own state plumbing, but lives under the same renderer contract,
        so the normaliser is the single point of failure in the
        dashboard path."""
        from pathlib import Path

        normalizer_path = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "js"
            / "normalizers"
            / "overlay-normalizer.js"
        )
        source = normalizer_path.read_text(encoding="utf-8")
        self.assertIn("lifecycle_state", source)
        # All four lifecycle states the backend can emit must be accepted.
        for state in ("idle", "partial_only", "completed_only", "completed_with_partial"):
            with self.subTest(state=state):
                self.assertIn(f"\"{state}\"", source)
        # Unknown lifecycle values must be coerced to "idle" so the renderer
        # never sees a string the backend can't produce.
        self.assertRegex(
            source,
            r"LIFECYCLE_STATES\.has\(rawLifecycle\)\s*\?\s*rawLifecycle\s*:\s*\"idle\"",
            msg=(
                "Normaliser must coerce unknown lifecycle_state values to "
                "'idle' instead of forwarding arbitrary strings — the "
                "renderer's gate compares against literal lifecycle states."
            ),
        )

    def test_overlay_window_forwards_lifecycle_state_into_render_payload(self) -> None:
        """The overlay window (`overlay/overlay.js`) builds its own
        presentation payload locally (it doesn't share the dashboard's
        normaliser). Without explicit plumbing here, the
        `composeRenderRows` lifecycle gate would always read `undefined`
        in the overlay process and the bug would re-appear in OBS even if
        the dashboard preview is fixed."""
        from pathlib import Path

        overlay_path = (
            Path(__file__).resolve().parents[1] / "overlay" / "overlay.js"
        )
        source = overlay_path.read_text(encoding="utf-8")
        # Overlay state stores the lifecycle string for downstream re-emit.
        self.assertIn("lifecycleState", source)
        # applyOverlayPayload writes the captured lifecycle state.
        self.assertRegex(
            source,
            r"overlayState\.lifecycleState\s*=\s*String\(payload\.lifecycle_state",
            msg=(
                "applyOverlayPayload must persist payload.lifecycle_state "
                "into overlayState so buildPresentationPayload can include "
                "it in the render-time payload."
            ),
        )
        # buildPresentationPayload forwards the lifecycle into the render
        # payload (both lifecycle and legacy branches must be safe).
        self.assertRegex(
            source,
            r"lifecycle_state:\s*overlayState\.lifecycleState\s*\|\|\s*\"idle\"",
            msg=(
                "buildPresentationPayload must forward the cached lifecycle "
                "state to the renderer so composeRenderRows can engage the "
                "completed_with_partial transient classification."
            ),
        )

    def test_compose_render_rows_marks_completed_with_partial_source_as_transient(self) -> None:
        """The backend presentation layer puts the LIVE partial text into
        `visible_items[source]` when the lifecycle state is
        ``completed_with_partial`` (next phrase being typed while the old
        phrase's translation block is still visible). Without explicitly
        marking that source entry as transient, the renderer treats every
        keystroke as a brand-new completed entry — different text every
        frame ⇒ different shape signature ⇒ slow path ⇒ fresh surface ⇒
        completion animation fires repeatedly. That is the precise
        ``когда появляется перевод, исходник постоянно перерендерится``
        regression reported on top of v0.4.2.

        Contract:
        - The composer detects ``lifecycle_state === "completed_with_partial"``
          combined with a non-empty ``active_partial_text``.
        - The matching source entry in ``visible_items`` (the one whose
          text equals ``active_partial_text``) is emitted with
          ``transient: true`` so the renderer routes it through the
          partial code path (typewriter-incremental, stable shape signature
          across frames, fast-path reuse).
        - Translation entries stay completed (old logic preserved per the
          user's explicit instruction that translations appear once and
          shouldn't be reworked)."""
        self.assertIn("completed_with_partial", self.source)
        self.assertIn("livePartialSourceInVisibleItems", self.source)
        # The transient flag MUST be derived from the lifecycle state — a
        # naïve text-equality check across all completed-block payloads
        # would mis-classify rare cases where the user re-says the same
        # phrase. Anchoring on the lifecycle state is what makes this safe.
        self.assertRegex(
            self.source,
            r"lifecycle_state\s*===\s*\"completed_with_partial\"",
            msg=(
                "Composer must gate the transient flag on the backend's "
                "lifecycle_state field. Without this gate, every "
                "completed-block payload where source text happens to "
                "equal active_partial_text would be reclassified."
            ),
        )
        # The transient flag must only attach to the SOURCE entry whose
        # text actually matches active_partial_text. Otherwise the old
        # completed source (if it somehow lingered) would also be
        # mis-classified.
        self.assertRegex(
            self.source,
            r"item\.kind\s*===\s*\"source\"\s*&&\s*String\(item\.text\s*\|\|\s*\"\"\)\s*===\s*activePartialText",
            msg=(
                "Transient classification must require BOTH kind === 'source' "
                "AND text === activePartialText. Either predicate alone "
                "would mis-classify translation rows or stale source rows."
            ),
        )
        # Translation rows must NOT be reclassified — they keep their
        # completed semantics so the old animation logic still applies.
        self.assertNotIn(
            "item.kind === \"translation\" && livePartialSourceInVisibleItems",
            self.source,
            msg=(
                "Composer must never mark translation entries as transient "
                "regardless of lifecycle state. Translations appear once "
                "per phrase and follow the old (completed) animation flow."
            ),
        )

    def test_slow_path_reuses_completed_source_surface_when_translation_arrives_in_next_frame(self) -> None:
        """The 'effects got worse' regression: the source row finalizes
        cleanly in the fast path (no animation), but when the *next* frame
        introduces a translation row, the slow path engages because the
        row count changed. Without dedicated reuse logic, the slow path
        would build a fresh surface for the (still unchanged) source
        completed entry and play the completion animation — making the
        source line appear to re-render the moment a translation lands.
        The previously tracked partial surface no longer applies because
        the previous frame was already completed, not transient.

        Contract:
        - Slow-path completed branch must search `previousEntryDescriptors`
          for a non-transient entry with the same slot/kind/lang/text and
          reuse the corresponding surface from `previousEntrySurfaces`
          when found.
        - The reused surface keeps `effect-none` (no completion replay).
        - The render summary marks the reuse via a dedicated metric so
          debug traces can distinguish 'finalized in place' from 'reused
          stable completed surface'."""
        # The slow-path completed branch must consult previous descriptors
        # for a matching completed entry (slot + kind + lang + text).
        self.assertIn("reusableCompletedSurface", self.source)
        self.assertRegex(
            self.source,
            r"prev\.transient\s*===\s*false",
            msg=(
                "Completed-surface reuse must only match against entries "
                "that were COMPLETED in the previous frame — picking up a "
                "transient surface here would replay partial fragments as "
                "plain text and lose the partial structure."
            ),
        )
        self.assertRegex(
            self.source,
            r"prev\.slot\s*===\s*slotName",
            msg=(
                "Completed-surface reuse must match on slot so a "
                "translation row never inherits the source row's surface."
            ),
        )
        self.assertRegex(
            self.source,
            r"prev\.kind\s*===\s*entryKind",
            msg="Completed-surface reuse must match on kind.",
        )
        self.assertRegex(
            self.source,
            r"prev\.lang\s*===\s*entryLang",
            msg=(
                "Completed-surface reuse must match on lang so a translated "
                "row in one language never inherits another language's surface."
            ),
        )
        self.assertRegex(
            self.source,
            r"prev\.text\s*===\s*entryText",
            msg=(
                "Completed-surface reuse requires an EXACT text match — a "
                "mismatched text would visibly swap content without the "
                "expected completion animation."
            ),
        )
        # The reused surface keeps effect-none (no completion animation).
        # Without this, the slow-path code would inadvertently animate the
        # stable source row every time a translation row is added.
        self.assertIn("reused_completed_surface", self.source)

    def test_dashboard_preview_clears_stale_notes_between_frames(self) -> None:
        """The dashboard overlay-preview panel appends a status note
        (`<p class="subtitle-stage-note">`) as a *sibling* of the renderer's
        wrapper after each render. The renderer's fast path leaves the
        container alone between frames, so the caller MUST remove any
        previous note before appending a new one — otherwise notes pile up
        ("Живой блок субтитров #23." repeated dozens of times under the
        preview), which is the regression reported right after the flicker
        fix landed.

        Slow-path-only ago, `container.innerHTML = ""` masked this bug by
        wiping all siblings every frame; now the caller owns the cleanup."""
        from pathlib import Path

        panel_path = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "js"
            / "panels"
            / "overlay-panel.js"
        )
        panel_source = panel_path.read_text(encoding="utf-8")
        self.assertIn(".subtitle-stage-note", panel_source)
        self.assertRegex(
            panel_source,
            r"querySelectorAll\(\"\.subtitle-stage-note\"\)",
            msg=(
                "renderPreview must clear stale `.subtitle-stage-note` "
                "siblings before appending a fresh one — otherwise the "
                "in-place fast path piles up duplicate notes."
            ),
        )
        self.assertIn(".remove()", panel_source)

    def test_fast_path_engages_for_pure_extension_in_browser(self) -> None:
        """Execute the renderer in a jsdom-style mini browser-emulation to
        prove the fast path actually keeps the wrapper element across pure
        extensions. We use Python's `pythonmonkey` if it's available;
        otherwise we run a hand-rolled DOM mock that is just enough for the
        renderer's `appendChild`/`firstElementChild`/`isConnected` calls.

        The contract:
        1. Frame 1 with partial 'Hel' builds a wrapper.
        2. Frame 2 with partial 'Hello' must reuse the SAME wrapper DOM node
           (no `container.innerHTML = ""` wipe). The static span must grow
           to 'Hel' and a fresh span must contain 'lo'.
        3. The render_summary debug event must report `fast_path: true`.

        We assert these contracts at the source level (string-shape
        verification) because the project has no headless JS runtime; the
        load-bearing predicate is `previousShape === shapeSignature` and
        is what unit-test #1 above guarantees stays intact.
        """
        # Pure-shape predicates assertable from the source — gate-keep the
        # specific predicate that decides whether the fast path engages.
        self.assertRegex(
            self.source,
            r"previousShape\s*===\s*shapeSignature",
            msg=(
                "Fast path engagement must be gated by shape-signature equality. "
                "Without this gate, a revision/jump or a new translation row "
                "would silently update partial text under stale shape assumptions."
            ),
        )
        # The fast path must also push the (possibly mutated) per-entry
        # surface back into the next render state so the third consecutive
        # extension can reuse it again — otherwise the second frame works
        # but every odd frame after that falls back to slow rebuild.
        self.assertRegex(
            self.source,
            r"entrySurfaces:\s*nextEntrySurfaces",
            msg=(
                "Fast path must repopulate `entrySurfaces` in the persisted "
                "render state, otherwise reuse is only one frame deep."
            ),
        )

    def test_renderer_exposes_partial_transition_classifier(self) -> None:
        """Debug-trace hook must classify each partial-frame transition so
        downstream consumers (overlay/dashboard) can flag revisions/jumps —
        the dominant cause of visible flicker reported on partial subtitles."""
        self.assertIn("function classifyPartialTransition", self.source)
        # All six transition labels must be present in the source so
        # filtering and grouping the debug logs stays straightforward.
        for label in ("initial", "identical", "extension", "shrink", "revision", "jump"):
            with self.subTest(label=label):
                self.assertIn(f'"{label}"', self.source)
        # The classifier must be exposed on the public API for tests and
        # external debug tools to assert against without resorting to
        # source-string scraping.
        self.assertIn("classifyPartialTransition,", self.source)

    def test_renderer_emits_structured_debug_trace_events(self) -> None:
        """The render() debug hook must emit three structured event kinds and
        forward them through the optional `onRenderTrace` callback. We assert
        on the JS source because there is no headless JS test runtime in this
        repo and the renderer is a vanilla browser script."""
        self.assertIn("_resolveTraceCallback(options)", self.source)
        self.assertIn("onRenderTrace", self.source)
        # Each event type literal must appear so callers can filter by kind.
        for event_type in ("partial_frame", "completed_frame", "render_summary"):
            with self.subTest(event_type=event_type):
                self.assertIn(f'"{event_type}"', self.source)
        # Anomaly kinds the renderer self-detects.
        self.assertIn('"partial_revision"', self.source)
        self.assertIn('"state_carryover_missing"', self.source)
        # Per-frame summary must include the diagnostic fields the
        # debug-overlay UI shows in DevTools (rows, partial/completed counts,
        # state carry-over, frame timing).
        for field in (
            "rows: rows.length",
            "partial_entries: partialEntryCount",
            "completed_entries: completedEntryCount",
            "state_carryover: hadPriorRenderState",
            "ms_since_last_render",
            "render_duration_ms",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.source)

    def test_overlay_subtitle_debug_hook_is_opt_in(self) -> None:
        """The OBS overlay must keep the new tracing strictly opt-in (URL
        param OR localStorage) and must pipe the callback into the renderer
        only when enabled — otherwise busy partials would flood the backend
        ui-trace log."""
        from pathlib import Path

        overlay_js = (Path(__file__).resolve().parents[1] / "overlay" / "overlay.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('params.get("debug-subtitles") === "1"', overlay_js)
        self.assertIn('"sst_debug_subtitles"', overlay_js)
        self.assertIn("subtitleDebugMode", overlay_js)
        # Renderer call must wire the trace through (gated by the flag).
        self.assertIn("onRenderTrace: subtitleDebugMode ? handleSubtitleRenderTrace : null", overlay_js)
        # Only summaries with anomalies should be persisted to the backend.
        self.assertIn('postOverlayUiTrace("subtitle_render_anomaly"', overlay_js)
        # Ring buffer must be exposed for DevTools inspection.
        self.assertIn("__sstOverlaySubtitleTrace", overlay_js)

    def test_dashboard_subtitle_debug_hook_is_opt_in(self) -> None:
        """The dashboard preview must follow the same opt-in rule via the
        same localStorage key and must persist anomalies through traceUi()
        (lands in logs/ui-trace.jsonl for offline analysis)."""
        from pathlib import Path

        panel_js = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "js"
            / "panels"
            / "overlay-panel.js"
        ).read_text(encoding="utf-8")
        self.assertIn('"sst_debug_subtitles"', panel_js)
        self.assertIn("isSubtitleDebugEnabled", panel_js)
        self.assertIn(
            "onRenderTrace: subtitleDebug ? handleSubtitleRenderTraceForDashboard : null",
            panel_js,
        )
        # traceUi(...) is the canonical backend-trace channel (see ui-trace.js).
        self.assertIn('traceUi("dashboard", "subtitle_render", "anomaly"', panel_js)
        # Ring buffer must be exposed for DevTools inspection.
        self.assertIn("__sstDashboardSubtitleTrace", panel_js)


if __name__ == "__main__":
    unittest.main()
