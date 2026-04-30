from __future__ import annotations

import asyncio
import unittest
from typing import Any

from backend.core.subtitle_router import SubtitleRouter
from backend.models import TranscriptEvent, TranscriptSegment, TranslationEvent, TranslationItem


def _config() -> dict[str, Any]:
    return {
        "source_lang": "ru",
        "translation": {
            "enabled": True,
            "target_languages": ["en", "de"],
        },
        "subtitle_output": {
            "show_source": True,
            "show_translations": True,
            "max_translation_languages": 2,
            "display_order": ["source", "en", "de"],
        },
        "overlay": {
            "preset": "stacked",
            "compact": False,
        },
        "subtitle_style": {},
        "subtitle_lifecycle": {
            "completed_block_ttl_ms": 1200,
            "completed_source_ttl_ms": 200,
            "completed_translation_ttl_ms": 900,
            "pause_to_finalize_ms": 700,
            "allow_early_replace_on_next_final": True,
            "sync_source_and_translation_expiry": False,
            "hard_max_phrase_ms": 12000,
        },
    }


class _WsManager:
    async def broadcast(self, message: dict[str, Any]) -> None:
        return None


class SubtitleLifecycleRelevanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.config = _config()
        self.router = SubtitleRouter(_WsManager(), config_getter=lambda: self.config)

    async def asyncTearDown(self) -> None:
        await self.router.reset()

    async def test_translation_relevance_keeps_still_visible_completed_translation(self) -> None:
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
                    provider="browser_google",
                    sequence=1,
                ),
            )
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
                        success=True,
                    )
                ],
                is_complete=False,
            )
        )

        await asyncio.sleep(0.6)

        self.assertTrue(self.router.is_sequence_relevant_for_translation(1))
        self.assertTrue(self.router.is_sequence_relevant_for_presentation(1))

        await self.router.handle_translation(
            TranslationEvent(
                sequence=1,
                source_text="Привет",
                source_lang="ru",
                provider="google_translate_v2",
                translations=[
                    TranslationItem(
                        target_lang="de",
                        text="Hallo",
                        provider="google_translate_v2",
                        success=True,
                    )
                ],
                is_complete=True,
            )
        )

    async def test_latest_final_stays_translation_relevant_after_source_ttl_until_translation_ttl(self) -> None:
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
                    provider="browser_google",
                    sequence=1,
                ),
            )
        )

        await asyncio.sleep(0.35)

        self.assertTrue(self.router.is_sequence_relevant_for_translation(1))
        self.assertTrue(self.router.is_sequence_relevant_for_presentation(1))


if __name__ == "__main__":
    unittest.main()
