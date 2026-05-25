from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.asr.parakeet.model_installer import (
    OFFICIAL_EU_PARAKEET_FILENAME,
    OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME,
    invalidate_official_eu_parakeet_integrity_cache,
    official_eu_parakeet_integrity_state,
    read_official_eu_parakeet_manifest,
)


SHA_OF_ABCD = "88d4266fd4e6338d13b845fcf289579d209c897823b9217da3e161936f031589"


def _real_sha256(path: Path, **_: object) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ParakeetModelInstallerManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        invalidate_official_eu_parakeet_integrity_cache()

    def tearDown(self) -> None:
        invalidate_official_eu_parakeet_integrity_cache()

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
            manifest = {"sha256": SHA_OF_ABCD}
            (target_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            state, detail = official_eu_parakeet_integrity_state(models_dir)
            self.assertEqual(state, "valid")
            self.assertIsNone(detail)

            # Corrupt manifest checksum (cache key changes because expected_sha changes).
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

    def test_integrity_state_caches_sha256_result(self) -> None:
        """Regression: SHA-256 of the .nemo must run at most once per (file, sha)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            target_dir = models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / OFFICIAL_EU_PARAKEET_FILENAME).write_bytes(b"abcd")
            (target_dir / "manifest.json").write_text(
                json.dumps({"sha256": SHA_OF_ABCD}), encoding="utf-8"
            )

            with mock.patch(
                "backend.asr.parakeet.model_installer._sha256_file",
                side_effect=_real_sha256,
            ) as spy:
                for _ in range(10):
                    state, detail = official_eu_parakeet_integrity_state(models_dir)
                    self.assertEqual(state, "valid")
                    self.assertIsNone(detail)
                self.assertEqual(spy.call_count, 1)

    def test_integrity_cache_invalidates_on_file_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            target_dir = models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME
            target_dir.mkdir(parents=True, exist_ok=True)
            model_path = target_dir / OFFICIAL_EU_PARAKEET_FILENAME
            model_path.write_bytes(b"abcd")
            (target_dir / "manifest.json").write_text(
                json.dumps({"sha256": SHA_OF_ABCD}), encoding="utf-8"
            )

            with mock.patch(
                "backend.asr.parakeet.model_installer._sha256_file",
                side_effect=_real_sha256,
            ) as spy:
                state, _ = official_eu_parakeet_integrity_state(models_dir)
                self.assertEqual(state, "valid")

                # Replace file content with new bytes and matching new manifest.
                stat_before = model_path.stat()
                model_path.write_bytes(b"abcde")
                # Force mtime forward to defeat coarse filesystem timestamp resolution.
                forced_mtime_ns = stat_before.st_mtime_ns + 1_000_000_000
                os.utime(model_path, ns=(stat_before.st_atime_ns, forced_mtime_ns))
                sha_abcde = hashlib.sha256(b"abcde").hexdigest()
                (target_dir / "manifest.json").write_text(
                    json.dumps({"sha256": sha_abcde}), encoding="utf-8"
                )

                state, _ = official_eu_parakeet_integrity_state(models_dir)
                self.assertEqual(state, "valid")
                self.assertEqual(spy.call_count, 2)

    def test_invalidate_helper_drops_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            target_dir = models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / OFFICIAL_EU_PARAKEET_FILENAME).write_bytes(b"abcd")
            (target_dir / "manifest.json").write_text(
                json.dumps({"sha256": SHA_OF_ABCD}), encoding="utf-8"
            )

            with mock.patch(
                "backend.asr.parakeet.model_installer._sha256_file",
                side_effect=_real_sha256,
            ) as spy:
                official_eu_parakeet_integrity_state(models_dir)
                self.assertEqual(spy.call_count, 1)
                invalidate_official_eu_parakeet_integrity_cache()
                official_eu_parakeet_integrity_state(models_dir)
                self.assertEqual(spy.call_count, 2)

    def test_missing_file_does_not_pollute_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            with mock.patch(
                "backend.asr.parakeet.model_installer._sha256_file",
                side_effect=_real_sha256,
            ) as spy:
                for _ in range(3):
                    state, detail = official_eu_parakeet_integrity_state(models_dir)
                    self.assertEqual(state, "missing")
                    self.assertIsNone(detail)
                # The .nemo never existed, so sha256 must never run.
                self.assertEqual(spy.call_count, 0)


if __name__ == "__main__":
    unittest.main()

