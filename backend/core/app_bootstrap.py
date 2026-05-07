from __future__ import annotations

from fastapi import FastAPI

from backend.config import LocalConfigManager, settings
from backend.core.audio_devices import AudioDeviceManager
from backend.core.cache_manager import CacheManager
from backend.core.dictionary_manager import DictionaryManager
from backend.core.logging_setup import configure_backend_logging
from backend.core.paths import APP_PATHS, ensure_app_layout
from backend.core.profile_manager import ProfileManager
from backend.core.remote_signaling import RemoteSignalingManager
from backend.core.remote_session import RemoteSessionManager
from backend.core.session_logger import SessionLogManager
from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.core.runtime_orchestrator import RuntimeOrchestrator
from backend.services.config_state_service import ConfigStateService
from backend.services import (
    AsrService,
    BrowserAsrService,
    DiagnosticsService,
    ExportService,
    ModelManagerService,
    OverlayService,
    RuntimeService,
    SettingsService,
    TranslationService,
)
from backend.ws_manager import WebSocketManager


def initialize_app_state(app: FastAPI) -> None:
    paths = ensure_app_layout(APP_PATHS)
    configure_backend_logging(paths.logs_dir)
    config_manager = LocalConfigManager(settings)
    config = config_manager.load()
    remote_session_manager = RemoteSessionManager()
    remote_signaling_manager = RemoteSignalingManager()

    app.state.paths = paths
    app.state.app_settings = settings
    app.state.config_manager = config_manager
    app.state.remote_session_manager = remote_session_manager
    app.state.remote_signaling_manager = remote_signaling_manager
    app.state.config_state_service = ConfigStateService(app)
    app.state.config_state_service.set_loaded_from_disk(config)

    ws_manager = WebSocketManager()
    audio_device_manager = AudioDeviceManager()
    profile_manager = ProfileManager(paths.profiles_dir, payload_normalizer=config_manager.normalize_profile_payload)
    profile_manager.ensure_default_profile()
    cache_manager = CacheManager(paths.user_data_dir / "cache")
    dictionary_manager = DictionaryManager(paths.user_data_dir)
    structured_runtime_logger = StructuredRuntimeLogger(paths.logs_dir)
    session_log_manager = SessionLogManager(paths.logs_dir)
    runtime_orchestrator = RuntimeOrchestrator(
        ws_manager,
        config_getter=lambda: app.state.config,
        cache_manager=cache_manager,
        export_dir=paths.user_data_dir / "exports",
        models_dir=paths.models_dir,
        structured_logger=structured_runtime_logger,
    )

    app.state.ws_manager = ws_manager
    app.state.websocket_manager = ws_manager
    app.state.audio_device_manager = audio_device_manager
    app.state.profile_manager = profile_manager
    app.state.cache_manager = cache_manager
    app.state.dictionary_manager = dictionary_manager
    app.state.structured_runtime_logger = structured_runtime_logger
    app.state.session_logger = session_log_manager
    app.state.session_log_manager = session_log_manager
    app.state.runtime_orchestrator = runtime_orchestrator

    app.state.asr_service = AsrService(app)
    app.state.browser_asr_service = BrowserAsrService(app)
    app.state.translation_service = TranslationService(app)
    app.state.overlay_service = OverlayService(app)
    app.state.export_service = ExportService(app)
    app.state.diagnostics_service = DiagnosticsService(app)
    app.state.model_manager = ModelManagerService(app)
    app.state.model_manager_service = app.state.model_manager
    app.state.settings_service = SettingsService(app)
    app.state.runtime_service = RuntimeService(app)
