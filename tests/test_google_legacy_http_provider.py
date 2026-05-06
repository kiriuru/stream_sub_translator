from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from typing import Any

from backend.core.google_legacy_http_parser import GoogleLegacyHttpParsedResult
from backend.core.google_legacy_http_provider import GoogleLegacyHttpAsrProvider
from backend.core.google_legacy_http_transport import GoogleLegacyHttpTransport


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRANSPORT_SOURCE = PROJECT_ROOT / "backend" / "core" / "google_legacy_http_transport.py"
PROVIDER_SOURCE = PROJECT_ROOT / "backend" / "core" / "google_legacy_http_provider.py"
REQUIREMENTS_FILES = [
    PROJECT_ROOT / "requirements.txt",
    PROJECT_ROOT / "requirements.controller.txt",
]


class _FakeTransport(GoogleLegacyHttpTransport):
    def __init__(
        self,
        *,
        fail_downstream_connect: Exception | None = None,
        fail_on_receive: Exception | None = None,
    ) -> None:
        self.upstream_connected = False
        self.downstream_connected = False
        self.fail_downstream_connect = fail_downstream_connect
        self.fail_on_receive = fail_on_receive
        self.sent_chunks: list[bytes] = []
        self.closed = False
        self.connect_upstream_calls = 0
        self.connect_downstream_calls = 0
        self.last_upstream_kwargs: dict[str, Any] | None = None
        self.last_downstream_kwargs: dict[str, Any] | None = None
        self._message_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def connect_upstream(self, **kwargs: Any) -> None:
        self.connect_upstream_calls += 1
        self.last_upstream_kwargs = dict(kwargs)
        self.upstream_connected = True

    async def connect_downstream(self, **kwargs: Any) -> None:
        self.connect_downstream_calls += 1
        self.last_downstream_kwargs = dict(kwargs)
        if self.fail_downstream_connect is not None:
            raise self.fail_downstream_connect
        self.downstream_connected = True

    async def send_audio_chunk(self, chunk: bytes) -> None:
        self.sent_chunks.append(bytes(chunk))

    async def receive_messages(self):
        if self.fail_on_receive is not None:
            raise self.fail_on_receive
        while True:
            message = await self._message_queue.get()
            if message is None:
                break
            yield message

    async def close(self) -> None:
        self.closed = True
        self.upstream_connected = False
        self.downstream_connected = False
        await self._message_queue.put(None)

    async def push_message(self, message: str) -> None:
        await self._message_queue.put(message)


class _TransportFactory:
    def __init__(self, transports: list[_FakeTransport]) -> None:
        self._transports = list(transports)
        self.created: list[_FakeTransport] = []

    def __call__(self) -> _FakeTransport:
        transport = self._transports.pop(0)
        self.created.append(transport)
        return transport


class GoogleLegacyHttpProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.config = {
            "asr": {
                "mode": "local",
                "provider_preference": "google_legacy_http_experimental",
                "google_legacy_http": {
                    "enabled": True,
                    "language": "ru-RU",
                    "profanity_filter": False,
                    "connect_timeout_ms": 1000,
                    "send_timeout_ms": 1000,
                    "recv_timeout_ms": 1000,
                    "max_queue_depth": 2,
                    "reconnect_initial_ms": 100,
                    "reconnect_max_ms": 200,
                    "endpoint_host": "https://example.test",
                    "pair_id_prefix": "sst",
                },
            }
        }
        self.results: list[GoogleLegacyHttpParsedResult] = []

    async def _build_provider(self, transports: list[_FakeTransport]) -> GoogleLegacyHttpAsrProvider:
        factory = _TransportFactory(transports)

        async def _record_result(result: GoogleLegacyHttpParsedResult) -> None:
            self.results.append(result)

        provider = GoogleLegacyHttpAsrProvider(
            config_getter=lambda: self.config,
            result_callback=_record_result,
            transport_factory=factory,
        )
        provider._transport_test_factory = factory  # type: ignore[attr-defined]
        return provider

    async def test_start_creates_generation_and_duplicate_start_does_not_open_second_stream(self) -> None:
        transport = _FakeTransport()
        provider = await self._build_provider([transport])

        first = await provider.start()
        second = await provider.start()

        self.assertEqual(first["stream_generation"], 1)
        self.assertEqual(second["stream_generation"], 1)
        self.assertEqual(provider.stream_generation, 1)
        self.assertEqual(len(provider._transport_test_factory.created), 1)  # type: ignore[attr-defined]

        await provider.stop()

    async def test_provider_config_does_not_require_api_key_and_uses_pair_prefix(self) -> None:
        transport = _FakeTransport()
        provider = await self._build_provider([transport])

        await provider.start()
        await asyncio.sleep(0)

        self.assertIsNotNone(transport.last_upstream_kwargs)
        self.assertIsNotNone(transport.last_downstream_kwargs)
        self.assertNotIn("api_key", transport.last_upstream_kwargs)
        self.assertNotIn("api_key", transport.last_downstream_kwargs)
        self.assertTrue(str(transport.last_upstream_kwargs["pair_id"]).startswith("sst-"))
        self.assertTrue(str(transport.last_downstream_kwargs["pair_id"]).startswith("sst-"))

        await provider.stop()

    async def test_stop_cancels_tasks_and_unblocks_audio_queue(self) -> None:
        transport = _FakeTransport()
        provider = await self._build_provider([transport])
        await provider.start()
        provider.enqueue_audio(b"abc")

        stopped = await provider.stop()

        self.assertEqual(stopped["provider_state"], "idle")
        self.assertFalse(provider.desired_running)
        self.assertIsNone(provider.upstream_task)
        self.assertIsNone(provider.downstream_task)
        self.assertTrue(transport.closed)

    async def test_stop_increments_generation_and_stale_results_are_ignored(self) -> None:
        transport = _FakeTransport()
        provider = await self._build_provider([transport])
        await provider.start()
        old_generation = provider.stream_generation
        await provider.stop()

        await provider._handle_parsed_result(  # noqa: SLF001
            old_generation,
            GoogleLegacyHttpParsedResult(text="stale", is_partial=True, is_final=False),
        )

        self.assertEqual(provider.stream_generation, old_generation + 1)
        self.assertEqual(provider.stale_results_ignored, 1)
        self.assertEqual(self.results, [])

    async def test_queue_overflow_drops_oldest_chunks(self) -> None:
        provider = await self._build_provider([_FakeTransport()])
        await provider.start()

        provider.enqueue_audio(b"one")
        provider.enqueue_audio(b"two")
        provider.enqueue_audio(b"three")

        self.assertEqual(provider.audio_chunks_dropped, 1)
        self.assertEqual(provider.audio_queue.qsize(), 2)
        await provider.stop()

    async def test_partial_and_final_messages_emit_results_and_suppress_duplicates(self) -> None:
        transport = _FakeTransport()
        provider = await self._build_provider([transport])
        await provider.start()
        await asyncio.sleep(0)

        await transport.push_message('{"result":[{"alternative":[{"transcript":"privet"}],"final":false}]}')
        await transport.push_message('{"result":[{"alternative":[{"transcript":"privet"}],"final":false}]}')
        await transport.push_message('{"result":[{"alternative":[{"transcript":"privet"}],"final":true}]}')
        await transport.push_message('{"result":[{"alternative":[{"transcript":"privet"}],"final":true}]}')
        await transport.push_message("not-json")
        await asyncio.sleep(0.05)

        self.assertEqual([result.text for result in self.results], ["privet", "privet"])
        self.assertTrue(self.results[0].is_partial)
        self.assertTrue(self.results[1].is_final)
        self.assertEqual(provider.duplicate_partials_suppressed, 1)
        self.assertEqual(provider.duplicate_finals_suppressed, 1)
        self.assertEqual(provider.partials_received, 1)
        self.assertEqual(provider.finals_received, 1)

        await provider.stop()

    async def test_final_matching_previous_partial_is_still_emitted(self) -> None:
        transport = _FakeTransport()
        provider = await self._build_provider([transport])
        await provider.start()
        await asyncio.sleep(0)

        await transport.push_message('{"result":[{"alternative":[{"transcript":"same"}],"final":false}]}')
        await transport.push_message('{"result":[{"alternative":[{"transcript":"same"}],"final":true}]}')
        await asyncio.sleep(0.05)

        self.assertEqual([(item.text, item.is_partial, item.is_final) for item in self.results], [
            ("same", True, False),
            ("same", False, True),
        ])
        await provider.stop()

    async def test_network_error_triggers_reconnect_and_caps_backoff(self) -> None:
        first = _FakeTransport(fail_downstream_connect=RuntimeError("connect failed"))
        second = _FakeTransport(fail_downstream_connect=RuntimeError("connect failed again"))
        third = _FakeTransport()
        provider = await self._build_provider([first, second, third])
        await provider.start()
        await asyncio.sleep(0.35)

        self.assertGreaterEqual(provider.reconnect_count, 1)
        self.assertLessEqual(provider._next_reconnect_delay_ms, 200)  # noqa: SLF001

        await provider.stop()

    async def test_repeated_stop_start_does_not_get_stuck(self) -> None:
        provider = await self._build_provider([_FakeTransport(), _FakeTransport(), _FakeTransport()])

        for _ in range(3):
            await provider.start()
            self.assertIn(provider.state, {"connecting", "streaming"})
            await provider.stop()
            self.assertEqual(provider.state, "idle")

    def test_transport_source_does_not_use_google_cloud_api_or_api_key_path(self) -> None:
        source = TRANSPORT_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("speech.googleapis.com/v1", source)
        self.assertNotIn("speech.googleapis.com/v2", source)
        self.assertNotIn("google-cloud-speech", source)
        self.assertNotIn("google.cloud.speech", source)
        self.assertNotIn('"key"', source)
        self.assertIn("/speech-api/full-duplex/v1/up", source)
        self.assertIn("/speech-api/full-duplex/v1/down", source)

    def test_repo_requirements_do_not_add_google_cloud_speech_dependency(self) -> None:
        for requirements_path in REQUIREMENTS_FILES:
            if not requirements_path.exists():
                continue
            content = requirements_path.read_text(encoding="utf-8")
            self.assertNotIn("google-cloud-speech", content)

    def test_provider_source_mentions_legacy_http_not_google_cloud(self) -> None:
        source = PROVIDER_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("Google Cloud", source)
        self.assertNotIn("Cloud Speech", source)


if __name__ == "__main__":
    unittest.main()
