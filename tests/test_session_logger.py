from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from backend.core.session_logger import SessionLogManager


class SessionLogManagerTests(unittest.TestCase):
    def test_repeated_messages_collapse_even_when_timestamps_differ(self) -> None:
        with TemporaryDirectory() as temp_dir:
            manager = SessionLogManager(Path(temp_dir))
            manager.log("browser_worker", "recognition.onend", source="browser-worker")
            manager.log("browser_worker", "recognition.onend", source="browser-worker")
            manager.log("browser_worker", "recognition.onend", source="browser-worker")
            manager.flush()

            lines = (Path(temp_dir) / "session-latest.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            self.assertEqual(first["message"], "recognition.onend")
            self.assertEqual(first["channel"], "browser_worker")
            self.assertEqual(second["type"], "repeat")
            self.assertEqual(second["repeat_count"], 2)

    def test_details_are_part_of_deduplication_key(self) -> None:
        with TemporaryDirectory() as temp_dir:
            manager = SessionLogManager(Path(temp_dir))
            manager.log("overlay", "overlay payload", source="overlay", details={"state": "idle"})
            manager.log("overlay", "overlay payload", source="overlay", details={"state": "listening"})
            manager.flush()

            lines = (Path(temp_dir) / "session-latest.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            self.assertEqual(first["details"]["state"], "idle")
            self.assertEqual(second["details"]["state"], "listening")

    def test_permission_error_drops_event_without_raising(self) -> None:
        with TemporaryDirectory() as temp_dir:
            manager = SessionLogManager(Path(temp_dir))
            with mock.patch.object(manager, "_safe_append_line_locked", return_value=False):
                result = manager.log("dashboard", "cannot write", source="dashboard")

            self.assertEqual(result["ok"], True)
            self.assertEqual(result["logged"], False)
            self.assertEqual(result["reason"], "log_write_failed")
            diagnostics = manager.diagnostics()
            self.assertEqual(diagnostics["client_log_events_received"], 1)
            self.assertEqual(diagnostics["client_log_events_dropped"], 1)


if __name__ == "__main__":
    unittest.main()
