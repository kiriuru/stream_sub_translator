from __future__ import annotations

from html import unescape
import logging
from typing import Any
from urllib.parse import parse_qs, urlparse

from backend.translation.base import (
    BaseTranslationProvider,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    PROVIDER_GROUP_STABLE,
    TranslationProviderError,
    TranslationProviderInfo,
)


logger = logging.getLogger(__name__)


class GoogleTranslateV2Provider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="google_translate_v2",
        group=PROVIDER_GROUP_STABLE,
        stable=True,
    )

    def _normalize_google_api_key(self, raw_value: str) -> tuple[str, dict[str, Any]]:
        trimmed = str(raw_value or "").strip()
        normalized = trimmed
        extracted_from_query = False
        removed_trailing_query = False

        if "key=" in trimmed:
            parsed = urlparse(trimmed)
            query_values = parse_qs(parsed.query or trimmed)
            candidate = (query_values.get("key") or [""])[0].strip()
            if candidate:
                normalized = candidate
                extracted_from_query = candidate != trimmed

        if normalized.startswith("AIza") and "&" in normalized:
            candidate = normalized.split("&", 1)[0].strip()
            if candidate and candidate != normalized:
                normalized = candidate
                removed_trailing_query = True

        diagnostics = {
            "api_key_present": bool(normalized),
            "api_key_length": len(normalized),
            "api_key_masked_preview": self._mask_secret(normalized),
            "api_key_trimmed_changed": raw_value != trimmed,
            "api_key_sanitized_changed": trimmed != normalized,
            "api_key_extracted_from_query": extracted_from_query,
            "api_key_removed_trailing_query": removed_trailing_query,
        }
        return normalized, diagnostics

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
        timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ) -> tuple[str, dict[str, Any]]:
        raw_api_key = str(provider_settings.get("api_key", ""))
        api_key, key_diagnostics = self._normalize_google_api_key(raw_api_key)
        if not api_key:
            raise TranslationProviderError("Google Translate v2 API key is missing.")

        endpoint = "https://translation.googleapis.com/language/translate/v2"
        params = {"key": api_key}
        data: dict[str, str] = {"q": text, "target": target_lang, "format": "text"}
        normalized_source = self._normalize_source_lang(source_lang)
        if normalized_source != "auto":
            data["source"] = normalized_source

        diagnostics = self.diagnostics(provider_settings)
        diagnostics.update(
            {
                "endpoint_used": endpoint,
                **key_diagnostics,
                "http_method": "POST",
            }
        )

        try:
            payload = await self._request_json(
                url=endpoint,
                method="POST",
                params=params,
                data=data,
                timeout=timeout,
                error_prefix="Google Translate v2 request failed",
            )
        except TranslationProviderError as exc:
            debug_message = (
                f"{exc} | provider=google_translate_v2"
                f" | endpoint={endpoint}"
                f" | api_key_present={key_diagnostics['api_key_present']}"
                f" | api_key_length={key_diagnostics['api_key_length']}"
                f" | api_key_preview={key_diagnostics['api_key_masked_preview']}"
                f" | trim_changed={key_diagnostics['api_key_trimmed_changed']}"
                f" | sanitized_changed={key_diagnostics['api_key_sanitized_changed']}"
                f" | extracted_from_query={key_diagnostics['api_key_extracted_from_query']}"
                f" | removed_trailing_query={key_diagnostics['api_key_removed_trailing_query']}"
            )
            logger.warning(debug_message)
            raise TranslationProviderError(debug_message, retryable=exc.retryable) from exc

        translated = payload.get("data", {}).get("translations", [{}])[0].get("translatedText")
        if not translated:
            raise TranslationProviderError("Google Translate v2 returned an empty translation.")
        diagnostics["status_message"] = (
            f"Google Translate v2 request succeeded. endpoint={endpoint} "
            f"api_key_present={key_diagnostics['api_key_present']} key_length={key_diagnostics['api_key_length']} "
            f"key_preview={key_diagnostics['api_key_masked_preview']} trim_changed={key_diagnostics['api_key_trimmed_changed']} "
            f"sanitized_changed={key_diagnostics['api_key_sanitized_changed']}"
        )
        return unescape(str(translated)), diagnostics

__all__ = ["GoogleTranslateV2Provider"]
