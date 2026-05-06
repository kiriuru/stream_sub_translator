from __future__ import annotations

import hashlib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


DESKTOP_USER_DATA_DIRNAME = "user-data"


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = str(os.environ.get(name, "") or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppPaths:
    project_root: Path
    bundle_root: Path
    backend_root: Path
    frontend_root: Path
    overlay_root: Path
    fonts_dir: Path
    user_data_dir: Path
    profiles_dir: Path
    logs_dir: Path
    secrets_dir: Path
    models_dir: Path
    debug_dir: Path
    debug_asr_segments_dir: Path
    session_db_path: Path
    runtime_dir: Path
    cache_root: Path
    temp_root: Path
    portable_mode: bool
    safe_mode: bool

    @property
    def data_dir(self) -> Path:
        return self.user_data_dir

    @property
    def frontend_dir(self) -> Path:
        return self.frontend_root

    @property
    def overlay_dir(self) -> Path:
        return self.overlay_root

    @property
    def runtime_root(self) -> Path:
        return self.runtime_dir

    @classmethod
    def detect(cls) -> "AppPaths":
        return detect_app_paths()


def _source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _project_runtime_root(project_root: Path) -> Path:
    explicit_root = os.environ.get("SST_RUNTIME_ROOT")
    if explicit_root:
        return Path(explicit_root).resolve()

    public_root = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
    project_token = hashlib.sha1(str(project_root).encode("utf-8", errors="ignore")).hexdigest()[:10]
    return (public_root / "Documents" / "StreamSubtitleTranslatorRuntime" / f"{project_root.name}-{project_token}").resolve()


def detect_app_paths() -> AppPaths:
    source_root = _source_root()
    env_bundle_root = os.environ.get("SST_BUNDLE_ROOT")
    env_project_root = os.environ.get("SST_PROJECT_ROOT")

    bundle_root = Path(env_bundle_root).resolve() if env_bundle_root else Path(getattr(sys, "_MEIPASS", source_root))
    if env_project_root:
        project_root = Path(env_project_root).resolve()
    else:
        project_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else source_root

    backend_root = project_root / "backend"
    user_data_dir = project_root / DESKTOP_USER_DATA_DIRNAME
    runtime_dir = _project_runtime_root(project_root)

    return AppPaths(
        project_root=project_root,
        bundle_root=bundle_root,
        backend_root=backend_root,
        frontend_root=bundle_root / "frontend",
        overlay_root=bundle_root / "overlay",
        fonts_dir=project_root / "fonts",
        user_data_dir=user_data_dir,
        profiles_dir=user_data_dir / "profiles",
        logs_dir=user_data_dir / "logs",
        secrets_dir=user_data_dir / "secrets",
        models_dir=backend_root / "data" / "models",
        debug_dir=user_data_dir / "debug",
        debug_asr_segments_dir=user_data_dir / "debug" / "asr-segments",
        session_db_path=user_data_dir / "session-log.sqlite3",
        runtime_dir=runtime_dir,
        cache_root=runtime_dir / "cache",
        temp_root=runtime_dir / "tmp",
        portable_mode=_env_flag("SST_PORTABLE_MODE", default=True),
        safe_mode=_env_flag("SST_SAFE_MODE", default=False),
    )


APP_PATHS = detect_app_paths()


def _copy_if_missing(source: Path, destination: Path) -> None:
    if destination.exists() or not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _migrate_legacy_logs_dir(paths: AppPaths) -> None:
    legacy_logs_dir = paths.project_root / "logs"
    target_logs_dir = paths.logs_dir
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


def ensure_app_layout(paths: AppPaths | None = None) -> AppPaths:
    app_paths = paths or APP_PATHS

    required_directories = (
        app_paths.runtime_dir,
        app_paths.cache_root,
        app_paths.temp_root,
        app_paths.user_data_dir,
        app_paths.profiles_dir,
        app_paths.logs_dir,
        app_paths.user_data_dir / "exports",
        app_paths.user_data_dir / "cache",
        app_paths.models_dir,
        app_paths.fonts_dir,
        app_paths.secrets_dir,
        app_paths.debug_dir,
        app_paths.debug_asr_segments_dir,
    )
    for directory in required_directories:
        directory.mkdir(parents=True, exist_ok=True)

    bundled_data_dir = app_paths.bundle_root / "backend" / "data"
    _copy_if_missing(bundled_data_dir / "config.example.json", app_paths.user_data_dir / "config.example.json")
    _copy_if_missing(
        bundled_data_dir / "dictionary_overrides.example.json",
        app_paths.user_data_dir / "dictionary_overrides.example.json",
    )
    _copy_if_missing(
        bundled_data_dir / "models" / "README.txt",
        app_paths.models_dir / "README.txt",
    )
    _copy_font_assets(app_paths.bundle_root, app_paths.fonts_dir)
    _migrate_legacy_logs_dir(app_paths)
    return app_paths
