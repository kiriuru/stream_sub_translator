from __future__ import annotations

import base64
import json

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes_devices import router as devices_router
from backend.api.routes_exports import router as exports_router
from backend.api.routes_logs import router as logs_router
from backend.api.routes_profiles import router as profiles_router
from backend.api.routes_remote import router as remote_router
from backend.api.routes_runtime import router as runtime_router
from backend.api.routes_settings import router as settings_router
from backend.api.routes_version import router as version_router
from backend.config import LocalConfigManager, settings
from backend.core.font_catalog import build_project_fonts_stylesheet
from backend.core.cache_manager import CacheManager
from backend.core.remote_diagnostics import build_remote_diagnostics
from backend.core.remote_signaling import RemoteSignalingManager
from backend.core.remote_session import RemoteSessionManager
from backend.core.dictionary_manager import DictionaryManager
from backend.core.session_logger import SessionLogManager
from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.core.audio_devices import AudioDeviceManager
from backend.core.profile_manager import ProfileManager
from backend.core.subtitle_router import RuntimeOrchestrator
from backend.models import HealthResponse
from backend.runtime_paths import RUNTIME_PATHS, ensure_runtime_layout
from backend.versioning import PROJECT_VERSION, build_version_info_payload
from backend.ws_manager import WebSocketManager

ensure_runtime_layout(RUNTIME_PATHS)

FRONTEND_DIR = RUNTIME_PATHS.frontend_dir
OVERLAY_DIR = RUNTIME_PATHS.overlay_dir
PROJECT_FONTS_DIR = RUNTIME_PATHS.fonts_dir

PROJECT_FONTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.app_name, version=PROJECT_VERSION)

app.state.app_settings = settings
app.state.config_manager = LocalConfigManager(settings)
app.state.config = app.state.config_manager.load()
app.state.remote_session_manager = RemoteSessionManager()
app.state.remote_signaling_manager = RemoteSignalingManager()
remote_config = app.state.config.get("remote", {}) if isinstance(app.state.config, dict) else {}
if not isinstance(remote_config, dict):
    remote_config = {}
app.state.remote_session_manager.preload(
    session_id=str(remote_config.get("session_id", "") or "").strip() or None,
    pair_code=str(remote_config.get("pair_code", "") or "").strip() or None,
)
app.state.ws_manager = WebSocketManager()
app.state.audio_device_manager = AudioDeviceManager()
app.state.profile_manager = ProfileManager(settings.data_dir / "profiles")
app.state.profile_manager.ensure_default_profile()
app.state.cache_manager = CacheManager(settings.data_dir / "cache")
app.state.dictionary_manager = DictionaryManager(settings.data_dir)
app.state.structured_runtime_logger = StructuredRuntimeLogger(settings.logs_dir)
app.state.session_logger = SessionLogManager(settings.logs_dir)
app.state.runtime_orchestrator = RuntimeOrchestrator(
    app.state.ws_manager,
    config_getter=lambda: app.state.config,
    cache_manager=app.state.cache_manager,
    export_dir=settings.data_dir / "exports",
    models_dir=settings.models_dir,
    structured_logger=app.state.structured_runtime_logger,
)

app.include_router(settings_router)
app.include_router(runtime_router)
app.include_router(devices_router)
app.include_router(profiles_router)
app.include_router(exports_router)
app.include_router(logs_router)
app.include_router(remote_router)
app.include_router(version_router)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend-static")
app.mount("/overlay-assets", StaticFiles(directory=str(OVERLAY_DIR)), name="overlay-static")
app.mount("/project-fonts", StaticFiles(directory=str(PROJECT_FONTS_DIR)), name="project-fonts")


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    asr_status = app.state.runtime_orchestrator.asr_status()
    asr_diagnostics = app.state.runtime_orchestrator.asr_diagnostics()
    translation_diagnostics = app.state.runtime_orchestrator.translation_diagnostics()
    obs_caption_diagnostics = app.state.runtime_orchestrator.obs_caption_diagnostics()
    remote_diagnostics = build_remote_diagnostics(
        app.state.config,
        app_host=settings.app_host,
        app_port=settings.app_port,
    )
    version_info = build_version_info_payload(app.state.config)
    return HealthResponse(
        app_version=version_info.get("current_version"),
        release_sync=version_info.get("sync"),
        asr_provider=asr_status.provider,
        asr_ready=asr_status.ready,
        asr_message=asr_status.message,
        asr_diagnostics=asr_diagnostics,
        translation_diagnostics=translation_diagnostics,
        obs_caption_diagnostics=obs_caption_diagnostics,
        remote_diagnostics=remote_diagnostics,
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/google-asr")
async def google_asr() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "google_asr.html")


@app.get("/remote/controller-bridge")
async def remote_controller_bridge() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "remote_controller_bridge.html")


