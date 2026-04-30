from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from desktop.bootstrap_payload import (
    BOOTSTRAP_INSTALL_MARKER,
    BOOTSTRAP_RUNTIME_DIR,
    BOOTSTRAP_RUNTIME_HIDDEN_EXE,
    build_payload_manifest,
    create_payload_archive,
    install_or_repair_runtime,
    verify_runtime_files,
)


class BootstrapPayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.payload_root = self.root / "payload-root"
        self.payload_root.mkdir(parents=True, exist_ok=True)
        (self.payload_root / BOOTSTRAP_RUNTIME_HIDDEN_EXE).write_text("runtime-exe", encoding="utf-8")
        runtime_dir = self.payload_root / BOOTSTRAP_RUNTIME_DIR
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "module.bin").write_text("module", encoding="utf-8")
        self.manifest = build_payload_manifest(self.payload_root, app_version="0.2.9.0", release_track="stable")
        self.archive_path = self.root / "payload.zip"
        create_payload_archive(self.payload_root, self.archive_path, self.manifest)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_install_or_repair_runtime_restores_missing_files(self) -> None:
        install_root = self.root / "install"
        install_root.mkdir(parents=True, exist_ok=True)

        verified, mismatches = install_or_repair_runtime(install_root, self.manifest, self.archive_path)
        self.assertTrue(verified)
        self.assertEqual(mismatches, [])
        self.assertTrue((install_root / BOOTSTRAP_RUNTIME_HIDDEN_EXE).exists())
        self.assertTrue((install_root / BOOTSTRAP_RUNTIME_DIR / "module.bin").exists())
        self.assertTrue((install_root / BOOTSTRAP_RUNTIME_DIR / BOOTSTRAP_INSTALL_MARKER).exists())

        (install_root / BOOTSTRAP_RUNTIME_DIR / "module.bin").unlink()
        verified_after_delete, delete_mismatches = verify_runtime_files(install_root, self.manifest)
        self.assertFalse(verified_after_delete)
        self.assertTrue(any(item.startswith("missing:") for item in delete_mismatches))

        repaired, repaired_mismatches = install_or_repair_runtime(install_root, self.manifest, self.archive_path)
        self.assertTrue(repaired)
        self.assertEqual(repaired_mismatches, [])

    def test_verify_runtime_files_detects_corruption(self) -> None:
        install_root = self.root / "install-corrupt"
        install_root.mkdir(parents=True, exist_ok=True)
        install_or_repair_runtime(install_root, self.manifest, self.archive_path)
        (install_root / BOOTSTRAP_RUNTIME_HIDDEN_EXE).write_text("tampered", encoding="utf-8")

        verified, mismatches = verify_runtime_files(install_root, self.manifest)
        self.assertFalse(verified)
        self.assertTrue(any(item.startswith("sha256:") or item.startswith("size:") for item in mismatches))


if __name__ == "__main__":
    unittest.main()
