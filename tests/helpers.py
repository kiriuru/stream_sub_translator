from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any

from backend import app as app_module
from backend.core.parakeet_provider import AsrProviderStatus
from backend.core.remote_session import RemoteSessionManager
from backend.core.remote_signaling import RemoteSignalingManager
from backend.models import AsrDiagnostics, ObsCaptionDiagnostics, RuntimeState, TranslationDiagnostics
from backend.ws_manager import WebSocketManager


class FakeConfigManager:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = dict(payload)
        self.saved_payloads: list[dict[str, Any]] = []

    def load(self) -> dict[str, Any]:
        return dict(self.payload)

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payload = dict(payload)
        self.saved_payloads.append(dict(payload))
        return dict(self.payload)

    def subtitle_style_presets(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ = payload
        return {}

    def font_catalog(self) -> dict[str, Any]:
        return {}


class FakeAudioDeviceManager:
    def __init__(self, devices: list[dict[str, Any]] | None = None) -> None:
        self.devices = devices if devices is not None else [{"id": "mic0", "name": "Microphone"}]

    def list_input_devices(self) -> list[dict[str, Any]]:
        return list(self.devices)


class FakeSessionLogger:
    def __init__(self) -> None:
        self.flush_count = 0
        self.records: list[dict[str, Any]] = []

    def log(self, channel: str, message: str, *, source: str | None = None, details: dict[str, Any] | None = None) -> None:
        self.records.append(
            {
                "channel": channel,
                "message": message,
                "source": source,
                "details": dict(details or {}),
            }
        )

    def flush(self) -> None:
        self.flush_count += 1


class FakeStructuredRuntimeLogger:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def log(self, channel: str, event: str, *, source: str | None = None, payload: dict[str, Any] | None = None, **fields: Any) -> None:
        merged_payload = dict(payload or {})
        merged_payload.update(fields)
        self.records.append(
            {
                "channel": channel,
                "event": event,
                "source": source,
                "payload": merged_payload,
            }
        )


class FakeRuntimeOrchestrator:
    def __init__(self) -> None:
        self.runtime_state = RuntimeState(is_running=False, status="idle")
        self.start_calls: list[dict[str, Any]] = []
        self.stop_calls = 0
        self.apply_live_settings_calls: list[dict[str, Any]] = []
        self.browser_worker_connected = 0
        self.browser_worker_disconnected = 0
        self.external_updates: list[dict[str, Any]] = []
        self.remote_audio_connected: list[str | None] = []
        self.remote_audio_disconnected = 0
        self.remote_audio_chunks: list[bytes] = []
        self.remote_transcript_payloads: list[dict[str, Any]] = []
        self.remote_translation_payloads: list[dict[str, Any]] = []

    async def start(self, *, has_audio_inputs: bool, device_id: str | None) -> RuntimeState:
        self.start_calls.append({"has_audio_inputs": has_audio_inputs, "device_id": device_id})
        self.runtime_state = RuntimeState(
            is_running=True,
            status="listening",
            started_at_utc="2026-01-01T00:00:00+00:00",
        )
        return self.runtime_state

    async def stop(self) -> RuntimeState:
        self.stop_calls += 1
        self.runtime_state = RuntimeState(is_running=False, status="idle")
        return self.runtime_state

    def status(self) -> RuntimeState:
        return self.runtime_state

    async def apply_live_settings(self, config: dict[str, Any]) -> None:
        self.apply_live_settings_calls.append(dict(config))

    def asr_status(self) -> AsrProviderStatus:
        return AsrProviderStatus(provider="fake_asr", ready=True, message="ready")

    def asr_diagnostics(self) -> AsrDiagnostics:
        return AsrDiagnostics(
            provider="fake_asr",
            requested_provider="fake_asr",
            requested_device_policy="fake",
            supports_gpu=False,
            supports_partials=True,
            supports_streaming=True,
            supports_word_timestamps=False,
            torch_built_with_cuda=False,
            torch_cuda_is_available=False,
            torch_device_count=0,
            degraded_mode=False,
            selected_device="fake",
            selected_execution_provider="fake",
            partials_supported=True,
            runtime_initialized=self.runtime_state.is_running,
        )

    def translation_diagnostics(self) -> TranslationDiagnostics:
        return TranslationDiagnostics(enabled=False, status="disabled", summary="Translation disabled.")

    def obs_caption_diagnostics(self) -> ObsCaptionDiagnostics:
        return ObsCaptionDiagnostics()

    async def browser_asr_worker_connected(self) -> None:
        self.browser_worker_connected += 1

    async def browser_asr_worker_disconnected(self) -> None:
        self.browser_worker_disconnected += 1

    async def ingest_external_asr_update(self, **payload: Any) -> None:
        self.external_updates.append(dict(payload))

    async def remote_audio_ingest_connected(self, *, session_id: str | None = None) -> None:
        self.remote_audio_connected.append(session_id)

    async def remote_audio_ingest_disconnected(self) -> None:
        self.remote_audio_disconnected += 1

    async def ingest_remote_audio_chunk(self, payload: bytes) -> bool:
        self.remote_audio_chunks.append(bytes(payload))
        return True

    async def ingest_remote_transcript_event(self, payload: dict[str, Any]) -> bool:
        self.remote_transcript_payloads.append(dict(payload))
        return True

    async def ingest_remote_translation_event(self, payload: dict[str, Any]) -> bool:
        self.remote_translation_payloads.append(dict(payload))
        return True


class AppStateSandbox(AbstractContextManager["AppStateSandbox"]):
    _STATE_KEYS = [
        "app_settings",
        "config_manager",
        "config",
        "remote_session_manager",
        "remote_signaling_manager",
        "ws_manager",
        "audio_device_manager",
        "runtime_orchestrator",
        "session_logger",
        "structured_runtime_logger",
    ]

    def __init__(self, *, config: dict[str, Any] | None = None, data_dir: Path | None = None) -> None:
        self.config = dict(config or {"source_lang": "ru", "translation": {}, "subtitle_output": {}, "remote": {}})
        self._temp_dir = TemporaryDirectory()
        base_dir = Path(data_dir) if data_dir is not None else Path(self._temp_dir.name)
        self.paths = SimpleNamespace(
            root=base_dir,
            data_dir=base_dir / "user-data",
            logs_dir=base_dir / "logs",
            config_path=base_dir / "user-data" / "config.json",
            models_dir=base_dir / "user-data" / "models",
            local_base_url="http://127.0.0.1:8765",
            app_host="127.0.0.1",
            app_port=8765,
        )
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        self.paths.models_dir.mkdir(parents=True, exist_ok=True)
        self.saved: dict[str, Any] = {}
        self.runtime_orchestrator = FakeRuntimeOrchestrator()
        self.config_manager = FakeConfigManager(self.config)
        self.audio_device_manager = FakeAudioDeviceManager()
        self.session_logger = FakeSessionLogger()
        self.structured_runtime_logger = FakeStructuredRuntimeLogger()
        self.remote_session_manager = RemoteSessionManager()
        self.remote_signaling_manager = RemoteSignalingManager()
        self.ws_manager = WebSocketManager()

    def __enter__(self) -> "AppStateSandbox":
        for key in self._STATE_KEYS:
            self.saved[key] = getattr(app_module.app.state, key)
        app_module.app.state.app_settings = self.paths
        app_module.app.state.config_manager = self.config_manager
        app_module.app.state.config = dict(self.config)
        app_module.app.state.remote_session_manager = self.remote_session_manager
        app_module.app.state.remote_signaling_manager = self.remote_signaling_manager
        app_module.app.state.ws_manager = self.ws_manager
        app_module.app.state.audio_device_manager = self.audio_device_manager
        app_module.app.state.runtime_orchestrator = self.runtime_orchestrator
        app_module.app.state.session_logger = self.session_logger
        app_module.app.state.structured_runtime_logger = self.structured_runtime_logger
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for key, value in self.saved.items():
            setattr(app_module.app.state, key, value)
        self._temp_dir.cleanup()
        return None
