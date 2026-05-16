from __future__ import annotations

import asyncio
import unittest

from backend.ws_manager import WebSocketManager


class _FakeWebSocket:
    def __init__(self, *, fail_with: type[BaseException] | None = None) -> None:
        self.fail_with = fail_with
        self.accepted = 0
        self.messages: list[dict] = []

    async def accept(self) -> None:
        self.accepted += 1

    async def send_json(self, message: dict) -> None:
        if self.fail_with is not None:
            raise self.fail_with("boom")
        self.messages.append(dict(message))


class WebSocketManagerTests(unittest.TestCase):
    def test_broadcast_removes_dead_socket_and_keeps_live_socket(self) -> None:
        async def scenario() -> None:
            manager = WebSocketManager()
            live = _FakeWebSocket()
            dead = _FakeWebSocket(fail_with=OSError)
            await manager.connect(live)
            await manager.connect(dead)

            await manager.broadcast({"type": "runtime_update", "payload": {"status": "listening"}})
            await asyncio.sleep(0.05)

            self.assertEqual(len(live.messages), 1)
            self.assertEqual(manager.diagnostics()["ws_events_send_failures"], 1)
            self.assertEqual(manager.diagnostics()["ws_events_connections_active"], 1)

        asyncio.run(scenario())

    def test_duplicate_disconnect_is_idempotent(self) -> None:
        async def scenario() -> None:
            manager = WebSocketManager()
            socket = _FakeWebSocket()
            await manager.connect(socket)
            await manager.disconnect(socket)
            await manager.disconnect(socket)
            self.assertEqual(manager.diagnostics()["ws_events_connections_active"], 0)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
