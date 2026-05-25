from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from backend.core.api_trace_log import api_trace
from backend.core.pipeline_trace_log import pipeline_trace

logger = logging.getLogger(__name__)

# Bounded per-connection outbound queue (broadcast/backpressure). See docs/plans browser ASR roadmap §7.
_DEFAULT_OUT_QUEUE_MAX = 128


class WebSocketManager:
    def __init__(self, *, outbound_queue_max: int = _DEFAULT_OUT_QUEUE_MAX) -> None:
        self._connections: set[WebSocket] = set()
        self._last_message_by_type: dict[str, dict[str, Any]] = {}
        self._accepted_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._outbound_queue_max = max(1, int(outbound_queue_max))
        self._out_queues: dict[WebSocket, asyncio.Queue] = {}
        self._sender_tasks: dict[WebSocket, asyncio.Task[None]] = {}
        # Per-connection send mutex: Starlette WebSocket frames cannot be safely interleaved
        # across coroutines. Bootstrap direct sends (hello, replay_last) and the sender task
        # must serialize through this lock so the underlying transport never sees concurrent writes.
        self._send_locks: dict[WebSocket, asyncio.Lock] = {}
        self._diagnostics: dict[str, Any] = {
            "ws_events_connections_active": 0,
            "ws_events_broadcast_count": 0,
            "ws_events_send_failures": 0,
            "ws_events_dead_connections_removed": 0,
            "ws_events_last_error_kind": None,
            "ws_events_dropped_oldest": 0,
            "ws_events_queue_max_depth_observed": 0,
        }

    async def connect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._accepted_connections:
                self._connections.add(websocket)
                self._diagnostics["ws_events_connections_active"] = len(self._connections)
                return
        await websocket.accept()
        q: asyncio.Queue = asyncio.Queue(maxsize=self._outbound_queue_max)
        send_lock = asyncio.Lock()
        async with self._lock:
            self._accepted_connections.add(websocket)
            self._connections.add(websocket)
            self._out_queues[websocket] = q
            self._send_locks[websocket] = send_lock
            sender = asyncio.create_task(self._connection_sender(websocket, q), name="sst-ws-sender")
            self._sender_tasks[websocket] = sender
            self._diagnostics["ws_events_connections_active"] = len(self._connections)
            pipeline_trace(
                "asyncio_event_loop",
                "ws_manager",
                "connection_open",
                connections_active=len(self._connections),
                outbound_queue_max=self._outbound_queue_max,
                sender_task_id=id(sender),
            )
            api_trace(
                "ws",
                "manager_connection_open",
                connections_active=len(self._connections),
                outbound_queue_max=self._outbound_queue_max,
            )

    async def _send_json_locked(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        """Send one JSON message to a single socket, serialized via the per-connection mutex.

        Falls back to a raw ``send_json`` if the socket has no registered lock yet
        (e.g. a transient send during teardown). Callers are responsible for handling
        transport exceptions; this helper does not swallow them.
        """
        lock = self._send_locks.get(websocket)
        if lock is None:
            await websocket.send_json(message)
            return
        async with lock:
            await websocket.send_json(message)

    async def _connection_sender(self, websocket: WebSocket, queue: asyncio.Queue) -> None:
        while True:
            message = await queue.get()
            if message is None:
                return
            try:
                await self._send_json_locked(websocket, message)
            except (WebSocketDisconnect, RuntimeError, OSError, ConnectionResetError, BrokenPipeError) as exc:
                self._diagnostics["ws_events_send_failures"] = int(self._diagnostics["ws_events_send_failures"]) + 1
                self._diagnostics["ws_events_last_error_kind"] = type(exc).__name__
                await self.disconnect(websocket)
                return

    async def disconnect(self, websocket: WebSocket) -> None:
        task = self._sender_tasks.pop(websocket, None)
        q = self._out_queues.pop(websocket, None)
        self._send_locks.pop(websocket, None)
        if q is not None:
            try:
                q.put_nowait(None)
            except Exception:
                pass
        if task is not None and not task.done():
            task.cancel()
        async with self._lock:
            removed = websocket in self._connections
            self._connections.discard(websocket)
            self._accepted_connections.discard(websocket)
            if removed:
                self._diagnostics["ws_events_dead_connections_removed"] = int(
                    self._diagnostics["ws_events_dead_connections_removed"]
                ) + 1
            self._diagnostics["ws_events_connections_active"] = len(self._connections)
        pipeline_trace(
            "asyncio_event_loop",
            "ws_manager",
            "connection_closed",
            connections_active=len(self._connections),
        )
        api_trace(
            "ws",
            "manager_connection_closed",
            connections_active=len(self._connections),
            dead_removed=bool(removed),
        )

    def _enqueue_to_connection(self, connection: WebSocket, message: dict[str, Any]) -> None:
        """Enqueue outbound JSON; drop-oldest on pressure.

        If ``disconnect`` has already removed this socket from ``_out_queues``,
        this is a no-op — no orphan queue growth after logical disconnect.
        """
        q = self._out_queues.get(connection)
        if q is None:
            return
        try:
            q.put_nowait(message)
            depth = q.qsize()
            if depth >= max(1, self._outbound_queue_max - 4):
                pipeline_trace(
                    "asyncio_event_loop",
                    "ws_manager",
                    "outbound_queue_pressure",
                    queue_depth=depth,
                    queue_max=self._outbound_queue_max,
                    message_type=str(message.get("type") or message.get("event") or ""),
                )
        except asyncio.QueueFull:
            try:
                _ = q.get_nowait()
                self._diagnostics["ws_events_dropped_oldest"] = int(self._diagnostics["ws_events_dropped_oldest"]) + 1
                pipeline_trace(
                    "asyncio_event_loop",
                    "ws_manager",
                    "outbound_queue_drop_oldest",
                    message_type=str(message.get("type") or message.get("event") or ""),
                )
            except asyncio.QueueEmpty:
                pass
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                self._diagnostics["ws_events_send_failures"] = int(self._diagnostics["ws_events_send_failures"]) + 1
                return
        depth = q.qsize()
        prev = int(self._diagnostics.get("ws_events_queue_max_depth_observed") or 0)
        if depth > prev:
            self._diagnostics["ws_events_queue_max_depth_observed"] = depth

    async def broadcast(self, message: dict[str, Any]) -> None:
        message_type = str(message.get("type", "") or "").strip()
        if message_type:
            self._last_message_by_type[message_type] = message
        async with self._lock:
            connections = list(self._connections)
        self._diagnostics["ws_events_broadcast_count"] = int(self._diagnostics["ws_events_broadcast_count"]) + 1
        if message_type and message_type != "runtime_update":
            api_trace(
                "ws",
                "manager_broadcast",
                message_type=message_type,
                connection_count=len(connections),
            )
        stale: list[WebSocket] = []
        for connection in connections:
            if connection in self._out_queues:
                self._enqueue_to_connection(connection, message)
                continue
            try:
                await self._send_json_locked(connection, message)
            except (WebSocketDisconnect, RuntimeError, OSError, ConnectionResetError, BrokenPipeError) as exc:
                self._diagnostics["ws_events_send_failures"] = int(self._diagnostics["ws_events_send_failures"]) + 1
                self._diagnostics["ws_events_last_error_kind"] = type(exc).__name__
                stale.append(connection)
        if stale:
            async with self._lock:
                for connection in stale:
                    self._connections.discard(connection)
                    self._accepted_connections.discard(connection)
                self._diagnostics["ws_events_dead_connections_removed"] = int(
                    self._diagnostics["ws_events_dead_connections_removed"]
                ) + len(stale)
                self._diagnostics["ws_events_connections_active"] = len(self._connections)
            api_trace(
                "ws",
                "manager_broadcast_stale_removed",
                message_type=message_type or None,
                stale_count=len(stale),
            )

    async def replay_last(self, websocket: WebSocket, *, message_types: list[str]) -> None:
        """
        Send last cached message per type to the socket so the client receives snapshot state
        before streamed broadcast traffic.

        **Semantics:** best-effort bootstrap. Each send is serialized via the per-connection
        send mutex, so it cannot interleave frames with the live sender task. Ordering against
        concurrent ``broadcast`` work is still best-effort (the broadcast may be queued and
        delivered before, between, or after these replay messages depending on scheduling).
        """
        for message_type in message_types:
            cached = self._last_message_by_type.get(str(message_type or "").strip())
            if cached:
                try:
                    await self._send_json_locked(websocket, cached)
                except (WebSocketDisconnect, RuntimeError, OSError, ConnectionResetError, BrokenPipeError) as exc:
                    self._diagnostics["ws_events_send_failures"] = int(self._diagnostics["ws_events_send_failures"]) + 1
                    self._diagnostics["ws_events_last_error_kind"] = type(exc).__name__
                    await self.disconnect(websocket)
                    return

    async def send_direct(self, websocket: WebSocket, message: dict[str, Any]) -> bool:
        """
        Send a single JSON message to one socket, serialized via the per-connection mutex.

        Used for endpoint-level bootstrap messages (e.g. the initial "hello") that should not
        be cached as ``last_message_by_type`` and must not interleave with the sender task.
        Returns False (and disconnects) if the socket is no longer writable.
        """
        try:
            await self._send_json_locked(websocket, message)
            return True
        except (WebSocketDisconnect, RuntimeError, OSError, ConnectionResetError, BrokenPipeError) as exc:
            self._diagnostics["ws_events_send_failures"] = int(self._diagnostics["ws_events_send_failures"]) + 1
            self._diagnostics["ws_events_last_error_kind"] = type(exc).__name__
            await self.disconnect(websocket)
            return False

    def diagnostics(self) -> dict[str, Any]:
        snapshot = dict(self._diagnostics)
        snapshot["ws_events_connections_active"] = len(self._connections)
        snapshot["captured_at_ms"] = int(time.time() * 1000)
        return snapshot


__all__ = ["WebSocketManager"]
