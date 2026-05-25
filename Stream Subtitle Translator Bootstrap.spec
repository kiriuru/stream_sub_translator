# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(globals().get("__file__", "Stream Subtitle Translator Bootstrap.spec")).resolve().parent
payload_dir = project_root / "build" / "bootstrap-payload"

datas = [
    (str(payload_dir / "payload.zip"), "."),
    (str(payload_dir / "payload.manifest.json"), "."),
]


a = Analysis(
    [str(project_root / "desktop" / "bootstrap_launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name="Stream Subtitle Translator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project_root / "desktop" / "assets" / "stream-sub-translator.ico"),
)
