from __future__ import annotations

from fastapi import FastAPI

from backend.core.remote_diagnostics import build_remote_diagnostics
from backend.models import HealthResponse, RemoteStateResponse
from backend.versioning import build_version_info_payload


class DiagnosticsService:
    def __init__(self, app: FastAPI) -> None:
        self._app = app

    @property
    def _config(self) -> dict:
        payload = getattr(self._app.state, "config", {})
        return payload if isinstance(payload, dict) else {}

    def version_info(self) -> dict:
        return build_version_info_payload(self._config)

    def remote_diagnostics(self):
        settings = self._app.state.app_settings
        return build_remote_diagnostics(
            self._config,
            app_host=settings.app_host,
            app_port=settings.app_port,
        )

    def remote_state(self) -> RemoteStateResponse:
        pairing = self._app.state.remote_session_manager.snapshot()
        return RemoteStateResponse(remote=self.remote_diagnostics(), pairing=pairing)

    def health(self) -> HealthResponse:
        asr_service = self._app.state.asr_service
        translation_service = self._app.state.translation_service
        runtime_orchestrator = self._app.state.runtime_orchestrator
        version_info = self.version_info()
        asr_status = asr_service.status()
        return HealthResponse(
            app_version=version_info.get("current_version"),
            release_sync=version_info.get("sync"),
            asr_provider=asr_status.provider,
            asr_ready=asr_status.ready,
            asr_message=asr_status.message,
            asr_diagnostics=asr_service.diagnostics(),
            translation_diagnostics=translation_service.diagnostics(),
            obs_caption_diagnostics=runtime_orchestrator.obs_caption_diagnostics(),
            remote_diagnostics=self.remote_diagnostics(),
        )
