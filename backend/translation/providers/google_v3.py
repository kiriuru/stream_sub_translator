from __future__ import annotations

from html import unescape
from typing import Any

from backend.translation.base import (
    BaseTranslationProvider,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    PROVIDER_GROUP_STABLE,
    TranslationProviderError,
    TranslationProviderInfo,
)


class GoogleCloudTranslationV3Provider(BaseTranslationProvider):
    info = TranslationProviderInfo(
        name="google_cloud_translation_v3",
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
        project_id = provider_settings.get("project_id", "").strip()
        access_token = provider_settings.get("access_token", "").strip()
        location = provider_settings.get("location", "").strip() or "global"
        model = provider_settings.get("model", "").strip()

        if not project_id:
            raise TranslationProviderError("Google Cloud Translation v3 project ID is missing.")
        if not access_token:
            raise TranslationProviderError("Google Cloud Translation v3 access token is missing.")

        endpoint = f"https://translation.googleapis.com/v3/projects/{project_id}/locations/{location}:translateText"
        payload: dict[str, Any] = {
            "contents": [text],
            "targetLanguageCode": target_lang,
            "mimeType": "text/plain",
        }
        normalized_source = self._normalize_source_lang(source_lang)
        if normalized_source != "auto":
            payload["sourceLanguageCode"] = normalized_source
        if model:
            payload["model"] = model

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
            "x-goog-user-project": project_id,
        }
        diagnostics = self.diagnostics(provider_settings)
        diagnostics.update(
            {
                "endpoint_used": endpoint,
                "http_method": "POST",
                "location": location,
                "project_id_present": True,
                "access_token_present": True,
                "access_token_masked_preview": self._mask_secret(access_token),
                "model_requested": model or None,
                "status_message": (
                    "Cloud Translation - Advanced (v3) via REST. "
                    "Requires OAuth access token; API keys are not supported."
                ),
            }
        )

        data = await self._request_json(
            url=endpoint,
            method="POST",
            json=payload,
            headers=headers,
            timeout=timeout,
            error_prefix="Google Cloud Translation v3 request failed",
        )

        translations = data.get("translations", [])
        translated = translations[0].get("translatedText") if translations else None
        if not translated:
            raise TranslationProviderError("Google Cloud Translation v3 returned an empty translation.")
        return unescape(str(translated)), diagnostics

__all__ = ["GoogleCloudTranslationV3Provider"]
