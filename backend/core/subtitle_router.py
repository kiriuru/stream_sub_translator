from __future__ import annotations

import audioop
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from typing import Any, Awaitable, Callable, Literal

from backend.core.asr_engine import AsrEngine
from backend.core.cache_manager import CacheManager
from backend.core.audio_capture import AudioCapture, RNNoiseRecognitionProcessor
from backend.core.browser_asr_gateway import BrowserAsrGateway
from backend.core.exporter import Exporter
from backend.core.obs_caption_output import ObsCaptionOutput
from backend.core.overlay_broadcaster import OverlayBroadcaster
from backend.core.parakeet_provider import AsrProviderStatus
from backend.core.remote_mode import (
    REMOTE_ROLE_CONTROLLER,
    REMOTE_ROLE_WORKER,
    resolve_configured_remote_state,
    resolve_effective_remote_role,
)
from backend.core.segment_queue import AsrWorkItem, SegmentQueue
from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.core.subtitle_style import resolve_effective_subtitle_style
from backend.core.translation_dispatcher import TranslationDispatcher
from backend.core.translation_engine import TranslationEngine
from backend.core.vad import VadEngine
from backend.models import (
    AsrDiagnostics,
    ObsCaptionDiagnostics,
    RuntimeMetrics,
    RuntimeState,
    SubtitleLineItem,
    SubtitlePayloadEvent,
    TranscriptEvent,
    TranscriptSegment,
    TranslationDiagnostics,
    TranslationEvent,
    TranslationItem,
)
from backend.ws_manager import WebSocketManager


