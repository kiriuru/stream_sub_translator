from __future__ import annotations

import base64
import json

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes_devices import router as devices_router
from backend.api.routes_exports import router as exports_router
from backend.api.routes_logs import router as logs_router
from backend.api.routes_profiles import router as profiles_router
from backend.api.routes_remote import router as remote_router
from backend.api.routes_runtime import router as runtime_router
from backend.api.routes_settings import router as settings_router
from backend.api.routes_openai_models import router as openai_models_router
from backend.api.routes_updates import router as updates_router
from backend.api.routes_version import router as version_router
from backend.config import settings
from backend.core.api_errors import register_api_error_handlers
from backend.core.api_trace_log import api_trace
from backend.core.app_bootstrap import initialize_app_state
from backend.core.http_api_trace_middleware import http_api_trace_middleware
from backend.core.font_catalog import build_project_fonts_stylesheet
from backend.core.remote_signaling import RemoteSignalingManager
from backend.models import HealthResponse
from backend.versioning import PROJECT_VERSION

app = FastAPI(title=settings.app_name, version=PROJECT_VERSION)
initialize_app_state(app)
register_api_error_handlers(app)
app.middleware("http")(http_api_trace_middleware)

FRONTEND_DIR = app.state.paths.frontend_root
OVERLAY_DIR = app.state.paths.overlay_root
PROJECT_FONTS_DIR = app.state.paths.fonts_dir

PROJECT_FONTS_DIR.mkdir(parents=True, exist_ok=True)

app.include_router(settings_router)
app.include_router(updates_router)
app.include_router(runtime_router)
app.include_router(devices_router)
app.include_router(profiles_router)
app.include_router(exports_router)
app.include_router(logs_router)
app.include_router(remote_router)
app.include_router(version_router)
app.include_router(openai_models_router)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend-static")
app.mount("/overlay-assets", StaticFiles(directory=str(OVERLAY_DIR)), name="overlay-static")
app.mount("/project-fonts", StaticFiles(directory=str(PROJECT_FONTS_DIR)), name="project-fonts")


@app.middleware("http")
async def disable_frontend_caching(request: Request, call_next):
    """
    Keep frontend iteration frictionless: avoid hard-reload requirements on Windows browsers
    by disabling HTTP caching for dashboard HTML + static assets.

    Settings are persisted server-side (`user-data/`) and in localStorage, so reloads are safe.
    """
    response = await call_next(request)
    path = request.url.path or "/"
    should_disable_cache = (
        path in {
            "/",
            "/overlay",
            "/google-asr",
            "/google-asr-experimental",
            "/remote/controller-bridge",
            "/remote/worker-bridge",
            "/project-fonts.css",
        }
        or path.startswith("/static/")
        or path.startswith("/overlay-assets/")
    )
    if should_disable_cache:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/api/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    return request.app.state.diagnostics_service.health()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/google-asr")
async def google_asr() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "google_asr.html")


@app.get("/google-asr-experimental")
async def google_asr_experimental() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "google_asr_experimental.html")


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
    manager = websocket.app.state.ws_manager
    client = websocket.client
    api_trace(
        "ws",
        "endpoint_accept",
        path="/ws/events",
        client_host=client.host if client else None,
        client_port=client.port if client else None,
    )
    await manager.connect(websocket)
    if not await manager.send_direct(websocket, {"type": "hello", "message": "connected"}):
        api_trace("ws", "endpoint_hello_failed", path="/ws/events")
        return
    api_trace("ws", "endpoint_hello_sent", path="/ws/events")
    await manager.replay_last(
        websocket,
        message_types=[
            "runtime_update",
            "subtitle_payload_update",
            "overlay_update",
        ],
    )
    api_trace("ws", "endpoint_replay_complete", path="/ws/events")
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        api_trace("ws", "endpoint_disconnect", path="/ws/events", reason="WebSocketDisconnect")
    finally:
        await manager.disconnect(websocket)
        api_trace("ws", "endpoint_closed", path="/ws/events")


