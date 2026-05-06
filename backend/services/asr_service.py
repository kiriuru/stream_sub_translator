from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from backend.core.parakeet_provider import AsrProviderStatus
from backend.models import AsrDiagnostics, BrowserAsrDiagnostics


class AsrService:
    def __init__(self, app: FastAPI) -> None:
        self._app = app

    @property
    def _runtime_orchestrator(self):
        return self._app.state.runtime_orchestrator

    def status(self) -> AsrProviderStatus:
        return self._runtime_orchestrator.asr_status()

    def diagnostics(self) -> AsrDiagnostics:
        diagnostics = self._runtime_orchestrator.asr_diagnostics()
        browser_asr_service = getattr(self._app.state, "browser_asr_service", None)
        if browser_asr_service is None:
            return diagnostics
        return diagnostics.model_copy(
            update={"browser_worker": BrowserAsrDiagnostics.model_validate(browser_asr_service.diagnostics())}
        )

    async def browser_worker_connected(self) -> None:
        await self._runtime_orchestrator.browser_asr_worker_connected()

    async def browser_worker_disconnected(self) -> None:
        await self._runtime_orchestrator.browser_asr_worker_disconnected()

    async def ingest_external_update(
        self,
        *,
        partial: str,
        final: str,
        is_final: bool,
        source_lang: str | None,
        generation_id: int | None = None,
        session_id: str | None = None,
        client_segment_id: str | None = None,
        forced_final: bool = False,
    ) -> None:
        await self._runtime_orchestrator.ingest_external_asr_update(
            partial=partial,
            final=final,
            is_final=is_final,
            source_lang=source_lang,
            generation_id=generation_id,
            session_id=session_id,
            client_segment_id=client_segment_id,
            forced_final=forced_final,
        )

    async def update_browser_worker_status(self, payload: dict[str, Any]) -> None:
        await self._runtime_orchestrator.update_browser_asr_worker_status(payload)

    async def remote_audio_ingest_connected(self, *, session_id: str | None = None) -> None:
        await self._runtime_orchestrator.remote_audio_ingest_connected(session_id=session_id)

    async def remote_audio_ingest_disconnected(self) -> None:
        await self._runtime_orchestrator.remote_audio_ingest_disconnected()

    async def ingest_remote_audio_chunk(self, payload: bytes) -> bool:
        return await self._runtime_orchestrator.ingest_remote_audio_chunk(payload)

    async def ingest_remote_transcript_event(self, payload: dict[str, Any]) -> bool:
        return await self._runtime_orchestrator.ingest_remote_transcript_event(payload)

    async def ingest_remote_translation_event(self, payload: dict[str, Any]) -> bool:
        return await self._runtime_orchestrator.ingest_remote_translation_event(payload)
