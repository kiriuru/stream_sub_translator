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
                "client_segment_id": "browser-seg-3",
                "forced_final": True,
                "last_error": "temporary glitch",
                "error_type": "network",
                "degraded_reason": "document_hidden",
                "visibility_state": "hidden",
                "rearm_count": 2,
                "restart_count": 3,
                "watchdog_rearm_count": 1,
                "rearm_delay_ms": 60,
                "duplicate_partial_suppressed": 4,
                "duplicate_final_suppressed": 2,
                "late_forced_final_suppressed": 1,
                "mic_track_ready_state": "live",
                "mic_track_muted": False,
                "mic_rms": 0.021,
                "mic_active_recent_ms": 320,
                "last_mic_activity_at": 1234567890,
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
        self.assertEqual(diagnostics.client_segment_id, "browser-seg-3")
        self.assertTrue(diagnostics.forced_final)
        self.assertEqual(diagnostics.duplicate_partial_suppressed, 4)
        self.assertEqual(diagnostics.duplicate_final_suppressed, 2)
        self.assertEqual(diagnostics.late_forced_final_suppressed, 1)
        self.assertEqual(diagnostics.mic_track_ready_state, "live")
        self.assertFalse(diagnostics.mic_track_muted)
        self.assertAlmostEqual(diagnostics.mic_rms or 0.0, 0.021, places=3)
        self.assertEqual(diagnostics.mic_active_recent_ms, 320)
        self.assertEqual(diagnostics.last_mic_activity_at, 1234567890)
        self.assertEqual(diagnostics.last_partial_age_ms, 0)
        self.assertEqual(diagnostics.last_final_age_ms, 0)
        self.assertIsNotNone(diagnostics.last_partial_at_utc)
        self.assertIsNotNone(diagnostics.last_final_at_utc)

        events = [record["event"] for record in logger.records]
        self.assertIn("browser_worker_connected", events)
        self.assertIn("browser_recognition_started", events)
        self.assertIn("browser_degraded", events)
        self.assertIn("browser_external_partial", events)
        self.assertIn("browser_external_final", events)

        gateway.worker_disconnected()
        diagnostics = gateway.diagnostics()
        self.assertFalse(diagnostics.worker_connected)
        self.assertFalse(diagnostics.websocket_ready)
        self.assertEqual(diagnostics.recognition_state, "disconnected")

    def test_skips_chatty_status_snapshots_for_routine_cycle_reasons(self) -> None:
        logger = _RecordingStructuredLogger()
        gateway = BrowserAsrGateway(structured_logger=logger)

        gateway.worker_connected()
        logger.records.clear()

        gateway.update_status(
            {
                "reason": "recognition-started",
                "desired_running": True,
                "recognition_running": True,
                "recognition_state": "running",
                "visibility_state": "visible",
                "rearm_count": 24,
            }
        )
        self.assertNotIn("browser_worker_status", [record["event"] for record in logger.records])
        self.assertNotIn("browser_recognition_started", [record["event"] for record in logger.records])

        logger.records.clear()
        gateway.update_status(
            {
                "reason": "recognition-started",
                "desired_running": True,
                "recognition_running": True,
                "recognition_state": "running",
                "visibility_state": "visible",
                "rearm_count": 25,
            }
        )
        self.assertIn("browser_recognition_started", [record["event"] for record in logger.records])

    def test_samples_repeated_no_speech_errors_but_keeps_critical_status(self) -> None:
        logger = _RecordingStructuredLogger()
        gateway = BrowserAsrGateway(structured_logger=logger)

        gateway.worker_connected()
        gateway.update_status(
            {
                "reason": "recognition-error",
                "desired_running": True,
                "recognition_running": True,
                "recognition_state": "running",
                "visibility_state": "visible",
                "rearm_count": 23,
                "last_error": "no-speech",
                "error_type": "no-speech",
            }
        )

        logger.records.clear()
        gateway.update_status(
            {
                "reason": "recognition-error",
                "desired_running": True,
                "recognition_running": True,
                "recognition_state": "running",
                "visibility_state": "visible",
                "rearm_count": 24,
                "last_error": "no-speech",
                "error_type": "no-speech",
            }
        )
        self.assertNotIn("browser_onerror", [record["event"] for record in logger.records])
        self.assertNotIn("browser_error", [record["event"] for record in logger.records])

        logger.records.clear()
        gateway.update_status(
            {
                "reason": "recognition-error",
                "desired_running": True,
                "recognition_running": True,
                "recognition_state": "running",
                "visibility_state": "visible",
                "rearm_count": 25,
                "last_error": "no-speech",
                "error_type": "no-speech",
            }
        )
        self.assertIn("browser_onerror", [record["event"] for record in logger.records])
        self.assertIn("browser_error", [record["event"] for record in logger.records])

    def test_accepts_experimental_audio_track_fields_and_logs_to_experimental_channel(self) -> None:
        logger = _RecordingStructuredLogger()
        gateway = BrowserAsrGateway(structured_logger=logger)

        gateway.worker_connected(browser_mode="browser_google_experimental")
        gateway.update_status(
            {
                "reason": "audio-track-start-attempt",
                "browser_mode": "browser_google_experimental",
                "experimental": True,
                "start_mode": "audio_track",
                "desired_running": True,
                "recognition_running": False,
                "recognition_state": "starting",
                "websocket_ready": True,
                "audio_track_enabled": True,
                "audio_track_live": True,
                "audio_track_kind": "audio",
                "audio_track_ready_state": "live",
                "audio_track_muted": False,
                "audio_track_reused": True,
                "audio_track_reopen_count": 2,
                "audio_track_start_attempts": 3,
                "audio_track_start_failures": 1,
                "fallback_to_default_start": True,
                "fallback_used": False,
                "last_start_error": "track start rejected",
                "last_audio_track_error": None,
            }
        )

        diagnostics = gateway.diagnostics()
        self.assertEqual(diagnostics.browser_mode, "browser_google_experimental")
        self.assertTrue(diagnostics.experimental)
        self.assertEqual(diagnostics.start_mode, "audio_track")
        self.assertEqual(diagnostics.audio_track_ready_state, "live")
        self.assertEqual(diagnostics.audio_track_start_attempts, 3)
        self.assertEqual(diagnostics.audio_track_start_failures, 1)
        self.assertEqual(diagnostics.last_start_error, "track start rejected")

        experimental_records = [record for record in logger.records if record["channel"] == "browser_recognition_experimental"]
        self.assertTrue(experimental_records)
        self.assertIn("experimental_worker_loaded", [record["event"] for record in experimental_records])
        self.assertIn("audio_track_start_attempt", [record["event"] for record in experimental_records])


if __name__ == "__main__":
    unittest.main()
