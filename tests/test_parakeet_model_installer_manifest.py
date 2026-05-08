from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.asr.parakeet.model_installer import (
    OFFICIAL_EU_PARAKEET_FILENAME,
    OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME,
    official_eu_parakeet_integrity_state,
    read_official_eu_parakeet_manifest,
)


class ParakeetModelInstallerManifestTests(unittest.TestCase):
    def test_integrity_state_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            state, detail = official_eu_parakeet_integrity_state(models_dir)
            self.assertEqual(state, "missing")
            self.assertIsNone(detail)

    def test_integrity_state_checksum_unknown_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            target_dir = models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / OFFICIAL_EU_PARAKEET_FILENAME).write_bytes(b"fake-nemo")
            state, detail = official_eu_parakeet_integrity_state(models_dir)
            self.assertEqual(state, "checksum_unknown")
            self.assertIsNone(detail)

    def test_integrity_state_valid_and_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            target_dir = models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME
            target_dir.mkdir(parents=True, exist_ok=True)
            model_path = target_dir / OFFICIAL_EU_PARAKEET_FILENAME
            model_path.write_bytes(b"abcd")

            # Correct sha256 for b"abcd"
            manifest = {
                "sha256": "88d4266fd4e6338d13b845fcf289579d209c897823b9217da3e161936f031589",
            }
            (target_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            state, detail = official_eu_parakeet_integrity_state(models_dir)
            self.assertEqual(state, "valid")
            self.assertIsNone(detail)

            # Corrupt manifest checksum.
            manifest["sha256"] = "0" * 64
            (target_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            state, detail = official_eu_parakeet_integrity_state(models_dir)
            self.assertEqual(state, "corrupt")
            self.assertIsNotNone(detail)

    def test_manifest_reader_returns_dict_or_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            self.assertIsNone(read_official_eu_parakeet_manifest(models_dir))

            target_dir = models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME
            target_dir.mkdir(parents=True, exist_ok=True)
            payload = {"repo_id": "x", "sha256": "y"}
            (target_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(read_official_eu_parakeet_manifest(models_dir), payload)


if __name__ == "__main__":
    unittest.main()

