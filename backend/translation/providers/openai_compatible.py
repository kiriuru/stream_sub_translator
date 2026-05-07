from __future__ import annotations

from typing import Any

import httpx

from backend.translation.base import (
    BaseTranslationProvider,
    PROVIDER_GROUP_STABLE,
    TranslationProviderError,
    TranslationProviderInfo,
)


DEFAULT_SUBTITLE_TRANSLATION_PROMPT = (
    "You are a subtitle translator for livestream captions. "
    "Translate only the user subtitle text into the requested target language. "
    "Do not explain anything. Do not add notes, prefixes, or assistant-style chatter. "
    "Keep the output concise, readable, and subtitle-friendly. "
    "Preserve names, game terms, UI labels, and obvious proper nouns when appropriate."
)


class OpenAICompatibleChatProvider(BaseTranslationProvider):
    def __init__(
        self,
        *,
        name: str,
        group: str,
        default_base_url: str,
        requires_api_key: bool,
        local_provider: bool = False,
    ) -> None:
        self.info = TranslationProviderInfo(
            name=name,
            group=group,
            stable=group == PROVIDER_GROUP_STABLE,
            local_provider=local_provider,
        )
        self.default_base_url = default_base_url
        self.requires_api_key = requires_api_key

    def diagnostics(self, provider_settings: dict[str, str]) -> dict[str, Any]:
        custom_prompt = provider_settings.get("custom_prompt", "").strip()
        diagnostics = super().diagnostics(provider_settings)
        diagnostics.update(
            {
                "provider_endpoint": provider_settings.get("base_url", "").strip() or self.default_base_url,
                "model": provider_settings.get("model", "").strip() or None,
                "used_default_prompt": not bool(custom_prompt),
            }
        )
        return diagnostics

    def _build_messages(self, text: str, source_lang: str, target_lang: str, custom_prompt: str) -> tuple[list[dict[str, str]], bool]:
        system_prompt = custom_prompt or DEFAULT_SUBTITLE_TRANSLATION_PROMPT
        normalized_source = self._normalize_source_lang(source_lang)
        if normalized_source == "auto":
            user_prompt = (
                f"Detect the source language and translate the subtitle text into '{target_lang}'. "
                "Return only the translated subtitle text.\n\n"
                f"Subtitle text:\n{text}"
            )
        else:
            user_prompt = (
                f"Translate the subtitle text from '{normalized_source}' into '{target_lang}'. "
                "Return only the translated subtitle text.\n\n"
                f"Subtitle text:\n{text}"
            )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], not bool(custom_prompt)

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        base_url = provider_settings.get("base_url", "").strip() or self.default_base_url
        api_key = provider_settings.get("api_key", "").strip()
        model = provider_settings.get("model", "").strip()
        custom_prompt = provider_settings.get("custom_prompt", "").strip()

        if self.requires_api_key and not api_key:
            raise TranslationProviderError(f"{self.info.name} API key is missing.")
        if not base_url:
            raise TranslationProviderError(f"{self.info.name} base URL is missing.")
        if not model:
            raise TranslationProviderError(f"{self.info.name} model is missing.")

        messages, used_default_prompt = self._build_messages(text, source_lang, target_lang, custom_prompt)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
        }

        diagnostics = self.diagnostics(provider_settings)
        diagnostics.update(
            {
                "provider_endpoint": base_url.rstrip("/"),
                "model": model,
                "used_default_prompt": used_default_prompt,
            }
        )

        async with httpx.AsyncClient() as client:
            data = await self._get_json(
                client,
                url=f"{base_url.rstrip('/')}/chat/completions",
                method="POST",
                json=payload,
                headers=headers,
                error_prefix=f"{self.info.name} request failed",
            )

        choices = data.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        translated = message.get("content")
        if isinstance(translated, list):
            translated = "".join(
                str(part.get("text", ""))
                for part in translated
                if isinstance(part, dict)
            )
        translated_text = str(translated or "").strip()
        if not translated_text:
            raise TranslationProviderError(f"{self.info.name} returned an empty translation.")
        return translated_text, diagnostics

__all__ = ["OpenAICompatibleChatProvider"]