class SubtitleRouter:
    def __init__(
        self,
        ws_manager: WebSocketManager,
        config_getter: Callable[[], dict],
        completed_callback: Callable[[dict], None] | None = None,
        presentation_callback: Callable[[SubtitlePayloadEvent], Awaitable[None]] | None = None,
    ) -> None:
        self.ws_manager = ws_manager
        self.config_getter = config_getter
        self.completed_callback = completed_callback
        self.presentation_callback = presentation_callback
        self.overlay_broadcaster = OverlayBroadcaster(ws_manager)
        self._records: dict[int, dict] = {}
        self._active_partial: dict | None = None
        self._completed_sequence: int | None = None
        self._latest_final_sequence: int | None = None
        self._completed_expires_at_utc: str | None = None
        self._completed_expires_at_monotonic: float | None = None
        self._completed_source_expires_at_monotonic: float | None = None
        self._completed_translation_expires_at_monotonic: float | None = None
        self._pending_final_sequence: int | None = None
        self._expiry_task: asyncio.Task | None = None
        self._exported_sequences: set[int] = set()

    def _subtitle_lifecycle_config(self) -> dict:
        config = self.config_getter()
        lifecycle = config.get("subtitle_lifecycle", {}) if isinstance(config, dict) else {}
        if not isinstance(lifecycle, dict):
            lifecycle = {}
        completed_ttl_ms = max(500, int(lifecycle.get("completed_block_ttl_ms", 4500) or 4500))
        source_ttl_ms = max(500, int(lifecycle.get("completed_source_ttl_ms", completed_ttl_ms) or completed_ttl_ms))
        translation_ttl_ms = max(500, int(lifecycle.get("completed_translation_ttl_ms", completed_ttl_ms) or completed_ttl_ms))
        return {
            "completed_block_ttl_ms": max(source_ttl_ms, translation_ttl_ms),
            "completed_source_ttl_ms": source_ttl_ms,
            "completed_translation_ttl_ms": translation_ttl_ms,
            "pause_to_finalize_ms": max(120, int(lifecycle.get("pause_to_finalize_ms", 700) or 700)),
            "allow_early_replace_on_next_final": bool(lifecycle.get("allow_early_replace_on_next_final", True)),
            "sync_source_and_translation_expiry": bool(lifecycle.get("sync_source_and_translation_expiry", True)),
            "hard_max_phrase_ms": max(1000, int(lifecycle.get("hard_max_phrase_ms", 12000) or 12000)),
        }

    def _translation_required_for_display(self) -> bool:
        config = self.config_getter()
        translation_config = config.get("translation", {}) if isinstance(config, dict) else {}
        subtitle_output = config.get("subtitle_output", {}) if isinstance(config, dict) else {}
        if not isinstance(translation_config, dict) or not isinstance(subtitle_output, dict):
            return False
        target_languages = translation_config.get("target_languages", [])
        return bool(
            translation_config.get("enabled")
            and subtitle_output.get("show_translations", True)
            and int(subtitle_output.get("max_translation_languages", 0) or 0) > 0
            and isinstance(target_languages, list)
            and any(str(item).strip() for item in target_languages)
        )

    def _should_suppress_source_partial_display(self) -> bool:
        config = self.config_getter()
        subtitle_output = config.get("subtitle_output", {}) if isinstance(config, dict) else {}
        if not isinstance(subtitle_output, dict):
            return False
        return not bool(subtitle_output.get("show_source", True))

    async def reset(self) -> None:
        if self._expiry_task is not None:
            self._expiry_task.cancel()
            try:
                await self._expiry_task
            except asyncio.CancelledError:
                pass
            self._expiry_task = None
        self._records.clear()
        self._active_partial = None
        self._completed_sequence = None
        self._latest_final_sequence = None
        self._completed_expires_at_utc = None
        self._completed_expires_at_monotonic = None
        self._completed_source_expires_at_monotonic = None
        self._completed_translation_expires_at_monotonic = None
        self._pending_final_sequence = None
        self._exported_sequences.clear()
        await self._publish_current()

    async def handle_transcript(self, event: TranscriptEvent) -> None:
        if event.event == "partial":
            segment = event.segment
            self._active_partial = {
                "sequence": event.sequence,
                "text": event.text,
                "source_lang": segment.source_lang if segment is not None else self.config_getter().get("source_lang", "auto"),
                "provider": segment.provider if segment is not None else None,
            }
            await self._publish_current()
            return

        segment = event.segment
        duration_ms = None
        if segment is not None:
            if segment.start_ms is not None and segment.end_ms is not None:
                duration_ms = max(0, int(segment.end_ms) - int(segment.start_ms))
            elif segment.end_ms is not None:
                duration_ms = int(segment.end_ms)
        self._records[event.sequence] = {
            "sequence": event.sequence,
            "source_text": event.text,
            "source_lang": segment.source_lang if segment is not None else self.config_getter().get("source_lang", "auto"),
            "translations": {},
            "provider": segment.provider if segment is not None else None,
            "translation_received": not self._translation_required_for_display(),
            "duration_ms": duration_ms,
            "finalized_at_utc": datetime.now(timezone.utc).isoformat(),
            "finalized_at_monotonic": time.perf_counter(),
        }
        self._active_partial = {
            "sequence": event.sequence,
            "text": event.text,
            "source_lang": segment.source_lang if segment is not None else self.config_getter().get("source_lang", "auto"),
            "provider": segment.provider if segment is not None else None,
        }
        self._pending_final_sequence = event.sequence
        if self._latest_final_sequence is None or event.sequence > self._latest_final_sequence:
            self._latest_final_sequence = event.sequence
        self._promote_or_defer(event.sequence)
        await self._publish_current()

    async def handle_translation(self, event: TranslationEvent) -> None:
        record = self._records.get(event.sequence)
        if record is None:
            record = {
                "sequence": event.sequence,
                "source_text": event.source_text,
                "source_lang": event.source_lang,
                "translations": {},
                "provider": event.provider,
                "translation_received": True,
                "duration_ms": None,
                "finalized_at_utc": None,
                "finalized_at_monotonic": None,
            }
            self._records[event.sequence] = record

        record["source_text"] = event.source_text
        record["source_lang"] = event.source_lang
        record["provider"] = event.provider
        translations = dict(record.get("translations", {}))
        for item in event.translations:
            translations[item.target_lang] = {
                "text": item.text,
                "success": item.success,
                "error": item.error,
            }
        record["translations"] = translations
        config = self.config_getter()
        translation_config = config.get("translation", {}) if isinstance(config, dict) else {}
        target_languages = [
            str(item).strip().lower()
            for item in translation_config.get("target_languages", [])
            if str(item).strip()
        ] if isinstance(translation_config, dict) else []
        received_targets = {str(item).strip().lower() for item in translations.keys() if str(item).strip()}
        record["translation_received"] = bool(
            event.is_complete
            or not target_languages
            or all(target_lang in received_targets for target_lang in target_languages)
        )
        was_exported = event.sequence in self._exported_sequences
        should_promote = (
            self._pending_final_sequence == event.sequence
            or self._completed_sequence == event.sequence
            or (
                self._pending_final_sequence is None
                and self._completed_sequence is None
                and self._latest_final_sequence == event.sequence
            )
        )
        if should_promote:
            self._promote_or_defer(event.sequence)
        if was_exported and self._completed_sequence == event.sequence and self.completed_callback is not None:
            payload = self._promotion_payload(event.sequence)
            if payload is not None and payload.visible_items:
                export_record = self._build_export_record(event.sequence, payload)
                if export_record is not None:
                    self.completed_callback(export_record)
        await self._publish_current()

    def _build_payload(self, sequence: int) -> SubtitlePayloadEvent | None:
        record = self._records.get(sequence)
        if record is None:
            return None

        config = self.config_getter()
        translation_config = config.get("translation", {})
        subtitle_output = config.get("subtitle_output", {})
        overlay = config.get("overlay", {})
        subtitle_style = resolve_effective_subtitle_style(config.get("subtitle_style", {}))

        show_source = bool(subtitle_output.get("show_source", True))
        show_translations = bool(subtitle_output.get("show_translations", True))
        max_translation_languages = max(0, min(5, int(subtitle_output.get("max_translation_languages", 0) or 0)))
        display_order = [
            str(item).lower()
            for item in subtitle_output.get("display_order", ["source", *translation_config.get("target_languages", [])])
        ]
        target_languages = [str(item).lower() for item in translation_config.get("target_languages", [])]
        items: list[SubtitleLineItem] = []
        visible_items: list[SubtitleLineItem] = []
        visible_translation_count = 0

        for code in display_order:
            if code == "source":
                source_item = SubtitleLineItem(
                    kind="source",
                    lang=str(record["source_lang"]),
                    label=str(record["source_lang"]).upper(),
                    text=str(record["source_text"]),
                    style_slot="source",
                    visible=show_source,
                )
                items.append(source_item)
                if source_item.visible and source_item.text:
                    visible_items.append(source_item)
                continue

            if code not in target_languages:
                continue

            translation = record["translations"].get(code)
            success = bool(translation and translation.get("success", False))
            text = str(translation.get("text", "")) if translation else ""
            error = str(translation.get("error")) if translation and translation.get("error") else None
            next_translation_slot = (
                f"translation_{visible_translation_count + 1}"
                if visible_translation_count < 5
                else None
            )
            can_show = show_translations and visible_translation_count < max_translation_languages and success and bool(text)
            item = SubtitleLineItem(
                kind="translation",
                lang=code,
                label=code.upper(),
                text=text,
                style_slot=next_translation_slot if can_show else None,
                visible=can_show,
                success=success,
                error=error,
            )
            items.append(item)
            if can_show:
                visible_items.append(item)
                visible_translation_count += 1

        line1 = visible_items[0].text if len(visible_items) > 0 else ""
        line2 = "\n".join(item.text for item in visible_items[1:]) if len(visible_items) > 1 else ""

        return SubtitlePayloadEvent(
            sequence=sequence,
            source_lang=str(record["source_lang"]),
            source_text=str(record["source_text"]),
            provider=record["provider"],
            preset=str(overlay.get("preset", "single")),
            compact=bool(overlay.get("compact", False)),
            display_order=display_order,
            show_source=show_source,
            show_translations=show_translations,
            max_translation_languages=max_translation_languages,
            items=items,
            visible_items=visible_items,
            style=subtitle_style,
            line1=line1,
            line2=line2,
        )

    def _completed_source_visible(self, now_monotonic: float | None = None) -> bool:
        if self._completed_sequence is None:
            return False
        if self._completed_source_expires_at_monotonic is None:
            return True
        current = now_monotonic if now_monotonic is not None else time.perf_counter()
        return current < self._completed_source_expires_at_monotonic

    def _completed_translation_visible(self, now_monotonic: float | None = None) -> bool:
        if self._completed_sequence is None:
            return False
        if self._completed_translation_expires_at_monotonic is None:
            return True
        current = now_monotonic if now_monotonic is not None else time.perf_counter()
        return current < self._completed_translation_expires_at_monotonic

    def _source_ttl_expired_for_sequence(self, sequence: int, now_monotonic: float | None = None) -> bool:
        record = self._records.get(sequence)
        if record is None:
            return False
        finalized_at_monotonic = record.get("finalized_at_monotonic")
        if not isinstance(finalized_at_monotonic, (int, float)):
            return False
        lifecycle = self._subtitle_lifecycle_config()
        current = now_monotonic if now_monotonic is not None else time.perf_counter()
        source_expiry_monotonic = float(finalized_at_monotonic) + (int(lifecycle["completed_source_ttl_ms"]) / 1000.0)
        return current >= source_expiry_monotonic

    def _translation_ttl_expired_for_sequence(self, sequence: int, now_monotonic: float | None = None) -> bool:
        record = self._records.get(sequence)
        if record is None:
            return False
        finalized_at_monotonic = record.get("finalized_at_monotonic")
        if not isinstance(finalized_at_monotonic, (int, float)):
            return False
        lifecycle = self._subtitle_lifecycle_config()
        current = now_monotonic if now_monotonic is not None else time.perf_counter()
        translation_expiry_monotonic = float(finalized_at_monotonic) + (int(lifecycle["completed_translation_ttl_ms"]) / 1000.0)
        return current >= translation_expiry_monotonic

    def _sequence_awaits_translation(self, sequence: int | None) -> bool:
        if sequence is None or not self._translation_required_for_display():
            return False
        record = self._records.get(sequence)
        if record is None:
            return False
        if bool(record.get("translation_received")):
            return False
        # Do not let an invisible stale source block newer finalized captions forever.
        if self._source_ttl_expired_for_sequence(sequence):
            return False
        return True

    def _sequence_can_accept_late_translation(self, sequence: int | None) -> bool:
        if sequence is None or not self._translation_required_for_display():
            return False
        record = self._records.get(sequence)
        if record is None:
            return False
        if bool(record.get("translation_received")):
            return False
        if self._translation_ttl_expired_for_sequence(sequence):
            return False
        return True

    def is_sequence_relevant_for_presentation(self, sequence: int) -> bool:
        if sequence not in self._records:
            return False
        if self._pending_final_sequence == sequence:
            return True
        if self._completed_sequence == sequence:
            if self._current_completed_payload() is not None:
                return True
            return self._sequence_can_accept_late_translation(sequence)
        if (
            self._completed_sequence is None
            and self._pending_final_sequence is None
            and self._latest_final_sequence == sequence
        ):
            payload = self._promotion_payload(sequence)
            return payload is not None and bool(payload.visible_items)
        return False

    def is_sequence_relevant_for_translation(self, sequence: int) -> bool:
        if sequence not in self._records:
            return False
        if self.is_sequence_relevant_for_presentation(sequence):
            return True
        if self._pending_final_sequence == sequence:
            return True
        if self._completed_sequence == sequence and self._sequence_awaits_translation(sequence):
            return True
        if self._latest_final_sequence == sequence and self._sequence_can_accept_late_translation(sequence):
            return True
        return False

    def _promotion_payload(self, sequence: int) -> SubtitlePayloadEvent | None:
        payload = self._build_payload(sequence)
        if payload is None:
            return None
        if (
            self._pending_final_sequence is None
            and self._latest_final_sequence == sequence
            and self._source_ttl_expired_for_sequence(sequence)
            and (self._completed_sequence is None or self._completed_sequence == sequence)
        ):
            remapped_items: list[SubtitleLineItem] = []
            remapped_visible: list[SubtitleLineItem] = []
            for item in payload.items:
                should_show = item.visible and bool(item.text) and item.kind != "source"
                updated_item = item.model_copy(
                    update={
                        "visible": should_show,
                        "style_slot": item.style_slot if should_show else None,
                    }
                )
                remapped_items.append(updated_item)
                if updated_item.visible and updated_item.text:
                    remapped_visible.append(updated_item)
            if not remapped_visible:
                return None
            line1 = remapped_visible[0].text if remapped_visible else ""
            line2 = "\n".join(item.text for item in remapped_visible[1:]) if len(remapped_visible) > 1 else ""
            return payload.model_copy(
                update={
                    "items": remapped_items,
                    "visible_items": remapped_visible,
                    "line1": line1,
                    "line2": line2,
                }
            )
        return payload

    def _current_completed_payload(self, *, hide_source: bool = False) -> SubtitlePayloadEvent | None:
        if self._completed_sequence is None:
            return None

        payload = self._build_payload(self._completed_sequence)
        if payload is None:
            return None

        now_monotonic = time.perf_counter()
        source_visible = self._completed_source_visible(now_monotonic) and not hide_source
        translation_visible = self._completed_translation_visible(now_monotonic)

        remapped_items: list[SubtitleLineItem] = []
        remapped_visible: list[SubtitleLineItem] = []
        for item in payload.items:
            should_show = item.visible and bool(item.text)
            if item.kind == "source":
                should_show = should_show and source_visible
            else:
                should_show = should_show and translation_visible
            updated_item = item.model_copy(
                update={
                    "visible": should_show,
                    "style_slot": item.style_slot if should_show else None,
                }
            )
            remapped_items.append(updated_item)
            if updated_item.visible and updated_item.text:
                remapped_visible.append(updated_item)

        if not remapped_visible:
            return None

        line1 = remapped_visible[0].text if remapped_visible else ""
        line2 = "\n".join(item.text for item in remapped_visible[1:]) if len(remapped_visible) > 1 else ""
        return payload.model_copy(
            update={
                "items": remapped_items,
                "visible_items": remapped_visible,
                "line1": line1,
                "line2": line2,
            }
        )

    def _can_promote(self, sequence: int) -> SubtitlePayloadEvent | None:
        record = self._records.get(sequence)
        if record is None:
            return None
        payload = self._promotion_payload(sequence)
        if payload is None or not payload.visible_items:
            return None
        return payload

    def _promote_or_defer(self, sequence: int) -> None:
        payload = self._can_promote(sequence)
        if payload is None:
            self._pending_final_sequence = sequence
            return

        lifecycle = self._subtitle_lifecycle_config()
        if (
            self._completed_sequence is not None
            and self._completed_sequence != sequence
            and self._sequence_awaits_translation(self._completed_sequence)
        ):
            self._pending_final_sequence = sequence
            return
        if (
            self._completed_sequence is not None
            and self._completed_sequence != sequence
            and not lifecycle["allow_early_replace_on_next_final"]
        ):
            self._pending_final_sequence = sequence
            return

        preserved_pending_sequence = (
            self._pending_final_sequence
            if self._pending_final_sequence is not None and self._pending_final_sequence != sequence
            else None
        )
        self._completed_sequence = sequence
        self._pending_final_sequence = preserved_pending_sequence
        if self._active_partial and int(self._active_partial.get("sequence", -1)) == sequence:
            self._active_partial = None
        self._schedule_expiry(payload)
        if sequence not in self._exported_sequences:
            self._exported_sequences.add(sequence)
            export_record = self._build_export_record(sequence, payload)
            if export_record is not None and self.completed_callback is not None:
                self.completed_callback(export_record)

    def _build_export_record(self, sequence: int, payload: SubtitlePayloadEvent) -> dict[str, object] | None:
        record = self._records.get(sequence)
        if record is None:
            return None

        visible_items = [item.model_dump() for item in payload.visible_items]
        srt_text = "\n".join(item["text"] for item in visible_items if str(item.get("text", "")).strip())
        return {
            "type": "subtitle_record",
            "sequence": sequence,
            "source_text": str(record.get("source_text", "")),
            "source_lang": str(record.get("source_lang", "auto")),
            "provider": record.get("provider"),
            "duration_ms": record.get("duration_ms"),
            "finalized_at_utc": record.get("finalized_at_utc"),
            "finalized_at_monotonic": record.get("finalized_at_monotonic"),
            "translation_received": bool(record.get("translation_received")),
            "translations": dict(record.get("translations", {})),
            "display_order": list(payload.display_order),
            "items": [item.model_dump() for item in payload.items],
            "visible_items": visible_items,
            "srt_text": srt_text,
        }

    def _schedule_expiry(self, payload: SubtitlePayloadEvent | None = None) -> None:
        if self._expiry_task is not None:
            self._expiry_task.cancel()
            self._expiry_task = None

        if self._completed_sequence is None:
            self._completed_expires_at_utc = None
            self._completed_expires_at_monotonic = None
            self._completed_source_expires_at_monotonic = None
            self._completed_translation_expires_at_monotonic = None
            return

        payload = payload or self._build_payload(self._completed_sequence)
        lifecycle = self._subtitle_lifecycle_config()
        visible_items = list(payload.visible_items) if payload is not None else []
        has_visible_source = any(item.kind == "source" and item.visible and item.text for item in visible_items)
        has_visible_translation = any(item.kind == "translation" and item.visible and item.text for item in visible_items)

        now_monotonic = time.perf_counter()
        now_utc = datetime.now(timezone.utc)
        source_ttl_ms = int(lifecycle["completed_source_ttl_ms"])
        translation_ttl_ms = int(lifecycle["completed_translation_ttl_ms"])
        if lifecycle["sync_source_and_translation_expiry"] and has_visible_translation:
            source_ttl_ms = max(source_ttl_ms, translation_ttl_ms)

        self._completed_source_expires_at_monotonic = (
            now_monotonic + (source_ttl_ms / 1000.0) if has_visible_source else now_monotonic - 0.001
        )
        self._completed_translation_expires_at_monotonic = (
            now_monotonic + (translation_ttl_ms / 1000.0) if has_visible_translation else now_monotonic - 0.001
        )
        self._schedule_next_expiry_check(now_monotonic=now_monotonic, now_utc=now_utc)

    def _schedule_next_expiry_check(
        self,
        *,
        now_monotonic: float | None = None,
        now_utc: datetime | None = None,
    ) -> None:
        expiry_points = [
            point
            for point in (
                self._completed_source_expires_at_monotonic,
                self._completed_translation_expires_at_monotonic,
            )
            if point is not None and point > (now_monotonic if now_monotonic is not None else time.perf_counter())
        ]
        if not expiry_points:
            self._completed_expires_at_utc = None
            self._completed_expires_at_monotonic = None
            self._expiry_task = None
            return

        current_monotonic = now_monotonic if now_monotonic is not None else time.perf_counter()
        current_utc = now_utc if now_utc is not None else datetime.now(timezone.utc)
        self._completed_expires_at_monotonic = max(expiry_points)
        self._completed_expires_at_utc = (
            current_utc + timedelta(milliseconds=int(round((self._completed_expires_at_monotonic - current_monotonic) * 1000.0)))
        ).isoformat()
        loop = asyncio.get_running_loop()
        next_check_monotonic = min(expiry_points)
        sequence = self._completed_sequence
        self._expiry_task = loop.create_task(self._expire_completed_after(sequence, next_check_monotonic))

    async def _expire_completed_after(self, sequence: int, check_monotonic: float) -> None:
        try:
            sleep_seconds = max(0.0, check_monotonic - time.perf_counter())
            await asyncio.sleep(sleep_seconds)
            if self._completed_sequence != sequence:
                return
            self._expiry_task = None

            if self._current_completed_payload() is not None:
                self._schedule_next_expiry_check()
                await self._publish_current()
                return

            self._completed_sequence = None
            self._completed_expires_at_monotonic = None
            self._completed_expires_at_utc = None
            self._completed_source_expires_at_monotonic = None
            self._completed_translation_expires_at_monotonic = None
            if self._pending_final_sequence is not None:
                self._promote_or_defer(self._pending_final_sequence)
            await self._publish_current()
        except asyncio.CancelledError:
            raise

    def _build_partial_plus_completed_payload(
        self,
        *,
        completed_payload: SubtitlePayloadEvent,
        active_partial_text: str,
        active_partial_sequence: int | None,
        active_partial_source_lang: str | None,
    ) -> SubtitlePayloadEvent:
        config = self.config_getter()
        subtitle_output = config.get("subtitle_output", {}) if isinstance(config, dict) else {}
        translation_config = config.get("translation", {}) if isinstance(config, dict) else {}
        show_source = bool(subtitle_output.get("show_source", True)) if isinstance(subtitle_output, dict) else True
        show_translations = bool(subtitle_output.get("show_translations", True)) if isinstance(subtitle_output, dict) else True
        max_translation_languages = (
            max(0, min(5, int(subtitle_output.get("max_translation_languages", 0) or 0)))
            if isinstance(subtitle_output, dict)
            else 0
        )
        display_order = [
            str(item).lower()
            for item in subtitle_output.get(
                "display_order",
                ["source", *translation_config.get("target_languages", [])] if isinstance(translation_config, dict) else ["source"],
            )
        ] if isinstance(subtitle_output, dict) else list(completed_payload.display_order)
        target_languages = [
            str(item).lower()
            for item in translation_config.get("target_languages", [])
        ] if isinstance(translation_config, dict) else []
        active_source_lang = active_partial_source_lang or completed_payload.source_lang
        source_item = SubtitleLineItem(
            kind="source",
            lang=str(active_source_lang),
            label=str(active_source_lang).upper(),
            text=active_partial_text,
            style_slot="source" if show_source and active_partial_text else None,
            visible=show_source and bool(active_partial_text),
        )

        items: list[SubtitleLineItem] = []
        visible_items: list[SubtitleLineItem] = []
        visible_translation_count = 0
        for code in display_order:
            if code == "source":
                items.append(source_item)
                if source_item.visible and source_item.text:
                    visible_items.append(source_item)
                continue

            if code not in target_languages:
                continue

            translation_item = next(
                (
                    item
                    for item in completed_payload.items
                    if item.kind == "translation" and item.lang == code
                ),
                None,
            )
            if translation_item is None:
                continue
            can_show = (
                show_translations
                and visible_translation_count < max_translation_languages
                and bool(translation_item.success)
                and bool(translation_item.text)
            )
            next_translation_slot = f"translation_{visible_translation_count + 1}" if can_show else None
            updated_translation_item = translation_item.model_copy(
                update={
                    "visible": can_show,
                    "style_slot": next_translation_slot,
                }
            )
            items.append(updated_translation_item)
            if updated_translation_item.visible and updated_translation_item.text:
                visible_items.append(updated_translation_item)
                visible_translation_count += 1

        line1 = visible_items[0].text if visible_items else ""
        line2 = "\n".join(item.text for item in visible_items[1:]) if len(visible_items) > 1 else ""
        return completed_payload.model_copy(
            update={
                "sequence": active_partial_sequence or completed_payload.sequence,
                "source_text": active_partial_text,
                "source_lang": str(active_source_lang),
                "provider": str(self._active_partial.get("provider")) if self._active_partial and self._active_partial.get("provider") else completed_payload.provider,
                "display_order": display_order,
                "show_source": show_source,
                "show_translations": show_translations,
                "max_translation_languages": max_translation_languages,
                "items": items,
                "visible_items": visible_items,
                "line1": line1,
                "line2": line2,
            }
        )

    def _build_presentation_payload(self) -> SubtitlePayloadEvent:
        completed_payload = self._current_completed_payload()
        active_partial_text = str(self._active_partial.get("text", "")) if self._active_partial else ""
        active_partial_sequence = int(self._active_partial["sequence"]) if self._active_partial and self._active_partial.get("sequence") is not None else None
        active_partial_source_lang = str(self._active_partial.get("source_lang", "auto")) if self._active_partial else None
        display_partial_source = not self._should_suppress_source_partial_display()
        visible_partial_text = active_partial_text if display_partial_source else ""
        completed_translation_payload = self._current_completed_payload(hide_source=True) if active_partial_text else completed_payload

        if active_partial_text and completed_translation_payload is not None:
            lifecycle_state: Literal["idle", "partial_only", "completed_only", "completed_with_partial"] = "completed_with_partial"
        elif active_partial_text:
            lifecycle_state = "partial_only"
        elif completed_payload is not None:
            lifecycle_state = "completed_only"
        else:
            lifecycle_state = "idle"

        config = self.config_getter()
        overlay = config.get("overlay", {}) if isinstance(config, dict) else {}
        translation_config = config.get("translation", {}) if isinstance(config, dict) else {}
        subtitle_output = config.get("subtitle_output", {}) if isinstance(config, dict) else {}
        display_order = [
            str(item).lower()
            for item in subtitle_output.get("display_order", ["source", *translation_config.get("target_languages", [])])
        ] if isinstance(subtitle_output, dict) and isinstance(translation_config, dict) else []
        if active_partial_text and completed_payload is None:
            return SubtitlePayloadEvent(
                sequence=active_partial_sequence or 0,
                source_lang=active_partial_source_lang or str(config.get("source_lang", "auto")) if isinstance(config, dict) else "auto",
                source_text=active_partial_text,
                provider=str(self._active_partial.get("provider")) if self._active_partial and self._active_partial.get("provider") else None,
                preset=str(overlay.get("preset", "single")) if isinstance(overlay, dict) else "single",
                compact=bool(overlay.get("compact", False)) if isinstance(overlay, dict) else False,
                display_order=display_order,
                show_source=bool(subtitle_output.get("show_source", True)) if isinstance(subtitle_output, dict) else True,
                show_translations=bool(subtitle_output.get("show_translations", True)) if isinstance(subtitle_output, dict) else True,
                max_translation_languages=max(0, min(5, int(subtitle_output.get("max_translation_languages", 0) or 0))) if isinstance(subtitle_output, dict) else 0,
                style=resolve_effective_subtitle_style(config.get("subtitle_style", {}) if isinstance(config, dict) else {}),
                lifecycle_state=lifecycle_state,
                completed_block_visible=False,
                completed_expires_at_utc=self._completed_expires_at_utc,
                active_partial_text=visible_partial_text,
                active_partial_sequence=active_partial_sequence,
                active_partial_source_lang=active_partial_source_lang,
                line1=visible_partial_text,
                line2="",
            )

        if completed_translation_payload is not None and active_partial_text:
            payload_for_display = self._build_partial_plus_completed_payload(
                completed_payload=completed_translation_payload,
                active_partial_text=active_partial_text,
                active_partial_sequence=active_partial_sequence,
                active_partial_source_lang=active_partial_source_lang,
            )
            return payload_for_display.model_copy(
                update={
                    "lifecycle_state": lifecycle_state,
                    "completed_block_visible": bool(payload_for_display.visible_items),
                    "completed_expires_at_utc": self._completed_expires_at_utc,
                    "active_partial_text": visible_partial_text,
                    "active_partial_sequence": active_partial_sequence,
                    "active_partial_source_lang": active_partial_source_lang,
                }
            )

        if completed_payload is not None:
            return completed_payload.model_copy(
                update={
                    "lifecycle_state": lifecycle_state,
                    "completed_block_visible": bool(completed_payload.visible_items),
                    "completed_expires_at_utc": self._completed_expires_at_utc,
                    "active_partial_text": visible_partial_text,
                    "active_partial_sequence": active_partial_sequence,
                    "active_partial_source_lang": active_partial_source_lang,
                }
            )

        return SubtitlePayloadEvent(
            sequence=0,
            source_lang=active_partial_source_lang or str(config.get("source_lang", "auto")) if isinstance(config, dict) else "auto",
            source_text="",
            provider=str(self._active_partial.get("provider")) if self._active_partial and self._active_partial.get("provider") else None,
            preset=str(overlay.get("preset", "single")) if isinstance(overlay, dict) else "single",
            compact=bool(overlay.get("compact", False)) if isinstance(overlay, dict) else False,
            display_order=display_order,
            show_source=bool(subtitle_output.get("show_source", True)) if isinstance(subtitle_output, dict) else True,
            show_translations=bool(subtitle_output.get("show_translations", True)) if isinstance(subtitle_output, dict) else True,
            max_translation_languages=max(0, min(5, int(subtitle_output.get("max_translation_languages", 0) or 0))) if isinstance(subtitle_output, dict) else 0,
            style=resolve_effective_subtitle_style(config.get("subtitle_style", {}) if isinstance(config, dict) else {}),
            lifecycle_state=lifecycle_state,
            completed_block_visible=False,
            completed_expires_at_utc=None,
            active_partial_text=visible_partial_text,
            active_partial_sequence=active_partial_sequence,
            active_partial_source_lang=active_partial_source_lang,
            line1=visible_partial_text,
            line2="",
        )

    async def _publish_current(self) -> None:
        payload = self._build_presentation_payload()
        await self.ws_manager.broadcast({"type": "subtitle_payload_update", "payload": payload.model_dump()})
        await self.overlay_broadcaster.publish(payload)
        if self.presentation_callback is not None:
            await self.presentation_callback(payload)

    async def republish_latest(self) -> None:
        if self._pending_final_sequence is not None:
            self._promote_or_defer(self._pending_final_sequence)
        await self._publish_current()

    async def clear_active_partial(self) -> None:
        if self._active_partial is None:
            return
        self._active_partial = None
        await self._publish_current()


