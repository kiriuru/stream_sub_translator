from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from desktop.bootstrap_payload import (
    BOOTSTRAP_INSTALL_MARKER,
    BOOTSTRAP_RUNTIME_DIR,
    BOOTSTRAP_RUNTIME_HIDDEN_EXE,
    PayloadManifest,
    build_payload_manifest,
    create_payload_archive,
    extract_payload_archive,
    install_or_repair_runtime,
    is_remote_version_newer,
    parse_semver,
    read_manifest,
    verify_runtime_files,
    write_manifest,
    _normalize_relative_path,
)


class ParseSemverTests(unittest.TestCase):
    def test_parses_dotted_versions(self) -> None:
        self.assertEqual(parse_semver("0.4.1"), (0, 4, 1, 0))
        self.assertEqual(parse_semver("v0.4.1"), (0, 4, 1, 0))
        self.assertEqual(parse_semver("1.2.3.4"), (1, 2, 3, 4))
        self.assertEqual(parse_semver("1.2.3-rc1"), (1, 2, 3, 0))

    def test_rejects_invalid(self) -> None:
        self.assertIsNone(parse_semver(""))
        self.assertIsNone(parse_semver("1.2"))
        self.assertIsNone(parse_semver("not-a-version"))
        self.assertIsNone(parse_semver(None))  # type: ignore[arg-type]


class IsRemoteVersionNewerTests(unittest.TestCase):
    def test_greater_remote(self) -> None:
        self.assertTrue(is_remote_version_newer("0.4.1", "0.4.2"))
        self.assertTrue(is_remote_version_newer("0.4.1", "0.5.0"))
        self.assertTrue(is_remote_version_newer("0.4.1", "1.0.0"))

    def test_equal_or_older_remote(self) -> None:
        self.assertFalse(is_remote_version_newer("0.4.1", "0.4.1"))
        self.assertFalse(is_remote_version_newer("0.4.2", "0.4.1"))
        self.assertFalse(is_remote_version_newer("1.0.0", "0.9.9"))

    def test_invalid_inputs(self) -> None:
        self.assertFalse(is_remote_version_newer("", "0.4.2"))
        self.assertFalse(is_remote_version_newer("0.4.1", ""))
        self.assertFalse(is_remote_version_newer("not-a-version", "0.4.2"))


class NormalizeRelativePathTests(unittest.TestCase):
    def test_accepts_safe_paths(self) -> None:
        self.assertEqual(_normalize_relative_path("a/b/c.txt"), "a/b/c.txt")
        self.assertEqual(_normalize_relative_path("a\\b\\c.txt"), "a/b/c.txt")

    def test_rejects_zipslip_attempts(self) -> None:
        with self.assertRaises(ValueError):
            _normalize_relative_path("../etc/passwd")
        with self.assertRaises(ValueError):
            _normalize_relative_path("a/../../etc/passwd")
        with self.assertRaises(ValueError):
            _normalize_relative_path("..\\etc\\passwd")
        with self.assertRaises(ValueError):
            _normalize_relative_path("")

    def test_strips_leading_slashes_to_keep_paths_relative(self) -> None:
        # Defense-in-depth: even absolute paths must collapse into the install root.
        self.assertEqual(_normalize_relative_path("/abs/path"), "abs/path")
        self.assertEqual(_normalize_relative_path("\\abs\\path"), "abs/path")


