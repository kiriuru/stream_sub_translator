from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


BOOTSTRAP_RUNTIME_EXE = "sst-runtime.exe"
BOOTSTRAP_RUNTIME_HIDDEN_EXE = ".sst-runtime.exe"
BOOTSTRAP_RUNTIME_DIR = "app-runtime"
BOOTSTRAP_USER_DATA_DIR = "user-data"
BOOTSTRAP_LOGS_DIR = "user-data/logs"
BOOTSTRAP_LOG_FILE = "bootstrap-launcher.log"
BOOTSTRAP_INSTALL_MARKER = ".install-complete"

_SEMVER_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:\.(?P<build>\d+))?(?:[-+].*)?$"
)


@dataclass(frozen=True)
class ManifestFile:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class PayloadManifest:
    app_version: str
    release_track: str
    runtime_entrypoint: str
    install_marker: str
    files: list[ManifestFile]

    def to_dict(self) -> dict[str, Any]:
        return {
            "appVersion": self.app_version,
            "releaseTrack": self.release_track,
            "runtimeEntrypoint": self.runtime_entrypoint,
            "installMarker": self.install_marker,
            "files": [asdict(item) for item in self.files],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PayloadManifest":
        files_payload = payload.get("files", [])
        files = [
            ManifestFile(
                path=str(item.get("path", "")),
                size=int(item.get("size", 0)),
                sha256=str(item.get("sha256", "")),
            )
            for item in files_payload
            if isinstance(item, dict)
        ]
        return cls(
            app_version=str(payload.get("appVersion", "")).strip(),
            release_track=str(payload.get("releaseTrack", "stable")).strip() or "stable",
            runtime_entrypoint=str(payload.get("runtimeEntrypoint", BOOTSTRAP_RUNTIME_HIDDEN_EXE)).strip()
            or BOOTSTRAP_RUNTIME_HIDDEN_EXE,
            install_marker=str(payload.get("installMarker", f"{BOOTSTRAP_RUNTIME_DIR}/{BOOTSTRAP_INSTALL_MARKER}")).strip()
            or f"{BOOTSTRAP_RUNTIME_DIR}/{BOOTSTRAP_INSTALL_MARKER}",
            files=files,
        )


def parse_semver(value: str) -> tuple[int, int, int, int] | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = _SEMVER_RE.match(text)
    if not match:
        return None
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        int(match.group("build") or 0),
    )


def is_remote_version_newer(local_version: str, remote_version: str) -> bool:
    local = parse_semver(local_version)
    remote = parse_semver(remote_version)
    if local is None or remote is None:
        return False
    return remote > local


def is_github_release_tag_relevant_for_local(local_version: str, remote_tag_version: str) -> bool:
    """
    Старые теги вида v2.8.x на GitHub семантически «новее» 0.3.x, но относятся к другой
    нумерации продукта. Для встроенной линии 0.x такие релизы не должны перехватывать
    проверку обновлений — иначе лаунчер предложит нерелевантный релиз.
    """
    local = parse_semver(local_version)
    remote = parse_semver(remote_tag_version)
    if local is None or remote is None:
        return True
    if local[0] == 0 and remote[0] >= 2:
        return False
    return True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_relative_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/").strip("/")
    if not normalized or normalized.startswith("../") or "/../" in normalized or normalized.startswith("/"):
        raise ValueError(f"Unsafe relative path: {path!r}")
    return normalized


def build_payload_manifest(payload_root: Path, *, app_version: str, release_track: str) -> PayloadManifest:
    files: list[ManifestFile] = []
    for source_path in sorted(payload_root.rglob("*")):
        if not source_path.is_file():
            continue
        relative_path = source_path.relative_to(payload_root).as_posix()
        files.append(
            ManifestFile(
                path=relative_path,
                size=source_path.stat().st_size,
                sha256=_sha256_file(source_path),
            )
        )
    return PayloadManifest(
        app_version=app_version,
        release_track=release_track,
        runtime_entrypoint=BOOTSTRAP_RUNTIME_HIDDEN_EXE,
        install_marker=f"{BOOTSTRAP_RUNTIME_DIR}/{BOOTSTRAP_INSTALL_MARKER}",
        files=files,
    )


def write_manifest(manifest: PayloadManifest, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def read_manifest(path: Path) -> PayloadManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid manifest payload: {path}")
    return PayloadManifest.from_dict(payload)


def create_payload_archive(payload_root: Path, archive_path: Path, manifest: PayloadManifest) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source_path in sorted(payload_root.rglob("*")):
            if not source_path.is_file():
                continue
            archive.write(source_path, arcname=source_path.relative_to(payload_root).as_posix())
        archive.writestr("payload.manifest.json", json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))


