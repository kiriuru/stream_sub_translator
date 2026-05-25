from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from backend.versioning import PROJECT_VERSION
from desktop.bootstrap_payload import (
    build_payload_manifest_from_file_entries,
    create_payload_archive_from_file_entries,
    iter_managed_payload_file_entries,
    write_manifest,
)


def build_bootstrap_payload(
    *,
    source_dist: Path,
    output_dir: Path,
    app_version: str | None = None,
    release_track: str = "stable",
    log: Callable[[str], None] | None = None,
) -> None:
    def emit(message: str) -> None:
        if log is not None:
            log(message)

    payload_root = source_dist.resolve()
    if not payload_root.is_dir():
        raise FileNotFoundError(f"Managed desktop dist folder not found: {payload_root}")

    version = str(app_version or PROJECT_VERSION).strip() or PROJECT_VERSION
    output_dir.mkdir(parents=True, exist_ok=True)

    emit(f"packaging bootstrap payload from {payload_root} (direct zip, no staging copy)")
    entries = iter_managed_payload_file_entries(payload_root)
    manifest = build_payload_manifest_from_file_entries(
        entries,
        app_version=version,
        release_track=release_track,
    )
    archive_path = output_dir / "payload.zip"
    manifest_path = output_dir / "payload.manifest.json"
    create_payload_archive_from_file_entries(entries, archive_path, manifest)
    write_manifest(manifest, manifest_path)

    emit(
        f"payload ready: {archive_path} ({archive_path.stat().st_size} bytes, {len(manifest.files)} files)"
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build embedded bootstrap payload for desktop launchers.")
    parser.add_argument(
        "--source-dist",
        required=True,
        type=Path,
        help="PyInstaller one-folder dist root (dist/Stream Subtitle Translator).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Output directory for payload.zip and payload.manifest.json.",
    )
    parser.add_argument(
        "--app-version",
        default=None,
        help="Override payload app version (defaults to backend.versioning.PROJECT_VERSION).",
    )
    parser.add_argument(
        "--release-track",
        default="stable",
        help="Release track label stored in the payload manifest.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    build_bootstrap_payload(
        source_dist=args.source_dist,
        output_dir=args.output_dir,
        app_version=args.app_version,
        release_track=args.release_track,
        log=print,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
