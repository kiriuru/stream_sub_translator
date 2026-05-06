from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI


class OverlayService:
    def __init__(self, app: FastAPI) -> None:
        self._app = app

    def overlay_url(self) -> str:
        return f"{self._app.state.app_settings.local_base_url}/overlay"

    def overlay_file(self) -> Path:
        return self._app.state.paths.overlay_root / "overlay.html"