@app.get("/remote/worker-bridge")
async def remote_worker_bridge() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "remote_worker_bridge.html")


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
    await manager.replay_last(
        websocket,
        message_types=[
            "runtime_update",
            "subtitle_payload_update",
            "overlay_update",
        ],
    )
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
            message_type = str(message.get("type", "")).strip().lower()
            if message_type == "external_asr_update":
                await app.state.runtime_orchestrator.ingest_external_asr_update(
                    partial=str(message.get("partial", "") or ""),
                    final=str(message.get("final", "") or ""),
                    is_final=bool(message.get("is_final", False)),
                    source_lang=str(message.get("source_lang", "") or "") or None,
                )
                continue
            if message_type == "browser_asr_status":
                await app.state.runtime_orchestrator.update_browser_asr_worker_status(message)
    except WebSocketDisconnect:
        pass
    finally:
        await app.state.runtime_orchestrator.browser_asr_worker_disconnected()


@app.websocket("/ws/remote/signaling")
async def ws_remote_signaling(websocket: WebSocket) -> None:
    session_id = str(websocket.query_params.get("session_id", "") or "").strip()
    pair_code = str(websocket.query_params.get("pair_code", "") or "").strip()
    role = str(websocket.query_params.get("role", "") or "").strip().lower()
    if role not in {"controller", "worker"}:
        await websocket.close(code=1008)
        return
    accepted, reason = app.state.remote_session_manager.verify_pairing(
        session_id=session_id,
        pair_code=pair_code,
    )
    if not accepted:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": reason or "Pairing rejected."})
        await websocket.close(code=1008)
        return

    signaling_manager: RemoteSignalingManager = app.state.remote_signaling_manager
    await signaling_manager.connect(session_id=session_id, role=role, websocket=websocket)
    app.state.remote_session_manager.heartbeat(session_id=session_id, role=role)
    await websocket.send_json(
        {
            "type": "hello",
            "message": "remote_signaling_connected",
            "role": role,
            "session_id": session_id,
        }
    )
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON payload."})
                continue
            if not isinstance(payload, dict):
                await websocket.send_json({"type": "error", "message": "Expected JSON object payload."})
                continue

            message_type = str(payload.get("type", "") or "").strip().lower()
            if message_type == "heartbeat":
                accepted_heartbeat, reason_heartbeat, pairing = app.state.remote_session_manager.heartbeat(
                    session_id=session_id,
                    role=role,
                )
                await websocket.send_json(
                    {
                        "type": "heartbeat_ack",
                        "accepted": accepted_heartbeat,
                        "reason": reason_heartbeat,
                        "pairing": pairing.model_dump() if pairing is not None else None,
                    }
                )
                continue

            relay_payload = payload.get("payload", payload)
            if not isinstance(relay_payload, dict):
                await websocket.send_json({"type": "error", "message": "Signal payload must be a JSON object."})
                continue
            app.state.remote_session_manager.heartbeat(session_id=session_id, role=role)
            relayed = await signaling_manager.relay(
                session_id=session_id,
                from_role=role,
                payload=relay_payload,
            )
            if not relayed:
                await websocket.send_json({"type": "warning", "message": "Remote peer is not connected yet."})
    except WebSocketDisconnect:
        pass
    finally:
        await signaling_manager.disconnect(session_id=session_id, role=role, websocket=websocket)


@app.websocket("/ws/remote/audio_ingest")
async def ws_remote_audio_ingest(websocket: WebSocket) -> None:
    session_id = str(websocket.query_params.get("session_id", "") or "").strip()
    pair_code = str(websocket.query_params.get("pair_code", "") or "").strip()
    accepted, reason = app.state.remote_session_manager.verify_pairing(
        session_id=session_id,
        pair_code=pair_code,
    )
    if not accepted:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": reason or "Pairing rejected."})
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await app.state.runtime_orchestrator.remote_audio_ingest_connected(session_id=session_id)
    app.state.remote_session_manager.heartbeat(session_id=session_id, role="controller")
    await websocket.send_json({"type": "hello", "message": "remote_audio_ingest_connected"})
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            payload_bytes = message.get("bytes")
            if payload_bytes is None:
                payload_text = message.get("text")
                if payload_text is None:
                    continue
                try:
                    payload = json.loads(payload_text)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                message_type = str(payload.get("type", "") or "").strip().lower()
                if message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                if message_type != "audio_chunk_b64":
                    continue
                encoded = str(payload.get("data", "") or "").strip()
                if not encoded:
                    continue
                try:
                    payload_bytes = base64.b64decode(encoded, validate=True)
                except Exception:
                    continue

            if not payload_bytes:
                continue
            await app.state.runtime_orchestrator.ingest_remote_audio_chunk(payload_bytes)
            app.state.remote_session_manager.heartbeat(session_id=session_id, role="controller")
    except WebSocketDisconnect:
        pass
    finally:
        await app.state.runtime_orchestrator.remote_audio_ingest_disconnected()


@app.websocket("/ws/remote/result_ingest")
async def ws_remote_result_ingest(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "hello", "message": "remote_result_ingest_connected"})
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            event_type = str(message.get("type", "") or "").strip().lower()
            payload = message.get("payload", {})
            if event_type == "transcript_update":
                await app.state.runtime_orchestrator.ingest_remote_transcript_event(payload)
                continue
            if event_type == "translation_update":
                await app.state.runtime_orchestrator.ingest_remote_translation_event(payload)
                continue
            if event_type == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass


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
