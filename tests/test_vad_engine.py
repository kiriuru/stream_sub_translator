from __future__ import annotations

import unittest
from unittest import mock

from backend.core.vad import VadEngine


class VadEngineTests(unittest.TestCase):
    def test_buffer_keeps_incomplete_frame_until_next_chunk(self) -> None:
        engine = VadEngine(sample_rate=16000, frame_duration_ms=30, energy_gate_enabled=False)
        # force speech for all frames so the engine would admit once a full frame is available
        engine.vad.is_speech = mock.Mock(return_value=True)  # type: ignore[method-assign]

        half_frame = b"\x00\x00" * (engine.frame_bytes // 4)  # bytes are int16, so /4 keeps < frame_bytes
        self.assertEqual(engine.process_chunk(half_frame), [])
        # Add the remaining bytes to complete a frame.
        remaining = b"\x00\x00" * (engine.frame_bytes // 4)
        segments = engine.process_chunk(remaining)
        # We don't necessarily emit partial immediately, but internal speech_frames should grow.
        self.assertTrue(engine._speech_frames)  # noqa: SLF001
        self.assertIsInstance(segments, list)

    def test_frame_count_uses_ceil_to_avoid_shorter_effective_holds(self) -> None:
        engine = VadEngine(sample_rate=16000, frame_duration_ms=30, energy_gate_enabled=False)
        engine.configure(
            silence_hold_ms=181,  # should resolve to 7 frames (210ms) with ceil, not 6 (180ms)
            finalization_hold_ms=181,
            min_speech_ms=0,
            partial_emit_interval_ms=450,
            max_segment_ms=6000,
            energy_gate_enabled=False,
            min_rms_for_recognition=0.0,
            min_voiced_ratio=0.0,
            first_partial_min_speech_ms=0,
        )
        self.assertEqual(engine.silence_hold_frames, 7)
        self.assertEqual(engine.finalization_hold_frames, 7)


if __name__ == "__main__":
    unittest.main()

