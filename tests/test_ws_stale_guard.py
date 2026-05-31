from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGIC_JS = PROJECT_ROOT / "frontend" / "js" / "core" / "ws-stale-guard-logic.js"


class WsStaleGuardJsTests(unittest.TestCase):
    def _run(self, script_body: str) -> dict:
        script_path = PROJECT_ROOT / "tests" / "_ws_stale_guard_scratch.mjs"
        logic_url = LOGIC_JS.resolve().as_uri()
        script_path.write_text(
            f'import {{ createWsStaleGuardState, isWsEventStale }} from "{logic_url}";\n{script_body}',
            encoding="utf-8",
        )
        try:
            completed = subprocess.run(
                ["node", str(script_path)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        finally:
            script_path.unlink(missing_ok=True)
        return json.loads(completed.stdout.strip())

    def test_accepts_newer_timestamp_after_sequence_reset(self) -> None:
        result = self._run(
            """
        const guard = createWsStaleGuardState();
        isWsEventStale(guard, "overlay_update", {
          created_at_ms: 1000,
          event_sequence: 99,
        });
        const stale = isWsEventStale(guard, "overlay_update", {
          created_at_ms: 2000,
          event_sequence: 1,
        });
        console.log(JSON.stringify({ stale }));
        """
        )
        self.assertFalse(result["stale"])

    def test_rejects_older_timestamp(self) -> None:
        result = self._run(
            """
        const guard = createWsStaleGuardState();
        isWsEventStale(guard, "overlay_update", {
          created_at_ms: 2000,
          event_sequence: 5,
        });
        const stale = isWsEventStale(guard, "overlay_update", {
          created_at_ms: 1000,
          event_sequence: 9,
        });
        console.log(JSON.stringify({ stale }));
        """
        )
        self.assertTrue(result["stale"])


if __name__ == "__main__":
    unittest.main()
