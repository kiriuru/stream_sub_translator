from __future__ import annotations

import asyncio
from dataclasses import dataclass
import unittest

from backend.core.translation_dispatcher import TranslationDispatcher
from backend.models import TranslationItem


@dataclass
class _PreparedRequest:
    provider_name: str
    provider_settings: dict[str, str]
    target_languages: list[str]
    provider_group: str = "stable"
    experimental: bool = False
    local_provider: bool = False


class _StubTranslationEngine:
    def __init__(self, *, delays: dict[str, float] | None = None) -> None:
        self.delays = delays or {}
        self.cancelled_targets: list[str] = []

    def prepare_request(self, translation_config: dict) -> _PreparedRequest:
        return _PreparedRequest(
            provider_name=str(translation_config.get("provider", "stub")),
            provider_settings={},
            target_languages=[str(item) for item in translation_config.get("target_languages", [])],
        )

    async def translate_target(
        self,
        *,
        source_text: str,
        source_lang: str,
        provider_name: str,
        provider_settings: dict,
        target_lang: str,
        retries: int = 2,
    ) -> tuple[TranslationItem, dict]:
        try:
            await asyncio.sleep(self.delays.get(target_lang, 0.01))
        except asyncio.CancelledError:
            self.cancelled_targets.append(target_lang)
            raise
        return (
            TranslationItem(
                target_lang=target_lang,
                text=f"{source_text}-{target_lang}",
                provider=provider_name,
                cached=False,
                success=True,
            ),
            {"status_message": f"translated:{target_lang}"},
        )


class _RecordingStructuredLogger:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def log(self, channel: str, event: str, *, source: str | None = None, payload: dict | None = None, **fields) -> None:
        merged_payload = dict(payload or {})
        merged_payload.update(fields)
        self.records.append(
            {
                "channel": channel,
                "event": event,
                "source": source,
                "payload": merged_payload,
            }
        )


class TranslationDispatcherTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.config = {
            "translation": {
                "enabled": True,
                "provider": "stub",
                "api_key": "top-secret-key",
                "target_languages": ["en"],
                "timeout_ms": 500,
                "queue_max_size": 8,
                "max_concurrent_jobs": 2,
            }
        }
        self.relevant_sequences: set[int] = set()
        self.published_events = []
        self.metrics = []
        self.structured_logger = _RecordingStructuredLogger()

    async def _publish(self, event) -> None:
        self.published_events.append(event)

    def _metrics_callback(self, payload: dict) -> None:
        self.metrics.append(dict(payload))

    async def test_publishes_fresh_translation(self) -> None:
        engine = _StubTranslationEngine()
        self.relevant_sequences.add(1)
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        await dispatcher.submit_final(sequence=1, source_text="hello", source_lang="en")
        await asyncio.sleep(0.08)
        await dispatcher.stop()

        translation_events = [event for event in self.published_events if event.translations]
        self.assertEqual(len(translation_events), 1)
        self.assertEqual(translation_events[0].translations[0].text, "hello-en")
        self.assertTrue(any(event.is_complete for event in self.published_events))

    async def test_drops_stale_translation_result(self) -> None:
        engine = _StubTranslationEngine(delays={"en": 0.1})
        self.relevant_sequences.add(1)
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        await dispatcher.submit_final(sequence=1, source_text="hello", source_lang="en")
        await asyncio.sleep(0.02)
        self.relevant_sequences.clear()
        await asyncio.sleep(0.15)
        await dispatcher.stop()

        self.assertEqual(self.published_events, [])
        self.assertGreaterEqual(self.metrics[-1]["translation_stale_results_dropped"], 1)

    async def test_slow_target_does_not_block_fast_target(self) -> None:
        self.config["translation"]["target_languages"] = ["en", "de"]
        engine = _StubTranslationEngine(delays={"en": 0.01, "de": 0.2})
        self.relevant_sequences.add(1)
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        await dispatcher.submit_final(sequence=1, source_text="hello", source_lang="en")
        deadline = asyncio.get_running_loop().time() + 0.4
        while not [event for event in self.published_events if event.translations]:
            if asyncio.get_running_loop().time() >= deadline:
                break
            await asyncio.sleep(0.02)
        first_translation_targets = [event.translations[0].target_lang for event in self.published_events if event.translations]
        await dispatcher.stop()

        self.assertEqual(first_translation_targets, ["en"])

    async def test_cancel_older_than_cancels_irrelevant_jobs(self) -> None:
        engine = _StubTranslationEngine(delays={"en": 0.2})
        self.relevant_sequences.add(1)
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        await dispatcher.submit_final(sequence=1, source_text="hello", source_lang="en")
        await asyncio.sleep(0.03)
        self.relevant_sequences.clear()
        self.relevant_sequences.add(2)
        await dispatcher.cancel_older_than(2)
        await dispatcher.submit_final(sequence=2, source_text="new", source_lang="en")
        deadline = asyncio.get_running_loop().time() + 0.5
        while not any(event.sequence == 2 for event in self.published_events):
            if asyncio.get_running_loop().time() >= deadline:
                break
            await asyncio.sleep(0.02)
        await dispatcher.stop()

        self.assertIn("en", engine.cancelled_targets)
        self.assertTrue(any(event.sequence == 2 for event in self.published_events))
        self.assertFalse(any(event.sequence == 1 for event in self.published_events))

    async def test_emits_structured_events_without_source_text_or_secrets(self) -> None:
        engine = _StubTranslationEngine()
        self.relevant_sequences.add(7)
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        await dispatcher.submit_final(sequence=7, source_text="do not leak this sentence", source_lang="en")
        await asyncio.sleep(0.08)
        await dispatcher.stop()

        events = [record["event"] for record in self.structured_logger.records]
        self.assertIn("translation_job_started", events)
        self.assertIn("translation_target_started", events)
        self.assertIn("translation_target_done", events)
        self.assertIn("translation_publish_accepted", events)

        serialized_records = repr(self.structured_logger.records)
        self.assertNotIn("do not leak this sentence", serialized_records)
        self.assertNotIn("top-secret-key", serialized_records)
        self.assertIn("source_text_len", serialized_records)


if __name__ == "__main__":
    unittest.main()
