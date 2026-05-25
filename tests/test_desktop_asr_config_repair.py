from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from desktop.asr_config_repair import repair_legacy_custom_asr_realtime


class DesktopAsrConfigRepairTests(unittest.TestCase):
    def test_repairs_custom_preset_with_energy_gate(self) -> None:
        with TemporaryDirectory() as raw:
            config_path = Path(raw) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "asr": {
                            "realtime": {
                                "latency_preset": "custom",
                                "energy_gate_enabled": True,
                                "partial_min_delta_chars": 4,
                                "vad_mode": 1,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(repair_legacy_custom_asr_realtime(config_path))
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            realtime = payload["asr"]["realtime"]
            self.assertEqual(realtime["latency_preset"], "balanced")
            self.assertFalse(realtime["energy_gate_enabled"])
            self.assertEqual(realtime["partial_min_delta_chars"], 0)

    def test_skips_balanced_preset(self) -> None:
        with TemporaryDirectory() as raw:
            config_path = Path(raw) / "config.json"
            config_path.write_text(
                json.dumps({"asr": {"realtime": {"latency_preset": "balanced"}}}),
                encoding="utf-8",
            )
            self.assertFalse(repair_legacy_custom_asr_realtime(config_path))


if __name__ == "__main__":
    unittest.main()
