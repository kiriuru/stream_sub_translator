from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from backend.translation.base import (
    BaseTranslationProvider,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    PROVIDER_GROUP_EXPERIMENTAL,
    TranslationProviderError,
    TranslationProviderInfo,
)


def _build_google_translate_url(text: str, source_lang: str, target_lang: str) -> str:
    return (
        "https://translate.googleapis.com/translate_a/single"
        f"?client=gtx&sl={quote_plus(source_lang)}&tl={quote_plus(target_lang)}&dt=t&q={quote_plus(text)}"
    )


def _extract_google_translation_text(payload: Any) -> str:
    translated_parts: list[str] = []
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, list):
            for item in first:
                if isinstance(item, list) and item:
                    translated_parts.append(str(item[0]))
    return "".join(translated_parts).strip()


class GoogleWebProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="google_web",
        group=PROVIDER_GROUP_EXPERIMENTAL,
        experimental=True,
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
        normalized_source = self._normalize_source_lang(source_lang)
        url = _build_google_translate_url(text, normalized_source, target_lang)
        payload = await self._request_json(
            url=url,
            method="GET",
            timeout=timeout,
            error_prefix="Google Web request failed",
        )
        translated = _extract_google_translation_text(payload)
        if not translated:
            raise TranslationProviderError("Google Web returned an empty translation.")
        diagnostics = self.diagnostics(provider_settings)
        diagnostics["status_message"] = "Experimental Google Web provider. Best-effort only."
        return translated, diagnostics


class FreeWebTranslateProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="free_web_translate",
        group=PROVIDER_GROUP_EXPERIMENTAL,
        experimental=True,
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
        normalized_source = self._normalize_source_lang(source_lang)
        url = _build_google_translate_url(text, normalized_source, target_lang)
        payload = await self._request_json(
            url=url,
            method="GET",
            timeout=timeout,
            error_prefix="Free Web Translate request failed",
        )
        translated = _extract_google_translation_text(payload)
        if not translated:
            raise TranslationProviderError("Free Web Translate returned an empty translation.")
        diagnostics = self.diagnostics(provider_settings)
        diagnostics["status_message"] = "Experimental free web provider. Best-effort only."
        return translated, diagnostics

__all__ = ["FreeWebTranslateProvider", "GoogleWebProvider"]