@app.websocket("/ws/asr_worker")
async def ws_asr_worker(websocket: WebSocket) -> None:
    asr_service = websocket.app.state.asr_service
    browser_asr_service = websocket.app.state.browser_asr_service
    client = websocket.client
    api_trace(
        "ws",
        "endpoint_accept",
        path="/ws/asr_worker",
        client_host=client.host if client else None,
    )
    await websocket.accept()
    transport_id = await browser_asr_service.register_connection(websocket)
    api_trace("ws", "endpoint_registered", path="/ws/asr_worker", transport_id=transport_id)
    await browser_asr_service.worker_connected()
    if not await browser_asr_service.send_hello(websocket):
        api_trace("ws", "endpoint_hello_failed", path="/ws/asr_worker", transport_id=transport_id)
        # send_hello already routed cleanup through ``disconnect`` on failure;
        # bail out so the endpoint does not race a partially-disconnected state.
        return
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            message_type = str(message.get("type", "")).strip().lower()
            if message_type == "external_asr_update":
                await browser_asr_service.handle_external_update(transport_id, message)
                continue
            if message_type == "browser_asr_status":
                await browser_asr_service.handle_status(transport_id, message)
                continue
            if message_type == "browser_asr_heartbeat":
                await browser_asr_service.handle_status(transport_id, message)
    except WebSocketDisconnect:
        api_trace("ws", "endpoint_disconnect", path="/ws/asr_worker", transport_id=transport_id)
    finally:
        await browser_asr_service.disconnect(transport_id)
        api_trace("ws", "endpoint_closed", path="/ws/asr_worker", transport_id=transport_id)


@app.websocket("/ws/remote/signaling")
async def ws_remote_signaling(websocket: WebSocket) -> None:
    session_id = str(websocket.query_params.get("session_id", "") or "").strip()
    pair_code = str(websocket.query_params.get("pair_code", "") or "").strip()
    role = str(websocket.query_params.get("role", "") or "").strip().lower()
    if role not in {"controller", "worker"}:
        await websocket.close(code=1008)
        return
    accepted, reason = websocket.app.state.remote_session_manager.verify_pairing(
        session_id=session_id,
        pair_code=pair_code,
    )
    if not accepted:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": reason or "Pairing rejected."})
        await websocket.close(code=1008)
        return

    signaling_manager: RemoteSignalingManager = websocket.app.state.remote_signaling_manager
    await signaling_manager.connect(session_id=session_id, role=role, websocket=websocket)
    websocket.app.state.remote_session_manager.heartbeat(session_id=session_id, role=role)
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
                accepted_heartbeat, reason_heartbeat, pairing = websocket.app.state.remote_session_manager.heartbeat(
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
            websocket.app.state.remote_session_manager.heartbeat(session_id=session_id, role=role)
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
    asr_service = websocket.app.state.asr_service
    session_id = str(websocket.query_params.get("session_id", "") or "").strip()
    pair_code = str(websocket.query_params.get("pair_code", "") or "").strip()
    accepted, reason = websocket.app.state.remote_session_manager.verify_pairing(
        session_id=session_id,
        pair_code=pair_code,
    )
    if not accepted:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": reason or "Pairing rejected."})
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await asr_service.remote_audio_ingest_connected(session_id=session_id)
    websocket.app.state.remote_session_manager.heartbeat(session_id=session_id, role="controller")
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
            await asr_service.ingest_remote_audio_chunk(payload_bytes)
            websocket.app.state.remote_session_manager.heartbeat(session_id=session_id, role="controller")
    except WebSocketDisconnect:
        pass
    finally:
        await asr_service.remote_audio_ingest_disconnected()


@app.websocket("/ws/remote/result_ingest")
async def ws_remote_result_ingest(websocket: WebSocket) -> None:
    asr_service = websocket.app.state.asr_service
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
                await asr_service.ingest_remote_transcript_event(payload)
                continue
            if event_type == "translation_update":
                await asr_service.ingest_remote_translation_event(payload)
                continue
            if event_type == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass


@app.on_event("shutdown")
async def shutdown_runtime() -> None:
    runtime_orchestrator = getattr(app.state, "runtime_orchestrator", None)
    session_logger = getattr(app.state, "session_logger", None)
    cache_manager = getattr(app.state, "cache_manager", None)
    if runtime_orchestrator is None:
        if session_logger is not None:
            session_logger.flush()
        if cache_manager is not None:
            try:
                cache_manager.flush_now()
            except Exception:
                pass
        return
    try:
        await runtime_orchestrator.stop()
    except Exception:
        # Shutdown should stay best-effort so the local server can still exit.
        pass
    finally:
        translation_engine = getattr(runtime_orchestrator, "_translation_engine", None)
        if translation_engine is not None:
            try:
                await translation_engine.aclose()
            except Exception:
                pass
        if cache_manager is not None:
            try:
                cache_manager.flush_now()
            except Exception:
                pass
        if session_logger is not None:
            session_logger.flush()
