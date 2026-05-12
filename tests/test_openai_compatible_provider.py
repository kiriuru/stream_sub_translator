from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, patch

from backend.translation.providers.openai_compatible import (
    DEFAULT_SUBTITLE_TRANSLATION_PROMPT,
    OpenAICompatibleChatProvider,
)


class OpenAICompatibleProviderTests(unittest.IsolatedAsyncioTestCase):
    def _make_provider(self) -> OpenAICompatibleChatProvider:
        return OpenAICompatibleChatProvider(
            name="openai",
            group="llm",
            default_base_url="https://api.openai.com/v1",
            requires_api_key=True,
        )

    async def test_translate_passes_max_tokens_and_short_subtitle_prompt(self) -> None:
        provider = self._make_provider()
        captured: dict[str, Any] = {}

        async def fake_get_json(_client, **kwargs):
            captured.update(kwargs)
            return {"choices": [{"message": {"content": "bonjour"}}]}

        with patch.object(provider, "_get_json", AsyncMock(side_effect=fake_get_json)):
            translated, diagnostics = await provider.translate(
                text="hello",
                source_lang="en",
                target_lang="fr",
                provider_settings={
                    "api_key": "sk-demo",
                    "model": "gpt-4o-mini",
                    "base_url": "https://api.openai.com/v1",
                },
            )

        self.assertEqual(translated, "bonjour")
        payload = captured["json"]
        self.assertIn("max_tokens", payload)
        self.assertGreater(payload["max_tokens"], 0)
        self.assertEqual(diagnostics["max_tokens_cap"], payload["max_tokens"])
        # System prompt must include the strict subtitle-only instruction.
        system_message = payload["messages"][0]
        self.assertEqual(system_message["role"], "system")
        self.assertIn("Output only the translated subtitle text", system_message["content"])

    async def test_translate_honors_custom_prompt_over_default(self) -> None:
        provider = self._make_provider()
        captured: dict[str, Any] = {}

        async def fake_get_json(_client, **kwargs):
            captured.update(kwargs)
            return {"choices": [{"message": {"content": "bonjour"}}]}

        custom_prompt = "Translate game subtitles directly into the requested language."
        with patch.object(provider, "_get_json", AsyncMock(side_effect=fake_get_json)):
            _translated, diagnostics = await provider.translate(
                text="hello",
                source_lang="en",
                target_lang="fr",
                provider_settings={
                    "api_key": "sk-demo",
                    "model": "gpt-4o-mini",
                    "base_url": "https://api.openai.com/v1",
                    "custom_prompt": custom_prompt,
                },
            )

        payload = captured["json"]
        self.assertEqual(payload["messages"][0]["content"], custom_prompt)
        self.assertFalse(diagnostics["used_default_prompt"])
        self.assertNotEqual(payload["messages"][0]["content"], DEFAULT_SUBTITLE_TRANSLATION_PROMPT)

    async def test_translate_passes_timeout_to_request(self) -> None:
        provider = self._make_provider()
        captured: dict[str, Any] = {}

        async def fake_get_json(_client, **kwargs):
            captured.update(kwargs)
            return {"choices": [{"message": {"content": "bonjour"}}]}

        with patch.object(provider, "_get_json", AsyncMock(side_effect=fake_get_json)):
            await provider.translate(
                text="hello",
                source_lang="en",
                target_lang="fr",
                provider_settings={
                    "api_key": "sk-demo",
                    "model": "gpt-4o-mini",
                    "base_url": "https://api.openai.com/v1",
                },
                timeout=2.5,
            )

        self.assertEqual(captured.get("timeout"), 2.5)


if __name__ == "__main__":
    unittest.main()
