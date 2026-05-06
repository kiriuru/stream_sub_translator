from __future__ import annotations

from fastapi import FastAPI

from backend.models import TranslationDiagnostics


class TranslationService:
    def __init__(self, app: FastAPI) -> None:
        self._app = app

    def diagnostics(self) -> TranslationDiagnostics:
        return self._app.state.runtime_orchestrator.translation_diagnostics()
