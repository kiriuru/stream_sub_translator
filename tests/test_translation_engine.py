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
from backend.translation.base import TranslationProviderError


class _FakeProvider(BaseTranslationProvider):
    info = TranslationProviderInfo(name="fake_provider", group="stable", stable=True)

    def __init__(self, delays: dict[str, float] | None = None) -> None:
        super().__init__()
        self.delays = delays or {}
        self.calls: list[str] = []
        self.completions: list[str] = []
        self.received_timeouts: list[float | None] = []

    async def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str,
        provider_settings: dict[str, str],
        timeout: float | None = None,
    ) -> tuple[str, dict[str, Any]]:
        self.calls.append(target_lang)
        self.received_timeouts.append(timeout)
        await asyncio.sleep(self.delays.get(target_lang, 0.0))
        self.completions.append(target_lang)
        return f"{text}:{target_lang}", self.diagnostics(provider_settings)


class TranslationEngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_manager = CacheManager(Path(self.temp_dir.name))
        self.engine = TranslationEngine(self.cache_manager)

    async def asyncTearDown(self) -> None:
        await self.engine.aclose()
        self.cache_manager.close()
        self.temp_dir.cleanup()

    async def test_translate_targets_preserves_requested_order_with_parallel_completion(self) -> None:
        provider = _FakeProvider(delays={"de": 0.05, "fr": 0.01, "en": 0.03})
        self.engine.providers = {"fake_provider": provider}

        batch = await self.engine.translate_targets(
            source_text="hello",
            source_lang="ru",
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
        self.cache_manager.set_translation("привет", "ru", "en", "hello", provider_name="fake_provider")

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

    def test_prepare_request_uses_per_line_provider_and_duplicate_languages(self) -> None:
        prepared = self.engine.prepare_request(
            {
                "enabled": True,
                "provider": "google_translate_v2",
                "target_languages": ["en"],
                "lines": [
                    {
                        "slot_id": "translation_1",
                        "enabled": True,
                        "target_lang": "en",
                        "provider": "google_translate_v2",
                        "label": "EN-G",
                    },
                    {
                        "slot_id": "translation_2",
                        "enabled": True,
                        "target_lang": "en",
                        "provider": "openai",
                        "label": "EN-AI",
                    },
                    {
                        "slot_id": "translation_3",
                        "enabled": False,
                        "target_lang": "ja",
                        "provider": "deepl",
                        "label": "JA",
                    },
                ],
                "provider_settings": {
                    "google_translate_v2": {"api_key": "AIza-demo"},
                    "openai": {
                        "api_key": "sk-demo",
                        "model": "gpt-4o-mini",
                        "base_url": "https://api.openai.com/v1",
                    },
                },
            }
        )

        self.assertEqual(prepared.provider_name, "mixed")
        self.assertEqual([line.slot_id for line in prepared.lines], ["translation_1", "translation_2"])
        self.assertEqual([line.target_lang for line in prepared.lines], ["en", "en"])
        self.assertEqual([line.provider_name for line in prepared.lines], ["google_translate_v2", "openai"])
        self.assertEqual(prepared.lines[0].provider_settings["api_key"], "AIza-demo")
        self.assertEqual(prepared.lines[1].provider_settings["model"], "gpt-4o-mini")
        self.assertEqual(prepared.lines[1].label, "EN-AI")

    async def test_translate_target_cache_key_includes_provider_name(self) -> None:
        google_provider = _FakeProvider()
        openai_provider = _FakeProvider()
        self.engine.providers = {
            "google_translate_v2": google_provider,
            "openai": openai_provider,
        }
        self.cache_manager.set_translation("hello", "en", "fr", "cached-google", provider_name="google_translate_v2")
        self.cache_manager.set_translation("hello", "en", "fr", "cached-openai", provider_name="openai")

        google_item, _ = await self.engine.translate_target(
            source_text="hello",
            source_lang="en",
            provider_name="google_translate_v2",
            provider_settings={},
            target_lang="fr",
        )
        openai_item, _ = await self.engine.translate_target(
            source_text="hello",
            source_lang="en",
            provider_name="openai",
            provider_settings={},
            target_lang="fr",
        )

        self.assertEqual(google_item.text, "cached-google")
        self.assertEqual(openai_item.text, "cached-openai")
        self.assertTrue(google_item.cached)
        self.assertTrue(openai_item.cached)
        self.assertEqual(google_provider.calls, [])
        self.assertEqual(openai_provider.calls, [])

    async def test_translate_target_short_circuits_for_empty_source_text(self) -> None:
        provider = _FakeProvider()
        self.engine.providers = {"fake_provider": provider}

        item, diagnostics = await self.engine.translate_target(
            source_text="   ",
            source_lang="en",
            provider_name="fake_provider",
            provider_settings={},
            target_lang="fr",
        )

        self.assertTrue(item.success)
        self.assertTrue(item.cached)
        self.assertEqual(item.text, "   ")
        self.assertEqual(provider.calls, [])
        self.assertIn("short-circuited", diagnostics.get("status_message", "").lower())

    async def test_translate_target_short_circuits_when_source_and_target_match(self) -> None:
        provider = _FakeProvider()
        self.engine.providers = {"fake_provider": provider}

        item, _diagnostics = await self.engine.translate_target(
            source_text="hello world",
            source_lang="EN",
            provider_name="fake_provider",
            provider_settings={},
            target_lang="en",
        )

        self.assertTrue(item.success)
        self.assertTrue(item.cached)
        self.assertEqual(item.text, "hello world")
        self.assertEqual(provider.calls, [])

    async def test_translate_target_does_not_short_circuit_when_source_is_auto(self) -> None:
        provider = _FakeProvider()
        self.engine.providers = {"fake_provider": provider}

        item, _diagnostics = await self.engine.translate_target(
            source_text="hello",
            source_lang="auto",
            provider_name="fake_provider",
            provider_settings={},
            target_lang="en",
        )

        self.assertEqual(provider.calls, ["en"])
        self.assertEqual(item.text, "hello:en")

    async def test_translate_target_propagates_budget_to_provider(self) -> None:
        provider = _FakeProvider()
        self.engine.providers = {"fake_provider": provider}

        await self.engine.translate_target(
            source_text="hello",
            source_lang="en",
            provider_name="fake_provider",
            provider_settings={},
            target_lang="fr",
            budget_seconds=4.0,
            retries=1,
        )

        self.assertEqual(len(provider.received_timeouts), 1)
        timeout = provider.received_timeouts[0]
        self.assertIsNotNone(timeout)
        # First attempt of two should get roughly budget/2; we allow a comfortable margin.
        self.assertGreater(timeout, 0.25)
        self.assertLessEqual(timeout, 4.0)

    async def test_translate_target_uses_default_timeout_when_no_budget_given(self) -> None:
        from backend.translation.base import DEFAULT_REQUEST_TIMEOUT_SECONDS

        provider = _FakeProvider()
        self.engine.providers = {"fake_provider": provider}

        await self.engine.translate_target(
            source_text="hello",
            source_lang="en",
            provider_name="fake_provider",
            provider_settings={},
            target_lang="fr",
            retries=0,
        )

        self.assertEqual(provider.received_timeouts, [DEFAULT_REQUEST_TIMEOUT_SECONDS])

    async def test_apply_live_settings_propagates_cache_toggle(self) -> None:
        self.cache_manager.set_translation("hello", "en", "fr", "bonjour")
        self.assertEqual(self.cache_manager.get_translation("hello", "en", "fr"), "bonjour")

        self.engine.apply_live_settings(
            {
                "enabled": True,
                "provider": "google_translate_v2",
                "lines": [
                    {
                        "slot_id": "translation_1",
                        "enabled": True,
                        "target_lang": "fr",
                        "provider": "google_translate_v2",
                    }
                ],
                "cache": {"enabled": False, "persist": False},
            }
        )

        self.assertIsNone(self.cache_manager.get_translation("hello", "en", "fr"))
        self.assertFalse(self.cache_manager.enabled)
        self.assertFalse(self.cache_manager.persist)

    async def test_engine_binds_shared_http_client_provider_to_registered_providers(self) -> None:
        await self.engine.aclose()
        self.engine.reset_for_restart()

        # All providers shipped via the registry should pick up the shared
        # client provider so they can reuse keep-alive connections.
        # The fake registry provider has its own translate() bypassing httpx,
        # so we just check the binding has been performed on a known provider.
        google_provider = self.engine.providers.get("google_translate_v2")
        self.assertIsNotNone(google_provider)
        self.assertIsNotNone(getattr(google_provider, "_http_client_provider", None))

    async def test_translate_with_retry_retries_on_retryable_failure_and_then_succeeds(self) -> None:
        class _FlakyProvider(BaseTranslationProvider):
            info = TranslationProviderInfo(name="flaky_provider", group="stable", stable=True)

            def __init__(self) -> None:
                super().__init__()
                self.attempts = 0

            async def translate(
                self,
                *,
                text: str,
                source_lang: str,
                target_lang: str,
                provider_settings: dict[str, str],
                timeout: float | None = None,
            ) -> tuple[str, dict[str, Any]]:
                self.attempts += 1
                if self.attempts == 1:
                    raise TranslationProviderError("transient", retryable=True)
                return f"{text}-{target_lang}", self.diagnostics(provider_settings)

        provider = _FlakyProvider()
        self.engine.providers["flaky_provider"] = provider

        item, _diagnostics = await self.engine.translate_target(
            source_text="hi",
            source_lang="en",
            provider_name="flaky_provider",
            provider_settings={},
            target_lang="fr",
            retries=2,
            budget_seconds=5.0,
        )

        self.assertTrue(item.success)
        self.assertEqual(item.text, "hi-fr")
        self.assertEqual(provider.attempts, 2)

    async def test_translate_with_retry_does_not_retry_non_retryable_failure(self) -> None:
        class _UnreliableProvider(BaseTranslationProvider):
            info = TranslationProviderInfo(name="unreliable_provider", group="stable", stable=True)

            def __init__(self) -> None:
                super().__init__()
                self.attempts = 0

            async def translate(
                self,
                *,
                text: str,
                source_lang: str,
                target_lang: str,
                provider_settings: dict[str, str],
                timeout: float | None = None,
            ) -> tuple[str, dict[str, Any]]:
                self.attempts += 1
                raise TranslationProviderError("nope", retryable=False)

        provider = _UnreliableProvider()
        self.engine.providers["unreliable_provider"] = provider

        item, _diagnostics = await self.engine.translate_target(
            source_text="hi",
            source_lang="en",
            provider_name="unreliable_provider",
            provider_settings={},
            target_lang="fr",
            retries=3,
            budget_seconds=5.0,
        )

        self.assertFalse(item.success)
        self.assertEqual(provider.attempts, 1)

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