class PayloadManifestRoundTripTests(unittest.TestCase):
    def test_build_and_verify_runtime_files(self) -> None:
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            payload_root = tmp / "payload-root"
            install_root = tmp / "install"
            (payload_root / BOOTSTRAP_RUNTIME_DIR).mkdir(parents=True, exist_ok=True)
            (payload_root / BOOTSTRAP_RUNTIME_HIDDEN_EXE).write_bytes(b"runtime-exe-stub")
            (payload_root / BOOTSTRAP_RUNTIME_DIR / "asset.txt").write_text("hello", encoding="utf-8")
            (payload_root / BOOTSTRAP_RUNTIME_DIR / BOOTSTRAP_INSTALL_MARKER).write_text("0.4.2\n", encoding="utf-8")

            manifest = build_payload_manifest(payload_root, app_version="0.4.2", release_track="stable")
            self.assertEqual(manifest.app_version, "0.4.2")
            self.assertEqual(manifest.release_track, "stable")
            self.assertEqual(manifest.runtime_entrypoint, BOOTSTRAP_RUNTIME_HIDDEN_EXE)
            self.assertGreaterEqual(len(manifest.files), 3)

            manifest_path = tmp / "payload.manifest.json"
            write_manifest(manifest, manifest_path)
            reloaded = read_manifest(manifest_path)
            self.assertEqual(reloaded.app_version, manifest.app_version)
            self.assertEqual(len(reloaded.files), len(manifest.files))

            archive_path = tmp / "payload.zip"
            create_payload_archive(payload_root, archive_path, manifest)
            self.assertTrue(archive_path.exists())
            self.assertGreater(archive_path.stat().st_size, 0)

            install_root.mkdir(parents=True, exist_ok=True)
            verified, mismatches = install_or_repair_runtime(install_root, manifest, archive_path)
            self.assertTrue(verified, msg=f"mismatches={mismatches}")
            self.assertFalse(mismatches)

            still_ok, _ = verify_runtime_files(install_root, manifest)
            self.assertTrue(still_ok)

            tampered = install_root / BOOTSTRAP_RUNTIME_DIR / "asset.txt"
            tampered.write_text("tampered-content", encoding="utf-8")
            ok_after_tamper, tamper_issues = verify_runtime_files(install_root, manifest)
            self.assertFalse(ok_after_tamper)
            self.assertTrue(any("sha256" in entry or "size" in entry for entry in tamper_issues))

    def test_verify_detects_marker_version_mismatch(self) -> None:
        """A previous install with a different exe must be flagged for repair."""
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            payload_root = tmp / "payload-root"
            install_root = tmp / "install"
            (payload_root / BOOTSTRAP_RUNTIME_DIR).mkdir(parents=True, exist_ok=True)
            (payload_root / BOOTSTRAP_RUNTIME_HIDDEN_EXE).write_bytes(b"runtime-exe-stub")
            (payload_root / BOOTSTRAP_RUNTIME_DIR / "asset.txt").write_text("hello", encoding="utf-8")
            (payload_root / BOOTSTRAP_RUNTIME_DIR / BOOTSTRAP_INSTALL_MARKER).write_text(
                "0.4.2\n", encoding="utf-8"
            )

            manifest = build_payload_manifest(payload_root, app_version="0.4.2", release_track="stable")
            archive_path = tmp / "payload.zip"
            create_payload_archive(payload_root, archive_path, manifest)
            install_root.mkdir(parents=True, exist_ok=True)
            verified, mismatches = install_or_repair_runtime(install_root, manifest, archive_path)
            self.assertTrue(verified, msg=f"initial install failed: {mismatches}")

            # Simulate a leftover marker from a previous install with the same files.
            marker_path = install_root / BOOTSTRAP_RUNTIME_DIR / BOOTSTRAP_INSTALL_MARKER
            marker_path.write_text("0.4.1\n", encoding="utf-8")
            verified, mismatches = verify_runtime_files(install_root, manifest)
            self.assertFalse(verified)
            self.assertTrue(
                any(entry.startswith("version-marker:") for entry in mismatches),
                msg=f"expected version-marker in mismatches: {mismatches}",
            )

    def test_verify_detects_stale_runtime_files(self) -> None:
        """Files left over inside app-runtime/ that aren't in the new manifest trigger repair."""
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            payload_root = tmp / "payload-root"
            install_root = tmp / "install"
            (payload_root / BOOTSTRAP_RUNTIME_DIR).mkdir(parents=True, exist_ok=True)
            (payload_root / BOOTSTRAP_RUNTIME_HIDDEN_EXE).write_bytes(b"runtime-exe-stub")
            (payload_root / BOOTSTRAP_RUNTIME_DIR / "asset.txt").write_text("hello", encoding="utf-8")
            (payload_root / BOOTSTRAP_RUNTIME_DIR / BOOTSTRAP_INSTALL_MARKER).write_text(
                "0.4.2\n", encoding="utf-8"
            )

            manifest = build_payload_manifest(payload_root, app_version="0.4.2", release_track="stable")
            archive_path = tmp / "payload.zip"
            create_payload_archive(payload_root, archive_path, manifest)
            install_root.mkdir(parents=True, exist_ok=True)
            verified, mismatches = install_or_repair_runtime(install_root, manifest, archive_path)
            self.assertTrue(verified, msg=f"initial install failed: {mismatches}")

            # Pretend a previous payload left an obsolete native extension behind.
            stale_file = install_root / BOOTSTRAP_RUNTIME_DIR / "obsolete.pyd"
            stale_file.write_bytes(b"stale-binary")
            verified, mismatches = verify_runtime_files(install_root, manifest)
            self.assertFalse(verified)
            self.assertTrue(
                any(entry == "stale: app-runtime/obsolete.pyd" for entry in mismatches),
                msg=f"expected stale entry in mismatches: {mismatches}",
            )

            # And the install_or_repair flow restores a clean state.
            verified, mismatches = install_or_repair_runtime(install_root, manifest, archive_path)
            self.assertTrue(verified, msg=f"repair did not wipe stale file: {mismatches}")
            self.assertFalse(stale_file.exists())

    def test_extract_payload_archive_skips_manifest_file(self) -> None:
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            payload_root = tmp / "src"
            extract_dest = tmp / "dst"
            payload_root.mkdir(parents=True, exist_ok=True)
            (payload_root / "a.txt").write_text("alpha", encoding="utf-8")
            manifest = build_payload_manifest(payload_root, app_version="0.0.1", release_track="stable")
            archive_path = tmp / "p.zip"
            create_payload_archive(payload_root, archive_path, manifest)

            extract_dest.mkdir(parents=True, exist_ok=True)
            extract_payload_archive(archive_path, extract_dest)
            self.assertTrue((extract_dest / "a.txt").exists())
            self.assertFalse((extract_dest / "payload.manifest.json").exists())


