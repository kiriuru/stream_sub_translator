from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable

import httpx


PROVIDER_GROUP_STABLE = "stable"
PROVIDER_GROUP_LLM = "llm"
PROVIDER_GROUP_LOCAL_LLM = "local_llm"
PROVIDER_GROUP_EXPERIMENTAL = "experimental"

DEFAULT_REQUEST_TIMEOUT_SECONDS = 20.0

SUPPORTED_TRANSLATION_PROVIDERS = (
    "google_translate_v2",
    "google_cloud_translation_v3",
    "google_gas_url",
    "google_web",
    "azure_translator",
    "deepl",
    "libretranslate",
    "openai",
    "openrouter",
    "lm_studio",
    "ollama",
    "public_libretranslate_mirror",
    "free_web_translate",
)


class TranslationProviderError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class TranslationProviderInfo:
    name: str
    group: str
    stable: bool = False
    experimental: bool = False
    local_provider: bool = False


class BaseTranslationProvider:
    info = TranslationProviderInfo(name="base", group=PROVIDER_GROUP_STABLE)

    def __init__(self) -> None:
        self._http_client_provider: Callable[[], httpx.AsyncClient] | None = None

    def bind_http_client_provider(
        self, provider: Callable[[], httpx.AsyncClient] | None
    ) -> None:
        """Allow the translation engine to share a connection-pooled client.

        When bound, request helpers reuse the engine-owned client which keeps
        TLS/keep-alive connections warm between requests. When unbound, the
        helpers fall back to a one-off client so providers stay usable in
        standalone tests and tooling.
        """
        self._http_client_provider = provider

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError

    def diagnostics(self, provider_settings: dict[str, str]) -> dict[str, Any]:
        return {
            "provider": self.info.name,
            "provider_group": self.info.group,
            "experimental": self.info.experimental,
            "local_provider": self.info.local_provider,
            "used_default_prompt": False,
            "status_message": None,
        }

    def _mask_secret(self, value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    def _normalize_source_lang(self, source_lang: str) -> str:
        normalized = str(source_lang or "auto").strip().lower()
        return normalized or "auto"

    def _http_error(self, prefix: str, exc: Exception) -> TranslationProviderError:
        if isinstance(exc, httpx.TimeoutException):
            return TranslationProviderError(f"{prefix}: request timed out.", retryable=True)
        if isinstance(exc, httpx.NetworkError):
            return TranslationProviderError(f"{prefix}: network error: {exc}", retryable=True)
        if isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            detail = exc.response.text.strip()
            retryable = status_code >= 500 or status_code == 429
            message = f"{prefix}: HTTP {status_code}"
            if detail:
                message = f"{message} - {detail[:280]}"
            return TranslationProviderError(message, retryable=retryable)
        if isinstance(exc, TranslationProviderError):
            return exc
        return TranslationProviderError(f"{prefix}: {exc}", retryable=False)

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        error_prefix: str,
    ) -> Any:
        try:
            response = await client.request(
                method,
                url,
                params=params,
                json=json,
                data=data,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise self._http_error(error_prefix, exc) from exc

    @asynccontextmanager
    async def _http_client_context(self) -> AsyncIterator[httpx.AsyncClient]:
        provider_callable = self._http_client_provider
        if provider_callable is not None:
            client = provider_callable()
            yield client
            return
        async with httpx.AsyncClient() as client:
            yield client

    async def _request_json(
        self,
        *,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        error_prefix: str,
    ) -> Any:
        async with self._http_client_context() as client:
            return await self._get_json(
                client,
                url=url,
                method=method,
                params=params,
                json=json,
                data=data,
                headers=headers,
                timeout=timeout,
                error_prefix=error_prefix,
            )
