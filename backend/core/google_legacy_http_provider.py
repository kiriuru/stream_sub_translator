from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from backend.core.google_legacy_http_parser import GoogleLegacyHttpParsedResult, parse_google_legacy_http_message
from backend.core.google_legacy_http_transport import GoogleLegacyHttpTransport, HttpxGoogleLegacyHttpTransport


GOOGLE_LEGACY_HTTP_PROVIDER_NAME = "google_legacy_http_experimental"
GOOGLE_LEGACY_HTTP_PROVIDER_LABEL = "Google Legacy HTTP Speech Experimental"
GOOGLE_LEGACY_HTTP_PROVIDER_WARNING = (
    "Experimental legacy Google speech endpoint. Sends audio to Google. "
    "Unofficial/unsupported and may stop working."
)


class GoogleLegacyHttpAsrProvider:
    _ACTIVE_STATES = {"connecting", "streaming", "reconnecting"}

    def __init__(
        self,
        *,
        config_getter: Callable[[], dict[str, Any]],
        result_callback: Callable[[GoogleLegacyHttpParsedResult], Awaitable[None]],
        transport_factory: Callable[[], GoogleLegacyHttpTransport] | None = None,
    ) -> None:
        self._config_getter = config_getter
        self._result_callback = result_callback
        self._transport_factory = transport_factory or HttpxGoogleLegacyHttpTransport
        self._state_lock = asyncio.Lock()
        self.state = "idle"
        self.stream_generation = 0
        self.desired_running = False
        self.upstream_task: asyncio.Task[None] | None = None
        self.downstream_task: asyncio.Task[None] | None = None
        self.reconnect_task: asyncio.Task[None] | None = None
        self.audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=50)
        self.stop_event = asyncio.Event()
        self.last_partial_text = ""
        self.last_final_text = ""
        self.last_error: str | None = None
        self.last_error_kind: str | None = None
        self.reconnect_count = 0
        self.audio_chunks_sent = 0
        self.audio_chunks_dropped = 0
        self.partials_received = 0
        self.finals_received = 0
        self.stale_results_ignored = 0
        self.duplicate_partials_suppressed = 0
        self.duplicate_finals_suppressed = 0
        self._connect_timeout_ms = 10000
        self._send_timeout_ms = 10000
        self._recv_timeout_ms = 30000
        self._max_queue_depth = 50
        self._reconnect_initial_ms = 1000
        self._reconnect_max_ms = 30000
        self._next_reconnect_delay_ms = self._reconnect_initial_ms
        self._pair_id_prefix = "sst"
        self._last_partial_at_monotonic: float | None = None
        self._last_final_at_monotonic: float | None = None
        self._transport: GoogleLegacyHttpTransport | None = None
        self._pair_id: str | None = None
        self._upstream_connected = False
        self._downstream_connected = False

    def _provider_config(self) -> dict[str, Any]:
        config = self._config_getter()
        asr = config.get("asr", {}) if isinstance(config, dict) else {}
        provider = asr.get("google_legacy_http", {}) if isinstance(asr, dict) else {}
        return provider if isinstance(provider, dict) else {}

    def _apply_config(self) -> dict[str, Any]:
        provider = self._provider_config()
        self._connect_timeout_ms = max(1000, int(provider.get("connect_timeout_ms", 10000) or 10000))
        self._send_timeout_ms = max(1000, int(provider.get("send_timeout_ms", 10000) or 10000))
        self._recv_timeout_ms = max(1000, int(provider.get("recv_timeout_ms", 30000) or 30000))
        self._max_queue_depth = max(1, int(provider.get("max_queue_depth", 50) or 50))
        self._reconnect_initial_ms = max(100, int(provider.get("reconnect_initial_ms", 1000) or 1000))
        self._reconnect_max_ms = max(self._reconnect_initial_ms, int(provider.get("reconnect_max_ms", 30000) or 30000))
        self._pair_id_prefix = str(provider.get("pair_id_prefix", "sst") or "sst").strip() or "sst"
        if self.audio_queue.maxsize != self._max_queue_depth:
            self.audio_queue = asyncio.Queue(maxsize=self._max_queue_depth)
        return provider

    async def start(self) -> dict[str, Any]:
        async with self._state_lock:
            if self.state in self._ACTIVE_STATES:
                return self.diagnostics()
            config = self._apply_config()
            if not bool(config.get("enabled", False)):
                self.state = "idle"
                self.last_error = "Provider is disabled in asr.google_legacy_http.enabled."
                self.last_error_kind = "disabled"
                return self.diagnostics()
            self.stream_generation += 1
            self.desired_running = True
            self.stop_event = asyncio.Event()
            self._reset_session_suppression_state()
            self._clear_audio_queue()
            self.last_error = None
            self.last_error_kind = None
            self._next_reconnect_delay_ms = self._reconnect_initial_ms
            self.state = "connecting"
            await self._cancel_stream_tasks_locked()
            self._start_stream_tasks_locked(self.stream_generation)
            return self.diagnostics()

    async def stop(self) -> dict[str, Any]:
        async with self._state_lock:
            self.desired_running = False
            self.stream_generation += 1
            self.state = "stopping"
            self.stop_event.set()
            self._unblock_audio_queue()
            await self._cancel_stream_tasks_locked()
            await self._close_transport_locked()
            self._clear_audio_queue()
            self._reset_session_suppression_state()
            self.state = "idle"
            return self.diagnostics()

    def enqueue_audio(self, chunk: bytes) -> None:
        if not self.desired_running:
            return
        payload = bytes(chunk or b"")
        if not payload:
            return
        while self.audio_queue.full():
            try:
                discarded = self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if discarded is not None:
                self.audio_chunks_dropped += 1
        try:
            self.audio_queue.put_nowait(payload)
        except asyncio.QueueFull:
            self.audio_chunks_dropped += 1

    def diagnostics(self) -> dict[str, Any]:
        now = time.perf_counter()
        return {
            "provider": GOOGLE_LEGACY_HTTP_PROVIDER_NAME,
            "provider_label": GOOGLE_LEGACY_HTTP_PROVIDER_LABEL,
            "provider_state": self.state,
            "stream_generation": self.stream_generation,
            "desired_running": self.desired_running,
            "upstream_connected": self._upstream_connected,
            "downstream_connected": self._downstream_connected,
            "reconnect_count": self.reconnect_count,
            "audio_queue_depth": self.audio_queue.qsize(),
            "audio_chunks_sent": self.audio_chunks_sent,
            "audio_chunks_dropped": self.audio_chunks_dropped,
            "stale_results_ignored": self.stale_results_ignored,
            "partials_received": self.partials_received,
            "finals_received": self.finals_received,
            "duplicate_partials_suppressed": self.duplicate_partials_suppressed,
            "duplicate_finals_suppressed": self.duplicate_finals_suppressed,
            "last_error": self.last_error,
            "last_error_kind": self.last_error_kind,
            "last_partial_age_ms": (
                max(0, int((now - self._last_partial_at_monotonic) * 1000))
                if self._last_partial_at_monotonic is not None
                else None
            ),
            "last_final_age_ms": (
                max(0, int((now - self._last_final_at_monotonic) * 1000))
                if self._last_final_at_monotonic is not None
                else None
            ),
            "connect_timeout_ms": self._connect_timeout_ms,
            "send_timeout_ms": self._send_timeout_ms,
            "recv_timeout_ms": self._recv_timeout_ms,
            "max_queue_depth": self._max_queue_depth,
            "endpoint_mode": "legacy_http",
            "uses_google_cloud_api": False,
            "requires_api_key": False,
            "warning_text": GOOGLE_LEGACY_HTTP_PROVIDER_WARNING,
        }

    async def _cancel_stream_tasks_locked(self) -> None:
        tasks = [task for task in (self.upstream_task, self.downstream_task, self.reconnect_task) if task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self.upstream_task = None
        self.downstream_task = None
        self.reconnect_task = None
        self._upstream_connected = False
        self._downstream_connected = False

    async def _close_transport_locked(self) -> None:
        transport = self._transport
        self._transport = None
        self._pair_id = None
        if transport is not None:
            await transport.close()
        self._upstream_connected = False
        self._downstream_connected = False

    def _start_stream_tasks_locked(self, generation: int) -> None:
        self._transport = self._transport_factory()
        self._pair_id = self._build_pair_id(self._transport, self._pair_id_prefix)
        self.upstream_task = asyncio.create_task(self._run_upstream(generation))
        self.downstream_task = asyncio.create_task(self._run_downstream(generation))

    async def _run_upstream(self, generation: int) -> None:
        transport = self._transport
        if transport is None:
            return
        config = self._apply_config()
        pair_id = self._pair_id or self._build_pair_id(transport, self._pair_id_prefix)
        try:
            await transport.connect_upstream(
                endpoint_host=str(config.get("endpoint_host", "") or ""),
                language=str(config.get("language", "ru-RU") or "ru-RU"),
                profanity_filter=bool(config.get("profanity_filter", False)),
                pair_id=pair_id,
                connect_timeout_ms=self._connect_timeout_ms,
                send_timeout_ms=self._send_timeout_ms,
                recv_timeout_ms=self._recv_timeout_ms,
            )
            if not self._is_current_generation(generation):
                self._note_stale_result()
                return
            self._upstream_connected = True
            self._refresh_streaming_state()
            while self.desired_running and self._is_current_generation(generation):
                chunk = await self.audio_queue.get()
                if chunk is None or self.stop_event.is_set():
                    break
                await transport.send_audio_chunk(chunk)
                self.audio_chunks_sent += 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._handle_stream_error(generation, "upstream_error", exc)
        finally:
            self._upstream_connected = False
            self._refresh_streaming_state()

    async def _run_downstream(self, generation: int) -> None:
        transport = self._transport
        if transport is None:
            return
        config = self._apply_config()
        pair_id = self._pair_id or self._build_pair_id(transport, self._pair_id_prefix)
        try:
            await transport.connect_downstream(
                endpoint_host=str(config.get("endpoint_host", "") or ""),
                pair_id=pair_id,
                connect_timeout_ms=self._connect_timeout_ms,
                recv_timeout_ms=self._recv_timeout_ms,
            )
            if not self._is_current_generation(generation):
                self._note_stale_result()
                return
            self._downstream_connected = True
            self._refresh_streaming_state()
            async for message in transport.receive_messages():
                if not self._is_current_generation(generation):
                    self._note_stale_result()
                    return
                parsed_results = parse_google_legacy_http_message(message)
                for parsed in parsed_results:
                    await self._handle_parsed_result(generation, parsed)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._handle_stream_error(generation, "downstream_error", exc)
        finally:
            self._downstream_connected = False
            self._refresh_streaming_state()

    async def _handle_parsed_result(self, generation: int, parsed: GoogleLegacyHttpParsedResult) -> None:
        if not self._is_current_generation(generation):
            self._note_stale_result()
            return
        if parsed.is_partial:
            if parsed.text == self.last_partial_text:
                self.duplicate_partials_suppressed += 1
                return
            self.last_partial_text = parsed.text
            self.partials_received += 1
            self._last_partial_at_monotonic = time.perf_counter()
        if parsed.is_final:
            if parsed.text == self.last_final_text:
                self.duplicate_finals_suppressed += 1
                return
            self.last_final_text = parsed.text
            self.last_partial_text = ""
            self.finals_received += 1
            self._last_final_at_monotonic = time.perf_counter()
        await self._result_callback(parsed)

    async def _handle_stream_error(self, generation: int, error_kind: str, exc: Exception) -> None:
        if not self._is_current_generation(generation):
            self._note_stale_result()
            return
        self.last_error = str(exc)
        self.last_error_kind = error_kind
        if not self.desired_running:
            self.state = "error"
            return
        async with self._state_lock:
            if not self._is_current_generation(generation) or not self.desired_running:
                return
            if self.reconnect_task is not None and not self.reconnect_task.done():
                return
            self.state = "reconnecting"
            self.reconnect_count += 1
            await self._cancel_peer_stream_tasks(asyncio.current_task())
            await self._close_transport_locked()
            self.reconnect_task = asyncio.create_task(self._run_reconnect_delay(generation))

    async def _run_reconnect_delay(self, generation: int) -> None:
        delay_ms = self._next_reconnect_delay_ms
        self._next_reconnect_delay_ms = min(self._reconnect_max_ms, max(delay_ms * 2, self._reconnect_initial_ms))
        try:
            await asyncio.sleep(delay_ms / 1000.0)
            async with self._state_lock:
                if not self.desired_running or not self._is_current_generation(generation):
                    return
                self.state = "connecting"
                self._start_stream_tasks_locked(generation)
        except asyncio.CancelledError:
            raise
        finally:
            if asyncio.current_task() is self.reconnect_task:
                self.reconnect_task = None

    def _refresh_streaming_state(self) -> None:
        if self._upstream_connected and self._downstream_connected:
            self.state = "streaming"
            self._next_reconnect_delay_ms = self._reconnect_initial_ms
            self.last_error = None
            self.last_error_kind = None
        elif self.desired_running and self.state not in {"reconnecting", "stopping"}:
            self.state = "connecting"

    def _build_pair_id(self, transport: GoogleLegacyHttpTransport, prefix: str | None = None) -> str:
        builder = getattr(transport, "build_pair_id", None)
        if callable(builder):
            try:
                return str(builder(prefix or self._pair_id_prefix))
            except Exception:
                pass
        normalized_prefix = str(prefix or self._pair_id_prefix or "sst").strip() or "sst"
        return f"{normalized_prefix}-{uuid.uuid4().hex[:16]}"

    def _clear_audio_queue(self) -> None:
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def _unblock_audio_queue(self) -> None:
        try:
            self.audio_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    def _reset_session_suppression_state(self) -> None:
        self.last_partial_text = ""
        self.last_final_text = ""
        self._last_partial_at_monotonic = None
        self._last_final_at_monotonic = None

    async def _cancel_peer_stream_tasks(self, current_task: asyncio.Task[Any] | None) -> None:
        peer_tasks = [
            task
            for task in (self.upstream_task, self.downstream_task)
            if task is not None and task is not current_task
        ]
        for task in peer_tasks:
            task.cancel()
        for task in peer_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        if self.upstream_task is not None and self.upstream_task is not current_task:
            self.upstream_task = None
        if self.downstream_task is not None and self.downstream_task is not current_task:
            self.downstream_task = None

    def _is_current_generation(self, generation: int) -> bool:
        return generation == self.stream_generation

    def _note_stale_result(self) -> None:
        self.stale_results_ignored += 1