class PayloadManifestFromDictTests(unittest.TestCase):
    def test_from_dict_normalizes_fields(self) -> None:
        payload = {
            "appVersion": " 0.4.2 ",
            "releaseTrack": "",
            "files": [{"path": "x.txt", "size": 5, "sha256": "deadbeef"}],
        }
        manifest = PayloadManifest.from_dict(payload)
        self.assertEqual(manifest.app_version, "0.4.2")
        self.assertEqual(manifest.release_track, "stable")
        self.assertEqual(manifest.runtime_entrypoint, BOOTSTRAP_RUNTIME_HIDDEN_EXE)
        self.assertEqual(manifest.install_marker, f"{BOOTSTRAP_RUNTIME_DIR}/{BOOTSTRAP_INSTALL_MARKER}")
        self.assertEqual(len(manifest.files), 1)

    def test_to_dict_round_trips_via_json(self) -> None:
        manifest = PayloadManifest(
            app_version="0.4.2",
            release_track="stable",
            runtime_entrypoint=BOOTSTRAP_RUNTIME_HIDDEN_EXE,
            install_marker=f"{BOOTSTRAP_RUNTIME_DIR}/{BOOTSTRAP_INSTALL_MARKER}",
            files=[],
        )
        encoded = json.dumps(manifest.to_dict())
        reloaded = PayloadManifest.from_dict(json.loads(encoded))
        self.assertEqual(reloaded, manifest)


if __name__ == "__main__":
    unittest.main()
