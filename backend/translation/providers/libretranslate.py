from __future__ import annotations

from typing import Any

from backend.translation.base import (
    BaseTranslationProvider,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    PROVIDER_GROUP_STABLE,
    TranslationProviderError,
    TranslationProviderInfo,
)


class LibreTranslateProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="libretranslate",
        group=PROVIDER_GROUP_STABLE,
    )

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
        timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ) -> tuple[str, dict[str, Any]]:
        api_url = provider_settings.get("api_url", "").strip() or "https://libretranslate.com/translate"
        payload: dict[str, str] = {
            "q": text,
            "source": self._normalize_source_lang(source_lang),
            "target": target_lang,
            "format": "text",
        }
        api_key = provider_settings.get("api_key", "").strip()
        if api_key:
            payload["api_key"] = api_key

        data = await self._request_json(
            url=api_url,
            method="POST",
            json=payload,
            timeout=timeout,
            error_prefix="LibreTranslate request failed",
        )

        translated = data.get("translatedText") or data.get("translation")
        if not translated:
            raise TranslationProviderError("LibreTranslate returned an empty translation.")
        return str(translated), self.diagnostics(provider_settings)


__all__ = ["LibreTranslateProvider"]
