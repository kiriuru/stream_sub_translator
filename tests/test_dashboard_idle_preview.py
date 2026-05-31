from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACTION_HELPERS = PROJECT_ROOT / "frontend" / "js" / "dashboard" / "action-helpers.js"
NODE_TEST = PROJECT_ROOT / "tests" / "fixtures" / "dashboard_idle_preview_test.mjs"


class DashboardIdlePreviewTests(unittest.TestCase):
    def test_action_helpers_gate_live_overlay_when_idle(self) -> None:
        source = ACTION_HELPERS.read_text(encoding="utf-8")
        self.assertIn("export function hasRenderableOverlayContent", source)
        self.assertIn("export function shouldUseLiveOverlayPreview", source)
        self.assertIn("if (shouldUseLiveOverlayPreview(state))", source)
        self.assertNotIn("if (state.overlay?.payload) {", source)

    def test_idle_empty_overlay_replay_keeps_style_placeholder(self) -> None:
        if not NODE_TEST.exists():
            self.skipTest("missing node fixture")
        completed = subprocess.run(
            ["node", str(NODE_TEST)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 and "Cannot find module" in (completed.stderr or ""):
            self.skipTest(f"node import unavailable: {completed.stderr.strip()}")
        self.assertEqual(
            completed.returncode,
            0,
            msg=(completed.stderr or completed.stdout or "node test failed").strip(),
        )


if __name__ == "__main__":
    unittest.main()
