from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.core.structured_runtime_logger import StructuredRuntimeLogger


class StructuredRuntimeLoggerTests(unittest.TestCase):
    def test_writes_valid_jsonl(self) -> None:
        with TemporaryDirectory() as temp_dir:
            logger = StructuredRuntimeLogger(Path(temp_dir))
            logger.log(
                "translation_dispatcher",
                "translation_job_started",
                source="translation_dispatcher",
                payload={"sequence": 9, "provider": "stub", "latency_ms": 12.5},
            )

            log_path = Path(temp_dir) / "translation-dispatcher.log"
            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["event"], "translation_job_started")
            self.assertEqual(record["source"], "translation_dispatcher")
            self.assertEqual(record["sequence"], 9)
            self.assertEqual(record["provider"], "stub")

    def test_redacts_secrets(self) -> None:
        with TemporaryDirectory() as temp_dir:
            logger = StructuredRuntimeLogger(Path(temp_dir))
            logger.log(
                "browser_recognition",
                "browser_worker_status",
                payload={
                    "api_key": "secret-value",
                    "token": "secret-token",
                    "access_token": "oauth-token",
                    "refresh_token": "refresh-me",
                    "nested": {
                        "pair_code": "123456",
                        "authorization": "Bearer abc",
                        "client_secret": "client-secret-value",
                        "credentials_blob": "serialized-secret",
                    },
                },
            )

            record = json.loads((Path(temp_dir) / "browser-recognition.log").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["api_key"], "[redacted]")
            self.assertEqual(record["token"], "[redacted]")
            self.assertEqual(record["access_token"], "[redacted]")
            self.assertEqual(record["refresh_token"], "[redacted]")
            self.assertEqual(record["nested"]["pair_code"], "[redacted]")
            self.assertEqual(record["nested"]["authorization"], "[redacted]")
            self.assertEqual(record["nested"]["client_secret"], "[redacted]")
            self.assertEqual(record["nested"]["credentials_blob"], "[redacted]")

    def test_write_failures_are_best_effort(self) -> None:
        with TemporaryDirectory() as temp_dir:
            logger = StructuredRuntimeLogger(Path(temp_dir))
            with patch.object(Path, "open", side_effect=OSError("disk unavailable")):
                logger.log("runtime_metrics", "metrics_snapshot", payload={"ok": True})
