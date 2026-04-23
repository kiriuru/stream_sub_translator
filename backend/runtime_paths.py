from __future__ import annotations

import hashlib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    bundle_root: Path
    data_dir: Path
    logs_dir: Path
    frontend_dir: Path
    overlay_dir: Path
    fonts_dir: Path
    runtime_root: Path
    cache_root: Path
    temp_root: Path


DESKTOP_USER_DATA_DIRNAME = "user-data"


def _source_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _project_runtime_root(project_root: Path) -> Path:
    explicit_root = os.environ.get("SST_RUNTIME_ROOT")
    if explicit_root:
        return Path(explicit_root).resolve()

    public_root = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
    project_token = hashlib.sha1(str(project_root).encode("utf-8", errors="ignore")).hexdigest()[:10]
    return (public_root / "Documents" / "StreamSubtitleTranslatorRuntime" / f"{project_root.name}-{project_token}").resolve()


def detect_runtime_paths() -> RuntimePaths:
    source_root = _source_root()
    env_bundle_root = os.environ.get("SST_BUNDLE_ROOT")
    env_project_root = os.environ.get("SST_PROJECT_ROOT")

    bundle_root = Path(env_bundle_root).resolve() if env_bundle_root else Path(getattr(sys, "_MEIPASS", source_root))
    if env_project_root:
        project_root = Path(env_project_root).resolve()
    else:
        project_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else source_root
    runtime_root = _project_runtime_root(project_root)

    return RuntimePaths(
        project_root=project_root,
        bundle_root=bundle_root,
        data_dir=project_root / DESKTOP_USER_DATA_DIRNAME,
        logs_dir=project_root / "logs",
        frontend_dir=bundle_root / "frontend",
        overlay_dir=bundle_root / "overlay",
        fonts_dir=project_root / "fonts",
        runtime_root=runtime_root,
        cache_root=runtime_root / "cache",
        temp_root=runtime_root / "tmp",
    )


RUNTIME_PATHS = detect_runtime_paths()


def _copy_if_missing(source: Path, destination: Path) -> None:
    if destination.exists() or not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _migrate_legacy_logs_dir(runtime_paths: RuntimePaths) -> None:
    legacy_logs_dir = runtime_paths.data_dir / "logs"
    target_logs_dir = runtime_paths.logs_dir
    if not legacy_logs_dir.exists() or legacy_logs_dir.resolve() == target_logs_dir.resolve():
        return
    target_logs_dir.mkdir(parents=True, exist_ok=True)
    for legacy_item in legacy_logs_dir.glob("*"):
        if not legacy_item.is_file():
            continue
        destination = target_logs_dir / legacy_item.name
        if destination.exists():
            continue
        _copy_if_missing(legacy_item, destination)
    try:
        legacy_logs_dir.rmdir()
    except OSError:
        # Keep non-empty legacy dir for safety; runtime now writes to logs_dir.
        pass


def _copy_font_assets(bundle_root: Path, fonts_dir: Path) -> None:
    bundled_fonts_dir = bundle_root / "fonts"
    if not bundled_fonts_dir.exists():
        return

    fonts_dir.mkdir(parents=True, exist_ok=True)
    for bundled_file in bundled_fonts_dir.rglob("*"):
        if not bundled_file.is_file():
            continue
        relative_path = bundled_file.relative_to(bundled_fonts_dir)
        destination = fonts_dir / relative_path
        _copy_if_missing(bundled_file, destination)


def ensure_runtime_layout(paths: RuntimePaths | None = None) -> RuntimePaths:
    runtime_paths = paths or RUNTIME_PATHS

    required_directories = (
        runtime_paths.runtime_root,
        runtime_paths.cache_root,
        runtime_paths.temp_root,
        runtime_paths.data_dir,
        runtime_paths.data_dir / "profiles",
        runtime_paths.logs_dir,
        runtime_paths.data_dir / "exports",
        runtime_paths.data_dir / "cache",
        runtime_paths.data_dir / "models",
        runtime_paths.fonts_dir,
    )
    for directory in required_directories:
        directory.mkdir(parents=True, exist_ok=True)

    bundled_data_dir = runtime_paths.bundle_root / "backend" / "data"
    _copy_if_missing(bundled_data_dir / "config.example.json", runtime_paths.data_dir / "config.example.json")
    _copy_if_missing(
        bundled_data_dir / "dictionary_overrides.example.json",
        runtime_paths.data_dir / "dictionary_overrides.example.json",
    )
    _copy_if_missing(
        bundled_data_dir / "models" / "README.txt",
        runtime_paths.data_dir / "models" / "README.txt",
    )
    _copy_font_assets(runtime_paths.bundle_root, runtime_paths.fonts_dir)
    _migrate_legacy_logs_dir(runtime_paths)

    return runtime_paths
