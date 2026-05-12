from __future__ import annotations

from typing import Any

from backend.translation.base import (
    BaseTranslationProvider,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    PROVIDER_GROUP_STABLE,
    TranslationProviderError,
    TranslationProviderInfo,
)


class AzureTranslatorProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="azure_translator",
        group=PROVIDER_GROUP_STABLE,
        stable=True,
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
        api_key = provider_settings.get("api_key", "").strip()
        endpoint = provider_settings.get("endpoint", "").strip() or "https://api.cognitive.microsofttranslator.com"
        region = provider_settings.get("region", "").strip()
        if not api_key:
            raise TranslationProviderError("Azure Translator API key is missing.")
        if not endpoint:
            raise TranslationProviderError("Azure Translator endpoint is missing.")

        params: dict[str, str] = {
            "api-version": "3.0",
            "to": target_lang,
        }
        normalized_source = self._normalize_source_lang(source_lang)
        if normalized_source != "auto":
            params["from"] = normalized_source

        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/json",
        }
        if region:
            headers["Ocp-Apim-Subscription-Region"] = region

        payload = await self._request_json(
            url=f"{endpoint.rstrip('/')}/translate",
            method="POST",
            params=params,
            json=[{"Text": text}],
            headers=headers,
            timeout=timeout,
            error_prefix="Azure Translator request failed",
        )

        translations = payload[0].get("translations", []) if isinstance(payload, list) and payload else []
        translated = translations[0].get("text") if translations else None
        if not translated:
            raise TranslationProviderError("Azure Translator returned an empty translation.")
        return str(translated), self.diagnostics(provider_settings)

__all__ = ["AzureTranslatorProvider"]
