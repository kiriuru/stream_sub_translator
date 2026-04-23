from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import time
import uuid
from typing import Any, Callable, Literal

import websockets

from backend.models import ObsCaptionDiagnostics, SubtitlePayloadEvent, TranscriptEvent

OBS_CC_OUTPUT_MODES = (
    "disabled",
    "source_live",
    "source_final_only",
    "translation_1",
    "translation_2",
    "translation_3",
    "translation_4",
    "translation_5",
    "first_visible_line",
)

_TRANSLATION_OUTPUT_MODES = {
    "translation_1",
    "translation_2",
    "translation_3",
    "translation_4",
    "translation_5",
}

_CONNECTABLE_OUTPUT_MODES = {
    "source_live",
    "source_final_only",
    "translation_1",
    "translation_2",
    "translation_3",
    "translation_4",
    "translation_5",
    "first_visible_line",
}

_SOURCE_EVENT_OUTPUT_MODES = {
    "source_live",
    "source_final_only",
}


class _ObsCaptionAuthError(RuntimeError):
    pass


class _ObsCaptionRequestError(RuntimeError):
    def __init__(self, code: int | None, comment: str) -> None:
        self.code = code
        self.comment = comment
        message = comment or (f"OBS request failed with code {code}." if code is not None else "OBS request failed.")
        super().__init__(message)


@dataclass(slots=True)
class _QueuedObsCaptionEvent:
    kind: Literal["source_partial", "source_final", "payload", "clear"]
    text: str = ""
    payload: SubtitlePayloadEvent | None = None


