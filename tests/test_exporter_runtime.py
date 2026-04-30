from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from backend.core.exporter import Exporter
from backend.core.subtitle_router import RuntimeOrchestrator


class ExporterRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.export_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_export_srt_formats_cues_and_falls_back_to_duration_when_end_is_missing(self) -> None:
        exporter = Exporter(self.export_dir)

        path = exporter.export_srt(
            "sample.srt",
            [
                {"srt_text": "Hello", "start_offset_ms": 0, "end_offset_ms": 0, "duration_ms": 0},
                {"srt_text": "World", "start_offset_ms": 2500, "end_offset_ms": 2600, "duration_ms": 100},
            ],
        )

        self.assertEqual(
            path.read_text(encoding="utf-8"),
            "1\n00:00:00,000 --> 00:00:01,500\nHello\n\n2\n00:00:02,500 --> 00:00:02,600\nWorld\n",
        )

    def test_runtime_export_session_replaces_existing_sequence_and_writes_jsonl_and_srt(self) -> None:
        orchestrator = RuntimeOrchestrator.__new__(RuntimeOrchestrator)
        orchestrator._session_id = "session-1"
        orchestrator._session_started_at_utc = "2026-01-01T00:00:00+00:00"
        orchestrator._session_started_at_monotonic = time.perf_counter() - 5.0
        orchestrator._session_export_records = []
        orchestrator._exporter = Exporter(self.export_dir)
        orchestrator.config_getter = lambda: {
            "profile": "default",
            "source_lang": "ru",
            "translation": {"enabled": True, "target_languages": ["en"]},
            "subtitle_output": {"show_source": True, "show_translations": True},
        }

        RuntimeOrchestrator._handle_completed_export_record(
            orchestrator,
            {
                "sequence": 1,
                "source_text": "Привет",
                "source_lang": "ru",
                "duration_ms": 1200,
                "finalized_at_monotonic": orchestrator._session_started_at_monotonic + 2.0,
                "srt_text": "Привет",
            },
        )
        RuntimeOrchestrator._handle_completed_export_record(
            orchestrator,
            {
                "sequence": 1,
                "source_text": "Привет",
                "source_lang": "ru",
                "duration_ms": 1200,
                "finalized_at_monotonic": orchestrator._session_started_at_monotonic + 2.4,
                "srt_text": "Привет\nHello",
            },
        )

        self.assertEqual(len(orchestrator._session_export_records), 1)
        self.assertEqual(orchestrator._session_export_records[0]["srt_text"], "Привет\nHello")

        files = RuntimeOrchestrator._export_session_files(
            orchestrator,
            stopped_at_utc="2026-01-01T00:00:05+00:00",
        )

        self.assertEqual(sorted(path.suffix for path in files), [".jsonl", ".srt"])
        jsonl_path = next(path for path in files if path.suffix == ".jsonl")
        srt_path = next(path for path in files if path.suffix == ".srt")

        rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows[0]["type"], "session")
        self.assertEqual(rows[1]["sequence"], 1)
        self.assertEqual(rows[1]["srt_text"], "Привет\nHello")
        self.assertIn("Привет\nHello", srt_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
