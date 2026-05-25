from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.core.pipeline_trace_log import configure_pipeline_trace_log, pipeline_trace


class PipelineTraceLogTests(unittest.TestCase):
    def test_writes_thread_and_event_records(self) -> None:
        with TemporaryDirectory() as raw:
            logs_dir = Path(raw)
            configure_pipeline_trace_log(logs_dir)
            pipeline_trace(
                "asyncio_capture_task",
                "local_asr_pipeline",
                "capture_loop_enter",
                device_id="2",
            )
            lines = logs_dir.joinpath("pipeline-trace.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["lane"], "asyncio_capture_task")
            self.assertEqual(record["component"], "local_asr_pipeline")
            self.assertEqual(record["event"], "capture_loop_enter")
            self.assertIn("thread", record)
            self.assertEqual(record["fields"]["device_id"], "2")
