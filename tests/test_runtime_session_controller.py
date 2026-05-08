from __future__ import annotations

import unittest

from backend.core.runtime.runtime_session_controller import RuntimeSessionController


class RuntimeSessionControllerTests(unittest.TestCase):
    def _make_controller(
        self,
        *,
        new_session_id: str = "session-1",
        now_utc_iso: str = "2026-01-01T00:00:00+00:00",
        now_monotonic: float = 100.0,
    ) -> RuntimeSessionController:
        return RuntimeSessionController(
            bump_asr_runtime_generation=lambda: None,
            set_sequence_zero=lambda: None,
            new_session_id=lambda: new_session_id,
            now_utc_iso=lambda: now_utc_iso,
            now_monotonic=lambda: now_monotonic,
            reset_metrics=lambda: None,
            reset_in_flight_transcribe_count=lambda: None,
            clear_runtime_loop=lambda: None,
        )

    def test_default_state(self) -> None:
        ctl = self._make_controller()
        self.assertIsNone(ctl.session_id)
        self.assertIsNone(ctl.session_started_at_utc)
        self.assertIsNone(ctl.session_started_at_monotonic)
        self.assertEqual(ctl.session_export_records, [])

    def test_start_new_session_sets_identity_and_resets_records(self) -> None:
        ctl = self._make_controller(new_session_id="session-9", now_utc_iso="2026-01-01T00:00:01+00:00", now_monotonic=55.0)
        ctl.add_completed_export_record({"finalized_at_monotonic": 60.0, "duration_ms": 1000, "srt_text": "x"})
        self.assertEqual(ctl.session_export_records, [])

        started_at = ctl.start_new_session()
        self.assertEqual(started_at, "2026-01-01T00:00:01+00:00")
        self.assertEqual(ctl.session_id, "session-9")
        self.assertEqual(ctl.session_started_at_utc, "2026-01-01T00:00:01+00:00")
        self.assertEqual(ctl.session_started_at_monotonic, 55.0)
        self.assertEqual(ctl.session_export_records, [])

    def test_reset_export_session_clears_identity_and_records(self) -> None:
        ctl = self._make_controller()
        ctl.start_new_session()
        ctl.add_completed_export_record({"finalized_at_monotonic": 101.0, "duration_ms": 500, "srt_text": "ok"})
        self.assertTrue(ctl.session_export_records)

        ctl.reset_export_session()
        self.assertIsNone(ctl.session_id)
        self.assertIsNone(ctl.session_started_at_utc)
        self.assertIsNone(ctl.session_started_at_monotonic)
        self.assertEqual(ctl.session_export_records, [])

    def test_add_completed_export_record_ignores_without_session(self) -> None:
        ctl = self._make_controller()
        ctl.add_completed_export_record({"finalized_at_monotonic": 101.0, "duration_ms": 500, "srt_text": "ignored"})
        self.assertEqual(ctl.session_export_records, [])

    def test_add_completed_export_record_ignores_invalid_finalized_at(self) -> None:
        ctl = self._make_controller(now_monotonic=100.0)
        ctl.start_new_session()
        ctl.add_completed_export_record({"duration_ms": 500, "srt_text": "ignored"})
        ctl.add_completed_export_record({"finalized_at_monotonic": "bad", "duration_ms": 500, "srt_text": "ignored"})  # type: ignore[arg-type]
        self.assertEqual(ctl.session_export_records, [])

    def test_add_completed_export_record_computes_offsets_and_preserves_duration(self) -> None:
        ctl = self._make_controller(now_monotonic=10.0)
        ctl.start_new_session()
        ctl.add_completed_export_record(
            {
                "sequence": 1,
                "duration_ms": 1200,
                "finalized_at_monotonic": 12.4,
                "srt_text": "Hello",
            }
        )
        self.assertEqual(len(ctl.session_export_records), 1)
        rec = ctl.session_export_records[0]
        self.assertEqual(rec["session_id"], "session-1")
        self.assertEqual(rec["end_offset_ms"], 2400)
        self.assertEqual(rec["start_offset_ms"], 1200)
        self.assertEqual(rec["duration_ms"], 1200)

    def test_add_completed_export_record_fallback_start_offset_when_duration_missing(self) -> None:
        ctl = self._make_controller(now_monotonic=10.0)
        ctl.start_new_session()
        ctl.add_completed_export_record(
            {
                "sequence": 1,
                "finalized_at_monotonic": 11.0,
                "srt_text": "Hello",
            }
        )
        rec = ctl.session_export_records[0]
        self.assertEqual(rec["end_offset_ms"], 1000)
        self.assertEqual(rec["start_offset_ms"], 0)
        self.assertIsNone(rec["duration_ms"])

    def test_add_completed_export_record_replaces_by_sequence(self) -> None:
        ctl = self._make_controller(now_monotonic=0.0)
        ctl.start_new_session()
        ctl.add_completed_export_record({"sequence": 1, "duration_ms": 1200, "finalized_at_monotonic": 2.0, "srt_text": "A"})
        ctl.add_completed_export_record({"sequence": 1, "duration_ms": 1200, "finalized_at_monotonic": 2.4, "srt_text": "B"})
        self.assertEqual(len(ctl.session_export_records), 1)
        self.assertEqual(ctl.session_export_records[0]["srt_text"], "B")

    def test_add_completed_export_record_appends_when_sequence_not_int(self) -> None:
        ctl = self._make_controller(now_monotonic=0.0)
        ctl.start_new_session()
        ctl.add_completed_export_record({"sequence": "x", "duration_ms": 1200, "finalized_at_monotonic": 2.0, "srt_text": "A"})  # type: ignore[arg-type]
        ctl.add_completed_export_record({"duration_ms": 1200, "finalized_at_monotonic": 2.4, "srt_text": "B"})
        self.assertEqual(len(ctl.session_export_records), 2)

    def test_build_session_export_payload(self) -> None:
        ctl = self._make_controller(new_session_id="session-2", now_utc_iso="2026-01-01T00:00:00+00:00", now_monotonic=10.0)
        self.assertIsNone(ctl.build_session_export_payload({}, stopped_at_utc="2026-01-01T00:00:05+00:00"))

        ctl.start_new_session()
        ctl.add_completed_export_record({"sequence": 1, "duration_ms": 1200, "finalized_at_monotonic": 11.2, "srt_text": "hi"})
        payload = ctl.build_session_export_payload(
            {
                "profile": "default",
                "source_lang": "ru",
                "translation": {"enabled": True, "target_languages": ["en"]},
                "subtitle_output": {"show_source": True, "show_translations": True},
            },
            stopped_at_utc="2026-01-01T00:00:05+00:00",
        )
        self.assertIsNotNone(payload)
        session_row, records = payload or ({}, [])
        self.assertEqual(session_row["type"], "session")
        self.assertEqual(session_row["session_id"], "session-2")
        self.assertEqual(session_row["started_at_utc"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(session_row["stopped_at_utc"], "2026-01-01T00:00:05+00:00")
        self.assertEqual(session_row["profile"], "default")
        self.assertEqual(session_row["source_lang"], "ru")
        self.assertEqual(session_row["translation_enabled"], True)
        self.assertEqual(session_row["target_languages"], ["en"])
        self.assertEqual(session_row["record_count"], 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["sequence"], 1)

    def test_diagnostics(self) -> None:
        ctl = self._make_controller(new_session_id="session-3")
        diag = ctl.diagnostics()
        self.assertIn("session_id", diag)
        self.assertIn("has_active_session", diag)
        self.assertIn("record_count", diag)
        self.assertFalse(diag["has_active_session"])

        ctl.start_new_session()
        diag2 = ctl.diagnostics()
        self.assertTrue(diag2["has_active_session"])
        self.assertEqual(diag2["session_id"], "session-3")


if __name__ == "__main__":
    unittest.main()

