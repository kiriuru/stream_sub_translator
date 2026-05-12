from __future__ import annotations

from typing import Any

from backend.translation.base import (
    BaseTranslationProvider,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    PROVIDER_GROUP_EXPERIMENTAL,
    TranslationProviderError,
    TranslationProviderInfo,
)


class GoogleGasUrlProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="google_gas_url",
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
        gas_url = provider_settings.get("gas_url", "").strip()
        if not gas_url:
            raise TranslationProviderError("Google GAS URL is missing.")

        payload = {
            "text": text,
            "source_lang": self._normalize_source_lang(source_lang),
            "target_lang": target_lang,
        }

        data = await self._request_json(
            url=gas_url,
            method="POST",
            json=payload,
            timeout=timeout,
            error_prefix="Google GAS URL request failed",
        )

        translated = (
            data.get("translatedText")
            or data.get("text")
            or data.get("translation")
            or data.get("output")
        )
        if not translated:
            raise TranslationProviderError(
                "Google GAS URL returned no translated text. Expected one of: translatedText, text, translation, output."
            )
        diagnostics = self.diagnostics(provider_settings)
        diagnostics["status_message"] = "Experimental Google GAS URL provider. Reliability depends on your script."
        return str(translated), diagnostics


__all__ = ["GoogleGasUrlProvider"]
