from __future__ import annotations

import unittest

from backend.core.pipeline_trace_helpers import (
    PipelineTraceHeartbeat,
    audio_bytes_metrics,
    text_outcome_metrics,
    vad_segment_metrics,
)
from backend.core.vad import VadSegment


class PipelineTraceHelpersTests(unittest.TestCase):
    def test_audio_bytes_metrics_empty(self) -> None:
        self.assertEqual(audio_bytes_metrics(b"")["audio_byte_len"], 0)
        self.assertNotIn("audio_rms", audio_bytes_metrics(b""))

    def test_audio_bytes_metrics_with_samples(self) -> None:
        payload = audio_bytes_metrics(b"\x00\x00\xff\x7f")
        self.assertEqual(payload["audio_byte_len"], 4)
        self.assertIn("audio_rms", payload)

    def test_vad_segment_metrics(self) -> None:
        segment = VadSegment(
            kind="partial",
            audio=b"\x00\x00",
            duration_ms=120,
            voiced_ratio=0.25,
            average_rms=42.0,
        )
        metrics = vad_segment_metrics(segment)
        self.assertEqual(metrics["kind"], "partial")
        self.assertEqual(metrics["duration_ms"], 120)

    def test_text_outcome_metrics(self) -> None:
        metrics = text_outcome_metrics("hello")
        self.assertTrue(metrics["text_nonempty"])
        self.assertEqual(metrics["text_len"], 5)

    def test_heartbeat_rate_limits(self) -> None:
        heartbeat = PipelineTraceHeartbeat(interval_ms=1000.0)
        self.assertTrue(heartbeat.due())
        self.assertFalse(heartbeat.due())
