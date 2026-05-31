"""Desktop launcher public entry: re-exports bootstrap class and shared helpers."""
from __future__ import annotations

from desktop import launcher_api
from desktop import launcher_context
from desktop.launcher_bootstrap import DesktopLauncher, main

for _export_name in dir(launcher_context):
    if _export_name.startswith("__"):
        continue
    globals()[_export_name] = getattr(launcher_context, _export_name)
for _export_name in dir(launcher_api):
    if _export_name.startswith("__") or _export_name == "DesktopApi":
        continue
    globals()[_export_name] = getattr(launcher_api, _export_name)

from desktop.launcher_api import DesktopApi  # noqa: E402

__all__ = [
    "DesktopLauncher",
    "DesktopApi",
    "main",
    "LaunchContext",
    "LaunchSelectionCancelled",
]


if __name__ == "__main__":
    main()
