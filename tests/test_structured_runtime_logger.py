from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.core.structured_runtime_logger import StructuredRuntimeLogger


class StructuredRuntimeLoggerTests(unittest.TestCase):
    def test_init_truncates_existing_log(self) -> None:
        with TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "runtime-events.log"
            log_path.write_text("old line\n", encoding="utf-8")
            logger = StructuredRuntimeLogger(Path(temp_dir))
            _ = logger
            self.assertEqual(log_path.read_text(encoding="utf-8"), "")

    def test_writes_compact_text_line(self) -> None:
        with TemporaryDirectory() as temp_dir:
            logger = StructuredRuntimeLogger(Path(temp_dir))
            logger.log(
                "translation_dispatcher",
                "translation_job_started",
                source="translation_dispatcher",
                payload={"sequence": 9, "provider": "stub", "latency_ms": 12.5},
            )

            log_path = Path(temp_dir) / "runtime-events.log"
            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            line = lines[0]
            self.assertRegex(line, r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} DBG\] Translation Dispatcher :: translation_job_started")
            self.assertIn("latency_ms=12.5", line)
            self.assertIn("provider=stub", line)
            self.assertIn("sequence=9", line)

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

            line = (Path(temp_dir) / "runtime-events.log").read_text(encoding="utf-8").splitlines()[0]
            self.assertIn("api_key=[redacted]", line)
            self.assertIn("token=[redacted]", line)
            self.assertNotIn("secret-value", line)
            self.assertNotIn("oauth-token", line)

    def test_write_failures_are_best_effort(self) -> None:
        with TemporaryDirectory() as temp_dir:
            logger = StructuredRuntimeLogger(Path(temp_dir))
            with patch.object(Path, "open", side_effect=OSError("disk unavailable")):
                logger.log("runtime_metrics", "metrics_snapshot", payload={"ok": True})

    def test_compacts_long_payload_strings_in_runtime_events(self) -> None:
        with TemporaryDirectory() as temp_dir:
            logger = StructuredRuntimeLogger(Path(temp_dir))
            long_msg = "e" * 400
            logger.log(
                "browser_recognition",
                "browser_error",
                source="browser_asr_gateway",
                payload={"error": long_msg, "code": 42},
            )
            log_path = Path(temp_dir) / "runtime-events.log"
            line = log_path.read_text(encoding="utf-8").splitlines()[0]
            self.assertIn("code=42", line)
            self.assertLess(len(line), 500)
            self.assertIn("error=", line)

    def test_experimental_browser_channel_is_recorded_in_runtime_events(self) -> None:
        with TemporaryDirectory() as temp_dir:
            logger = StructuredRuntimeLogger(Path(temp_dir))
            logger.log(
                "browser_recognition_experimental",
                "audio_track_start_attempt",
                payload={"browser_mode": "browser_google_experimental", "chunk": "not-audio-data"},
            )

            log_path = Path(temp_dir) / "runtime-events.log"
            line = log_path.read_text(encoding="utf-8").splitlines()[0]
            self.assertIn("audio_track_start_attempt", line)
            self.assertIn("browser_mode=browser_google_experimental", line)
            self.assertIn("chunk=not-audio-data", line)
