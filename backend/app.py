from __future__ import annotations

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes_devices import router as devices_router
from backend.api.routes_exports import router as exports_router
from backend.api.routes_logs import router as logs_router
from backend.api.routes_profiles import router as profiles_router
from backend.api.routes_runtime import router as runtime_router
from backend.api.routes_settings import router as settings_router
from backend.config import LocalConfigManager, settings
from backend.core.font_catalog import build_project_fonts_stylesheet
from backend.core.cache_manager import CacheManager
from backend.core.dictionary_manager import DictionaryManager
from backend.core.session_logger import SessionLogManager
from backend.core.audio_devices import AudioDeviceManager
from backend.core.profile_manager import ProfileManager
from backend.core.subtitle_router import RuntimeOrchestrator
from backend.models import HealthResponse
from backend.runtime_paths import RUNTIME_PATHS, ensure_runtime_layout
from backend.ws_manager import WebSocketManager

ensure_runtime_layout(RUNTIME_PATHS)

FRONTEND_DIR = RUNTIME_PATHS.frontend_dir
OVERLAY_DIR = RUNTIME_PATHS.overlay_dir
PROJECT_FONTS_DIR = RUNTIME_PATHS.fonts_dir

PROJECT_FONTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.app_name, version="0.1.0")

app.state.app_settings = settings
app.state.config_manager = LocalConfigManager(settings)
app.state.config = app.state.config_manager.load()
app.state.ws_manager = WebSocketManager()
app.state.audio_device_manager = AudioDeviceManager()
app.state.profile_manager = ProfileManager(settings.data_dir / "profiles")
app.state.profile_manager.ensure_default_profile()
app.state.cache_manager = CacheManager(settings.data_dir / "cache")
app.state.dictionary_manager = DictionaryManager(settings.data_dir)
app.state.session_logger = SessionLogManager(settings.logs_dir)
app.state.runtime_orchestrator = RuntimeOrchestrator(
    app.state.ws_manager,
    config_getter=lambda: app.state.config,
    cache_manager=app.state.cache_manager,
    export_dir=settings.data_dir / "exports",
    models_dir=settings.models_dir,
)

app.include_router(settings_router)
app.include_router(runtime_router)
app.include_router(devices_router)
app.include_router(profiles_router)
app.include_router(exports_router)
app.include_router(logs_router)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend-static")
app.mount("/overlay-assets", StaticFiles(directory=str(OVERLAY_DIR)), name="overlay-static")
app.mount("/project-fonts", StaticFiles(directory=str(PROJECT_FONTS_DIR)), name="project-fonts")


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    asr_status = app.state.runtime_orchestrator.asr_status()
    asr_diagnostics = app.state.runtime_orchestrator.asr_diagnostics()
    translation_diagnostics = app.state.runtime_orchestrator.translation_diagnostics()
    obs_caption_diagnostics = app.state.runtime_orchestrator.obs_caption_diagnostics()
    return HealthResponse(
        asr_provider=asr_status.provider,
        asr_ready=asr_status.ready,
        asr_message=asr_status.message,
        asr_diagnostics=asr_diagnostics,
        translation_diagnostics=translation_diagnostics,
        obs_caption_diagnostics=obs_caption_diagnostics,
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/google-asr")
async def google_asr() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "google_asr.html")


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools_probe() -> Response:
    return Response(status_code=204)


@app.get("/project-fonts.css")
async def project_fonts_css() -> Response:
    return Response(
        content=build_project_fonts_stylesheet(PROJECT_FONTS_DIR),
        media_type="text/css",
    )


@app.get("/overlay")
async def overlay() -> FileResponse:
    return FileResponse(OVERLAY_DIR / "overlay.html")


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    manager: WebSocketManager = app.state.ws_manager
    await manager.connect(websocket)
    await websocket.send_json({"type": "hello", "message": "connected"})
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/asr_worker")
async def ws_asr_worker(websocket: WebSocket) -> None:
    await websocket.accept()
    await app.state.runtime_orchestrator.browser_asr_worker_connected()
    await websocket.send_json({"type": "hello", "message": "browser_asr_worker_connected"})
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            if str(message.get("type", "")).strip().lower() != "external_asr_update":
                continue
            await app.state.runtime_orchestrator.ingest_external_asr_update(
                partial=str(message.get("partial", "") or ""),
                final=str(message.get("final", "") or ""),
                is_final=bool(message.get("is_final", False)),
                source_lang=str(message.get("source_lang", "") or "") or None,
            )
    except WebSocketDisconnect:
        pass
    finally:
        await app.state.runtime_orchestrator.browser_asr_worker_disconnected()


@app.on_event("shutdown")
async def shutdown_runtime() -> None:
    runtime_orchestrator = getattr(app.state, "runtime_orchestrator", None)
    session_logger = getattr(app.state, "session_logger", None)
    if runtime_orchestrator is None:
        if session_logger is not None:
            session_logger.flush()
        return
    try:
        await runtime_orchestrator.stop()
    except Exception:
        # Shutdown should stay best-effort so the local server can still exit.
        pass
    finally:
        if session_logger is not None:
            session_logger.flush()
