from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
JS_ROOT = FRONTEND_ROOT / "js"


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
            JS_ROOT / "panels" / "runtime-panel.js",
            JS_ROOT / "panels" / "asr-panel.js",
            JS_ROOT / "panels" / "model-manager-panel.js",
            JS_ROOT / "panels" / "translation-panel.js",
            JS_ROOT / "panels" / "overlay-panel.js",
            JS_ROOT / "panels" / "obs-captions-panel.js",
            JS_ROOT / "panels" / "diagnostics-panel.js",
            JS_ROOT / "panels" / "style-editor-panel.js",
            JS_ROOT / "panels" / "profiles-panel.js",
            JS_ROOT / "panels" / "remote-panel.js",
            JS_ROOT / "normalizers" / "config-normalizer.js",
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


if __name__ == "__main__":
    unittest.main()
