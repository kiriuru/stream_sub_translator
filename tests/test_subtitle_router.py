from __future__ import annotations

import asyncio
import unittest
from typing import Any

from backend.core.subtitle_router import SubtitleRouter
from backend.models import TranscriptEvent, TranscriptSegment, TranslationEvent, TranslationItem


def _base_config() -> dict[str, Any]:
    return {
        "source_lang": "ru",
        "translation": {
            "enabled": True,
            "target_languages": ["en"],
        },
        "subtitle_output": {
            "show_source": True,
            "show_translations": True,
            "max_translation_languages": 1,
            "display_order": ["source", "en"],
        },
        "overlay": {
            "preset": "stacked",
            "compact": False,
        },
        "subtitle_style": {},
        "subtitle_lifecycle": {
            "completed_block_ttl_ms": 10_000,
            "completed_source_ttl_ms": 10_000,
            "completed_translation_ttl_ms": 10_000,
            "pause_to_finalize_ms": 700,
            "allow_early_replace_on_next_final": True,
            "sync_source_and_translation_expiry": True,
            "hard_max_phrase_ms": 12_000,
        },
    }


class _RecordingWsManager:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def broadcast(self, message: dict[str, Any]) -> None:
        self.messages.append(message)


class SubtitleRouterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._config = _base_config()
        self.ws_manager = _RecordingWsManager()
        self.presentation_payloads: list[dict[str, Any]] = []
        self.router = SubtitleRouter(
            self.ws_manager,
            config_getter=lambda: self._config,
            presentation_callback=self._capture_presentation,
        )

    async def asyncTearDown(self) -> None:
        await self.router.reset()

    async def _capture_presentation(self, payload) -> None:
        self.presentation_payloads.append(payload.model_dump())

    def _last_payload(self) -> dict[str, Any]:
        for message in reversed(self.ws_manager.messages):
            if message.get("type") == "subtitle_payload_update":
                return dict(message["payload"])
        self.fail("No subtitle_payload_update message was captured.")

    async def _wait_for_visible_texts(self, expected: list[str], *, timeout: float = 1.5) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            payload = self._last_payload()
            visible_texts = [item["text"] for item in payload["visible_items"]]
            if visible_texts == expected:
                return payload
            if asyncio.get_running_loop().time() >= deadline:
                self.fail(f"Timed out waiting for visible texts {expected!r}; last payload was {visible_texts!r}")
            await asyncio.sleep(0.01)

    async def test_translation_update_enriches_existing_completed_block(self) -> None:
        await self.router.handle_transcript(
            TranscriptEvent(
                event="final",
                text="Привет",
                sequence=1,
                segment=TranscriptSegment(
                    segment_id="seg-1",
                    text="Привет",
                    is_final=True,
                    source_lang="ru",
                    provider="local",
                    sequence=1,
                ),
            )
        )

        payload_before_translation = self._last_payload()
        self.assertEqual(payload_before_translation["lifecycle_state"], "completed_only")
        self.assertTrue(payload_before_translation["completed_block_visible"])
        self.assertEqual(payload_before_translation["active_partial_text"], "")
        self.assertEqual(
            [item["text"] for item in payload_before_translation["visible_items"]],
            ["Привет"],
        )

        await self.router.handle_translation(
            TranslationEvent(
                sequence=1,
                source_text="Привет",
                source_lang="ru",
                provider="google_translate_v2",
                translations=[
                    TranslationItem(
                        target_lang="en",
                        text="Hello",
                        provider="google_translate_v2",
                        cached=False,
                        success=True,
                    )
                ],
            )
        )

        payload_after_translation = self._last_payload()
        self.assertEqual(payload_after_translation["lifecycle_state"], "completed_only")
        self.assertTrue(payload_after_translation["completed_block_visible"])
        self.assertEqual(payload_after_translation["active_partial_text"], "")
        self.assertEqual(
            [item["text"] for item in payload_after_translation["visible_items"]],
            ["Привет", "Hello"],
        )

    async def test_new_partial_keeps_previous_completed_translation_block_visible_until_next_final(self) -> None:
        await self.router.handle_transcript(
            TranscriptEvent(
                event="final",
                text="Первая фраза",
                sequence=1,
                segment=TranscriptSegment(
                    segment_id="seg-1",
                    text="Первая фраза",
                    is_final=True,
                    source_lang="ru",
                    provider="local",
                    sequence=1,
                ),
            )
        )
        await self.router.handle_translation(
            TranslationEvent(
                sequence=1,
                source_text="Первая фраза",
                source_lang="ru",
                provider="google_translate_v2",
                translations=[
                    TranslationItem(
                        target_lang="en",
                        text="First phrase",
                        provider="google_translate_v2",
                    )
                ],
            )
        )

        await self.router.handle_transcript(
            TranscriptEvent(
                event="partial",
                text="Новая",
                sequence=2,
                segment=TranscriptSegment(
                    segment_id="seg-2",
                    text="Новая",
                    is_partial=True,
                    source_lang="ru",
                    provider="local",
                    sequence=2,
                ),
            )
        )

        payload = self._last_payload()
        self.assertEqual(payload["lifecycle_state"], "completed_with_partial")
        self.assertTrue(payload["completed_block_visible"])
        self.assertEqual(payload["active_partial_text"], "Новая")
        self.assertEqual(
            [item["text"] for item in payload["visible_items"]],
            ["Новая", "First phrase"],
        )

    async def test_completed_source_expires_before_translation_and_then_returns_to_idle(self) -> None:
        self._config["subtitle_lifecycle"]["completed_source_ttl_ms"] = 500
        self._config["subtitle_lifecycle"]["completed_translation_ttl_ms"] = 900
        self._config["subtitle_lifecycle"]["sync_source_and_translation_expiry"] = False

        await self.router.handle_transcript(
            TranscriptEvent(
                event="final",
                text="Первая фраза",
                sequence=1,
                segment=TranscriptSegment(
                    segment_id="seg-1",
                    text="Первая фраза",
                    is_final=True,
                    source_lang="ru",
                    provider="local",
                    sequence=1,
                ),
            )
        )
        await self.router.handle_translation(
            TranslationEvent(
                sequence=1,
                source_text="Первая фраза",
                source_lang="ru",
                provider="google_translate_v2",
                translations=[
                    TranslationItem(
                        target_lang="en",
                        text="First phrase",
                        provider="google_translate_v2",
                    )
                ],
            )
        )

        payload_after_source_ttl = await self._wait_for_visible_texts(["First phrase"])
        self.assertEqual(payload_after_source_ttl["lifecycle_state"], "completed_only")

        payload_after_all_ttl = await self._wait_for_visible_texts([])
        self.assertEqual(payload_after_all_ttl["lifecycle_state"], "idle")
        self.assertFalse(payload_after_all_ttl["completed_block_visible"])

    async def test_late_translation_after_source_ttl_reappears_as_translation_only(self) -> None:
        self._config["translation"]["target_languages"] = ["en"]
        self._config["subtitle_output"]["display_order"] = ["source", "en"]
        self._config["subtitle_output"]["max_translation_languages"] = 1
        self._config["subtitle_lifecycle"]["completed_source_ttl_ms"] = 500
        self._config["subtitle_lifecycle"]["completed_translation_ttl_ms"] = 1400
        self._config["subtitle_lifecycle"]["sync_source_and_translation_expiry"] = False

        await self.router.handle_transcript(
            TranscriptEvent(
                event="final",
                text="Поздний перевод",
                sequence=1,
                segment=TranscriptSegment(
                    segment_id="seg-late",
                    text="Поздний перевод",
                    is_final=True,
                    source_lang="ru",
                    provider="local",
                    sequence=1,
                ),
            )
        )

        payload_after_source_ttl = await self._wait_for_visible_texts([])
        self.assertEqual(payload_after_source_ttl["lifecycle_state"], "idle")

        await self.router.handle_translation(
            TranslationEvent(
                sequence=1,
                source_text="Поздний перевод",
                source_lang="ru",
                provider="google_translate_v2",
                translations=[
                    TranslationItem(
                        target_lang="en",
                        text="Late translation",
                        provider="google_translate_v2",
                        success=True,
                    )
                ],
                is_complete=False,
            )
        )

        payload_after_translation = await self._wait_for_visible_texts(["Late translation"])
        self.assertEqual(payload_after_translation["lifecycle_state"], "completed_only")
        self.assertTrue(payload_after_translation["completed_block_visible"])

    async def test_failed_target_counts_as_received_for_lifecycle(self) -> None:
        await self.router.handle_transcript(
            TranscriptEvent(
                event="final",
                text="Ошибка перевода",
                sequence=3,
                segment=TranscriptSegment(
                    segment_id="seg-failed-target",
                    text="Ошибка перевода",
                    is_final=True,
                    source_lang="ru",
                    provider="local",
                    sequence=3,
                ),
            )
        )

        await self.router.handle_translation(
            TranslationEvent(
                sequence=3,
                source_text="Ошибка перевода",
                source_lang="ru",
                provider="google_translate_v2",
                translations=[
                    TranslationItem(
                        target_lang="en",
                        text="",
                        provider="google_translate_v2",
                        cached=False,
                        success=False,
                        error="timeout",
                    )
                ],
                is_complete=False,
            )
        )

        self.assertTrue(self.router._records[3]["translation_received"])
        payload = self._last_payload()
        self.assertEqual(payload["lifecycle_state"], "completed_only")
        self.assertEqual([item["text"] for item in payload["visible_items"]], ["Ошибка перевода"])


if __name__ == "__main__":
    unittest.main()
