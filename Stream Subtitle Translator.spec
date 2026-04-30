# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


project_root = Path(globals().get("__file__", "Stream Subtitle Translator.spec")).resolve().parent


def collect_project_files(root: Path, prefix: str, *, exclude_dirs: list[str] | None = None, exclude_files: list[str] | None = None):
    entries = []
    skipped_dirs = [item.replace("\\", "/").strip("/") for item in (exclude_dirs or [])]
    skipped_files = {item.replace("\\", "/").strip("/") for item in (exclude_files or [])}
    for source_file in root.rglob("*"):
        if not source_file.is_file():
            continue
        relative_path = source_file.relative_to(root).as_posix()
        path_parts = relative_path.split("/")
        if "__pycache__" in path_parts:
            continue
        if any(relative_path == skipped or relative_path.startswith(f"{skipped}/") for skipped in skipped_dirs):
            continue
        if relative_path in skipped_files:
            continue
        target_dir = f"{prefix}/{source_file.parent.relative_to(root).as_posix()}" if source_file.parent != root else prefix
        entries.append((str(source_file), target_dir))
    return entries


def collect_local_site_package(site_packages_root: Path, package_name: str, target_prefix: str):
    source_path = site_packages_root / package_name
    if not source_path.exists():
        raise FileNotFoundError(f"Missing local build dependency for desktop runtime payload: {source_path}")
    if source_path.is_file():
        return [(str(source_path), target_prefix)]
    return collect_project_files(source_path, f"{target_prefix}/{package_name}")

datas = [
    (str(project_root / "bootstrap-python.ps1"), "."),
    (str(project_root / "requirements.txt"), "."),
    (str(project_root / "requirements.runtime.base.txt"), "."),
    (str(project_root / "requirements.runtime.ai.txt"), "."),
    (str(project_root / "requirements.desktop.txt"), "."),
    (str(project_root / "requirements.torch.cpu.txt"), "."),
    (str(project_root / "requirements.torch.cuda.txt"), "."),
    (str(project_root / "README.md"), "."),
    (str(project_root / "start.bat"), "."),
    (str(project_root / "update.bat"), "."),
]
site_packages_root = project_root / ".venv" / "Lib" / "site-packages"
datas += collect_local_site_package(site_packages_root, "lightning", "vendor/python-site-packages")
datas += collect_local_site_package(site_packages_root, "lightning-2.4.0.dist-info", "vendor/python-site-packages")
datas += collect_project_files(
    project_root / "backend",
    "backend",
    exclude_dirs=[
        "data/cache",
        "data/exports",
        "data/logs",
        "data/models",
        "data/profiles",
    ],
    exclude_files=[
        "data/config.json",
        "data/dictionary_overrides.json",
        "data/install_profile.txt",
    ],
)
datas += collect_data_files("webview")
datas += collect_data_files("pythonnet")

hiddenimports = collect_submodules("webview")

try:
    datas += copy_metadata("pywebview")
except Exception:
    pass

try:
    datas += copy_metadata("pythonnet")
except Exception:
    pass


a = Analysis(
    [str(project_root / "desktop" / "launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Stream Subtitle Translator",
    contents_directory="app-runtime",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project_root / "desktop" / "assets" / "stream-sub-translator.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    Tree(str(project_root / "frontend"), prefix="frontend"),
    Tree(str(project_root / "overlay"), prefix="overlay"),
    Tree(str(project_root / "fonts"), prefix="fonts"),
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Stream Subtitle Translator",
)
