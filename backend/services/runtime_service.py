from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI

from backend.models import (
    AudioInputsResponse,
    BrowserAsrDiagnostics,
    ObsUrlResponse,
    RemoteWorkerHealthResponse,
    RemoteWorkerRuntimeActionResponse,
    RemoteWorkerRuntimeStatusResponse,
    RuntimeActionResponse,
    RuntimeStartRequest,
    RuntimeState,
)


class RuntimeService:
    def __init__(self, app: FastAPI) -> None:
        self._app = app

    @property
    def _runtime_orchestrator(self):
        return self._app.state.runtime_orchestrator

    def _current_config(self) -> dict[str, Any]:
        config_state_service = getattr(self._app.state, "config_state_service", None)
        if config_state_service is not None:
            return config_state_service.current_payload()
        payload = getattr(self._app.state, "config", {})
        return payload if isinstance(payload, dict) else {}

    def _apply_runtime_start_config(self, payload: dict[str, Any] | None) -> None:
        if not isinstance(payload, dict) or not payload:
            return
        config_state_service = getattr(self._app.state, "config_state_service", None)
        if config_state_service is not None:
            config_state_service.set_runtime_start_snapshot(payload)
            return
        self._app.state.config = dict(payload)

    def _remote_config(self) -> dict[str, Any]:
        remote = self._current_config().get("remote", {})
        return remote if isinstance(remote, dict) else {}

    def _configured_worker_url(self) -> str | None:
        controller = self._remote_config().get("controller", {})
        if not isinstance(controller, dict):
            return None
        worker_url = str(controller.get("worker_url", "") or "").strip()
        return worker_url or None

    def _controller_connect_timeout_seconds(self) -> float:
        controller = self._remote_config().get("controller", {})
        if not isinstance(controller, dict):
            return 8.0
        try:
            timeout_ms = int(controller.get("connect_timeout_ms", 8000) or 8000)
        except (TypeError, ValueError):
            timeout_ms = 8000
        return max(1.0, min(120.0, float(timeout_ms) / 1000.0))

    @staticmethod
    def _build_target_url(base_url: str, path: str) -> str:
        normalized_base = str(base_url or "").strip().rstrip("/")
        normalized_path = "/" + str(path or "").lstrip("/")
        return f"{normalized_base}{normalized_path}"

    async def _proxy_worker_request(
        self,
        *,
        method: str,
        path: str,
        json_payload: dict[str, Any] | None = None,
    ) -> tuple[str | None, dict[str, Any] | None, str | None]:
        worker_url = self._configured_worker_url()
        if not worker_url:
            return None, None, "Worker URL is not configured in remote.controller.worker_url."
        target_url = self._build_target_url(worker_url, path)
        timeout_seconds = self._controller_connect_timeout_seconds()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                if method.upper() == "GET":
                    response = await client.get(target_url)
                elif method.upper() == "POST":
                    response = await client.post(target_url, json=json_payload or {})
                else:
                    return worker_url, None, f"Unsupported proxy method: {method}"
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict):
                    return worker_url, None, "Worker response is not a JSON object."
                return worker_url, body, None
        except Exception as exc:
            return worker_url, None, str(exc)

    def audio_inputs(self) -> AudioInputsResponse:
        devices = self._app.state.audio_device_manager.list_input_devices()
        return AudioInputsResponse(devices=devices, source="sounddevice")

    async def start(self, body: RuntimeStartRequest | None = None) -> RuntimeActionResponse:
        payload = body or RuntimeStartRequest()
        self._apply_runtime_start_config(payload.config_payload)
        devices = self._app.state.audio_device_manager.list_input_devices()
        state = await self._runtime_orchestrator.start(
            has_audio_inputs=bool(devices),
            device_id=payload.device_id,
        )
        return RuntimeActionResponse(action="start", runtime=state)

    async def stop(self) -> RuntimeActionResponse:
        browser_asr_service = getattr(self._app.state, "browser_asr_service", None)
        if browser_asr_service is not None:
            await browser_asr_service.send_control("stop", reason="runtime_stop")
        state = await self._runtime_orchestrator.stop()
        return RuntimeActionResponse(action="stop", runtime=state)

    def status(self) -> RuntimeState:
        state = self._runtime_orchestrator.status()
        remote_diagnostics = self._app.state.diagnostics_service.remote_diagnostics()
        ws_diagnostics = self._app.state.ws_manager.diagnostics()
        client_log_diagnostics = self._app.state.session_logger.diagnostics()
        browser_worker_diagnostics = self._app.state.browser_asr_service.diagnostics()
        config = self._current_config()
        asr_config = config.get("asr", {}) if isinstance(config, dict) else {}
        overlay_config = config.get("overlay", {}) if isinstance(config, dict) else {}
        subtitle_output = config.get("subtitle_output", {}) if isinstance(config, dict) else {}
        translation_config = config.get("translation", {}) if isinstance(config, dict) else {}

        asr = state.asr.model_copy(
            update={
                "active_mode": str(asr_config.get("mode", state.asr.active_mode) or state.asr.active_mode)
                if isinstance(asr_config, dict)
                else state.asr.active_mode,
                "provider": state.asr.provider or (state.asr_diagnostics.provider if state.asr_diagnostics else None),
                "provider_label": state.asr.provider_label
                or (state.asr_diagnostics.provider_label if state.asr_diagnostics else None),
                "diagnostics": (
                    state.asr.diagnostics.model_copy(
                        update={"browser_worker": BrowserAsrDiagnostics.model_validate(browser_worker_diagnostics)}
                    )
                    if state.asr.diagnostics is not None
                    else (
                        state.asr_diagnostics.model_copy(
                            update={"browser_worker": BrowserAsrDiagnostics.model_validate(browser_worker_diagnostics)}
                        )
                        if state.asr_diagnostics is not None
                        else None
                    )
                ),
            }
        )
        metrics = state.metrics.model_copy(
            update={
                "client_log_events_received": int(client_log_diagnostics.get("client_log_events_received", 0) or 0),
                "client_log_events_written": int(client_log_diagnostics.get("client_log_events_written", 0) or 0),
                "client_log_events_dropped": int(client_log_diagnostics.get("client_log_events_dropped", 0) or 0),
                "ws_events_connections_active": int(ws_diagnostics.get("ws_events_connections_active", 0) or 0),
                "ws_events_broadcast_count": int(ws_diagnostics.get("ws_events_broadcast_count", 0) or 0),
                "ws_events_send_failures": int(ws_diagnostics.get("ws_events_send_failures", 0) or 0),
                "ws_events_dead_connections_removed": int(ws_diagnostics.get("ws_events_dead_connections_removed", 0) or 0),
            }
        )
        overlay = state.overlay.model_copy(
            update={
                "preset": str(overlay_config.get("preset", state.overlay.preset) or state.overlay.preset)
                if isinstance(overlay_config, dict)
                else state.overlay.preset,
                "compact": bool(overlay_config.get("compact", state.overlay.compact))
                if isinstance(overlay_config, dict)
                else state.overlay.compact,
                "overlay_url": self._app.state.overlay_service.overlay_url(),
                "show_source": bool(subtitle_output.get("show_source", state.overlay.show_source))
                if isinstance(subtitle_output, dict)
                else state.overlay.show_source,
                "show_translations": bool(subtitle_output.get("show_translations", state.overlay.show_translations))
                if isinstance(subtitle_output, dict)
                else state.overlay.show_translations,
                "display_order": list(subtitle_output.get("display_order", state.overlay.display_order))
                if isinstance(subtitle_output, dict)
                else state.overlay.display_order,
            }
        )
        translation = state.translation.model_copy(
            update={
                "enabled": bool(translation_config.get("enabled", state.translation.enabled))
                if isinstance(translation_config, dict)
                else state.translation.enabled,
                "provider": str(translation_config.get("provider", state.translation.provider or "") or state.translation.provider or "")
                if isinstance(translation_config, dict)
                else state.translation.provider,
                "target_languages": list(translation_config.get("target_languages", state.translation.target_languages))
                if isinstance(translation_config, dict)
                else state.translation.target_languages,
                "diagnostics": state.translation.diagnostics or state.translation_diagnostics,
            }
        )
        return state.model_copy(
            update={
                "asr": asr,
                "translation": translation,
                "remote": remote_diagnostics,
                "remote_diagnostics": remote_diagnostics,
                "overlay": overlay,
                "metrics": metrics,
                "active_config_source": getattr(getattr(self._app.state, "active_config_state", None), "source", None),
                "active_config_persisted": getattr(getattr(self._app.state, "active_config_state", None), "persisted", None),
                "active_config_hash": getattr(getattr(self._app.state, "active_config_state", None), "hash", None),
            }
        )

    def obs_url(self) -> ObsUrlResponse:
        return ObsUrlResponse(overlay_url=self._app.state.overlay_service.overlay_url())

    async def worker_runtime_start(self) -> RemoteWorkerRuntimeActionResponse:
        worker_url, body, error = await self._proxy_worker_request(
            method="POST",
            path="/api/runtime/start",
            json_payload={"device_id": None},
        )
        if error:
            return RemoteWorkerRuntimeActionResponse(
                ok=False,
                action="start",
                worker_url=worker_url,
                worker_runtime=None,
                error=error,
            )
        worker_runtime_payload = body.get("runtime", {}) if isinstance(body, dict) else {}
        return RemoteWorkerRuntimeActionResponse(
            ok=bool(body.get("ok", True)),
            action="start",
            worker_url=worker_url,
            worker_runtime=worker_runtime_payload if isinstance(worker_runtime_payload, dict) else None,
            error=None,
        )

    async def worker_runtime_stop(self) -> RemoteWorkerRuntimeActionResponse:
        worker_url, body, error = await self._proxy_worker_request(
            method="POST",
            path="/api/runtime/stop",
            json_payload={},
        )
        if error:
            return RemoteWorkerRuntimeActionResponse(
                ok=False,
                action="stop",
                worker_url=worker_url,
                worker_runtime=None,
                error=error,
            )
        worker_runtime_payload = body.get("runtime", {}) if isinstance(body, dict) else {}
        return RemoteWorkerRuntimeActionResponse(
            ok=bool(body.get("ok", True)),
            action="stop",
            worker_url=worker_url,
            worker_runtime=worker_runtime_payload if isinstance(worker_runtime_payload, dict) else None,
            error=None,
        )

    async def worker_runtime_status(self) -> RemoteWorkerRuntimeStatusResponse:
        worker_url, body, error = await self._proxy_worker_request(
            method="GET",
            path="/api/runtime/status",
        )
        if error:
            return RemoteWorkerRuntimeStatusResponse(
                ok=False,
                worker_url=worker_url,
                worker_runtime=None,
                error=error,
            )
        return RemoteWorkerRuntimeStatusResponse(
            ok=True,
            worker_url=worker_url,
            worker_runtime=body if isinstance(body, dict) else None,
            error=None,
        )

    async def worker_health(self) -> RemoteWorkerHealthResponse:
        worker_url, body, error = await self._proxy_worker_request(
            method="GET",
            path="/api/health",
        )
        if error:
            return RemoteWorkerHealthResponse(
                ok=False,
                worker_url=worker_url,
                health=None,
                error=error,
            )
        return RemoteWorkerHealthResponse(
            ok=True,
            worker_url=worker_url,
            health=body if isinstance(body, dict) else None,
            error=None,
        )
