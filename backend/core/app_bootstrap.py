from __future__ import annotations

import os

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
from backend.core.pipeline_trace_log import configure_pipeline_trace_log, pipeline_trace_mapping
from backend.core.startup_journey_log import (
    collect_runtime_environment_snapshot,
    configure_startup_journey_log,
    journey_log_mapping,
)
from backend.core.api_trace_log import configure_api_trace_log
from backend.core.ui_trace_log import configure_ui_trace_log
from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.core.runtime_lifecycle_trace import runtime_trace
from backend.core.diagnostic_flags import (
    is_api_trace_enabled,
    is_pipeline_trace_enabled,
    is_startup_journey_enabled,
    is_ui_trace_enabled,
)
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
    UpdateService,
)
from backend.ws_manager import WebSocketManager


def initialize_app_state(app: FastAPI) -> None:
    paths = ensure_app_layout(APP_PATHS)
    configure_backend_logging(paths.logs_dir)
    # Deep-diagnostic JSONL traces are opt-in (see backend/core/diagnostic_flags.py).
    # Without the corresponding env vars these files are simply not created, which
    # matches the 0.4.1 release surface. Each downstream call site already no-ops
    # when its trace singleton is not configured.
    if is_startup_journey_enabled():
        configure_startup_journey_log(paths.logs_dir)
    ui_trace_log = configure_ui_trace_log(paths.logs_dir) if is_ui_trace_enabled() else None
    api_trace_log = configure_api_trace_log(paths.logs_dir) if is_api_trace_enabled() else None
    if is_pipeline_trace_enabled():
        configure_pipeline_trace_log(paths.logs_dir)
        pipeline_trace_mapping(
            "backend",
            "app_bootstrap",
            "backend_initialized",
            {
                "python_executable": os.environ.get("SST_PYTHON_EXECUTABLE") or "",
                "desktop_launcher": os.environ.get("SST_DESKTOP_LAUNCHER") or "",
                "bundle_root": os.environ.get("SST_BUNDLE_ROOT") or "",
            },
        )
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
    app.state.ui_trace_log = ui_trace_log
    app.state.api_trace_log = api_trace_log
    app.state.runtime_orchestrator = runtime_orchestrator

    startup_payload = {
        "project_root": str(paths.project_root),
        "user_data_dir": str(paths.user_data_dir),
        "logs_dir": str(paths.logs_dir),
        "models_dir": str(paths.models_dir),
        "config_path": str(settings.config_path),
        "desktop_launcher": os.environ.get("SST_DESKTOP_LAUNCHER", ""),
        "remote_role": os.environ.get("SST_REMOTE_ROLE", ""),
        "allow_lan": os.environ.get("SST_ALLOW_LAN", ""),
        "python_executable": os.environ.get("SST_PYTHON_EXECUTABLE", ""),
        **collect_runtime_environment_snapshot(),
    }
    runtime_trace(
        structured_runtime_logger,
        "backend_startup",
        source="app_bootstrap",
        payload=startup_payload,
    )
    journey_log_mapping("backend", "backend_startup", startup_payload)

    app.state.asr_service = AsrService(app)
    app.state.browser_asr_service = BrowserAsrService(app)
    runtime_orchestrator.set_browser_asr_transport_probe(lambda: app.state.browser_asr_service.has_active_transport())
    app.state.translation_service = TranslationService(app)
    app.state.overlay_service = OverlayService(app)
    app.state.export_service = ExportService(app)
    app.state.diagnostics_service = DiagnosticsService(app)
    app.state.model_manager = ModelManagerService(app)
    app.state.model_manager_service = app.state.model_manager
    app.state.settings_service = SettingsService(app)
    app.state.runtime_service = RuntimeService(app)
    app.state.update_service = UpdateService(app)
