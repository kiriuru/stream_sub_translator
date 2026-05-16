from __future__ import annotations

import asyncio
from dataclasses import dataclass
import unittest

from backend.core.translation_dispatcher import TranslationDispatcher
from backend.core.translation_engine import PreparedTranslationLine
from backend.models import TranslationItem


@dataclass
class _PreparedRequest:
    provider_name: str
    provider_settings: dict[str, str]
    target_languages: list[str]
    lines: list[PreparedTranslationLine]
    provider_group: str = "stable"
    experimental: bool = False
    local_provider: bool = False


class _StubTranslationEngine:
    def __init__(
        self,
        *,
        delays: dict[str, float] | None = None,
        fail_prepare: Exception | None = None,
        slot_errors: dict[str, Exception] | None = None,
    ) -> None:
        self.delays = delays or {}
        self.fail_prepare = fail_prepare
        self.slot_errors = slot_errors or {}
        self.cancelled_targets: list[str] = []
        self.calls: list[tuple[str | None, str, str]] = []

    def prepare_request(self, translation_config: dict) -> _PreparedRequest:
        if self.fail_prepare is not None:
            raise self.fail_prepare

        raw_lines = translation_config.get("lines")
        prepared_lines: list[PreparedTranslationLine] = []
        if isinstance(raw_lines, list) and raw_lines:
            for raw_line in raw_lines:
                if not isinstance(raw_line, dict) or raw_line.get("enabled", True) is False:
                    continue
                prepared_lines.append(
                    PreparedTranslationLine(
                        slot_id=str(raw_line.get("slot_id")),
                        target_lang=str(raw_line.get("target_lang")),
                        provider_name=str(raw_line.get("provider", translation_config.get("provider", "stub"))),
                        provider=None,
                        provider_settings={},
                        provider_group="stable",
                        experimental=False,
                        local_provider=False,
                        label=str(raw_line.get("label") or "").strip() or str(raw_line.get("target_lang") or "").upper(),
                    )
                )
        else:
            prepared_lines = [
                PreparedTranslationLine(
                    slot_id=f"translation_{index + 1}",
                    target_lang=str(item),
                    provider_name=str(translation_config.get("provider", "stub")),
                    provider=None,
                    provider_settings={},
                    provider_group="stable",
                    experimental=False,
                    local_provider=False,
                    label=str(item).upper(),
                )
                for index, item in enumerate(translation_config.get("target_languages", []))
            ]

        provider_names = [line.provider_name for line in prepared_lines]
        return _PreparedRequest(
            provider_name=provider_names[0] if provider_names and len(set(provider_names)) == 1 else ("mixed" if provider_names else str(translation_config.get("provider", "stub"))),
            provider_settings={},
            target_languages=[line.target_lang for line in prepared_lines],
            lines=prepared_lines,
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
        slot_id: str | None = None,
        label: str | None = None,
        provider_group: str | None = None,
        experimental: bool | None = None,
        local_provider: bool | None = None,
        budget_seconds: float | None = None,
    ) -> tuple[TranslationItem, dict]:
        try:
            self.calls.append((slot_id, target_lang, provider_name))
            await asyncio.sleep(self.delays.get(slot_id or target_lang, self.delays.get(target_lang, 0.01)))
        except asyncio.CancelledError:
            self.cancelled_targets.append(slot_id or target_lang)
            raise

        if slot_id and slot_id in self.slot_errors:
            raise self.slot_errors[slot_id]

        return (
            TranslationItem(
                slot_id=slot_id,
                label=label,
                target_lang=target_lang,
                text=f"{source_text}-{target_lang}",
                provider=provider_name,
                provider_group=provider_group,
                experimental=experimental,
                local_provider=local_provider,
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
                "lines": [
                    {
                        "slot_id": "translation_1",
                        "enabled": True,
                        "target_lang": "en",
                        "provider": "stub",
                        "label": "EN",
                    }
                ],
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

        translation_events = [event for event in self.published_events if event.translations and not event.is_complete]
        self.assertEqual(len(translation_events), 1)
        self.assertEqual(translation_events[0].translations[0].text, "hello-en")
        self.assertEqual(translation_events[0].translations[0].slot_id, "translation_1")
        complete_events = [event for event in self.published_events if event.is_complete]
        self.assertEqual(len(complete_events), 1)
        self.assertEqual([item.text for item in complete_events[0].translations], ["hello-en"])

    async def test_skips_provider_when_preview_superseded_with_concurrent_jobs(self) -> None:
        """Superseded job must not call the translation engine when a newer final shares preview lineage."""
        self.config["translation"]["max_concurrent_jobs"] = 2
        engine = _StubTranslationEngine(delays={"translation_1": 20.0})
        self.relevant_sequences.update({1, 2})
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        key = "seg:rev:1"
        await asyncio.gather(
            dispatcher.submit_final(sequence=1, source_text="older", source_lang="en", preview_lineage_key=key),
            dispatcher.submit_final(sequence=2, source_text="newer", source_lang="en", preview_lineage_key=key),
        )
        await asyncio.sleep(0.35)
        await dispatcher.stop()
        self.assertEqual(len(engine.calls), 1)

    async def test_completion_event_keeps_published_translations(self) -> None:
        self.config["translation"]["lines"] = [
            {"slot_id": "translation_1", "enabled": True, "target_lang": "en", "provider": "stub", "label": "EN"},
            {"slot_id": "translation_2", "enabled": True, "target_lang": "de", "provider": "stub", "label": "DE"},
        ]
        engine = _StubTranslationEngine(delays={"translation_1": 0.01, "translation_2": 0.02})
        self.relevant_sequences.add(12)
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        await dispatcher.submit_final(sequence=12, source_text="hello", source_lang="en")
        await asyncio.sleep(0.1)
        await dispatcher.stop()

        complete_events = [event for event in self.published_events if event.sequence == 12 and event.is_complete]
        self.assertEqual(len(complete_events), 1)
        self.assertEqual([item.target_lang for item in complete_events[0].translations], ["en", "de"])
        self.assertEqual([item.slot_id for item in complete_events[0].translations], ["translation_1", "translation_2"])
        self.assertEqual([item.text for item in complete_events[0].translations], ["hello-en", "hello-de"])

    async def test_drops_stale_translation_result(self) -> None:
        engine = _StubTranslationEngine(delays={"translation_1": 0.1})
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
        self.config["translation"]["lines"] = [
            {"slot_id": "translation_1", "enabled": True, "target_lang": "en", "provider": "stub", "label": "EN"},
            {"slot_id": "translation_2", "enabled": True, "target_lang": "de", "provider": "stub", "label": "DE"},
        ]
        engine = _StubTranslationEngine(delays={"translation_1": 0.01, "translation_2": 0.2})
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
        first_translation_slots = [event.translations[0].slot_id for event in self.published_events if event.translations]
        await dispatcher.stop()

        self.assertEqual(first_translation_slots, ["translation_1"])

    async def test_cancel_older_than_cancels_irrelevant_jobs(self) -> None:
        engine = _StubTranslationEngine(delays={"translation_1": 0.2})
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
        # Let job 1 enter translate_target (0.2s in-engine delay) before we mark seq 1 irrelevant.
        await asyncio.sleep(0.12)
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

        self.assertIn("translation_1", engine.cancelled_targets)
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
        self.assertIn("translation_line_started", events)
        self.assertIn("translation_line_done", events)
        self.assertIn("translation_publish_accepted", events)

        serialized_records = repr(self.structured_logger.records)
        self.assertNotIn("do not leak this sentence", serialized_records)
        self.assertNotIn("top-secret-key", serialized_records)
        self.assertIn("source_text_len", serialized_records)

    async def test_timeout_emits_structured_event_and_job_still_completes(self) -> None:
        self.config["translation"]["timeout_ms"] = 1000
        engine = _StubTranslationEngine(delays={"translation_1": 1.2})
        self.relevant_sequences.add(8)
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        await dispatcher.submit_final(sequence=8, source_text="slow target", source_lang="en")
        await asyncio.sleep(1.35)
        await dispatcher.stop()

        translation_events = [event for event in self.published_events if event.sequence == 8 and event.translations and not event.is_complete]
        self.assertEqual(len(translation_events), 1)
        self.assertFalse(translation_events[0].translations[0].success)
        complete_events = [event for event in self.published_events if event.sequence == 8 and event.is_complete]
        self.assertEqual(len(complete_events), 1)
        self.assertEqual(len(complete_events[0].translations), 1)
        self.assertFalse(complete_events[0].translations[0].success)
        self.assertIn("translation_line_timeout", [record["event"] for record in self.structured_logger.records])

    async def test_mixed_provider_lines_publish_independently_and_completion_is_mixed(self) -> None:
        self.config["translation"]["provider"] = "google_translate_v2"
        self.config["translation"]["lines"] = [
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
        ]
        engine = _StubTranslationEngine(delays={"translation_1": 0.01, "translation_2": 0.02})
        self.relevant_sequences.add(21)
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        await dispatcher.submit_final(sequence=21, source_text="hello", source_lang="en")
        await asyncio.sleep(0.1)
        await dispatcher.stop()

        partials = [event for event in self.published_events if event.sequence == 21 and event.translations and not event.is_complete]
        self.assertEqual([event.translations[0].slot_id for event in partials], ["translation_1", "translation_2"])
        self.assertEqual([event.translations[0].provider for event in partials], ["google_translate_v2", "openai"])
        completion = [event for event in self.published_events if event.sequence == 21 and event.is_complete][0]
        self.assertEqual(completion.provider, "mixed")
        self.assertEqual([item.slot_id for item in completion.translations], ["translation_1", "translation_2"])
        self.assertEqual(engine.calls, [("translation_1", "en", "google_translate_v2"), ("translation_2", "en", "openai")])
        self.assertEqual(self.metrics[-1]["translation_last_slot_id"], "translation_2")

    async def test_one_line_failure_does_not_block_other_line_success(self) -> None:
        self.config["translation"]["lines"] = [
            {"slot_id": "translation_1", "enabled": True, "target_lang": "en", "provider": "stub", "label": "EN"},
            {"slot_id": "translation_2", "enabled": True, "target_lang": "de", "provider": "stub", "label": "DE"},
        ]
        engine = _StubTranslationEngine(slot_errors={"translation_2": RuntimeError("deepl exploded")})
        self.relevant_sequences.add(22)
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        await dispatcher.submit_final(sequence=22, source_text="hello", source_lang="en")
        await asyncio.sleep(0.1)
        await dispatcher.stop()

        partials = [event for event in self.published_events if event.sequence == 22 and event.translations and not event.is_complete]
        self.assertEqual(len(partials), 2)
        by_slot = {event.translations[0].slot_id: event.translations[0] for event in partials}
        self.assertTrue(by_slot["translation_1"].success)
        self.assertFalse(by_slot["translation_2"].success)
        self.assertEqual(by_slot["translation_2"].error, "deepl exploded")
        completion = [event for event in self.published_events if event.sequence == 22 and event.is_complete][0]
        self.assertEqual({item.slot_id for item in completion.translations}, {"translation_1", "translation_2"})

    async def test_prepare_request_failure_emits_structured_job_error(self) -> None:
        engine = _StubTranslationEngine(fail_prepare=RuntimeError("prepare_request exploded"))
        self.relevant_sequences.add(11)
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        await dispatcher.submit_final(sequence=11, source_text="boom", source_lang="en")
        await asyncio.sleep(0.08)
        await dispatcher.stop()

        job_error_records = [record for record in self.structured_logger.records if record["event"] == "translation_job_error"]
        self.assertEqual(len(job_error_records), 1)
        self.assertEqual(job_error_records[0]["payload"]["sequence"], 11)
        self.assertEqual(job_error_records[0]["payload"]["error_type"], "RuntimeError")
        self.assertEqual(job_error_records[0]["payload"]["reason"], "prepare_request exploded")
        self.assertEqual(self.metrics[-1]["translation_last_runtime_reason"], "job_error:prepare_request exploded")

    async def test_can_restart_after_stop(self) -> None:
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

        # Previously, stop() permanently disabled submit_final(). start() should re-enable it.
        self.published_events.clear()
        self.relevant_sequences.clear()
        self.relevant_sequences.add(2)
        dispatcher.start()
        await dispatcher.submit_final(sequence=2, source_text="again", source_lang="en")
        await asyncio.sleep(0.08)
        await dispatcher.stop()

        translation_events = [event for event in self.published_events if event.sequence == 2 and event.translations]
        self.assertTrue(translation_events)

    async def test_provider_concurrency_limit_serializes_same_provider_targets(self) -> None:
        self.config["translation"]["provider_limits"] = {"stub": {"max_concurrent_targets": 1}}
        self.config["translation"]["lines"] = [
            {"slot_id": "translation_1", "enabled": True, "target_lang": "en", "provider": "stub", "label": "EN"},
            {"slot_id": "translation_2", "enabled": True, "target_lang": "de", "provider": "stub", "label": "DE"},
        ]

        started: list[tuple[str, float]] = []

        class _TimedEngine(_StubTranslationEngine):
            async def translate_target(self, **kwargs):  # type: ignore[override]
                slot_id = kwargs.get("slot_id") or kwargs.get("target_lang")
                started.append((str(slot_id), asyncio.get_running_loop().time()))
                return await super().translate_target(**kwargs)

        engine = _TimedEngine(delays={"translation_1": 0.08, "translation_2": 0.08})
        self.relevant_sequences.add(30)
        dispatcher = TranslationDispatcher(
            engine,
            lambda: self.config,
            self._publish,
            lambda sequence: sequence in self.relevant_sequences,
            self._metrics_callback,
            structured_logger=self.structured_logger,
        )
        await dispatcher.submit_final(sequence=30, source_text="hello", source_lang="en")
        await asyncio.sleep(0.25)
        await dispatcher.stop()

        # With max_concurrent_targets=1 for provider 'stub', the second target should start noticeably later.
        self.assertEqual([slot for slot, _ in started], ["translation_1", "translation_2"])
        self.assertGreaterEqual(started[1][1] - started[0][1], 0.05)


if __name__ == "__main__":
    unittest.main()
