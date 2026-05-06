from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelRuntimeStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    models_dir: str
    safe_mode: bool = False
    heavy_model_loading_allowed: bool = True
