from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import httpx


DEFAULT_GOOGLE_LEGACY_HTTP_ENDPOINT = "https://www.google.com"
LEGACY_UPSTREAM_PATH = "/speech-api/full-duplex/v1/up"
LEGACY_DOWNSTREAM_PATH = "/speech-api/full-duplex/v1/down"


class GoogleLegacyHttpTransport:
    upstream_connected: bool = False
    downstream_connected: bool = False

    async def connect_upstream(
        self,
        *,
        endpoint_host: str,
        language: str,
        profanity_filter: bool,
        pair_id: str,
        connect_timeout_ms: int,
        send_timeout_ms: int,
        recv_timeout_ms: int,
    ) -> None:
        raise NotImplementedError

    async def connect_downstream(
        self,
        *,
        endpoint_host: str,
        pair_id: str,
        connect_timeout_ms: int,
        recv_timeout_ms: int,
    ) -> None:
        raise NotImplementedError

    async def send_audio_chunk(self, chunk: bytes) -> None:
        raise NotImplementedError

    async def receive_messages(self) -> AsyncIterator[str]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class HttpxGoogleLegacyHttpTransport(GoogleLegacyHttpTransport):
    def __init__(self) -> None:
        self.upstream_connected = False
        self.downstream_connected = False
        self._upstream_client: httpx.AsyncClient | None = None
        self._downstream_client: httpx.AsyncClient | None = None
        self._upstream_task: asyncio.Task[None] | None = None
        self._upstream_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._downstream_stream: httpx.Response | None = None
        self._closed = False
        self._upstream_error: Exception | None = None
        self._json_decoder = json.JSONDecoder()

    @staticmethod
    def _resolved_host(endpoint_host: str) -> str:
        normalized = str(endpoint_host or "").strip().rstrip("/")
        if not normalized:
            return DEFAULT_GOOGLE_LEGACY_HTTP_ENDPOINT
        if "://" not in normalized:
            normalized = f"https://{normalized}"
        return normalized

    @staticmethod
    def build_pair_id(prefix: str = "sst") -> str:
        normalized_prefix = str(prefix or "sst").strip() or "sst"
        return f"{normalized_prefix}-{uuid.uuid4().hex[:16]}"

    def _build_upstream_url(self, *, endpoint_host: str, language: str, profanity_filter: bool, pair_id: str) -> str:
        params = {
            "pair": pair_id,
            "lang": language,
            "pFilter": "1" if profanity_filter else "0",
            "client": "chromium",
            "continuous": "1",
            "interim": "1",
        }
        return httpx.URL(
            f"{self._resolved_host(endpoint_host)}{LEGACY_UPSTREAM_PATH}",
            params=params,
        ).unicode_string()

    def _build_downstream_url(self, *, endpoint_host: str, pair_id: str) -> str:
        return httpx.URL(
            f"{self._resolved_host(endpoint_host)}{LEGACY_DOWNSTREAM_PATH}",
            params={"pair": pair_id},
        ).unicode_string()

    async def connect_upstream(
        self,
        *,
        endpoint_host: str,
        language: str,
        profanity_filter: bool,
        pair_id: str,
        connect_timeout_ms: int,
        send_timeout_ms: int,
        recv_timeout_ms: int,
    ) -> None:
        timeout = httpx.Timeout(
            connect=max(1.0, connect_timeout_ms / 1000.0),
            read=max(1.0, recv_timeout_ms / 1000.0),
            write=max(1.0, send_timeout_ms / 1000.0),
            pool=max(1.0, connect_timeout_ms / 1000.0),
        )
        self._upstream_client = httpx.AsyncClient(timeout=timeout, http2=False)
        self._upstream_error = None
        url = self._build_upstream_url(
            endpoint_host=endpoint_host,
            language=language,
            profanity_filter=profanity_filter,
            pair_id=pair_id,
        )
        self._upstream_task = asyncio.create_task(self._run_upstream_request(url))
        self.upstream_connected = True

    async def connect_downstream(
        self,
        *,
        endpoint_host: str,
        pair_id: str,
        connect_timeout_ms: int,
        recv_timeout_ms: int,
    ) -> None:
        timeout = httpx.Timeout(
            connect=max(1.0, connect_timeout_ms / 1000.0),
            read=max(1.0, recv_timeout_ms / 1000.0),
            write=max(1.0, connect_timeout_ms / 1000.0),
            pool=max(1.0, connect_timeout_ms / 1000.0),
        )
        self._downstream_client = httpx.AsyncClient(timeout=timeout, http2=False)
        request = self._downstream_client.build_request(
            "GET",
            self._build_downstream_url(endpoint_host=endpoint_host, pair_id=pair_id),
            headers={
                "Accept": "*/*",
                "User-Agent": "SSTGoogleLegacyHttpExperimental/1.0",
            },
        )
        response = await self._downstream_client.send(request, stream=True)
        response.raise_for_status()
        self._downstream_stream = response
        self.downstream_connected = True

    async def send_audio_chunk(self, chunk: bytes) -> None:
        if self._closed:
            raise RuntimeError("transport_closed")
        if self._upstream_task is not None and self._upstream_task.done():
            try:
                self._upstream_task.result()
            except Exception as exc:
                self._upstream_error = exc
        if self._upstream_error is not None:
            raise self._upstream_error
        await self._upstream_queue.put(bytes(chunk))

    async def receive_messages(self) -> AsyncIterator[str]:
        response = self._downstream_stream
        if response is None:
            return
        buffer = ""
        async for chunk in response.aiter_bytes():
            if self._closed:
                break
            if not chunk:
                continue
            buffer += chunk.decode("utf-8", errors="replace")
            messages, buffer = self._extract_messages(buffer)
            for message in messages:
                yield message

    async def close(self) -> None:
        self._closed = True
        self.upstream_connected = False
        self.downstream_connected = False
        try:
            self._upstream_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
        if self._downstream_stream is not None:
            await self._downstream_stream.aclose()
            self._downstream_stream = None
        if self._upstream_task is not None:
            self._upstream_task.cancel()
            try:
                await self._upstream_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            self._upstream_task = None
        if self._upstream_client is not None:
            await self._upstream_client.aclose()
            self._upstream_client = None
        if self._downstream_client is not None:
            await self._downstream_client.aclose()
            self._downstream_client = None

    def _extract_messages(self, buffer: str) -> tuple[list[str], str]:
        messages: list[str] = []
        remainder = buffer
        while remainder:
            working = remainder.lstrip()
            leading_trim = len(remainder) - len(working)
            if leading_trim:
                remainder = working
            if remainder.startswith(")]}'"):
                remainder = remainder[4:].lstrip()
                continue
            try:
                _parsed, end = self._json_decoder.raw_decode(remainder)
            except json.JSONDecodeError:
                break
            messages.append(remainder[:end])
            remainder = remainder[end:]
        return messages, remainder

    async def _run_upstream_request(self, url: str) -> None:
        assert self._upstream_client is not None

        async def _body() -> AsyncIterator[bytes]:
            try:
                while True:
                    chunk = await self._upstream_queue.get()
                    if chunk is None:
                        break
                    if chunk:
                        yield bytes(chunk)
            finally:
                self.upstream_connected = False

        response: httpx.Response | None = None
        try:
            request = self._upstream_client.build_request(
                "POST",
                url,
                headers={
                    "Content-Type": "audio/l16; rate=16000",
                    "Accept": "*/*",
                    "User-Agent": "SSTGoogleLegacyHttpExperimental/1.0",
                    "Transfer-Encoding": "chunked",
                },
                content=_body(),
            )
            response = await self._upstream_client.send(request, stream=True)
            response.raise_for_status()
            await response.aread()
        except Exception as exc:
            self._upstream_error = exc
            raise
        finally:
            self.upstream_connected = False
            if response is not None:
                await response.aclose()
