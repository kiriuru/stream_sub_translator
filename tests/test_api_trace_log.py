from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.core.api_trace_log import ApiTraceLog, api_trace, configure_api_trace_log


class ApiTraceLogTests(unittest.TestCase):
    def tearDown(self) -> None:
        ApiTraceLog._instance = None

    def test_configure_writes_http_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            logger = configure_api_trace_log(tmp)
            api_trace("http", "request_complete", method="GET", path="/api/health", status_code=200)
            records = [json.loads(line) for line in logger.path().read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["channel"], "http")
            self.assertEqual(records[0]["event"], "request_complete")


if __name__ == "__main__":
    unittest.main()
