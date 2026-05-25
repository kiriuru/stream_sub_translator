from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.core.ui_trace_log import UiTraceLog, configure_ui_trace_log, ui_trace


class UiTraceLogTests(unittest.TestCase):
    def tearDown(self) -> None:
        import backend.core.ui_trace_log as module

        module.UiTraceLog._instance = None

    def test_configure_writes_jsonl_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            logger = configure_ui_trace_log(tmp)
            ui_trace("dashboard", "runtime", "status_transition", from_status="idle", to_status="listening")
            path = logger.path()
            self.assertTrue(path.exists())
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["surface"], "dashboard")
            self.assertEqual(records[0]["event"], "status_transition")
            self.assertEqual(records[0]["fields"]["from_status"], "idle")


if __name__ == "__main__":
    unittest.main()
