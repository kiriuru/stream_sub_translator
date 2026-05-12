from __future__ import annotations

from typing import Any

from backend.translation.base import (
    BaseTranslationProvider,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    PROVIDER_GROUP_EXPERIMENTAL,
    TranslationProviderError,
    TranslationProviderInfo,
)


class PublicLibreTranslateMirrorProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="public_libretranslate_mirror",
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
        api_url = provider_settings.get("api_url", "").strip() or "https://translate.fedilab.app/translate"
        payload = {
            "q": text,
            "source": self._normalize_source_lang(source_lang),
            "target": target_lang,
            "format": "text",
        }
        data = await self._request_json(
            url=api_url,
            method="POST",
            json=payload,
            timeout=timeout,
            error_prefix="Public LibreTranslate mirror request failed",
        )
        translated = data.get("translatedText") or data.get("translation")
        if not translated:
            raise TranslationProviderError("Public LibreTranslate mirror returned an empty translation.")
        diagnostics = self.diagnostics(provider_settings)
        diagnostics["status_message"] = "Experimental public LibreTranslate mirror. Availability may change."
        return str(translated), diagnostics


__all__ = ["PublicLibreTranslateMirrorProvider"]
