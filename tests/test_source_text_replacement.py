from __future__ import annotations

import unittest

from backend.core.source_text_replacement import (
    apply_replacement_rules,
    apply_source_text_replacement,
    apply_to_transcript_event,
    effective_replacement_pairs,
)
from backend.models import TranscriptEvent, TranscriptSegment


class SourceTextReplacementTests(unittest.TestCase):
    def test_effective_pairs_custom_overrides_builtin_key(self) -> None:
        cfg = {
            "source_text_replacement": {
                "enabled": True,
                "include_builtin": True,
                "case_insensitive": True,
                "whole_words": True,
                "pairs": [{"source": "fuck", "target": "[beep]"}],
            }
        }
        pairs = effective_replacement_pairs(cfg)
        by_source = {s: t for s, t in pairs}
        self.assertEqual(by_source.get("fuck"), "[beep]")

    def test_whole_word_does_not_touch_substrings(self) -> None:
        cfg = {
            "source_text_replacement": {
                "enabled": True,
                "include_builtin": False,
                "case_insensitive": True,
                "whole_words": True,
                "pairs": [{"source": "ass", "target": "X"}],
            }
        }
        self.assertEqual(apply_source_text_replacement("class", cfg), "class")

    def test_case_insensitive(self) -> None:
        cfg = {
            "source_text_replacement": {
                "enabled": True,
                "include_builtin": False,
                "case_insensitive": True,
                "whole_words": True,
                "pairs": [{"source": "bad", "target": "X"}],
            }
        }
        self.assertEqual(apply_source_text_replacement("BAD word", cfg), "X word")

    def test_longer_custom_match_first(self) -> None:
        pairs = [("bad phrase", "P"), ("bad", "B")]
        self.assertEqual(
            apply_replacement_rules("say bad phrase end", pairs, case_insensitive=False, whole_words=True),
            "say P end",
        )

    def test_apply_to_transcript_event_updates_segment(self) -> None:
        cfg = {
            "source_text_replacement": {
                "enabled": True,
                "include_builtin": False,
                "case_insensitive": True,
                "whole_words": True,
                "pairs": [{"source": "bad", "target": "X"}],
            }
        }
        event = TranscriptEvent(
            event="partial",
            text="bad text",
            sequence=3,
            segment=TranscriptSegment(
                segment_id="s1",
                text="bad text",
                is_partial=True,
                is_final=False,
                source_lang="en",
                provider="test",
                sequence=3,
                revision=0,
            ),
        )
        out = apply_to_transcript_event(event, cfg)
        self.assertEqual(out.text, "X text")
        self.assertIsNotNone(out.segment)
        self.assertEqual(out.segment.text, "X text")

    def test_disabled_returns_original(self) -> None:
        cfg = {"source_text_replacement": {"enabled": False, "pairs": [{"source": "bad", "target": "X"}]}}
        event = TranscriptEvent(event="partial", text="bad", sequence=1, segment=None)
        self.assertIs(apply_to_transcript_event(event, cfg), event)


if __name__ == "__main__":
    unittest.main()
