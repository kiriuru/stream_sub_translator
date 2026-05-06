from __future__ import annotations

from fastapi import FastAPI

from backend.schemas.model_schema import ModelRuntimeStatus


class ModelManagerService:
    def __init__(self, app: FastAPI) -> None:
        self._app = app

    def models_dir(self):
        return self._app.state.paths.models_dir

    def safe_mode_enabled(self) -> bool:
        return bool(self._app.state.paths.safe_mode)

    def heavy_model_loading_allowed(self) -> bool:
        return not self.safe_mode_enabled()

    def status(self) -> ModelRuntimeStatus:
        return ModelRuntimeStatus(
            models_dir=str(self.models_dir()),
            safe_mode=self.safe_mode_enabled(),
            heavy_model_loading_allowed=self.heavy_model_loading_allowed(),
        )
