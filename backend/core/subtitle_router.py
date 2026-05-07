from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from typing import Any, Awaitable, Callable, Literal

from backend.core.asr_engine import AsrEngine
from backend.core.cache_manager import CacheManager
from backend.core.audio_capture import AudioCapture, RNNoiseRecognitionProcessor
from backend.core.asr_provider_selection import (
    BROWSER_GOOGLE_EXPERIMENTAL_MODE,
    BROWSER_GOOGLE_MODE,
    DEFAULT_PARAKEET_PROVIDER,
    LOCAL_ASR_MODE as RESOLVED_LOCAL_ASR_MODE,
)
from backend.core.browser_asr_gateway import BrowserAsrGateway
from backend.core.exporter import Exporter
from backend.core.obs_caption_output import ObsCaptionOutput
from backend.core.overlay_broadcaster import OverlayBroadcaster
from backend.core.parakeet_provider import AsrProviderStatus, OFFICIAL_EU_PARAKEET_REPO
from backend.core.remote_mode import (
    REMOTE_ROLE_WORKER,
)
from backend.core.runtime.asr_runtime_controller import (
    BROWSER_ASR_MODES,
    browser_asr_config,
    browser_asr_source_lang,
    browser_worker_provider_name,
    current_asr_mode,
    current_local_provider_preference,
    current_remote_role,
    is_browser_asr_mode,
    is_remote_enabled,
    resolved_asr_provider,
    uses_remote_audio_source,
    uses_remote_event_source,
)
from backend.core.runtime.audio_runtime_controller import (
    pcm16_rms_level,
    prepare_recognition_audio,
)
from backend.core.runtime.output_fanout_coordinator import broadcast_event, publish_subtitle_payload
from backend.core.runtime.runtime_metrics_collector import (
    apply_translation_dispatcher_metrics,
    enrich_event_payload,
    increment_counter_metric,
    increment_metric,
    next_event_sequence,
    record_metrics,
    runtime_material_status_snapshot,
)
from backend.core.runtime.runtime_status_builder import build_overlay_runtime_status, build_runtime_state
from backend.core.runtime.translation_runtime_coordinator import summarize_translation_diagnostics
from backend.core.segment_queue import AsrWorkItem, SegmentQueue
from backend.core.structured_runtime_logger import StructuredRuntimeLogger
from backend.core.subtitle_style import resolve_effective_subtitle_style
from backend.core.translation_dispatcher import TranslationDispatcher
from backend.core.translation_engine import TranslationEngine
from backend.core.vad import VadEngine
from backend.models import (
    AsrDiagnostics,
    ObsCaptionDiagnostics,
    OverlayRuntimeStatus,
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

LOCAL_ASR_MODE = RESOLVED_LOCAL_ASR_MODE
BROWSER_ASR_MODE = BROWSER_GOOGLE_MODE
EXPERIMENTAL_BROWSER_ASR_MODE = BROWSER_GOOGLE_EXPERIMENTAL_MODE
BROWSER_ASR_MODES = {BROWSER_ASR_MODE, EXPERIMENTAL_BROWSER_ASR_MODE}


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
        self._diagnostic_counters = {
            "overlay_stale_translation_suppressed": 0,
            "overlay_payload_mismatch_count": 0,
        }

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
            "keep_completed_translation_during_active_partial": bool(
                lifecycle.get("keep_completed_translation_during_active_partial", True)
            ),
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

    def diagnostic_counters(self) -> dict[str, int]:
        return dict(self._diagnostic_counters)

    def _increment_counter_metric(
        self,
        key: Literal["overlay_stale_translation_suppressed", "overlay_payload_mismatch_count"],
        amount: int = 1,
    ) -> None:
        self._diagnostic_counters[key] = int(self._diagnostic_counters.get(key, 0) or 0) + int(amount)

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
        lifecycle = self._subtitle_lifecycle_config()
        preserve_completed_translations = bool(lifecycle.get("keep_completed_translation_during_active_partial", True))
        if not preserve_completed_translations and completed_payload.visible_items:
            self._increment_counter_metric("overlay_payload_mismatch_count", 1)
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
                preserve_completed_translations
                and
                show_translations
                and visible_translation_count < max_translation_languages
                and bool(translation_item.success)
                and bool(translation_item.text)
            )
            if not preserve_completed_translations and bool(translation_item.text):
                self._increment_counter_metric("overlay_stale_translation_suppressed", 1)
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

def __getattr__(name: str) -> Any:
    if name == "RuntimeOrchestrator":
        from backend.core.runtime_orchestrator import RuntimeOrchestrator

        return RuntimeOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "SubtitleRouter",
    "RuntimeOrchestrator",
    "LOCAL_ASR_MODE",
    "BROWSER_ASR_MODE",
    "EXPERIMENTAL_BROWSER_ASR_MODE",
    "BROWSER_ASR_MODES",
]
