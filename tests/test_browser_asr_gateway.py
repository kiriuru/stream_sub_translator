from __future__ import annotations

import unittest

from backend.core.browser_asr_gateway import BrowserAsrGateway


class _RecordingStructuredLogger:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def log(self, channel: str, event: str, *, source: str | None = None, payload: dict | None = None, **fields) -> None:
        merged_payload = dict(payload or {})
        merged_payload.update(fields)
        self.records.append(
            {
                "channel": channel,
                "event": event,
                "source": source,
                "payload": merged_payload,
            }
        )


class BrowserAsrGatewayTests(unittest.TestCase):
    def test_tracks_connection_state_and_last_error(self) -> None:
        logger = _RecordingStructuredLogger()
        gateway = BrowserAsrGateway(structured_logger=logger)

        gateway.worker_connected()
        gateway.update_status(
            {
                "reason": "recognition-started",
                "desired_running": True,
                "recognition_running": True,
                "recognition_state": "running",
                "last_error": "temporary glitch",
                "error_type": "network",
                "degraded_reason": "document_hidden",
                "visibility_state": "hidden",
                "rearm_count": 2,
                "restart_count": 3,
                "watchdog_rearm_count": 1,
                "rearm_delay_ms": 60,
                "last_partial_age_ms": 25,
                "last_final_age_ms": 120,
            }
        )
        gateway.note_partial(text_len=7, source_lang="en", sequence=11)
        gateway.note_final(text_len=12, source_lang="en", sequence=12)

        diagnostics = gateway.diagnostics()
        self.assertTrue(diagnostics.worker_connected)
        self.assertTrue(diagnostics.desired_running)
        self.assertTrue(diagnostics.recognition_running)
        self.assertEqual(diagnostics.last_error, "temporary glitch")
        self.assertEqual(diagnostics.error_type, "network")
        self.assertEqual(diagnostics.degraded_reason, "document_hidden")
        self.assertEqual(diagnostics.visibility_state, "hidden")
        self.assertEqual(diagnostics.rearm_count, 2)
        self.assertEqual(diagnostics.restart_count, 3)
        self.assertEqual(diagnostics.watchdog_rearm_count, 1)
        self.assertEqual(diagnostics.last_rearm_delay_ms, 60)
        self.assertEqual(diagnostics.last_partial_age_ms, 0)
        self.assertEqual(diagnostics.last_final_age_ms, 0)
        self.assertIsNotNone(diagnostics.last_partial_at_utc)
        self.assertIsNotNone(diagnostics.last_final_at_utc)

        events = [record["event"] for record in logger.records]
        self.assertIn("browser_worker_connected", events)
        self.assertIn("browser_worker_status", events)
        self.assertIn("browser_recognition_started", events)
        self.assertIn("browser_degraded", events)
        self.assertIn("browser_external_partial", events)
        self.assertIn("browser_external_final", events)

        gateway.worker_disconnected()
        diagnostics = gateway.diagnostics()
        self.assertFalse(diagnostics.worker_connected)
        self.assertFalse(diagnostics.websocket_ready)
        self.assertEqual(diagnostics.recognition_state, "disconnected")


if __name__ == "__main__":
    unittest.main()
