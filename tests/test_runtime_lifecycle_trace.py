from __future__ import annotations

import unittest

from backend.core.runtime_lifecycle_trace import (
    summarize_asr_diagnostics_snapshot,
    summarize_device_resolution,
    summarize_metrics_snapshot,
    summarize_runtime_config,
)


class RuntimeLifecycleTraceTests(unittest.TestCase):
    def test_summarize_runtime_config_includes_asr_and_audio(self) -> None:
        summary = summarize_runtime_config(
            {
                "config_version": 7,
                "asr": {
                    "mode": "local",
                    "provider_preference": "official_eu_parakeet_low_latency",
                    "prefer_gpu": False,
                    "realtime": {"latency_preset": "quality"},
                },
                "audio": {"input_device_id": "2"},
                "translation": {"enabled": True, "provider": "google_web", "target_languages": ["en"]},
                "remote": {"role": "disabled"},
            }
        )
        self.assertEqual(summary["asr.mode"], "local")
        self.assertEqual(summary["audio.input_device_id"], "2")
        self.assertEqual(summary["asr.latency_preset"], "quality")
        self.assertEqual(summary["target_languages_count"], 1)

    def test_summarize_device_resolution_marks_config_fallback(self) -> None:
        summary = summarize_device_resolution(
            requested_device_id=None,
            resolved_device_id="mic-2",
            audio_input_count=3,
            configured_device_id="mic-2",
        )
        self.assertEqual(summary["resolution"], "config")

    def test_summarize_metrics_snapshot_keeps_vad_counters(self) -> None:
        summary = summarize_metrics_snapshot({"vad_segments_partial": 4, "asr_queue_depth": 1})
        self.assertEqual(summary["vad_segments_partial"], 4)
        self.assertEqual(summary["asr_queue_depth"], 1)

    def test_summarize_asr_diagnostics_snapshot_maps_sample_rate(self) -> None:
        summary = summarize_asr_diagnostics_snapshot(
            {"sample_rate": 16000, "model_loaded": True, "selected_device": "cpu"}
        )
        self.assertEqual(summary["sample_rate"], 16000)
        self.assertEqual(summary["capture_sample_rate"], 16000)
        self.assertTrue(summary["model_loaded"])


if __name__ == "__main__":
    unittest.main()
