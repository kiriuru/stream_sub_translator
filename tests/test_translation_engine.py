from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from backend.core.cache_manager import CacheManager
from backend.core.translation_engine import (
    BaseTranslationProvider,
    GoogleCloudTranslationV3Provider,
    TranslationBatch,
    TranslationEngine,
    TranslationProviderInfo,
)


class _FakeProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(name="fake_provider", group="stable", stable=True)

    def __init__(self, delays: dict[str, float] | None = None) -> None:
        self.delays = delays or {}
        self.calls: list[str] = []
        self.completions: list[str] = []

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        self.calls.append(target_lang)
        await asyncio.sleep(self.delays.get(target_lang, 0.0))
        self.completions.append(target_lang)
        return f"{text}:{target_lang}", self.diagnostics(provider_settings)


class TranslationEngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_manager = CacheManager(Path(self.temp_dir.name))
        self.engine = TranslationEngine(self.cache_manager)

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_translate_targets_preserves_requested_order_with_parallel_completion(self) -> None:
        provider = _FakeProvider(delays={"de": 0.05, "fr": 0.01, "en": 0.03})
        self.engine.providers = {"fake_provider": provider}

        batch = await self.engine.translate_targets(
            source_text="hello",
            source_lang="en",
            provider_name="fake_provider",
            provider_settings={},
            target_languages=["de", "fr", "en"],
            retries=0,
        )

        self.assertIsInstance(batch, TranslationBatch)
        self.assertEqual([item.target_lang for item in batch.items], ["de", "fr", "en"])
        self.assertEqual([item.text for item in batch.items], ["hello:de", "hello:fr", "hello:en"])
        self.assertEqual(provider.calls, ["de", "fr", "en"])
        self.assertEqual(provider.completions, ["fr", "en", "de"])

    async def test_translate_targets_uses_cache_before_calling_provider(self) -> None:
        provider = _FakeProvider()
        self.engine.providers = {"fake_provider": provider}
        self.cache_manager.set_translation("привет", "ru", "en", "hello")

        batch = await self.engine.translate_targets(
            source_text="привет",
            source_lang="ru",
            provider_name="fake_provider",
            provider_settings={},
            target_languages=["en", "fr"],
            retries=0,
        )

        self.assertEqual([item.target_lang for item in batch.items], ["en", "fr"])
        self.assertTrue(batch.items[0].cached)
        self.assertEqual(batch.items[0].text, "hello")
        self.assertFalse(batch.items[1].cached)
        self.assertEqual(batch.items[1].text, "привет:fr")
        self.assertEqual(provider.calls, ["fr"])

    async def test_google_cloud_translation_v3_uses_advanced_endpoint_and_bearer_token(self) -> None:
        provider = GoogleCloudTranslationV3Provider()
        captured: dict[str, Any] = {}

        async def fake_get_json(_client, **kwargs):
            captured.update(kwargs)
            return {"translations": [{"translatedText": "hello"}]}

        with patch.object(provider, "_get_json", AsyncMock(side_effect=fake_get_json)):
            translated, diagnostics = await provider.translate(
                text="привет",
                source_lang="ru",
                target_lang="en",
                provider_settings={
                    "project_id": "demo-project",
                    "access_token": "ya29.token-value",
                    "location": "global",
                    "model": "general/nmt",
                },
            )

        self.assertEqual(translated, "hello")
        self.assertEqual(
            captured["url"],
            "https://translation.googleapis.com/v3/projects/demo-project/locations/global:translateText",
        )
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer ya29.token-value")
        self.assertEqual(captured["headers"]["x-goog-user-project"], "demo-project")
        self.assertEqual(captured["json"]["contents"], ["привет"])
        self.assertEqual(captured["json"]["targetLanguageCode"], "en")
        self.assertEqual(captured["json"]["sourceLanguageCode"], "ru")
        self.assertEqual(captured["json"]["model"], "general/nmt")
        self.assertEqual(diagnostics["provider"], "google_cloud_translation_v3")
        self.assertEqual(diagnostics["location"], "global")


if __name__ == "__main__":
    unittest.main()