class RuntimeOrchestrator:
    _SHORT_HALLUCINATION_TOKENS = {
        "yeah",
        "yeah.",
        "mm-hmm",
        "mm-hmm.",
        "mhm",
        "mhm.",
        "uh-huh",
        "uh-huh.",
        "okay",
        "okay.",
        "ok",
        "ok.",
        "hmm",
        "hmm.",
        "uh",
        "uh.",
        "ah",
        "ah.",
        "yep",
        "yep.",
        "nope",
        "nope.",
    }
    _LEGACY_VAD_SETTINGS = {
        "vad_mode": 2,
        "energy_gate_enabled": False,
        "min_rms_for_recognition": 0.0018,
        "min_voiced_ratio": 0.0,
        "first_partial_min_speech_ms": 180,
        "partial_emit_interval_ms": 450,
        "min_speech_ms": 180,
        "max_segment_ms": 5500,
        "silence_hold_ms": 180,
        "finalization_hold_ms": 350,
        "chunk_window_ms": 0,
        "chunk_overlap_ms": 0,
        "partial_min_delta_chars": 12,
        "partial_coalescing_ms": 160,
    }

    def __init__(
        self,
        ws_manager: WebSocketManager,
        *,
        config_getter: Callable[[], dict],
        cache_manager: CacheManager,
        export_dir: Path,
        models_dir: Path,
        structured_logger: StructuredRuntimeLogger | None = None,
    ) -> None:
        self.ws_manager = ws_manager
        self.config_getter = config_getter
        self._obs_caption_output = ObsCaptionOutput(config_getter)
        self.subtitle_router = SubtitleRouter(
            ws_manager,
            config_getter,
            completed_callback=self._handle_completed_export_record,
            presentation_callback=self._handle_obs_caption_payload,
        )
        self._state = RuntimeState()
        self._audio_capture: AudioCapture | None = None
        self._vad = VadEngine()
        self._segment_queue = SegmentQueue()
        self._runtime_loop: asyncio.AbstractEventLoop | None = None
        self._latest_runtime_status_message: str | None = None
        self._asr_engine = AsrEngine(
            models_dir=models_dir,
            config_getter=config_getter,
            runtime_status_callback=self._emit_asr_runtime_status,
        )
        self._translation_engine = TranslationEngine(cache_manager)
        self._exporter = Exporter(export_dir)
        self._structured_runtime_logger = structured_logger
        self._capture_task: asyncio.Task | None = None
        self._asr_task: asyncio.Task | None = None
        self._remote_audio_queue: asyncio.Queue[bytes] | None = None
        self._device_id: str | None = None
        self._sequence = 0
        self._segment_counter = 0
        self._active_segment_id: str | None = None
        self._active_segment_revision = 0
        self._metrics = RuntimeMetrics()
        self._effective_realtime_settings = dict(self._LEGACY_VAD_SETTINGS)
        self._effective_subtitle_lifecycle_settings = {
            "completed_block_ttl_ms": 4500,
            "completed_source_ttl_ms": 4500,
            "completed_translation_ttl_ms": 4500,
            "pause_to_finalize_ms": self._LEGACY_VAD_SETTINGS["finalization_hold_ms"],
            "allow_early_replace_on_next_final": True,
            "sync_source_and_translation_expiry": True,
            "hard_max_phrase_ms": self._LEGACY_VAD_SETTINGS["max_segment_ms"],
        }
        self._session_id: str | None = None
        self._session_started_at_utc: str | None = None
        self._session_started_at_monotonic: float | None = None
        self._session_export_records: list[dict[str, object]] = []
        self._rnnoise_processor = RNNoiseRecognitionProcessor(sample_rate=self._asr_engine.sample_rate, channels=1)
        self._last_partial_text_by_segment: dict[str, str] = {}
        self._last_partial_emit_monotonic_by_segment: dict[str, float] = {}
        self._external_worker_connected = False
        self._browser_asr_gateway = BrowserAsrGateway(structured_logger=structured_logger)
        self._active_runtime_mode: str | None = None
        self._remote_audio_connected = False
        self._remote_audio_session_id: str | None = None
        self._remote_audio_last_chunk_monotonic: float | None = None
        self._translation_dispatcher_snapshot: dict[str, Any] = {}
        self._translation_dispatcher = TranslationDispatcher(
            self._translation_engine,
            self.config_getter,
            self._publish_translation_dispatch_event,
            self.subtitle_router.is_sequence_relevant_for_translation,
            self._apply_translation_dispatcher_metrics,
            structured_logger=structured_logger,
        )
        self._apply_vad_tuning()
        self._apply_recognition_processing_settings()
        self._translation_engine.apply_live_settings(self.config_getter().get("translation", {}))

    def _emit_asr_runtime_status(self, message: str) -> None:
        normalized = str(message or "").strip()
        if not normalized:
            return
        if normalized == self._latest_runtime_status_message:
            return
        self._latest_runtime_status_message = normalized
        loop = self._runtime_loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self._apply_runtime_status_message(normalized))
        )

    async def _apply_runtime_status_message(self, message: str) -> None:
        if self._state.status not in {"starting", "listening", "transcribing", "translating"}:
            return
        self._state = self._state.model_copy(update={"status_message": message})
        await self._broadcast_runtime()

    def _current_asr_mode(self) -> str:
        if self._state.is_running and self._active_runtime_mode in {"local", "browser_google"}:
            return str(self._active_runtime_mode)
        config = self.config_getter()
        asr = config.get("asr", {}) if isinstance(config, dict) else {}
        if not isinstance(asr, dict):
            return "local"
        mode = str(asr.get("mode", "local")).strip().lower()
        return mode if mode in {"local", "browser_google"} else "local"

    def _browser_asr_config(self) -> dict[str, object]:
        config = self.config_getter()
        asr = config.get("asr", {}) if isinstance(config, dict) else {}
        browser = asr.get("browser", {}) if isinstance(asr, dict) else {}
        return browser if isinstance(browser, dict) else {}

    def _browser_asr_source_lang(self) -> str:
        language = str(self._browser_asr_config().get("recognition_language", "ru-RU") or "ru-RU").strip()
        primary = language.split("-", 1)[0].strip().lower()
        return primary or "auto"

    def _current_remote_role(self) -> str:
        try:
            return resolve_effective_remote_role(self.config_getter())
        except Exception:
            return "disabled"

    def _uses_remote_audio_source(self) -> bool:
        return self._current_asr_mode() != "browser_google" and self._current_remote_role() == REMOTE_ROLE_WORKER

    def _is_remote_enabled(self) -> bool:
        enabled, _ = resolve_configured_remote_state(self.config_getter())
        return enabled

    def _uses_remote_event_source(self) -> bool:
        return (
            self._current_asr_mode() != "browser_google"
            and self._is_remote_enabled()
            and self._current_remote_role() == REMOTE_ROLE_CONTROLLER
        )

    async def _broadcast_runtime(self) -> None:
        await self.ws_manager.broadcast({"type": "runtime_update", "payload": self._state.model_dump()})

    async def _broadcast_transcript(self, event: TranscriptEvent) -> None:
        await self.ws_manager.broadcast({"type": "transcript_update", "payload": event.model_dump()})

    async def _broadcast_transcript_segment_event(self, event: TranscriptEvent) -> None:
        await self.ws_manager.broadcast({"type": "transcript_segment_event", "payload": event.model_dump()})

    async def _broadcast_translation(self, event: TranslationEvent) -> None:
        await self.ws_manager.broadcast({"type": "translation_update", "payload": event.model_dump()})

    async def _publish_translation_dispatch_event(self, event: TranslationEvent) -> None:
        await self.subtitle_router.handle_translation(event)
        if self.subtitle_router.is_sequence_relevant_for_presentation(event.sequence):
            await self._broadcast_translation(event)
        await self._broadcast_runtime()

    async def _handle_obs_caption_payload(self, payload: SubtitlePayloadEvent) -> None:
        await self._obs_caption_output.publish_subtitle_payload(payload)

    def _reset_export_session(self) -> None:
        self._session_id = None
        self._session_started_at_utc = None
        self._session_started_at_monotonic = None
        self._session_export_records.clear()

    def _handle_completed_export_record(self, record: dict) -> None:
        finalized_at_monotonic = record.get("finalized_at_monotonic")
        if self._session_started_at_monotonic is None or not isinstance(finalized_at_monotonic, (int, float)):
            return

        end_offset_ms = max(0, int(round((float(finalized_at_monotonic) - self._session_started_at_monotonic) * 1000.0)))
        duration_ms_raw = record.get("duration_ms")
        duration_ms = int(duration_ms_raw) if isinstance(duration_ms_raw, (int, float)) and int(duration_ms_raw) > 0 else None
        start_offset_ms = max(0, end_offset_ms - duration_ms) if duration_ms is not None else max(0, end_offset_ms - 1200)

        export_record = dict(record)
        export_record["session_id"] = self._session_id
        export_record["start_offset_ms"] = start_offset_ms
        export_record["end_offset_ms"] = end_offset_ms
        export_record["duration_ms"] = duration_ms
        sequence = export_record.get("sequence")
        if isinstance(sequence, int):
            for index, existing in enumerate(self._session_export_records):
                if int(existing.get("sequence", -1)) == sequence:
                    self._session_export_records[index] = export_record
                    break
            else:
                self._session_export_records.append(export_record)
            return
        self._session_export_records.append(export_record)

    def _export_session_files(self, *, stopped_at_utc: str) -> list[Path]:
        if not self._session_id or not self._session_started_at_utc or not self._session_export_records:
            return []

        config = self.config_getter()
        translation_config = config.get("translation", {}) if isinstance(config, dict) else {}
        subtitle_output = config.get("subtitle_output", {}) if isinstance(config, dict) else {}
        session_row = {
            "type": "session",
            "session_id": self._session_id,
            "started_at_utc": self._session_started_at_utc,
            "stopped_at_utc": stopped_at_utc,
            "profile": str(config.get("profile", "default")) if isinstance(config, dict) else "default",
            "source_lang": str(config.get("source_lang", "auto")) if isinstance(config, dict) else "auto",
            "translation_enabled": bool(translation_config.get("enabled", False)) if isinstance(translation_config, dict) else False,
            "target_languages": list(translation_config.get("target_languages", [])) if isinstance(translation_config, dict) else [],
            "subtitle_output": dict(subtitle_output) if isinstance(subtitle_output, dict) else {},
            "record_count": len(self._session_export_records),
        }
        base_filename = self._exporter.build_session_basename(
            session_started_at_utc=self._session_started_at_utc,
            session_id=self._session_id,
            profile=session_row["profile"],
        )
        return self._exporter.export_session(
            base_filename=base_filename,
            session_row=session_row,
            records=self._session_export_records,
        )

    async def apply_live_settings(self, config: dict) -> None:
        self._apply_vad_tuning()
        self._apply_recognition_processing_settings()
        self._translation_engine.apply_live_settings(config.get("translation", {}) if isinstance(config, dict) else {})
        await self._obs_caption_output.apply_live_settings(config if isinstance(config, dict) else {})
        await self.subtitle_router.republish_latest()
        self._state = self._state.model_copy(
            update={
                "asr_diagnostics": self.asr_diagnostics(),
                "translation_diagnostics": self.translation_diagnostics(),
                "obs_caption_diagnostics": self.obs_caption_diagnostics(),
                "metrics": self._metrics.model_copy(),
            }
        )
        await self._broadcast_runtime()

    def _set_state(
        self,
        *,
        is_running: bool,
        status: Literal["idle", "starting", "listening", "transcribing", "translating", "error"],
        started_at_utc: str | None,
        last_error: str | None = None,
        status_message: str | None = None,
    ) -> None:
        self._state = RuntimeState(
            is_running=is_running,
            status=status,
            started_at_utc=started_at_utc,
            last_error=last_error,
            status_message=status_message,
            asr_diagnostics=self.asr_diagnostics(),
            translation_diagnostics=self.translation_diagnostics(),
            obs_caption_diagnostics=self.obs_caption_diagnostics(),
            metrics=self._metrics.model_copy(),
        )

    def _record_metrics(self, **values: float | int | None) -> None:
        updates: dict[str, float | int] = {}
        for key, value in values.items():
            if value is None:
                continue
            if isinstance(value, int) and not isinstance(value, bool):
                updates[key] = int(value)
            else:
                updates[key] = round(float(value), 2)
        self._metrics = self._metrics.model_copy(update=updates)

    def _apply_translation_dispatcher_metrics(self, metrics: dict) -> None:
        if not isinstance(metrics, dict):
            return
        self._translation_dispatcher_snapshot = dict(metrics)
        updates: dict[str, float | int | None] = {}
        for key in (
            "translation_queue_depth",
            "translation_jobs_started",
            "translation_jobs_cancelled",
            "translation_stale_results_dropped",
            "translation_queue_latency_ms",
            "translation_provider_latency_ms",
        ):
            if key in metrics:
                updates[key] = metrics.get(key)
        if metrics.get("translation_provider_latency_ms") is not None:
            updates["translation_ms"] = metrics.get("translation_provider_latency_ms")
        self._record_metrics(**updates)

    def _increment_metric(self, key: Literal["partial_updates_emitted", "finals_emitted", "suppressed_partial_updates"]) -> None:
        current = getattr(self._metrics, key, 0) or 0
        self._record_metrics(**{key: int(current) + 1})

    def _increment_counter_metric(
        self,
        key: Literal[
            "remote_audio_chunks_in",
            "remote_audio_bytes_in",
            "remote_audio_chunks_dropped",
            "vad_segments_partial",
            "vad_segments_final",
        ],
        amount: int = 1,
    ) -> None:
        current = getattr(self._metrics, key, 0) or 0
        self._record_metrics(**{key: int(current) + int(amount)})

    @staticmethod
    def _pcm16_rms_level(audio: bytes) -> float:
        payload = bytes(audio or b"")
        if not payload or len(payload) < 2:
            return 0.0
        try:
            rms = float(audioop.rms(payload, 2))
        except Exception:
            return 0.0
        return max(0.0, min(1.0, rms / 32768.0))

    def _resolve_realtime_settings(self) -> dict[str, int | float | bool]:
        config = self.config_getter()
        asr_config = config.get("asr", {}) if isinstance(config, dict) else {}
        if not isinstance(asr_config, dict):
            asr_config = {}

        status = self._asr_engine.status()
        if status.provider != "official_eu_parakeet_realtime":
            return dict(self._LEGACY_VAD_SETTINGS)

        effective = dict(self._LEGACY_VAD_SETTINGS)
        realtime_settings = asr_config.get("realtime", {})
        if isinstance(realtime_settings, dict):
            for key in effective:
                value = realtime_settings.get(key)
                if isinstance(value, (int, float)):
                    effective[key] = int(value)
        for key in ("vad_mode", "energy_gate_enabled", "min_rms_for_recognition", "min_voiced_ratio", "first_partial_min_speech_ms"):
            value = realtime_settings.get(key) if isinstance(realtime_settings, dict) else None
            if key in {"energy_gate_enabled"}:
                effective[key] = bool(value) if value is not None else effective[key]
            elif key in {"min_rms_for_recognition", "min_voiced_ratio"}:
                if isinstance(value, (int, float)):
                    effective[key] = float(value)
            elif isinstance(value, (int, float)):
                effective[key] = int(value)
        return effective

    def _resolve_subtitle_lifecycle_settings(self) -> dict[str, int | bool]:
        config = self.config_getter()
        lifecycle = config.get("subtitle_lifecycle", {}) if isinstance(config, dict) else {}
        if not isinstance(lifecycle, dict):
            lifecycle = {}
        completed_ttl_ms = max(500, int(lifecycle.get("completed_block_ttl_ms", 4500) or 4500))
        source_ttl_ms = max(500, int(lifecycle.get("completed_source_ttl_ms", completed_ttl_ms) or completed_ttl_ms))
        translation_ttl_ms = max(500, int(lifecycle.get("completed_translation_ttl_ms", completed_ttl_ms) or completed_ttl_ms))
        return {
            "completed_block_ttl_ms": max(source_ttl_ms, translation_ttl_ms),
            "completed_source_ttl_ms": source_ttl_ms,
            "completed_translation_ttl_ms": translation_ttl_ms,
            "pause_to_finalize_ms": max(
                120,
                int(lifecycle.get("pause_to_finalize_ms", self._LEGACY_VAD_SETTINGS["finalization_hold_ms"]) or self._LEGACY_VAD_SETTINGS["finalization_hold_ms"]),
            ),
            "allow_early_replace_on_next_final": bool(lifecycle.get("allow_early_replace_on_next_final", True)),
            "sync_source_and_translation_expiry": bool(lifecycle.get("sync_source_and_translation_expiry", True)),
            "hard_max_phrase_ms": max(
                1000,
                int(lifecycle.get("hard_max_phrase_ms", self._LEGACY_VAD_SETTINGS["max_segment_ms"]) or self._LEGACY_VAD_SETTINGS["max_segment_ms"]),
            ),
        }

    def _apply_recognition_processing_settings(self) -> None:
        config = self.config_getter()
        asr_config = config.get("asr", {}) if isinstance(config, dict) else {}
        if not isinstance(asr_config, dict):
            asr_config = {}
        try:
            rnnoise_strength = int(asr_config.get("rnnoise_strength", 70) or 70)
        except (TypeError, ValueError):
            rnnoise_strength = 70
        self._rnnoise_processor.configure(
            enabled=bool(asr_config.get("rnnoise_enabled", asr_config.get("experimental_noise_reduction_enabled", False))),
            strength=rnnoise_strength,
        )

    def _prepare_recognition_audio(self, audio: bytes) -> bytes:
        return self._rnnoise_processor.process(audio)

    def _apply_vad_tuning(self) -> None:
        settings = self._resolve_realtime_settings()
        lifecycle = self._resolve_subtitle_lifecycle_settings()
        self._vad.configure(
            mode=int(settings["vad_mode"]),
            silence_hold_ms=settings["silence_hold_ms"],
            finalization_hold_ms=int(lifecycle["pause_to_finalize_ms"]),
            min_speech_ms=settings["min_speech_ms"],
            partial_emit_interval_ms=settings["partial_emit_interval_ms"],
            max_segment_ms=int(lifecycle["hard_max_phrase_ms"]),
            energy_gate_enabled=bool(settings["energy_gate_enabled"]),
            min_rms_for_recognition=float(settings["min_rms_for_recognition"]),
            min_voiced_ratio=float(settings["min_voiced_ratio"]),
            first_partial_min_speech_ms=int(settings["first_partial_min_speech_ms"]),
        )
        self._effective_realtime_settings = settings
        self._effective_subtitle_lifecycle_settings = lifecycle

    def _should_emit_partial(self, segment_id: str, text: str) -> bool:
        normalized_text = " ".join(text.split())
        if not normalized_text:
            return False

        previous_text = self._last_partial_text_by_segment.get(segment_id, "")
        normalized_previous = " ".join(previous_text.split())
        if normalized_text == normalized_previous:
            return False

        coalescing_ms = int(self._effective_realtime_settings.get("partial_coalescing_ms", 0))
        min_delta_chars = int(self._effective_realtime_settings.get("partial_min_delta_chars", 0))
        previous_emit_at = self._last_partial_emit_monotonic_by_segment.get(segment_id, 0.0)
        elapsed_ms = (time.perf_counter() - previous_emit_at) * 1000.0 if previous_emit_at else None
        growth_chars = len(normalized_text) - len(normalized_previous)

        if (
            normalized_previous
            and coalescing_ms > 0
            and min_delta_chars > 0
            and growth_chars >= 0
            and growth_chars < min_delta_chars
            and elapsed_ms is not None
            and elapsed_ms < coalescing_ms
        ):
            return False

        return True

    def _should_drop_short_hallucination(self, *, text: str, duration_ms: int, is_final: bool) -> bool:
        normalized_text = " ".join(str(text or "").strip().split())
        if not normalized_text:
            return True

        lowered = normalized_text.casefold()
        word_count = len([part for part in lowered.replace("\n", " ").split(" ") if part.strip()])
        if lowered not in self._SHORT_HALLUCINATION_TOKENS:
            return False

        short_duration_limit_ms = 900 if is_final else 1100
        if duration_ms > short_duration_limit_ms:
            return False
        if word_count > 2:
            return False
        return True

    def _mark_partial_emitted(self, segment_id: str, text: str) -> None:
        self._last_partial_text_by_segment[segment_id] = " ".join(text.split())
        self._last_partial_emit_monotonic_by_segment[segment_id] = time.perf_counter()

    def _clear_partial_tracking(self, segment_id: str | None) -> None:
        if not segment_id:
            return
        self._last_partial_text_by_segment.pop(segment_id, None)
        self._last_partial_emit_monotonic_by_segment.pop(segment_id, None)

    async def _set_listening_if_current(
        self,
        *expected_statuses: Literal["listening", "transcribing", "translating"],
        last_error: str | None = None,
        status_message: str | None = None,
    ) -> None:
        if not self._state.is_running or self._state.status not in expected_statuses:
            return
        await self._set_runtime_state(
            is_running=True,
            status="listening",
            started_at_utc=self._state.started_at_utc,
            last_error=last_error,
            status_message=status_message,
        )

    async def _set_runtime_state(
        self,
        *,
        is_running: bool,
        status: Literal["idle", "starting", "listening", "transcribing", "translating", "error"],
        started_at_utc: str | None,
        last_error: str | None = None,
        status_message: str | None = None,
    ) -> None:
        self._set_state(
            is_running=is_running,
            status=status,
            started_at_utc=started_at_utc,
            last_error=last_error,
            status_message=status_message,
        )
        await self._broadcast_runtime()

    def _build_startup_status_message(self) -> str:
        if self._current_asr_mode() == "browser_google":
            browser_lang = str(self._browser_asr_config().get("recognition_language", "ru-RU") or "ru-RU")
            return f"Preparing browser speech worker mode for {browser_lang}. The popup window will capture audio."
        if self._uses_remote_event_source():
            return "Initializing controller relay mode and waiting for remote worker transcript events."
        if self._uses_remote_audio_source():
            return "Initializing worker ASR runtime and waiting for remote controller audio stream."
        asr_status = self._asr_engine.status()
        model_path = Path(asr_status.model_path) if asr_status.model_path else None
        if model_path is not None and not model_path.exists():
            return (
                "Preparing the first local Parakeet model download. "
                "In desktop mode there is no console, so watch the runtime log panel for status updates."
            )
        return "Initializing the ASR runtime and loading the Parakeet model."

    async def _capture_loop(self) -> None:
        try:
            while self._state.is_running:
                if self._uses_remote_audio_source():
                    remote_audio_queue = self._remote_audio_queue
                    if remote_audio_queue is None:
                        await asyncio.sleep(0.05)
                        continue
                    try:
                        chunk_data = await asyncio.wait_for(remote_audio_queue.get(), timeout=0.25)
                    except asyncio.TimeoutError:
                        if self._remote_audio_last_chunk_monotonic is not None:
                            self._record_metrics(
                                remote_audio_last_chunk_age_ms=(time.perf_counter() - self._remote_audio_last_chunk_monotonic) * 1000.0
                            )
                        continue
                    if not chunk_data:
                        continue
                    self._record_metrics(remote_audio_last_chunk_age_ms=0.0)
                else:
                    if self._audio_capture is None:
                        await asyncio.sleep(0.05)
                        continue
                    chunk = await asyncio.to_thread(self._audio_capture.read_chunk, 0.25)
                    if chunk is None:
                        continue
                    chunk_data = chunk.data
                vad_started = time.perf_counter()
                segments = self._vad.process_chunk(chunk_data)
                vad_elapsed_ms = (time.perf_counter() - vad_started) * 1000.0
                self._record_metrics(
                    vad_ms=vad_elapsed_ms,
                    vad_dropped_segments=int(getattr(self._vad, "_segment_dropped_count", 0) or 0),
                )
                if not segments:
                    continue
                partial_segments = sum(1 for segment in segments if segment.kind == "partial")
                final_segments = sum(1 for segment in segments if segment.kind == "final")
                if partial_segments > 0:
                    self._increment_counter_metric("vad_segments_partial", partial_segments)
                if final_segments > 0:
                    self._increment_counter_metric("vad_segments_final", final_segments)

                for segment in segments:
                    segment_id, revision, started_now = self._assign_segment_tracking(segment.kind)
                    if started_now:
                        await self._broadcast_transcript_segment_event(
                            TranscriptEvent(
                                event="partial" if segment.kind == "partial" else "final",
                                lifecycle_event="segment_started",
                                text="",
                                device_id=self._device_id,
                                sequence=self._sequence,
                                segment=TranscriptSegment(
                                    segment_id=segment_id,
                                    text="",
                                    is_partial=False,
                                    is_final=False,
                                    start_ms=0,
                                    end_ms=segment.duration_ms,
                                    source_lang=str(self.config_getter().get("source_lang", "auto")),
                                    provider=self._asr_engine.capabilities().provider_name,
                                    latency_ms=None,
                                    sequence=self._sequence,
                                    revision=revision,
                                ),
                            )
                        )
                    self._segment_queue.push(
                        AsrWorkItem(
                            kind=segment.kind,
                            audio=self._prepare_recognition_audio(segment.audio),
                            duration_ms=segment.duration_ms,
                            segment_id=segment_id,
                            revision=revision,
                            vad_ms=vad_elapsed_ms,
                        )
                    )
                    if segment.kind == "final":
                        self._active_segment_id = None
                        self._active_segment_revision = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._safe_stop_audio()
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=self._state.started_at_utc,
                last_error=str(exc),
            )

    async def _asr_loop(self) -> None:
        try:
            while self._state.is_running:
                work_item = await asyncio.to_thread(self._segment_queue.pop, 0.25)
                if work_item is None:
                    continue

                await self._set_runtime_state(
                    is_running=True,
                    status="transcribing",
                    started_at_utc=self._state.started_at_utc,
                )
                result = await asyncio.to_thread(
                    self._asr_engine.run,
                    work_item.audio,
                    is_final=work_item.kind == "final",
                    segment_id=work_item.segment_id or None,
                )
                asr_elapsed_ms = (time.perf_counter() - work_item.created_at_monotonic) * 1000.0 - work_item.vad_ms
                total_elapsed_ms = (time.perf_counter() - work_item.created_at_monotonic) * 1000.0
                if work_item.kind == "final":
                    self._record_metrics(
                        vad_ms=work_item.vad_ms,
                        asr_final_ms=max(0.0, asr_elapsed_ms),
                        total_ms=total_elapsed_ms,
                    )
                else:
                    self._record_metrics(
                        vad_ms=work_item.vad_ms,
                        asr_partial_ms=max(0.0, asr_elapsed_ms),
                        total_ms=total_elapsed_ms,
                    )
                self._sequence += 1
                text = result.final if work_item.kind == "final" else result.partial
                if text:
                    if self._should_drop_short_hallucination(
                        text=text,
                        duration_ms=work_item.duration_ms,
                        is_final=work_item.kind == "final",
                    ):
                        if work_item.kind == "partial":
                            self._increment_metric("suppressed_partial_updates")
                        else:
                            self._clear_partial_tracking(work_item.segment_id)
                        await self._set_runtime_state(
                            is_running=True,
                            status="listening",
                            started_at_utc=self._state.started_at_utc,
                        )
                        continue
                    if work_item.kind == "partial":
                        segment_id = work_item.segment_id or ""
                        if not self._should_emit_partial(segment_id, text):
                            self._increment_metric("suppressed_partial_updates")
                            await self._set_runtime_state(
                                is_running=True,
                                status="listening",
                                started_at_utc=self._state.started_at_utc,
                            )
                            continue
                        self._mark_partial_emitted(segment_id, text)

                    lifecycle_event = "segment_finalized" if work_item.kind == "final" else "partial_updated"
                    segment = self._build_transcript_segment(
                        work_item=work_item,
                        text=text,
                        latency_ms=max(0.0, asr_elapsed_ms),
                    )
                    transcript_event = TranscriptEvent(
                        event=work_item.kind,
                        text=text,
                        device_id=self._device_id,
                        sequence=self._sequence,
                        lifecycle_event=lifecycle_event,
                        segment=segment,
                    )
                    await self._broadcast_transcript(transcript_event)
                    if work_item.kind == "final":
                        self._increment_metric("finals_emitted")
                        self._clear_partial_tracking(work_item.segment_id)
                        await self.subtitle_router.handle_transcript(transcript_event)
                        await self._obs_caption_output.publish_source_event(transcript_event)
                        await self._translation_dispatcher.submit_final(
                            sequence=self._sequence,
                            source_text=text,
                            source_lang=segment.source_lang,
                        )
                        await self._broadcast_runtime()
                    else:
                        await self.subtitle_router.handle_transcript(transcript_event)
                        await self._obs_caption_output.publish_source_event(transcript_event)
                        self._increment_metric("partial_updates_emitted")
                        await self._broadcast_runtime()
                elif work_item.kind == "final":
                    self._clear_partial_tracking(work_item.segment_id)
                await self._set_listening_if_current("transcribing")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._safe_stop_audio()
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=self._state.started_at_utc,
                last_error=str(exc),
            )

    async def _broadcast_external_segment_started(
        self,
        *,
        segment_id: str,
        revision: int,
        source_lang: str,
    ) -> None:
        await self._broadcast_transcript_segment_event(
            TranscriptEvent(
                event="partial",
                lifecycle_event="segment_started",
                text="",
                device_id="browser_google_worker",
                sequence=self._sequence,
                segment=TranscriptSegment(
                    segment_id=segment_id,
                    text="",
                    is_partial=False,
                    is_final=False,
                    start_ms=0,
                    end_ms=0,
                    source_lang=source_lang,
                    provider="browser_google",
                    latency_ms=None,
                    sequence=self._sequence,
                    revision=revision,
                ),
            )
        )

    def _build_external_transcript_segment(
        self,
        *,
        segment_id: str,
        revision: int,
        text: str,
        is_final: bool,
        source_lang: str,
    ) -> TranscriptSegment:
        return TranscriptSegment(
            segment_id=segment_id,
            text=text,
            is_partial=not is_final,
            is_final=is_final,
            start_ms=0,
            end_ms=0,
            source_lang=source_lang,
            provider="browser_google",
            latency_ms=0.0,
            sequence=self._sequence,
            revision=revision,
        )

    async def browser_asr_worker_connected(self) -> None:
        self._external_worker_connected = True
        self._browser_asr_gateway.worker_connected()
        if self._state.is_running and self._current_asr_mode() == "browser_google":
            await self._set_runtime_state(
                is_running=True,
                status="listening",
                started_at_utc=self._state.started_at_utc,
                last_error=None,
                status_message="Browser speech worker connected. Press Start Recognition in the popup window.",
            )

    async def browser_asr_worker_disconnected(self) -> None:
        self._external_worker_connected = False
        self._browser_asr_gateway.worker_disconnected()
        segment_id = self._active_segment_id
        self._active_segment_id = None
        self._active_segment_revision = 0
        self._clear_partial_tracking(segment_id)
        await self.subtitle_router.clear_active_partial()
        if self._state.is_running and self._current_asr_mode() == "browser_google":
            await self._set_runtime_state(
                is_running=True,
                status="listening",
                started_at_utc=self._state.started_at_utc,
                status_message="Browser speech worker disconnected. Reopen or restart the browser recognition window.",
            )

    async def update_browser_asr_worker_status(self, payload: dict[str, Any]) -> None:
        self._browser_asr_gateway.update_status(payload)
        if self._state.is_running and self._current_asr_mode() == "browser_google":
            await self._broadcast_runtime()

    async def ingest_external_asr_update(
        self,
        *,
        partial: str = "",
        final: str = "",
        is_final: bool = False,
        source_lang: str | None = None,
    ) -> None:
        if not self._state.is_running or self._current_asr_mode() != "browser_google":
            return

        normalized_source_lang = str(source_lang or self._browser_asr_source_lang() or "auto").strip().lower() or "auto"
        partial_text = str(partial or "").strip()
        final_text = str(final or "").strip()
        if is_final and not final_text and partial_text:
            final_text = partial_text

        if partial_text and not is_final:
            segment_id, revision, started_now = self._assign_segment_tracking("partial")
            if started_now:
                await self._broadcast_external_segment_started(
                    segment_id=segment_id,
                    revision=revision,
                    source_lang=normalized_source_lang,
                )
            if not self._should_emit_partial(segment_id, partial_text):
                self._increment_metric("suppressed_partial_updates")
                return
            self._mark_partial_emitted(segment_id, partial_text)
            self._sequence += 1
            transcript_event = TranscriptEvent(
                event="partial",
                text=partial_text,
                device_id="browser_google_worker",
                sequence=self._sequence,
                lifecycle_event="partial_updated",
                segment=self._build_external_transcript_segment(
                    segment_id=segment_id,
                    revision=revision,
                    text=partial_text,
                    is_final=False,
                    source_lang=normalized_source_lang,
                ),
            )
            self._browser_asr_gateway.note_partial(
                text_len=len(partial_text),
                source_lang=normalized_source_lang,
                sequence=transcript_event.sequence,
            )
            await self._broadcast_transcript(transcript_event)
            await self.subtitle_router.handle_transcript(transcript_event)
            await self._obs_caption_output.publish_source_event(transcript_event)
            self._increment_metric("partial_updates_emitted")
            await self._set_listening_if_current(
                "listening",
                last_error=None,
                status_message="Browser speech recognition is active.",
            )

        if is_final and final_text:
            segment_id, revision, started_now = self._assign_segment_tracking("final")
            if started_now:
                await self._broadcast_external_segment_started(
                    segment_id=segment_id,
                    revision=revision,
                    source_lang=normalized_source_lang,
                )
            self._clear_partial_tracking(segment_id)
            self._sequence += 1
            transcript_event = TranscriptEvent(
                event="final",
                text=final_text,
                device_id="browser_google_worker",
                sequence=self._sequence,
                lifecycle_event="segment_finalized",
                segment=self._build_external_transcript_segment(
                    segment_id=segment_id,
                    revision=revision,
                    text=final_text,
                    is_final=True,
                    source_lang=normalized_source_lang,
                ),
            )
            self._browser_asr_gateway.note_final(
                text_len=len(final_text),
                source_lang=normalized_source_lang,
                sequence=transcript_event.sequence,
            )
            await self._broadcast_transcript(transcript_event)
            self._increment_metric("finals_emitted")
            await self.subtitle_router.handle_transcript(transcript_event)
            await self._obs_caption_output.publish_source_event(transcript_event)
            await self._translation_dispatcher.submit_final(
                sequence=self._sequence,
                source_text=final_text,
                source_lang=normalized_source_lang,
            )
            self._active_segment_id = None
            self._active_segment_revision = 0
            await self._set_listening_if_current(
                "listening",
                last_error=None,
                status_message="Browser speech recognition is active.",
            )

    async def start(self, *, has_audio_inputs: bool, device_id: str | None) -> RuntimeState:
        if self._state.is_running:
            return self._state

        self._runtime_loop = asyncio.get_running_loop()
        self._latest_runtime_status_message = None
        self._metrics = RuntimeMetrics()
        self._translation_dispatcher_snapshot = {}
        self._translation_dispatcher = TranslationDispatcher(
            self._translation_engine,
            self.config_getter,
            self._publish_translation_dispatch_event,
            self.subtitle_router.is_sequence_relevant_for_translation,
            self._apply_translation_dispatcher_metrics,
            structured_logger=self._structured_runtime_logger,
        )
        self._remote_audio_queue = asyncio.Queue(maxsize=256)
        asr_mode = self._current_asr_mode()
        if self._current_remote_role() == REMOTE_ROLE_WORKER and asr_mode == "browser_google":
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=None,
                last_error="Remote worker mode supports AI runtime only. Browser speech mode is not allowed.",
                status_message=None,
            )
            return self._state
        use_remote_audio_source = self._uses_remote_audio_source()
        use_remote_event_source = self._uses_remote_event_source()
        if asr_mode != "browser_google" and not use_remote_audio_source and not use_remote_event_source and not has_audio_inputs:
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=None,
                last_error="No input audio devices found.",
            )
            return self._state

        await self._set_runtime_state(
            is_running=False,
            status="starting",
            started_at_utc=None,
            status_message=self._build_startup_status_message(),
        )

        try:
            if asr_mode != "browser_google" and not use_remote_event_source:
                asr_status = await asyncio.to_thread(self._asr_engine.initialize_runtime)
                self._apply_vad_tuning()
                if not asr_status.ready:
                    await self._set_runtime_state(
                        is_running=False,
                        status="error",
                        started_at_utc=None,
                        last_error=asr_status.message,
                        status_message=None,
                    )
                    return self._state
            self._device_id = "remote_webrtc_controller" if use_remote_audio_source else device_id
            if asr_mode != "browser_google":
                self._external_worker_connected = False
            if asr_mode != "browser_google" and not use_remote_audio_source:
                self._audio_capture = AudioCapture()
                self._audio_capture.start(device_id=device_id)
            if use_remote_audio_source:
                self._clear_remote_audio_queue()
                self._remote_audio_connected = False
                self._remote_audio_session_id = None
                self._remote_audio_last_chunk_monotonic = None
            await self._obs_caption_output.start()
            await self._obs_caption_output.apply_live_settings(self.config_getter())
            self._reset_export_session()
            await self.subtitle_router.reset()
            self._vad.reset()
            self._asr_engine.reset_runtime_state()
            self._segment_queue.clear()
            self._sequence = 0
            self._last_partial_text_by_segment.clear()
            self._last_partial_emit_monotonic_by_segment.clear()
            started_at = datetime.now(timezone.utc).isoformat()
            self._session_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            self._session_started_at_utc = started_at
            self._session_started_at_monotonic = time.perf_counter()
            self._active_runtime_mode = asr_mode
            await self._set_runtime_state(
                is_running=True,
                status="listening",
                started_at_utc=started_at,
                status_message=(
                    "Controller relay mode is ready and waiting for remote worker events."
                    if use_remote_event_source
                    else
                    "Worker runtime is ready and waiting for remote WebRTC audio."
                    if use_remote_audio_source
                    else
                    (
                        "Browser speech worker connected. Press Start Recognition in the popup window."
                        if self._external_worker_connected
                        else "Waiting for the browser speech worker window to connect."
                    )
                    if asr_mode == "browser_google"
                    else None
                ),
            )
            if asr_mode != "browser_google" and not use_remote_event_source:
                self._capture_task = asyncio.create_task(self._capture_loop())
                self._asr_task = asyncio.create_task(self._asr_loop())
        except Exception as exc:
            await self._safe_stop_audio()
            await self._obs_caption_output.stop()
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=None,
                last_error=str(exc),
                status_message=None,
            )
        return self._state

    async def _safe_stop_audio(self) -> None:
        if self._audio_capture is not None:
            await asyncio.to_thread(self._audio_capture.stop)
            self._audio_capture = None

    async def stop(self) -> RuntimeState:
        self._latest_runtime_status_message = None
        self._set_state(is_running=False, status="idle", started_at_utc=None, last_error=None)
        tasks = [task for task in (self._capture_task, self._asr_task) if task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._capture_task = None
        self._asr_task = None
        self._external_worker_connected = False
        self._active_runtime_mode = None
        self._remote_audio_connected = False
        self._remote_audio_session_id = None
        self._remote_audio_last_chunk_monotonic = None
        await self._safe_stop_audio()
        await self._obs_caption_output.stop()
        stopped_at_utc = datetime.now(timezone.utc).isoformat()
        export_error: str | None = None
        try:
            self._export_session_files(stopped_at_utc=stopped_at_utc)
        except Exception as exc:
            export_error = str(exc)
        await self.subtitle_router.reset()
        await self._translation_dispatcher.stop()
        self._segment_queue.clear()
        self._vad.reset()
        await asyncio.to_thread(self._asr_engine.unload_runtime_state)
        self._last_partial_text_by_segment.clear()
        self._last_partial_emit_monotonic_by_segment.clear()
        self._clear_remote_audio_queue()
        self._remote_audio_queue = None
        self._reset_export_session()
        self._metrics = RuntimeMetrics()
        self._runtime_loop = None
        if export_error:
            self._state = self._state.model_copy(update={"last_error": f"Export error: {export_error}"})
        await self._broadcast_runtime()
        return self._state

    def _clear_remote_audio_queue(self) -> None:
        remote_audio_queue = self._remote_audio_queue
        if remote_audio_queue is None:
            return
        while not remote_audio_queue.empty():
            try:
                remote_audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def remote_audio_ingest_connected(self, *, session_id: str | None = None) -> None:
        self._remote_audio_connected = True
        self._remote_audio_session_id = str(session_id or "").strip() or None
        self._remote_audio_last_chunk_monotonic = time.perf_counter()
        await self._set_listening_if_current(
            "listening",
            last_error=None,
            status_message="Remote controller audio stream is connected.",
        )

    async def remote_audio_ingest_disconnected(self) -> None:
        self._remote_audio_connected = False
        self._remote_audio_last_chunk_monotonic = None
        await self._set_listening_if_current(
            "listening",
            last_error=None,
            status_message="Waiting for remote controller audio stream.",
        )

    async def ingest_remote_audio_chunk(self, payload: bytes) -> bool:
        if not self._state.is_running:
            return False
        if not self._uses_remote_audio_source():
            return False
        audio = bytes(payload or b"")
        if not audio:
            return False
        if len(audio) % 2 != 0:
            audio = audio[:-1]
            if not audio:
                return False
        remote_audio_queue = self._remote_audio_queue
        if remote_audio_queue is None:
            return False
        if remote_audio_queue.full():
            try:
                remote_audio_queue.get_nowait()
                self._increment_counter_metric("remote_audio_chunks_dropped", 1)
            except asyncio.QueueEmpty:
                pass
        await remote_audio_queue.put(audio)
        self._increment_counter_metric("remote_audio_chunks_in", 1)
        self._increment_counter_metric("remote_audio_bytes_in", len(audio))
        self._record_metrics(
            remote_audio_level_rms=self._pcm16_rms_level(audio),
            remote_audio_last_chunk_age_ms=0.0,
        )
        self._remote_audio_last_chunk_monotonic = time.perf_counter()
        return True

    async def ingest_remote_transcript_event(self, payload: dict) -> bool:
        if not self._state.is_running or not self._uses_remote_event_source():
            return False
        if not isinstance(payload, dict):
            return False
        try:
            event = TranscriptEvent.model_validate(payload)
        except Exception:
            return False
        if event.event == "partial":
            await self._set_runtime_state(
                is_running=True,
                status="transcribing",
                started_at_utc=self._state.started_at_utc,
                status_message="Receiving remote worker transcript stream.",
            )
        await self._broadcast_transcript(event)
        await self.subtitle_router.handle_transcript(event)
        await self._obs_caption_output.publish_source_event(event)
        if event.event == "final":
            self._increment_metric("finals_emitted")
            await self._set_runtime_state(
                is_running=True,
                status="listening",
                started_at_utc=self._state.started_at_utc,
                status_message="Remote worker transcript stream is active.",
            )
        return True

    async def ingest_remote_translation_event(self, payload: dict) -> bool:
        if not self._state.is_running or not self._uses_remote_event_source():
            return False
        if not isinstance(payload, dict):
            return False
        try:
            event = TranslationEvent.model_validate(payload)
        except Exception:
            return False
        await self._set_runtime_state(
            is_running=True,
            status="translating",
            started_at_utc=self._state.started_at_utc,
            status_message="Receiving remote worker translation stream.",
        )
        await self._broadcast_translation(event)
        await self.subtitle_router.handle_translation(event)
        await self._set_runtime_state(
            is_running=True,
            status="listening",
            started_at_utc=self._state.started_at_utc,
            status_message="Remote worker transcript stream is active.",
        )
        return True

    def status(self) -> RuntimeState:
        self._apply_vad_tuning()
        if self._uses_remote_audio_source():
            if self._remote_audio_last_chunk_monotonic is not None:
                self._record_metrics(
                    remote_audio_last_chunk_age_ms=(time.perf_counter() - self._remote_audio_last_chunk_monotonic) * 1000.0
                )
        else:
            self._record_metrics(remote_audio_last_chunk_age_ms=None)
        self._state = self._state.model_copy(
            update={
                "asr_diagnostics": self.asr_diagnostics(),
                "translation_diagnostics": self.translation_diagnostics(),
                "obs_caption_diagnostics": self.obs_caption_diagnostics(),
                "metrics": self._metrics.model_copy(),
            }
        )
        return self._state

    def asr_status(self):
        if self._current_asr_mode() == "browser_google":
            message = (
                "Browser speech worker is connected."
                if self._external_worker_connected
                else "Browser speech mode is configured. Open the browser worker window to capture audio."
            )
            return AsrProviderStatus(
                provider="browser_google",
                ready=True,
                message=message,
                requested_provider="browser_google",
                requested_device_policy="browser_window",
                supports_gpu=False,
                supports_partials=True,
                supports_streaming=True,
                partials_supported=True,
                selected_device="browser",
                selected_execution_provider="webkitSpeechRecognition",
                runtime_initialized=self._state.is_running,
            )
        return self._asr_engine.status()

    def translation_diagnostics(self) -> TranslationDiagnostics:
        try:
            config = self.config_getter()
            translation_config = config.get("translation", {}) if isinstance(config, dict) else {}
            diagnostics = self._translation_engine.summarize_readiness(
                translation_config if isinstance(translation_config, dict) else {}
            )
            snapshot = self._translation_dispatcher_snapshot if isinstance(self._translation_dispatcher_snapshot, dict) else {}
            runtime_reason = snapshot.get("translation_last_runtime_reason")
            return diagnostics.model_copy(
                update={
                    "queue_depth": int(snapshot.get("translation_queue_depth", 0) or 0),
                    "jobs_started": int(snapshot.get("translation_jobs_started", 0) or 0),
                    "jobs_cancelled": int(snapshot.get("translation_jobs_cancelled", 0) or 0),
                    "stale_results_dropped": int(snapshot.get("translation_stale_results_dropped", 0) or 0),
                    "last_queue_latency_ms": snapshot.get("translation_queue_latency_ms"),
                    "last_provider_latency_ms": snapshot.get("translation_provider_latency_ms"),
                    "last_runtime_reason": str(runtime_reason).strip() or None if runtime_reason is not None else None,
                }
            )
        except Exception as exc:
            return TranslationDiagnostics(
                enabled=False,
                status="error",
                summary="Translation diagnostics unavailable.",
                reason=str(exc),
                degraded=True,
            )

    def obs_caption_diagnostics(self) -> ObsCaptionDiagnostics:
        return self._obs_caption_output.diagnostics()

    def asr_diagnostics(self) -> AsrDiagnostics:
        try:
            if self._current_asr_mode() == "browser_google":
                browser_config = self._browser_asr_config()
                browser_lang = str(browser_config.get("recognition_language", "ru-RU") or "ru-RU")
                browser_worker = self._browser_asr_gateway.diagnostics()
                worker_message = (
                    "Browser speech worker is connected."
                    if self._external_worker_connected
                    else "Open the browser speech window and start recognition there."
                )
                return AsrDiagnostics(
                    provider="browser_google",
                    requested_provider="browser_google",
                    requested_device_policy="browser_window",
                    supports_gpu=False,
                    supports_partials=True,
                    supports_streaming=True,
                    supports_word_timestamps=False,
                    gpu_requested=False,
                    gpu_available=False,
                    torch_built_with_cuda=False,
                    torch_cuda_is_available=False,
                    torch_device_count=0,
                    degraded_mode=bool(browser_worker.degraded_reason),
                    selected_device="browser",
                    selected_execution_provider="webkitSpeechRecognition",
                    partials_supported=True,
                    sample_rate=None,
                    recognition_noise_reduction_enabled=False,
                    rnnoise_strength=0,
                    rnnoise_available=False,
                    rnnoise_active=False,
                    rnnoise_message="RNNoise is not used in browser speech mode.",
                    message=f"{worker_message} Recognition language: {browser_lang}.",
                    runtime_initialized=self._state.is_running,
                    browser_worker=browser_worker,
                )
            diagnostics = self._asr_engine.diagnostics()
            rnnoise_status = self._rnnoise_processor.status()
            return AsrDiagnostics(
                provider=diagnostics.provider_name,
                requested_provider=diagnostics.requested_provider,
                requested_device_policy=diagnostics.requested_device_policy,
                model_path=diagnostics.model_path,
                supports_gpu=diagnostics.supports_gpu,
                supports_partials=diagnostics.supports_partials,
                supports_streaming=diagnostics.supports_streaming,
                supports_word_timestamps=diagnostics.supports_word_timestamps,
                gpu_requested=diagnostics.gpu_requested,
                gpu_available=diagnostics.gpu_available,
                torch_version=diagnostics.torch_version,
                torch_built_with_cuda=diagnostics.torch_built_with_cuda,
                torch_cuda_is_available=diagnostics.torch_cuda_is_available,
                torch_cuda_version=diagnostics.torch_cuda_version,
                torch_device_count=diagnostics.torch_device_count,
                first_gpu_name=diagnostics.first_gpu_name,
                python_executable=diagnostics.python_executable,
                venv_path=diagnostics.venv_path,
                degraded_mode=diagnostics.degraded_mode,
                fallback_reason=diagnostics.fallback_reason,
                cpu_fallback_reason=diagnostics.cpu_fallback_reason,
                selected_device=diagnostics.actual_selected_device,
                selected_execution_provider=diagnostics.actual_execution_provider,
                partials_supported=diagnostics.supports_partials,
                sample_rate=getattr(self._audio_capture, "sample_rate", None) or self._asr_engine.sample_rate,
                audio_frame_duration_ms=getattr(self._vad, "frame_duration_ms", None),
                vad_mode=getattr(self._vad, "vad_mode", None),
                vad_partial_interval_ms=getattr(self._vad, "partial_interval_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_min_speech_ms=getattr(self._vad, "min_speech_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_first_partial_min_speech_ms=getattr(self._vad, "first_partial_min_speech_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_silence_padding_ms=getattr(self._vad, "silence_hold_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_finalization_hold_ms=getattr(self._vad, "finalization_hold_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_max_segment_ms=getattr(self._vad, "max_segment_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_energy_gate_enabled=bool(getattr(self._vad, "energy_gate_enabled", False)),
                vad_min_rms_for_recognition=float(getattr(self._vad, "min_rms_for_recognition", 0.0)),
                vad_min_voiced_ratio=float(getattr(self._vad, "min_voiced_ratio", 0.0)),
                realtime_chunk_window_ms=int(self._effective_realtime_settings.get("chunk_window_ms", 0) or 0),
                realtime_chunk_overlap_ms=int(self._effective_realtime_settings.get("chunk_overlap_ms", 0) or 0),
                partial_min_delta_chars=int(self._effective_realtime_settings.get("partial_min_delta_chars", 0) or 0),
                partial_coalescing_ms=int(self._effective_realtime_settings.get("partial_coalescing_ms", 0) or 0),
                recognition_noise_reduction_enabled=rnnoise_status.enabled,
                rnnoise_strength=rnnoise_status.strength,
                rnnoise_available=rnnoise_status.backend_available,
                rnnoise_active=rnnoise_status.active,
                rnnoise_backend=rnnoise_status.backend_name,
                rnnoise_uses_resample=rnnoise_status.uses_resample,
                rnnoise_input_sample_rate=rnnoise_status.input_sample_rate,
                rnnoise_processing_sample_rate=rnnoise_status.processing_sample_rate,
                rnnoise_frame_size_samples=rnnoise_status.frame_size_samples,
                rnnoise_message=rnnoise_status.message,
                message=diagnostics.message,
                runtime_initialized=diagnostics.runtime_initialized,
            )
        except Exception as exc:
            return AsrDiagnostics(
                provider="unknown",
                requested_provider="unknown",
                requested_device_policy="unknown",
                supports_gpu=False,
                supports_partials=False,
                supports_streaming=False,
                supports_word_timestamps=False,
                torch_built_with_cuda=False,
                torch_cuda_is_available=False,
                torch_device_count=0,
                degraded_mode=True,
                fallback_reason=f"ASR diagnostics unavailable: {exc}",
                selected_device="unknown",
                selected_execution_provider="unknown",
                partials_supported=False,
                sample_rate=self._asr_engine.sample_rate,
                audio_frame_duration_ms=getattr(self._vad, "frame_duration_ms", None),
                vad_mode=getattr(self._vad, "vad_mode", None),
                vad_partial_interval_ms=getattr(self._vad, "partial_interval_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_min_speech_ms=getattr(self._vad, "min_speech_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_first_partial_min_speech_ms=getattr(self._vad, "first_partial_min_speech_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_silence_padding_ms=getattr(self._vad, "silence_hold_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_finalization_hold_ms=getattr(self._vad, "finalization_hold_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_max_segment_ms=getattr(self._vad, "max_segment_frames", 0) * getattr(self._vad, "frame_duration_ms", 0) or None,
                vad_energy_gate_enabled=bool(getattr(self._vad, "energy_gate_enabled", False)),
                vad_min_rms_for_recognition=float(getattr(self._vad, "min_rms_for_recognition", 0.0)),
                vad_min_voiced_ratio=float(getattr(self._vad, "min_voiced_ratio", 0.0)),
                realtime_chunk_window_ms=int(self._effective_realtime_settings.get("chunk_window_ms", 0) or 0),
                realtime_chunk_overlap_ms=int(self._effective_realtime_settings.get("chunk_overlap_ms", 0) or 0),
                message=f"ASR diagnostics unavailable: {exc}",
            )

    def _assign_segment_tracking(self, kind: str) -> tuple[str, int, bool]:
        started_now = False
        if self._active_segment_id is None:
            self._segment_counter += 1
            self._active_segment_id = f"segment-{self._segment_counter}"
            self._active_segment_revision = 0
            started_now = True
        self._active_segment_revision += 1
        return self._active_segment_id, self._active_segment_revision, started_now

    def _build_transcript_segment(self, *, work_item: AsrWorkItem, text: str, latency_ms: float) -> TranscriptSegment:
        capabilities = self._asr_engine.capabilities()
        return TranscriptSegment(
            segment_id=work_item.segment_id or f"segment-{self._sequence}",
            text=text,
            is_partial=work_item.kind == "partial",
            is_final=work_item.kind == "final",
            start_ms=0,
            end_ms=work_item.duration_ms,
            source_lang=str(self.config_getter().get("source_lang", "auto")),
            provider=capabilities.provider_name,
            latency_ms=round(float(latency_ms), 2),
            sequence=self._sequence,
            revision=work_item.revision,
        )
