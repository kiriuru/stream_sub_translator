from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.core.structured_runtime_logger import StructuredRuntimeLogger


@contextmanager
def _verbose_runtime_events():
    """
    Enable SST_TRACE_RUNTIME_EVENTS_VERBOSE for the duration of the block.

    Without this flag, DBG/VRB events are filtered out by
    ``StructuredRuntimeLogger`` to match the 0.4.1 logs footprint on user
    installs. The existing assertions in this suite use DBG events
    (`translation_job_started`, `audio_track_start_attempt`, …) and VRB
    heartbeats (`browser_worker_status`), so we need the verbose channel on.
    """
    previous = os.environ.get("SST_TRACE_RUNTIME_EVENTS_VERBOSE")
    os.environ["SST_TRACE_RUNTIME_EVENTS_VERBOSE"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("SST_TRACE_RUNTIME_EVENTS_VERBOSE", None)
        else:
            os.environ["SST_TRACE_RUNTIME_EVENTS_VERBOSE"] = previous


class StructuredRuntimeLoggerTests(unittest.TestCase):
    def test_init_truncates_existing_log(self) -> None:
        with TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "runtime-events.log"
            log_path.write_text("old line\n", encoding="utf-8")
            logger = StructuredRuntimeLogger(Path(temp_dir))
            _ = logger
            self.assertEqual(log_path.read_text(encoding="utf-8"), "")

    def test_writes_compact_text_line(self) -> None:
        with TemporaryDirectory() as temp_dir, _verbose_runtime_events():
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
        with TemporaryDirectory() as temp_dir, _verbose_runtime_events():
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
        with TemporaryDirectory() as temp_dir, _verbose_runtime_events():
            logger = StructuredRuntimeLogger(Path(temp_dir))
            with patch.object(Path, "open", side_effect=OSError("disk unavailable")):
                logger.log("runtime_metrics", "metrics_snapshot", payload={"ok": True})

    def test_compacts_long_payload_strings_in_runtime_events(self) -> None:
        with TemporaryDirectory() as temp_dir, _verbose_runtime_events():
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
        with TemporaryDirectory() as temp_dir, _verbose_runtime_events():
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

    def test_default_skips_dbg_and_vrb_events(self) -> None:
        """
        Default footprint contract: high-frequency DBG/VRB events
        (browser ASR FSM, browser_worker_status, translation queue depth)
        do not reach runtime-events.log unless SST_DEEP_DIAGNOSTICS or the
        per-channel verbose flag is set.
        """
        previous = os.environ.pop("SST_DEEP_DIAGNOSTICS", None)
        previous_verbose = os.environ.pop("SST_TRACE_RUNTIME_EVENTS_VERBOSE", None)
        try:
            with TemporaryDirectory() as temp_dir:
                logger = StructuredRuntimeLogger(Path(temp_dir))
                logger.log("browser_recognition", "basr.fsm_transition", payload={"from_phase": "idle"})
                logger.log("browser_recognition", "browser_worker_status", payload={"connected": True})
                logger.log("translation_dispatcher", "translation_queue_depth_changed", payload={"queue_depth": 0})
                logger.log("translation_dispatcher", "translation_publish_accepted", payload={"sequence": 1})
                logger.log("browser_recognition", "browser_degraded", payload={"reason": "noise"})

                log_path = Path(temp_dir) / "runtime-events.log"
                lines = log_path.read_text(encoding="utf-8").splitlines()
                joined = "\n".join(lines)
                self.assertNotIn("basr.fsm_transition", joined)
                self.assertNotIn("browser_worker_status", joined)
                self.assertNotIn("translation_queue_depth_changed", joined)
                self.assertIn("translation_publish_accepted", joined)
                self.assertIn("browser_degraded", joined)
        finally:
            if previous is not None:
                os.environ["SST_DEEP_DIAGNOSTICS"] = previous
            if previous_verbose is not None:
                os.environ["SST_TRACE_RUNTIME_EVENTS_VERBOSE"] = previous_verbose
