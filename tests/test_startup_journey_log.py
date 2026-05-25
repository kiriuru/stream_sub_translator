from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.core.startup_journey_log import StartupJourneyLog, configure_startup_journey_log


class StartupJourneyLogTests(unittest.TestCase):
    def test_writes_jsonl_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            logger = configure_startup_journey_log(logs_dir)
            logger.log("desktop", "bootstrap_begin", project_root=str(logs_dir))
            logger.log("runtime", "runtime_start_complete", status="listening")
            lines = logger.path().read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            self.assertEqual(first["phase"], "desktop")
            self.assertEqual(first["event"], "bootstrap_begin")
            second = json.loads(lines[1])
            self.assertEqual(second["event"], "runtime_start_complete")
            self.assertEqual(second["fields"]["status"], "listening")


if __name__ == "__main__":
    unittest.main()
