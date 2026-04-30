from __future__ import annotations

import unittest
from typing import Any

from backend.core.obs_caption_output import ObsCaptionOutput
from backend.models import SubtitleLineItem, SubtitlePayloadEvent


def _base_config() -> dict[str, Any]:
    return {
        "obs_closed_captions": {
            "enabled": True,
            "output_mode": "source_final_only",
            "connection": {"host": "127.0.0.1", "port": 4455, "password": ""},
            "debug_mirror": {"enabled": False, "input_name": "CC_DEBUG", "send_partials": True},
            "timing": {
                "send_partials": True,
                "partial_throttle_ms": 1000,
                "min_partial_delta_chars": 3,
                "final_replace_delay_ms": 0,
                "clear_after_ms": 2500,
                "avoid_duplicate_text": True,
            },
        }
    }


class RecordingObsCaptionOutput(ObsCaptionOutput):
    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        super().__init__(lambda: self._config)
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self._connected = True
        self._websocket = object()

    async def _wait_for_connection(self, timeout_seconds: float = 3.0) -> bool:
        _ = timeout_seconds
        return True

    async def _send_request(self, request_type: str, request_data: dict[str, Any]) -> None:
        self.requests.append((request_type, dict(request_data)))


def _payload() -> SubtitlePayloadEvent:
    items = [
        SubtitleLineItem(kind="source", lang="ru", label="RU", text="Привет", style_slot="source"),
        SubtitleLineItem(kind="translation", lang="en", label="EN", text="Hello", style_slot="translation_1"),
        SubtitleLineItem(kind="translation", lang="de", label="DE", text="Hallo", style_slot="translation_2"),
    ]
    return SubtitlePayloadEvent(
        sequence=1,
        source_lang="ru",
        source_text="Привет",
        display_order=["source", "en", "de"],
        show_source=True,
        show_translations=True,
        max_translation_languages=2,
        items=items,
        visible_items=items,
        lifecycle_state="completed_only",
        completed_block_visible=True,
        line1="Привет",
        line2="Hello\nHallo",
    )


def _payload_for_sequence(sequence: int, visible_items: list[SubtitleLineItem]) -> SubtitlePayloadEvent:
    return SubtitlePayloadEvent(
        sequence=sequence,
        source_lang="ru",
        source_text="Привет",
        display_order=["source", "en", "de"],
        show_source=True,
        show_translations=True,
        max_translation_languages=2,
        items=list(visible_items),
        visible_items=list(visible_items),
        lifecycle_state="completed_only",
        completed_block_visible=True,
        line1=visible_items[0].text if visible_items else "",
        line2="\n".join(item.text for item in visible_items[1:]) if len(visible_items) > 1 else "",
    )


class ObsCaptionOutputTests(unittest.IsolatedAsyncioTestCase):
    async def test_source_final_only_routes_final_caption_to_send_stream_caption(self) -> None:
        config = _base_config()
        output = RecordingObsCaptionOutput(config)

        await output._handle_source_final("  hello \n world ")

        self.assertEqual(output.requests, [("SendStreamCaption", {"captionText": "hello\nworld"})])

    async def test_translation_mode_selects_requested_visible_translation_and_dedups(self) -> None:
        config = _base_config()
        config["obs_closed_captions"]["output_mode"] = "translation_2"
        output = RecordingObsCaptionOutput(config)
        payload = _payload()

        await output._handle_payload(payload)
        await output._handle_payload(payload)

        self.assertEqual(output.requests, [("SendStreamCaption", {"captionText": "Hallo"})])

    async def test_translation_mode_skips_repeat_for_same_sequence_after_caption_clear(self) -> None:
        config = _base_config()
        config["obs_closed_captions"]["output_mode"] = "translation_1"
        output = RecordingObsCaptionOutput(config)
        initial_payload = _payload_for_sequence(
            7,
            [
                SubtitleLineItem(kind="source", lang="ru", label="RU", text="Привет", style_slot="source"),
                SubtitleLineItem(kind="translation", lang="en", label="EN", text="Hello", style_slot="translation_1"),
            ],
        )
        late_payload = _payload_for_sequence(
            7,
            [
                SubtitleLineItem(kind="source", lang="ru", label="RU", text="Привет", style_slot="source"),
                SubtitleLineItem(kind="translation", lang="en", label="EN", text="Hello", style_slot="translation_1"),
                SubtitleLineItem(kind="translation", lang="de", label="DE", text="Hallo", style_slot="translation_2"),
            ],
        )

        await output._handle_payload(initial_payload)
        output._last_caption_text = ""
        await output._handle_payload(late_payload)

        self.assertEqual(output.requests, [("SendStreamCaption", {"captionText": "Hello"})])

    async def test_translation_mode_allows_same_text_for_new_sequence(self) -> None:
        config = _base_config()
        config["obs_closed_captions"]["output_mode"] = "translation_1"
        output = RecordingObsCaptionOutput(config)
        first_payload = _payload_for_sequence(
            7,
            [
                SubtitleLineItem(kind="source", lang="ru", label="RU", text="Привет", style_slot="source"),
                SubtitleLineItem(kind="translation", lang="en", label="EN", text="Hello", style_slot="translation_1"),
            ],
        )
        second_payload = _payload_for_sequence(
            8,
            [
                SubtitleLineItem(kind="source", lang="ru", label="RU", text="Пока", style_slot="source"),
                SubtitleLineItem(kind="translation", lang="en", label="EN", text="Hello", style_slot="translation_1"),
            ],
        )

        await output._handle_payload(first_payload)
        output._last_caption_text = ""
        await output._handle_payload(second_payload)

        self.assertEqual(
            output.requests,
            [
                ("SendStreamCaption", {"captionText": "Hello"}),
                ("SendStreamCaption", {"captionText": "Hello"}),
            ],
        )

    async def test_source_live_partial_skips_duplicate_and_small_growth_within_throttle_window(self) -> None:
        config = _base_config()
        config["obs_closed_captions"]["output_mode"] = "source_live"
        output = RecordingObsCaptionOutput(config)

        await output._handle_source_partial("Hello")
        await output._handle_source_partial("Hello")
        await output._handle_source_partial("Hello!")

        self.assertEqual(output.requests, [("SendStreamCaption", {"captionText": "Hello"})])


if __name__ == "__main__":
    unittest.main()
