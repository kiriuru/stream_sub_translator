from __future__ import annotations

from typing import Any

import httpx

from backend.translation.base import (
    BaseTranslationProvider,
    PROVIDER_GROUP_STABLE,
    TranslationProviderError,
    TranslationProviderInfo,
)


class DeepLProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="deepl",
        group=PROVIDER_GROUP_STABLE,
    )

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        api_key = provider_settings.get("api_key", "").strip()
        if not api_key:
            raise TranslationProviderError("DeepL API key is missing.")

        api_url = provider_settings.get("api_url", "").strip() or "https://api-free.deepl.com/v2/translate"
        data: dict[str, str] = {
            "auth_key": api_key,
            "text": text,
            "target_lang": target_lang.upper(),
        }
        normalized_source = self._normalize_source_lang(source_lang)
        if normalized_source != "auto":
            data["source_lang"] = normalized_source.upper()

        async with httpx.AsyncClient() as client:
            payload = await self._get_json(
                client,
                url=api_url,
                method="POST",
                data=data,
                error_prefix="DeepL request failed",
            )

        translations = payload.get("translations", [])
        if not translations:
            raise TranslationProviderError("DeepL returned an empty translation.")
        return str(translations[0].get("text", "")), self.diagnostics(provider_settings)

__all__ = ["DeepLProvider"]