class ObsCaptionOutput:
    def __init__(self, config_getter: Callable[[], dict[str, Any]]) -> None:
        self.config_getter = config_getter
        self._queue: asyncio.Queue[_QueuedObsCaptionEvent] | None = None
        self._worker_task: asyncio.Task | None = None
        self._connection_task: asyncio.Task | None = None
        self._delayed_send_task: asyncio.Task | None = None
        self._clear_task: asyncio.Task | None = None
        self._request_lock: asyncio.Lock | None = None
        self._state_lock: asyncio.Lock | None = None
        self._connected_event: asyncio.Event | None = None
        self._websocket: Any | None = None
        self._connected = False
        self._desired_connection = False
        self._connection_state: Literal["disabled", "disconnected", "connecting", "connected", "auth_failed", "error"] = "disabled"
        self._connection_key: tuple[str, int, str] | None = None
        self._obs_studio_version: str | None = None
        self._obs_websocket_version: str | None = None
        self._last_error: str | None = None
        self._last_caption_text: str | None = None
        self._last_caption_sent_at_utc: str | None = None
        self._last_debug_text: str | None = None
        self._last_debug_input_name: str | None = None
        self._last_partial_text: str = ""
        self._last_partial_sent_monotonic: float = 0.0
        self._reconnect_attempt_count: int = 0
        self._last_send_used_active_connection: bool = False
        self._last_send_waited_for_connection: bool = False
        self._stream_output_active: bool | None = None
        self._stream_output_reconnecting: bool | None = None
        self._native_caption_status: str | None = None

    def _settings(self) -> dict[str, Any]:
        config = self.config_getter()
        current = config.get("obs_closed_captions", {}) if isinstance(config, dict) else {}
        if not isinstance(current, dict):
            current = {}
        connection = current.get("connection", {})
        if not isinstance(connection, dict):
            connection = {}
        debug_mirror = current.get("debug_mirror", {})
        if not isinstance(debug_mirror, dict):
            debug_mirror = {}
        timing = current.get("timing", {})
        if not isinstance(timing, dict):
            timing = {}

        mode = str(current.get("output_mode", "disabled") or "disabled").strip().lower()
        if mode not in OBS_CC_OUTPUT_MODES:
            mode = "disabled"

        try:
            port = int(connection.get("port", 4455) or 4455)
        except (TypeError, ValueError):
            port = 4455

        return {
            "enabled": bool(current.get("enabled", False)),
            "output_mode": mode,
            "connection": {
                "host": str(connection.get("host", "127.0.0.1") or "127.0.0.1").strip() or "127.0.0.1",
                "port": max(1, min(65535, port)),
                "password": str(connection.get("password", "") or ""),
            },
            "debug_mirror": {
                "enabled": bool(debug_mirror.get("enabled", False)),
                "input_name": str(debug_mirror.get("input_name", "CC_DEBUG") or "").strip(),
                "send_partials": bool(debug_mirror.get("send_partials", True)),
            },
            "timing": {
                "send_partials": bool(timing.get("send_partials", True)),
                "partial_throttle_ms": max(0, int(timing.get("partial_throttle_ms", 250) or 0)),
                "min_partial_delta_chars": max(0, int(timing.get("min_partial_delta_chars", 3) or 0)),
                "final_replace_delay_ms": max(0, int(timing.get("final_replace_delay_ms", 0) or 0)),
                "clear_after_ms": max(0, int(timing.get("clear_after_ms", 2500) or 0)),
                "avoid_duplicate_text": bool(timing.get("avoid_duplicate_text", True)),
            },
        }

    def diagnostics(self) -> ObsCaptionDiagnostics:
        settings = self._settings()
        connection_state = self._connection_state
        if connection_state == "disabled" and self._should_connect(settings):
            connection_state = "disconnected"
        native_enabled = bool(settings["enabled"]) and str(settings["output_mode"]) in _CONNECTABLE_OUTPUT_MODES
        native_caption_ready = bool(native_enabled and self._connected and self._stream_output_active)
        native_caption_status = self._native_caption_status
        if native_enabled and not native_caption_status:
            if not self._connected:
                native_caption_status = "OBS websocket is not connected."
            elif self._stream_output_active is True:
                native_caption_status = "OBS stream output is active. Native captions can be delivered."
            elif self._stream_output_active is False:
                native_caption_status = "OBS stream output is not active. Native SendStreamCaption will not reach viewers."
            else:
                native_caption_status = "OBS websocket is connected, but stream caption readiness has not been confirmed yet."
        return ObsCaptionDiagnostics(
            enabled=bool(settings["enabled"]),
            output_mode=str(settings["output_mode"]),
            host=str(settings["connection"]["host"]),
            port=int(settings["connection"]["port"]),
            password_configured=bool(settings["connection"]["password"]),
            connection_state=connection_state,
            send_partials=bool(settings["timing"]["send_partials"]),
            partial_throttle_ms=int(settings["timing"]["partial_throttle_ms"]),
            min_partial_delta_chars=int(settings["timing"]["min_partial_delta_chars"]),
            final_replace_delay_ms=int(settings["timing"]["final_replace_delay_ms"]),
            clear_after_ms=int(settings["timing"]["clear_after_ms"]),
            avoid_duplicate_text=bool(settings["timing"]["avoid_duplicate_text"]),
            connected=self._connected,
            active=native_caption_ready,
            stream_output_active=self._stream_output_active,
            stream_output_reconnecting=self._stream_output_reconnecting,
            native_caption_ready=native_caption_ready,
            native_caption_status=native_caption_status,
            reconnect_attempt_count=self._reconnect_attempt_count,
            last_send_used_active_connection=self._last_send_used_active_connection,
            last_send_waited_for_connection=self._last_send_waited_for_connection,
            last_error=self._last_error,
            last_caption_text=self._last_caption_text,
            last_caption_sent_at_utc=self._last_caption_sent_at_utc,
            debug_request_type="SetInputSettings" if self._debug_text_input_is_enabled(settings) else None,
            debug_text_input_enabled=self._debug_text_input_is_enabled(settings),
            debug_text_input_name=self._debug_input_name(settings),
            debug_text_input_send_partials=bool(settings["debug_mirror"]["send_partials"]),
            last_debug_text=self._last_debug_text,
            obs_websocket_version=self._obs_websocket_version,
            obs_studio_version=self._obs_studio_version,
        )

    async def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._queue = asyncio.Queue(maxsize=32)
            self._request_lock = asyncio.Lock()
            self._state_lock = asyncio.Lock()
            self._connected_event = asyncio.Event()
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        self._desired_connection = False
        await self._cancel_delayed_tasks()
        self._drain_queue()
        await self._clear_remote_outputs_if_possible(self._settings())
        await self._stop_connection_task()
        await self._close_connection()
        self._set_connection_state("disconnected")
        self._last_partial_text = ""
        self._last_partial_sent_monotonic = 0.0
        self._stream_output_active = None
        self._stream_output_reconnecting = None
        self._native_caption_status = None
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        self._queue = None
        self._request_lock = None
        self._state_lock = None
        self._connected_event = None

    async def apply_live_settings(self, config: dict[str, Any]) -> None:
        _ = config
        settings = self._settings()
        await self._cancel_delayed_tasks()

        if not self._should_connect(settings):
            self._desired_connection = False
            self._drain_queue()
            await self._clear_remote_outputs_if_possible(settings)
            await self._stop_connection_task()
            await self._close_connection()
            self._set_connection_state("disabled")
            return

        next_key = self._settings_connection_key(settings)
        if self._connection_key != next_key:
            self._connection_key = next_key
            await self._close_connection()

        self._desired_connection = True
        self._ensure_connection_task()

    async def publish_source_event(self, event: TranscriptEvent) -> None:
        if event.event == "partial":
            self._enqueue(_QueuedObsCaptionEvent(kind="source_partial", text=event.text))
            return
        self._enqueue(_QueuedObsCaptionEvent(kind="source_final", text=event.text))

    async def publish_subtitle_payload(self, payload: SubtitlePayloadEvent) -> None:
        self._enqueue(_QueuedObsCaptionEvent(kind="payload", payload=payload))

    def _enqueue(self, item: _QueuedObsCaptionEvent) -> None:
        if self._worker_task is None or self._worker_task.done():
            return
        queue = self._queue
        if queue is None:
            return
        if item.kind == "source_partial":
            self._drop_queued_partials()
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            try:
                _ = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                queue.put_nowait(item)
            except asyncio.QueueFull:
                pass

    def _drop_queued_partials(self) -> None:
        queue = self._queue
        if queue is None:
            return
        retained: list[_QueuedObsCaptionEvent] = []
        while True:
            try:
                current = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if current.kind != "source_partial":
                retained.append(current)
        for current in retained:
            try:
                queue.put_nowait(current)
            except asyncio.QueueFull:
                break

    def _drain_queue(self) -> None:
        queue = self._queue
        if queue is None:
            return
        while True:
            try:
                _ = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _worker_loop(self) -> None:
        while True:
            queue = self._queue
            if queue is None:
                await asyncio.sleep(0.05)
                continue
            item = await queue.get()
            try:
                if item.kind == "clear":
                    settings = self._settings()
                    await self._send_text(
                        "",
                        send_stream_caption=bool(settings["enabled"]) and str(settings["output_mode"]) in _CONNECTABLE_OUTPUT_MODES,
                        mirror_debug_text=self._debug_text_input_is_enabled(settings),
                        force=True,
                    )
                elif item.kind == "source_partial":
                    await self._handle_source_partial(item.text)
                elif item.kind == "source_final":
                    await self._handle_source_final(item.text)
                elif item.kind == "payload" and item.payload is not None:
                    await self._handle_payload(item.payload)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = str(exc)

    async def _handle_source_partial(self, text: str) -> None:
        settings = self._settings()
        output_mode = str(settings["output_mode"])
        send_stream_caption = bool(settings["enabled"]) and output_mode == "source_live"
        mirror_debug_text = (
            self._debug_text_input_is_enabled(settings)
            and output_mode == "source_live"
            and bool(settings["debug_mirror"]["send_partials"])
        )
        if not send_stream_caption and not mirror_debug_text:
            return
        if send_stream_caption and not settings["timing"]["send_partials"]:
            send_stream_caption = False
        if not send_stream_caption and not mirror_debug_text:
            return
        normalized = self._normalize_text(text)
        if not normalized:
            return

        previous = self._last_partial_text
        elapsed_ms = (time.perf_counter() - self._last_partial_sent_monotonic) * 1000.0 if self._last_partial_sent_monotonic else None
        growth_chars = len(normalized) - len(previous)
        if normalized == previous:
            return
        if (
            previous
            and elapsed_ms is not None
            and elapsed_ms < int(settings["timing"]["partial_throttle_ms"])
            and growth_chars >= 0
            and growth_chars < int(settings["timing"]["min_partial_delta_chars"])
        ):
            return

        self._last_partial_text = normalized
        self._last_partial_sent_monotonic = time.perf_counter()
        await self._send_text(
            normalized,
            send_stream_caption=send_stream_caption,
            mirror_debug_text=mirror_debug_text,
            force=not bool(settings["timing"]["avoid_duplicate_text"]),
        )

    async def _handle_source_final(self, text: str) -> None:
        settings = self._settings()
        output_mode = str(settings["output_mode"])
        send_stream_caption = bool(settings["enabled"]) and output_mode in _SOURCE_EVENT_OUTPUT_MODES
        mirror_debug_text = self._debug_text_input_is_enabled(settings) and output_mode in _SOURCE_EVENT_OUTPUT_MODES
        if not send_stream_caption and not mirror_debug_text:
            return
        normalized = self._normalize_text(text)
        if not normalized:
            return
        self._last_partial_text = ""
        self._last_partial_sent_monotonic = 0.0
        await self._schedule_final_send(
            normalized,
            send_stream_caption=send_stream_caption,
            mirror_debug_text=mirror_debug_text,
        )

    async def _handle_payload(self, payload: SubtitlePayloadEvent) -> None:
        settings = self._settings()
        mode = str(settings["output_mode"])
        send_stream_caption = bool(settings["enabled"]) and mode not in {"disabled", "source_live", "source_final_only"}
        mirror_debug_text = self._debug_text_input_is_enabled(settings)
        if not send_stream_caption and not mirror_debug_text:
            return
        if not payload.completed_block_visible:
            return

        selected_text = self._select_payload_text(payload, mode)
        if send_stream_caption and mode not in _TRANSLATION_OUTPUT_MODES and mode != "first_visible_line":
            selected_text = self._select_first_visible_text(payload)
        normalized = self._normalize_text(selected_text)
        if not normalized:
            return
        await self._schedule_final_send(
            normalized,
            send_stream_caption=send_stream_caption,
            mirror_debug_text=mirror_debug_text,
        )

    def _select_payload_text(self, payload: SubtitlePayloadEvent, mode: str) -> str:
        visible_items = [item for item in payload.visible_items if str(item.text).strip()]
        if mode == "first_visible_line":
            return visible_items[0].text if visible_items else ""
        if mode in _TRANSLATION_OUTPUT_MODES:
            index = int(mode.split("_", 1)[1]) - 1
            visible_translations = [item for item in visible_items if item.kind == "translation"]
            return visible_translations[index].text if index < len(visible_translations) else ""
        return ""

    def _select_first_visible_text(self, payload: SubtitlePayloadEvent) -> str:
        visible_items = [item for item in payload.visible_items if str(item.text).strip()]
        return visible_items[0].text if visible_items else ""

    async def _schedule_final_send(self, text: str, *, send_stream_caption: bool, mirror_debug_text: bool) -> None:
        await self._cancel_task(self._delayed_send_task)
        self._delayed_send_task = None
        delay_ms = int(self._settings()["timing"]["final_replace_delay_ms"])
        if delay_ms <= 0:
            await self._send_text(
                text,
                send_stream_caption=send_stream_caption,
                mirror_debug_text=mirror_debug_text,
            )
            return

        async def _delayed() -> None:
            await asyncio.sleep(delay_ms / 1000.0)
            await self._send_text(
                text,
                send_stream_caption=send_stream_caption,
                mirror_debug_text=mirror_debug_text,
            )

        self._delayed_send_task = asyncio.create_task(_delayed())

    async def _send_text(
        self,
        text: str,
        *,
        send_stream_caption: bool,
        mirror_debug_text: bool,
        force: bool = False,
    ) -> None:
        normalized = self._normalize_text(text)
        settings = self._settings()
        if not send_stream_caption and not mirror_debug_text:
            return
        if (
            send_stream_caption
            and not force
            and bool(settings["timing"]["avoid_duplicate_text"])
            and normalized == (self._last_caption_text or "")
        ):
            return

        had_active_connection = self._connected and self._websocket is not None
        waited_for_connection = False
        if not had_active_connection:
            waited_for_connection = True
            if not await self._wait_for_connection():
                self._last_send_used_active_connection = False
                self._last_send_waited_for_connection = True
                if self._last_error is None:
                    self._last_error = "OBS websocket is not connected."
                return

        self._last_send_used_active_connection = had_active_connection
        self._last_send_waited_for_connection = waited_for_connection

        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            debug_input_name = self._debug_input_name(settings)
            if mirror_debug_text:
                if debug_input_name:
                    await self._send_request(
                        "SetInputSettings",
                        {
                            "inputName": debug_input_name,
                            "inputSettings": {"text": normalized},
                            "overlay": True,
                        },
                    )
                    self._last_debug_text = normalized
                    self._last_debug_input_name = debug_input_name
            if send_stream_caption:
                try:
                    await self._send_request("SendStreamCaption", {"captionText": normalized})
                    self._last_caption_text = normalized
                    self._last_caption_sent_at_utc = timestamp
                    self._stream_output_active = True
                    self._stream_output_reconnecting = False
                    self._native_caption_status = "OBS accepted SendStreamCaption while the stream output was active."
                except _ObsCaptionRequestError as exc:
                    if exc.code == 501:
                        self._stream_output_active = False
                        self._stream_output_reconnecting = False
                        self._native_caption_status = (
                            "OBS stream output is not running. Native SendStreamCaption only works during an active stream."
                        )
                        self._last_error = (
                            "OBS stream output is not running. "
                            "SendStreamCaption only works while OBS is actively streaming."
                        )
                        if self._connected:
                            self._set_connection_state("connected")
                        if mirror_debug_text and debug_input_name:
                            self._schedule_clear(normalized, send_stream_caption=False, mirror_debug_text=True)
                        return
                    raise
            self._last_error = None
            self._schedule_clear(normalized, send_stream_caption=send_stream_caption, mirror_debug_text=mirror_debug_text)
        except _ObsCaptionRequestError as exc:
            self._last_error = f"OBS caption send failed: {exc}"
            self._set_connection_state("error")
            await self._close_connection()
            self._ensure_connection_task()
        except Exception as exc:
            self._last_error = f"OBS caption send failed: {exc}"
            self._set_connection_state("error")
            await self._close_connection()
            self._ensure_connection_task()

    def _schedule_clear(self, text: str, *, send_stream_caption: bool, mirror_debug_text: bool) -> None:
        if self._clear_task is not None:
            self._clear_task.cancel()
            self._clear_task = None
        clear_after_ms = int(self._settings()["timing"]["clear_after_ms"])
        if not text or clear_after_ms <= 0:
            return

        async def _delayed_clear() -> None:
            await asyncio.sleep(clear_after_ms / 1000.0)
            await self._send_text(
                "",
                send_stream_caption=send_stream_caption,
                mirror_debug_text=mirror_debug_text,
                force=True,
            )

        self._clear_task = asyncio.create_task(_delayed_clear())

    async def _cancel_delayed_tasks(self) -> None:
        await self._cancel_task(self._delayed_send_task)
        self._delayed_send_task = None
        await self._cancel_task(self._clear_task)
        self._clear_task = None

    async def _cancel_task(self, task: asyncio.Task | None) -> None:
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def _ensure_connection_task(self) -> None:
        if not self._desired_connection:
            return
        if self._connection_task is None or self._connection_task.done():
            self._connection_task = asyncio.create_task(self._connection_loop())

    async def _stop_connection_task(self) -> None:
        if self._connection_task is None:
            return
        self._connection_task.cancel()
        try:
            await self._connection_task
        except asyncio.CancelledError:
            pass
        self._connection_task = None

    async def _connection_loop(self) -> None:
        backoff_seconds = 1.0
        try:
            while self._desired_connection:
                settings = self._settings()
                if not self._should_connect(settings):
                    self._set_connection_state("disabled")
                    return

                if self._connected and self._websocket is not None:
                    try:
                        await asyncio.sleep(15.0)
                        if not self._desired_connection:
                            return
                        await self._perform_keepalive_ping()
                        await self._refresh_stream_status()
                        continue
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        self._last_error = f"OBS websocket connection lost: {exc}"
                        self._set_connection_state("error")
                        await self._close_connection()

                self._set_connection_state("connecting")
                try:
                    await self._open_connection(settings)
                    self._reconnect_attempt_count = 0
                    backoff_seconds = 1.0
                    self._set_connection_state("connected")
                    self._last_error = None
                    await self._refresh_stream_status()
                    continue
                except asyncio.CancelledError:
                    raise
                except _ObsCaptionAuthError as exc:
                    self._reconnect_attempt_count += 1
                    self._last_error = str(exc)
                    self._set_connection_state("auth_failed")
                    await self._close_connection()
                    await asyncio.sleep(5.0)
                except Exception as exc:
                    self._reconnect_attempt_count += 1
                    self._last_error = f"OBS captions unavailable: {exc}"
                    self._set_connection_state("error")
                    await self._close_connection()
                    await asyncio.sleep(backoff_seconds)
                    backoff_seconds = min(backoff_seconds * 2.0, 10.0)
        except asyncio.CancelledError:
            raise
        finally:
            if self._connected_event is not None:
                self._connected_event.clear()

    async def _wait_for_connection(self, timeout_seconds: float = 3.0) -> bool:
        if self._connected and self._websocket is not None:
            return True
        settings = self._settings()
        if not self._should_connect(settings):
            return False
        self._desired_connection = True
        self._ensure_connection_task()
        connected_event = self._connected_event
        if connected_event is None:
            return False
        try:
            await asyncio.wait_for(connected_event.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return False
        return self._connected and self._websocket is not None

    async def _open_connection(self, settings: dict[str, Any]) -> None:
        state_lock = self._state_lock
        if state_lock is None:
            raise RuntimeError("OBS state lock is not initialized.")
        async with state_lock:
            if self._connected and self._websocket is not None:
                return

            host = str(settings["connection"]["host"])
            port = int(settings["connection"]["port"])
            password = str(settings["connection"]["password"])
            websocket = await asyncio.wait_for(
                websockets.connect(
                    f"ws://{host}:{port}",
                    subprotocols=["obswebsocket.json"],
                    open_timeout=2.5,
                    ping_interval=20,
                    ping_timeout=20,
                ),
                timeout=3.0,
            )

            try:
                hello_message = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                hello = json.loads(hello_message)
                if int(hello.get("op", -1)) != 0:
                    raise RuntimeError("OBS websocket did not return a Hello message.")
                hello_data = hello.get("d", {}) if isinstance(hello.get("d"), dict) else {}
                identify_payload: dict[str, Any] = {
                    "rpcVersion": 1,
                    "eventSubscriptions": 0,
                }
                authentication = hello_data.get("authentication")
                if isinstance(authentication, dict):
                    if not password:
                        raise _ObsCaptionAuthError("OBS websocket requires a password, but none is configured.")
                    identify_payload["authentication"] = self._build_auth_response(
                        password=password,
                        salt=str(authentication.get("salt", "")),
                        challenge=str(authentication.get("challenge", "")),
                    )
                await asyncio.wait_for(websocket.send(json.dumps({"op": 1, "d": identify_payload})), timeout=3.0)
                identified_message = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                identified = json.loads(identified_message)
                op_code = int(identified.get("op", -1))
                if op_code == 5:
                    raise _ObsCaptionAuthError("OBS websocket authentication failed.")
                if op_code != 2:
                    raise RuntimeError("OBS websocket identify step did not complete.")

                self._websocket = websocket
                self._connected = True
                if self._connected_event is not None:
                    self._connected_event.set()
                self._obs_studio_version = str(hello_data.get("obsStudioVersion", "") or "") or None
                self._obs_websocket_version = str(hello_data.get("obsWebSocketVersion", "") or "") or None
                self._connection_key = self._settings_connection_key(settings)
            except Exception:
                try:
                    await websocket.close()
                except Exception:
                    pass
                raise

    async def _perform_keepalive_ping(self) -> None:
        websocket = self._websocket
        if websocket is None or not self._connected:
            raise RuntimeError("OBS websocket is not connected.")
        request_lock = self._request_lock
        if request_lock is None:
            raise RuntimeError("OBS request lock is not initialized.")
        async with request_lock:
            pong_waiter = await websocket.ping()
            await asyncio.wait_for(pong_waiter, timeout=5.0)

    async def _send_request_response(self, request_type: str, request_data: dict[str, Any]) -> dict[str, Any]:
        websocket = self._websocket
        if websocket is None or not self._connected:
            raise RuntimeError("OBS websocket is not connected.")

        request_lock = self._request_lock
        if request_lock is None:
            raise RuntimeError("OBS request lock is not initialized.")
        async with request_lock:
            request_id = str(uuid.uuid4())
            await asyncio.wait_for(
                websocket.send(
                    json.dumps(
                        {
                            "op": 6,
                            "d": {
                                "requestType": request_type,
                                "requestId": request_id,
                                "requestData": request_data,
                            },
                        }
                    )
                ),
                timeout=2.0,
            )
            while True:
                raw_message = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                message = json.loads(raw_message)
                if int(message.get("op", -1)) != 7:
                    continue
                data = message.get("d", {}) if isinstance(message.get("d"), dict) else {}
                if str(data.get("requestId", "")) != request_id:
                    continue
                status = data.get("requestStatus", {}) if isinstance(data.get("requestStatus"), dict) else {}
                if not bool(status.get("result")):
                    comment = str(status.get("comment", "") or "")
                    code = status.get("code")
                    raise _ObsCaptionRequestError(code, comment)
                response_data = data.get("responseData", {})
                return response_data if isinstance(response_data, dict) else {}

    async def _send_request(self, request_type: str, request_data: dict[str, Any]) -> None:
        await self._send_request_response(request_type, request_data)

    async def _refresh_stream_status(self) -> None:
        settings = self._settings()
        native_enabled = bool(settings["enabled"]) and str(settings["output_mode"]) in _CONNECTABLE_OUTPUT_MODES
        if not self._connected or self._websocket is None or not native_enabled:
            self._stream_output_active = None
            self._stream_output_reconnecting = None
            self._native_caption_status = None if not native_enabled else self._native_caption_status
            return
        try:
            response = await self._send_request_response("GetStreamStatus", {})
            output_active = bool(response.get("outputActive", False))
            output_reconnecting = bool(response.get("outputReconnecting", False))
            self._stream_output_active = output_active
            self._stream_output_reconnecting = output_reconnecting
            if output_active:
                self._native_caption_status = (
                    "OBS stream output is active but reconnecting. Native captions may be unstable."
                    if output_reconnecting
                    else "OBS stream output is active. Native SendStreamCaption captions can be delivered."
                )
            else:
                self._native_caption_status = (
                    "OBS stream output is not active. Native SendStreamCaption only works while OBS is actively streaming."
                )
        except Exception as exc:
            self._stream_output_active = None
            self._stream_output_reconnecting = None
            self._native_caption_status = f"Could not confirm OBS stream status: {exc}"

    async def _clear_remote_outputs_if_possible(self, settings: dict[str, Any] | None = None) -> None:
        if not self._connected or self._websocket is None:
            return
        current_settings = settings or self._settings()
        try:
            should_clear_native = (
                (bool(current_settings["enabled"]) and str(current_settings["output_mode"]) in _CONNECTABLE_OUTPUT_MODES)
                or self._last_caption_text is not None
            )
            if should_clear_native:
                await self._send_request("SendStreamCaption", {"captionText": ""})
                self._last_caption_text = ""
                self._last_caption_sent_at_utc = datetime.now(timezone.utc).isoformat()
            debug_input_name = self._debug_input_name(current_settings) or self._last_debug_input_name
            if (self._debug_text_input_is_enabled(current_settings) or self._last_debug_input_name) and debug_input_name:
                await self._send_request(
                    "SetInputSettings",
                    {
                        "inputName": debug_input_name,
                        "inputSettings": {"text": ""},
                        "overlay": True,
                    },
                )
                self._last_debug_text = ""
                self._last_debug_input_name = debug_input_name
        except Exception:
            pass

    async def _close_connection(self) -> None:
        websocket = self._websocket
        self._websocket = None
        self._connected = False
        if self._connected_event is not None:
            self._connected_event.clear()
        self._stream_output_active = None
        self._stream_output_reconnecting = None
        if websocket is not None:
            try:
                await websocket.close()
            except Exception:
                pass

    def _should_connect(self, settings: dict[str, Any]) -> bool:
        native_enabled = bool(settings["enabled"]) and str(settings["output_mode"]) in _CONNECTABLE_OUTPUT_MODES
        return native_enabled or self._debug_text_input_is_enabled(settings)

    def _debug_input_name(self, settings: dict[str, Any]) -> str | None:
        input_name = str(settings.get("debug_mirror", {}).get("input_name", "") or "").strip()
        return input_name or None

    def _debug_text_input_is_enabled(self, settings: dict[str, Any]) -> bool:
        return bool(settings.get("debug_mirror", {}).get("enabled")) and self._debug_input_name(settings) is not None

    def _settings_connection_key(self, settings: dict[str, Any]) -> tuple[str, int, str]:
        return (
            str(settings["connection"]["host"]),
            int(settings["connection"]["port"]),
            str(settings["connection"]["password"]),
        )

    def _set_connection_state(
        self,
        state: Literal["disabled", "disconnected", "connecting", "connected", "auth_failed", "error"],
    ) -> None:
        self._connection_state = state
        if self._connected_event is None:
            return
        if state == "connected":
            self._connected_event.set()
        else:
            self._connected_event.clear()

    def _normalize_text(self, text: str) -> str:
        lines = [" ".join(str(line).split()) for line in str(text or "").splitlines()]
        return "\n".join(line for line in lines if line).strip()

    def _build_auth_response(self, *, password: str, salt: str, challenge: str) -> str:
        secret = hashlib.sha256(f"{password}{salt}".encode("utf-8")).digest()
        secret_b64 = base64.b64encode(secret).decode("utf-8")
        challenge_digest = hashlib.sha256(f"{secret_b64}{challenge}".encode("utf-8")).digest()
        return base64.b64encode(challenge_digest).decode("utf-8")