def ensure_writable_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / ".sst-write-probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)


def verify_runtime_files(install_root: Path, manifest: PayloadManifest) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    for entry in manifest.files:
        relative_path = _normalize_relative_path(entry.path)
        target = install_root / relative_path
        if not target.exists():
            mismatches.append(f"missing: {relative_path}")
            continue
        if not target.is_file():
            mismatches.append(f"not-file: {relative_path}")
            continue
        stat = target.stat()
        if stat.st_size != entry.size:
            mismatches.append(f"size: {relative_path}")
            continue
        if _sha256_file(target) != entry.sha256:
            mismatches.append(f"sha256: {relative_path}")
    marker = install_root / _normalize_relative_path(manifest.install_marker)
    if not marker.exists():
        mismatches.append(f"missing-marker: {manifest.install_marker}")
    return (not mismatches), mismatches


def extract_payload_archive(archive_path: Path, destination_root: Path) -> None:
    with zipfile.ZipFile(archive_path, "r") as archive:
        for member in archive.infolist():
            relative_name = member.filename.replace("\\", "/").strip("/")
            if not relative_name or member.is_dir() or relative_name == "payload.manifest.json":
                continue
            safe_name = _normalize_relative_path(relative_name)
            target_path = destination_root / safe_name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as source_handle, target_path.open("wb") as target_handle:
                shutil.copyfileobj(source_handle, target_handle)


def _remove_if_exists(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def _atomic_replace(source_path: Path, destination_path: Path) -> None:
    backup_path = destination_path.with_name(f"{destination_path.name}.__old")
    _remove_if_exists(backup_path)
    if destination_path.exists():
        os.replace(destination_path, backup_path)
    os.replace(source_path, destination_path)
    _remove_if_exists(backup_path)


def install_or_repair_runtime(
    install_root: Path,
    manifest: PayloadManifest,
    archive_path: Path,
    *,
    log: Callable[[str], None] | None = None,
) -> tuple[bool, list[str]]:
    def emit(message: str) -> None:
        if log is not None:
            log(message)

    stale_stage_dir = install_root / ".__sst_stage_new"
    stale_extract_dir = install_root / ".__sst_extract_tmp"
    _remove_if_exists(stale_stage_dir)
    _remove_if_exists(stale_extract_dir)

    with tempfile.TemporaryDirectory(dir=str(install_root), prefix="sst-bootstrap-") as temp_dir:
        stage_root = Path(temp_dir) / "stage"
        stage_root.mkdir(parents=True, exist_ok=True)
        emit("extracting embedded runtime payload")
        extract_payload_archive(archive_path, stage_root)
        marker_path = stage_root / _normalize_relative_path(manifest.install_marker)
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(f"{manifest.app_version}\n", encoding="utf-8")
        verified, mismatches = verify_runtime_files(stage_root, manifest)
        if not verified:
            raise RuntimeError(f"Embedded runtime payload verification failed: {', '.join(mismatches[:8])}")

        staged_runtime_exe = stage_root / BOOTSTRAP_RUNTIME_HIDDEN_EXE
        staged_runtime_dir = stage_root / BOOTSTRAP_RUNTIME_DIR
        final_runtime_exe = install_root / BOOTSTRAP_RUNTIME_HIDDEN_EXE
        final_runtime_dir = install_root / BOOTSTRAP_RUNTIME_DIR
        backup_runtime_dir = install_root / f"{BOOTSTRAP_RUNTIME_DIR}.__old"
        backup_runtime_exe = install_root / f"{BOOTSTRAP_RUNTIME_HIDDEN_EXE}.__old"
        _remove_if_exists(backup_runtime_dir)
        _remove_if_exists(backup_runtime_exe)
        if final_runtime_dir.exists():
            os.replace(final_runtime_dir, backup_runtime_dir)
        if final_runtime_exe.exists():
            os.replace(final_runtime_exe, backup_runtime_exe)
        os.replace(staged_runtime_dir, final_runtime_dir)
        os.replace(staged_runtime_exe, final_runtime_exe)
        _remove_if_exists(backup_runtime_dir)
        _remove_if_exists(backup_runtime_exe)

        install_marker_path = install_root / _normalize_relative_path(manifest.install_marker)
        install_marker_path.parent.mkdir(parents=True, exist_ok=True)
        install_marker_path.write_text(f"{manifest.app_version}\n", encoding="utf-8")

    verified, mismatches = verify_runtime_files(install_root, manifest)
    return verified, mismatches


def apply_windows_hidden_attribute(path: Path) -> None:
    if os.name != "nt" or not path.exists():
        return
    try:
        import ctypes

        FILE_ATTRIBUTE_HIDDEN = 0x2
        ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        return
