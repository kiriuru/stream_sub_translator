from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

import httpx

from backend.translation.base import (
    BaseTranslationProvider,
    PROVIDER_GROUP_EXPERIMENTAL,
    TranslationProviderInfo,
)


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
    ) -> tuple[str, dict[str, Any]]:
        normalized_source = self._normalize_source_lang(source_lang)
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl={quote_plus(normalized_source)}&tl={quote_plus(target_lang)}&dt=t&q={quote_plus(text)}"
        )
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=20.0)
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                raise self._http_error("Google Web request failed", exc) from exc

        translated_parts: list[str] = []
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, list):
                for item in first:
                    if isinstance(item, list) and item:
                        translated_parts.append(str(item[0]))
        translated = "".join(translated_parts).strip()
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
    ) -> tuple[str, dict[str, Any]]:
        normalized_source = self._normalize_source_lang(source_lang)
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl={quote_plus(normalized_source)}&tl={quote_plus(target_lang)}&dt=t&q={quote_plus(text)}"
        )
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=20.0)
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                raise self._http_error("Free Web Translate request failed", exc) from exc

        translated_parts: list[str] = []
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, list):
                for item in first:
                    if isinstance(item, list) and item:
                        translated_parts.append(str(item[0]))
        translated = "".join(translated_parts).strip()
        if not translated:
            raise TranslationProviderError("Free Web Translate returned an empty translation.")
        diagnostics = self.diagnostics(provider_settings)
        diagnostics["status_message"] = "Experimental free web provider. Best-effort only."
        return translated, diagnostics

__all__ = ["FreeWebTranslateProvider", "GoogleWebProvider"]
