from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
JS_ROOT = FRONTEND_ROOT / "js"
OVERLAY_ROOT = PROJECT_ROOT / "overlay"


class FrontendArchitectureTests(unittest.TestCase):
    def test_index_uses_es_module_entrypoint(self) -> None:
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('<script type="module" src="/static/js/main.js', index_html)
        self.assertNotIn('/static/js/state.js', index_html)
        self.assertNotIn('/static/js/api.js', index_html)
        self.assertNotIn('/static/js/ws.js', index_html)

    def test_core_and_panel_modules_exist(self) -> None:
        expected_paths = [
            JS_ROOT / "main.js",
            JS_ROOT / "core" / "store.js",
            JS_ROOT / "core" / "api-client.js",
            JS_ROOT / "core" / "redaction.js",
            JS_ROOT / "core" / "ws-client.js",
            JS_ROOT / "core" / "events.js",
            JS_ROOT / "core" / "dom.js",
            JS_ROOT / "core" / "panel-mount.js",
            JS_ROOT / "core" / "selectors.js",
            JS_ROOT / "dashboard" / "action-helpers.js",
            JS_ROOT / "dashboard" / "actions" / "index.js",
            JS_ROOT / "shell" / "help-content-loader.js",
            JS_ROOT / "panels" / "runtime-panel.js",
            JS_ROOT / "panels" / "overlay" / "overlay-display-order-view.js",
            JS_ROOT / "panels" / "translation" / "translation-panel-shared.js",
            JS_ROOT / "panels" / "translation" / "translation-line-editor-view.js",
            JS_ROOT / "panels" / "asr" / "asr-panel-render.js",
            JS_ROOT / "panels" / "style" / "style-editor-panel-shared.js",
            JS_ROOT / "panels" / "style" / "style-editor-panel-render.js",
            JS_ROOT / "panels" / "source-text-replacement" / "source-text-replacement-panel-render.js",
            JS_ROOT / "panels" / "asr-panel.js",
            JS_ROOT / "panels" / "model-manager-panel.js",
            JS_ROOT / "panels" / "translation-panel.js",
            JS_ROOT / "panels" / "overlay-panel.js",
            JS_ROOT / "panels" / "obs-captions-panel.js",
            JS_ROOT / "panels" / "diagnostics-panel.js",
            JS_ROOT / "panels" / "style-editor-panel.js",
            JS_ROOT / "panels" / "profiles-panel.js",
            JS_ROOT / "panels" / "remote-panel.js",
            JS_ROOT / "dashboard" / "desktop-profile-lock.js",
            JS_ROOT / "normalizers" / "config-normalizer.js",
            JS_ROOT / "normalizers" / "parakeet-latency-presets.js",
            JS_ROOT / "normalizers" / "runtime-normalizer.js",
            JS_ROOT / "normalizers" / "translation-normalizer.js",
            JS_ROOT / "normalizers" / "overlay-normalizer.js",
            JS_ROOT / "normalizers" / "diagnostics-normalizer.js",
            JS_ROOT / "normalizers" / "model-normalizer.js",
        ]
        missing = [str(path.relative_to(PROJECT_ROOT)) for path in expected_paths if not path.exists()]
        self.assertEqual(missing, [])

    def test_store_contract_is_centralized_and_clone_based(self) -> None:
        store_js = (JS_ROOT / "core" / "store.js").read_text(encoding="utf-8")
        self.assertIn("const listeners = new Set()", store_js)
        self.assertIn("export function getState()", store_js)
        self.assertIn("return structuredClone(value)", store_js)
        self.assertIn("export function updateState(patch)", store_js)
        self.assertIn("Object.assign(state, nextPatch)", store_js)

    def test_index_loads_shared_redaction_and_diagnostics_export_button(self) -> None:
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('/static/js/core/redaction.js', index_html)
        self.assertIn('id="diagnostics-export-btn"', index_html)
        self.assertIn('id="local-parakeet-saved-config-summary"', index_html)
        self.assertIn('id="rt-tools-latency-preset"', index_html)
        self.assertIn('id="rt-streaming-decode"', index_html)
        self.assertIn('id="parakeet-latency-preset"', index_html)
        self.assertIn('id="parakeet-latency-preset-row"', index_html)

    def test_design_system_tokens_and_bridge_status_contracts_exist(self) -> None:
        app_css = (FRONTEND_ROOT / "css" / "app.css").read_text(encoding="utf-8")
        for token in [
            "--sst-bg",
            "--sst-panel",
            "--sst-panel-strong",
            "--sst-border",
            "--sst-text",
            "--sst-muted",
            "--sst-ok",
            "--sst-warning",
            "--sst-danger",
            "--sst-info",
            "--sst-radius-sm",
            "--sst-radius-md",
            "--sst-radius-lg",
            "--sst-shadow-panel",
        ]:
            self.assertIn(token, app_css)
        for selector in [
            ".sst-card",
            ".sst-health-card",
            ".sst-status-badge",
            ".sst-button",
            ".sst-button-danger",
            ".sst-button-ghost",
            ".sst-field",
            ".sst-field-row",
            ".sst-tabs",
            ".sst-toast",
            ".sst-modal",
            ".sst-latency-meter",
        ]:
            self.assertIn(selector, app_css)
        for status in ["ready", "running", "disabled", "warning", "error", "degraded", "loading"]:
            self.assertIn(f'.sst-status-badge[data-status="{status}"]', app_css)

        controller_html = (FRONTEND_ROOT / "remote_controller_bridge.html").read_text(encoding="utf-8")
        worker_html = (FRONTEND_ROOT / "remote_worker_bridge.html").read_text(encoding="utf-8")
        self.assertIn('data-status="ready"', controller_html)
        self.assertIn('data-status="ready"', worker_html)
        self.assertNotIn(".ok {", controller_html)
        self.assertNotIn(".warn {", controller_html)
        self.assertNotIn(".bad {", controller_html)
        self.assertNotIn(".ok {", worker_html)
        self.assertNotIn(".warn {", worker_html)
        self.assertNotIn(".bad {", worker_html)

        controller_js = (JS_ROOT / "remote-controller-bridge.js").read_text(encoding="utf-8")
        worker_js = (JS_ROOT / "remote-worker-bridge.js").read_text(encoding="utf-8")
        self.assertIn("statusLine.dataset.status = level", controller_js)
        self.assertIn("statusLine.dataset.status = level", worker_js)
        self.assertNotIn('classList.remove("ok", "warn", "bad")', controller_js)
        self.assertNotIn('classList.remove("ok", "warn", "bad")', worker_js)

    def test_style_editor_rebuilds_preset_options_when_catalog_changes(self) -> None:
        shared_js = (JS_ROOT / "panels" / "style" / "style-editor-panel-shared.js").read_text(encoding="utf-8")
        render_js = (JS_ROOT / "panels" / "style" / "style-editor-panel-render.js").read_text(encoding="utf-8")
        panel_js = (JS_ROOT / "panels" / "style-editor-panel.js").read_text(encoding="utf-8")
        self.assertIn("export function buildPresetCatalogSignature", shared_js)
        self.assertIn("lastPresetCatalogSignature", render_js)
        self.assertIn("shouldRebuildPresets", render_js)
        self.assertIn("createPanelMount", panel_js)

    def test_style_editor_keeps_native_color_picker_open_during_edits(self) -> None:
        shared_js = (JS_ROOT / "panels" / "style" / "style-editor-panel-shared.js").read_text(encoding="utf-8")
        render_js = (JS_ROOT / "panels" / "style" / "style-editor-panel-render.js").read_text(encoding="utf-8")
        panel_js = (JS_ROOT / "panels" / "style-editor-panel.js").read_text(encoding="utf-8")
        self.assertIn("export function bindStyleColorPickerEvents", shared_js)
        self.assertIn("export function shouldSkipStyleControlRenderSync", shared_js)
        self.assertIn("shouldSkipStyleControlRenderSync(element)", render_js)
        self.assertIn("bindStyleColorPickerEvents(element, add", panel_js)
        self.assertIn('isStyleColorInput(element)', panel_js)

    def test_subtitle_style_renderer_maps_effect_ids_to_css_classes(self) -> None:
        renderer_js = (JS_ROOT / "subtitle-style.js").read_text(encoding="utf-8")
        self.assertIn("function effectClassName(effect)", renderer_js)
        self.assertIn('replace(/_/g, "-")', renderer_js)
        # Effect resolution now goes through a `slotEffect` local that captures
        # `lineStyle.effect || effectiveStyle.effect || "none"`, then we feed it
        # into effectClassName() for either the surface (completed entries) or
        # the fresh-suffix span (partial entries). Assert the resolution chain
        # is still present without coupling to a specific call site.
        self.assertIn("lineStyle.effect || effectiveStyle.effect", renderer_js)
        self.assertIn("effectClassName(slotEffect)", renderer_js)

    def test_subtitle_style_renderer_does_not_reanimate_partial_or_existing_rows(self) -> None:
        renderer_js = (JS_ROOT / "subtitle-style.js").read_text(encoding="utf-8")
        self.assertIn('transient: true', renderer_js)
        self.assertIn("function shouldAnimateEntry(entry, previousEntrySignatures)", renderer_js)
        self.assertIn("if (entry.transient)", renderer_js)
        self.assertIn("__subtitleStyleRenderState", renderer_js)
        self.assertIn('nextEntrySignatures.push(renderEntrySignature(entry))', renderer_js)

    def test_overlay_filters_stale_payloads_using_created_at_ms(self) -> None:
        overlay_js = (OVERLAY_ROOT / "overlay.js").read_text(encoding="utf-8")
        self.assertIn("created_at_ms", overlay_js)
        self.assertIn("ignored stale overlay_update", overlay_js)

    def test_overlay_skips_dom_render_when_payload_signature_is_unchanged(self) -> None:
        overlay_js = (OVERLAY_ROOT / "overlay.js").read_text(encoding="utf-8")
        self.assertIn("signature !== overlayState.lastRenderSignature", overlay_js)
        self.assertIn("applyClasses();\n      return;", overlay_js)

    def test_parakeet_tuning_controls_visible_outside_browser_speech_lock(self) -> None:
        """Parakeet-specific tuning controls (latency preset, incremental
        streaming decode, partial_emit_mode, partial_min_new_words) must remain
        visible whenever the install can run Parakeet at all — even if the user
        is currently in browser_google mode. They only get hidden when the
        install is locked to Web Speech via desktop_profile_lock (Browser Speech
        quick-start profile or desktop web_speech_only context).

        Regression: previously the controls were also hidden whenever
        config.asr.mode === "browser_google", which made them unreachable to
        users who wanted to pre-tune Parakeet before switching modes.
        """
        render_js = (JS_ROOT / "panels" / "asr" / "asr-panel-render.js").read_text(encoding="utf-8")
        # The visibility helper must key off the lock, not the current mode.
        self.assertIn("function isLocalParakeetTuningAvailable(config)", render_js)
        self.assertIn("!isDesktopBrowserQuickStartLocked(config)", render_js)
        # Visibility wiring must reference the new helper, not the legacy
        # isLocalParakeetMode that conflates "currently in local" with
        # "Parakeet tuning is available".
        self.assertIn("isLocalParakeetTuningAvailable(config)", render_js)
        self.assertIn(
            "setElementVisibility(elements.parakeetLatencyPresetRow, parakeetTuningVisible)",
            render_js,
        )
        self.assertIn(
            "setElementVisibility(elements.rtToolsLocalParakeetExtras, parakeetTuningVisible)",
            render_js,
        )

    def test_compact_layout_hides_decorative_labels_and_static_notes_in_tab_panels(self) -> None:
        """Compact layout strategy is 'control-only': decorative eyebrow labels
        and static documentation paragraphs inside tab panels must be hidden,
        while runtime status placeholders (id'd paragraphs that JS mutates) must
        keep their normal visibility. These rules are the contract that lets us
        keep the compact dashboard short on small/vertical windows.

        IMPORTANT: technical panels (recognition / tuning / asr_advanced) are
        intentionally excluded — they expose Parakeet-specific knobs whose
        meaning is non-obvious without eyebrow titles and inline notes.
        The 0.4.1 release kept those hints visible in compact mode too.
        """
        compact_css = (FRONTEND_ROOT / "css" / "compact-layout.css").read_text(encoding="utf-8")

        technical_exclusion = (
            ':not([data-tab-panel="recognition"])'
            ':not([data-tab-panel="tuning"])'
            ':not([data-tab-panel="asr_advanced"])'
        )

        required_substrings = (
            # (a) eyebrow labels in non-technical tab panels
            f".tab-panel{technical_exclusion}",
            ".eyebrow",
            # (b) notes under section/panel/surface headings
            ".section-heading .muted",
            ".panel-header .muted",
            ".surface-header > div > .muted",
            # (c) standalone static <p class="muted" data-i18n="..."> without an id
            'p.muted[data-i18n]:not([id])',
        )
        for fragment in required_substrings:
            self.assertIn(
                fragment,
                compact_css,
                msg=f"compact-layout.css must contain fragment: {fragment}",
            )

        # Technical hints must NOT be stripped wholesale in compact mode.
        # These selectors used to exist and have been deliberately removed.
        forbidden_strip_selectors = (
            'body.sst-layout-compact .dashboard-recognition-panel .dashboard-hint-text',
            'body.sst-layout-compact .asr-advanced-notes',
            'body.sst-layout-compact [data-tab-panel="asr_advanced"] .inline-field-note',
        )
        for selector in forbidden_strip_selectors:
            self.assertNotIn(
                selector,
                compact_css,
                msg=(
                    f"compact-layout.css must NOT bulk-hide technical hint surface: "
                    f"{selector}. These Parakeet/VAD hints existed in 0.4.1 and must "
                    f"stay visible in compact mode too."
                ),
            )

        # The :not([id]) clause is load-bearing: removing it would also hide
        # runtime status placeholders like #font-source-status / #ui-theme-status
        # which JS uses to surface live state.
        self.assertIn(":not([id])", compact_css)

    def test_overview_preview_card_sits_under_completed_transcript_and_hides_in_compact(self) -> None:
        """The live snapshot ('Текущий срез') sits inside the left overview column
        right after the completed transcript block, and compact layout must keep it
        hidden via a dedicated CSS rule even if the DOM is later restructured.
        """
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        compact_css = (FRONTEND_ROOT / "css" / "compact-layout.css").read_text(encoding="utf-8")

        final_pre_pos = index_html.find('id="final-transcript"')
        preview_pos = index_html.find('id="subtitle-output-preview"')
        right_column_pos = index_html.find('class="overview-right-column"')
        self.assertGreater(final_pre_pos, 0, "completed transcript block must exist")
        self.assertGreater(preview_pos, 0, "subtitle preview block must exist")
        self.assertLess(
            final_pre_pos,
            preview_pos,
            "preview must appear after the completed-transcript pre",
        )
        if right_column_pos > 0:
            self.assertLess(
                preview_pos,
                right_column_pos,
                "preview must live in the left overview column, before the right column",
            )

        self.assertIn("body.sst-layout-compact .overview-preview-card", compact_css)
        # The rule must use `display: none !important` so it survives DOM moves.
        rule_anchor = compact_css.index("body.sst-layout-compact .overview-preview-card")
        rule_window = compact_css[rule_anchor : rule_anchor + 200]
        self.assertIn("display: none !important", rule_window)

    def test_dashboard_ws_client_treats_timestamp_as_authoritative_freshness_signal(self) -> None:
        # Regression: dashboards sit on a long-lived /ws/events connection while
        # the backend resets per-session sequence counters on every Stop/Start.
        # If the ws client trusts those resettable sequences over created_at_ms,
        # it freezes after a runtime restart until sequences catch up. The
        # client must therefore compare timestamps first and only fall back to
        # the sequence when timestamps are equal or missing.
        ws_client_js = (JS_ROOT / "core" / "ws-client.js").read_text(encoding="utf-8")
        self.assertIn("isStale(eventType, payload)", ws_client_js)
        self.assertIn("created_at_ms", ws_client_js)
        self.assertIn("hasTimestamp && hasLastTimestamp", ws_client_js)
        self.assertIn("updatedAt > lastTimestamp", ws_client_js)
        self.assertIn("this.sequenceByType.set(eventType, currentSequence)", ws_client_js)


if __name__ == "__main__":
    unittest.main()
