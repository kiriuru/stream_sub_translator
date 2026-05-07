from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


PROVIDER_GROUP_STABLE = "stable"
PROVIDER_GROUP_LLM = "llm"
PROVIDER_GROUP_LOCAL_LLM = "local_llm"
PROVIDER_GROUP_EXPERIMENTAL = "experimental"


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
        timeout: float = 20.0,
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
