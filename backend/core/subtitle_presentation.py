from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from backend.core.subtitle_style import resolve_effective_subtitle_style
from backend.models import SubtitleLineItem, SubtitlePayloadEvent

from backend.core.subtitle_lifecycle_core import SubtitleLifecycleCore


@dataclass(slots=True)
class SubtitlePresentation:
    """
    Owns payload construction: ordering, visibility, style slots, and partial+completed composition.
    """

    config_getter: Callable[[], dict]
    increment_counter_metric: Callable[[Literal["overlay_stale_translation_suppressed", "overlay_payload_mismatch_count"], int], None]

    @staticmethod
    def _translation_lines(translation_config: dict[str, Any]) -> list[dict[str, Any]]:
        lines = translation_config.get("lines", []) if isinstance(translation_config, dict) else []
        return [line for line in lines if isinstance(line, dict)]

    @classmethod
    def _enabled_translation_lines(cls, translation_config: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            line
            for line in cls._translation_lines(translation_config)
            if line.get("enabled", True)
            and str(line.get("slot_id") or "").strip()
            and str(line.get("target_lang") or "").strip()
        ]

    @classmethod
    def translation_slot_map(cls, translation_config: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            str(line.get("slot_id")).strip().lower(): line
            for line in cls._enabled_translation_lines(translation_config)
        }

    @classmethod
    def legacy_language_to_slot_map(cls, translation_config: dict[str, Any]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for line in cls._enabled_translation_lines(translation_config):
            target_lang = str(line.get("target_lang") or "").strip().lower()
            slot_id = str(line.get("slot_id") or "").strip().lower()
            if target_lang and slot_id and target_lang not in mapping:
                mapping[target_lang] = slot_id
        return mapping

    @classmethod
    def resolved_display_order(cls, translation_config: dict[str, Any], subtitle_output: dict[str, Any]) -> list[str]:
        enabled_slots = list(cls.translation_slot_map(translation_config).keys())
        language_to_slot = cls.legacy_language_to_slot_map(translation_config)
        raw_display_order = (
            subtitle_output.get("display_order", ["source", *enabled_slots])
            if isinstance(subtitle_output, dict)
            else ["source", *enabled_slots]
        )
        normalized_order: list[str] = []
        for item in raw_display_order if isinstance(raw_display_order, list) else []:
            value = str(item).strip().lower()
            if value == "source":
                if value not in normalized_order:
                    normalized_order.append(value)
                continue
            if value in enabled_slots:
                if value not in normalized_order:
                    normalized_order.append(value)
                continue
            mapped_slot = language_to_slot.get(value)
            if mapped_slot and mapped_slot not in normalized_order:
                normalized_order.append(mapped_slot)
        if "source" not in normalized_order:
            normalized_order.append("source")
        for slot_id in enabled_slots:
            if slot_id not in normalized_order:
                normalized_order.append(slot_id)
        return normalized_order

    def build_payload(self, sequence: int, *, record: dict) -> SubtitlePayloadEvent:
        config = self.config_getter()
        translation_config = config.get("translation", {})
        subtitle_output = config.get("subtitle_output", {})
        overlay = config.get("overlay", {})
        subtitle_style = resolve_effective_subtitle_style(config.get("subtitle_style", {}))

        show_source = bool(subtitle_output.get("show_source", True))
        show_translations = bool(subtitle_output.get("show_translations", True))
        max_translation_languages = max(0, min(5, int(subtitle_output.get("max_translation_languages", 0) or 0)))
        translation_slots = self.translation_slot_map(translation_config if isinstance(translation_config, dict) else {})
        display_order = self.resolved_display_order(
            translation_config if isinstance(translation_config, dict) else {},
            subtitle_output if isinstance(subtitle_output, dict) else {},
        )

        items: list[SubtitleLineItem] = []
        visible_items: list[SubtitleLineItem] = []

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

            line_config = translation_slots.get(code)
            if line_config is None:
                continue

            translation = record["translations"].get(code)
            success = bool(translation and translation.get("success", False))
            text = str(translation.get("text", "")) if translation else ""
            error = str(translation.get("error")) if translation and translation.get("error") else None
            can_show = (
                show_translations
                and len([item for item in visible_items if item.kind == "translation"]) < max_translation_languages
                and success
                and bool(text)
            )
            item = SubtitleLineItem(
                kind="translation",
                lang=str(translation.get("target_lang") if translation else line_config.get("target_lang", code)),
                label=str(
                    translation.get("label")
                    if translation and translation.get("label")
                    else line_config.get("label") or str(line_config.get("target_lang", code)).upper()
                ),
                text=text,
                style_slot=code if can_show else None,
                slot_id=code,
                target_lang=str(translation.get("target_lang") if translation else line_config.get("target_lang", code)),
                provider=str(translation.get("provider")) if translation and translation.get("provider") else None,
                visible=can_show,
                success=success,
                error=error,
            )
            items.append(item)
            if can_show:
                visible_items.append(item)

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

    def should_suppress_source_partial_display(self) -> bool:
        config = self.config_getter()
        subtitle_output = config.get("subtitle_output", {}) if isinstance(config, dict) else {}
        if not isinstance(subtitle_output, dict):
            return False
        return not bool(subtitle_output.get("show_source", True))

    def build_presentation_payload(self, core: SubtitleLifecycleCore) -> SubtitlePayloadEvent:
        completed_payload = core.current_completed_payload()
        active_partial = core.active_partial or {}
        active_partial_text = str(active_partial.get("text", "")) if active_partial else ""
        active_partial_sequence = int(active_partial.get("sequence")) if active_partial and active_partial.get("sequence") is not None else None
        active_partial_source_lang = str(active_partial.get("source_lang", "auto")) if active_partial else None
        display_partial_source = not self.should_suppress_source_partial_display()
        visible_partial_text = active_partial_text if display_partial_source else ""

        completed_translation_payload = core.current_completed_payload(hide_source=True) if active_partial_text else completed_payload

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
        display_order = self.resolved_display_order(
            translation_config if isinstance(translation_config, dict) else {},
            subtitle_output if isinstance(subtitle_output, dict) else {},
        ) if isinstance(subtitle_output, dict) else []

        if active_partial_text and completed_payload is None:
            show_source = bool(subtitle_output.get("show_source", True)) if isinstance(subtitle_output, dict) else True
            source_item = SubtitleLineItem(
                kind="source",
                lang=str(
                    active_partial_source_lang
                    or (str(config.get("source_lang", "auto")) if isinstance(config, dict) else "auto")
                ),
                label=str(
                    active_partial_source_lang
                    or (str(config.get("source_lang", "auto")) if isinstance(config, dict) else "auto")
                ).upper(),
                text=active_partial_text,
                style_slot="source" if show_source and bool(active_partial_text) else None,
                visible=show_source and bool(active_partial_text),
            )
            visible_items = [source_item] if source_item.visible and source_item.text else []
            return SubtitlePayloadEvent(
                sequence=active_partial_sequence or 0,
                source_lang=active_partial_source_lang or str(config.get("source_lang", "auto")) if isinstance(config, dict) else "auto",
                source_text=active_partial_text,
                provider=str(active_partial.get("provider")) if active_partial and active_partial.get("provider") else None,
                preset=str(overlay.get("preset", "single")) if isinstance(overlay, dict) else "single",
                compact=bool(overlay.get("compact", False)) if isinstance(overlay, dict) else False,
                display_order=display_order,
                show_source=bool(subtitle_output.get("show_source", True)) if isinstance(subtitle_output, dict) else True,
                show_translations=bool(subtitle_output.get("show_translations", True)) if isinstance(subtitle_output, dict) else True,
                max_translation_languages=max(0, min(5, int(subtitle_output.get("max_translation_languages", 0) or 0))) if isinstance(subtitle_output, dict) else 0,
                style=resolve_effective_subtitle_style(config.get("subtitle_style", {}) if isinstance(config, dict) else {}),
                lifecycle_state=lifecycle_state,
                completed_block_visible=False,
                completed_expires_at_utc=core.completed_expires_at_utc,
                active_partial_text=visible_partial_text,
                active_partial_sequence=active_partial_sequence,
                active_partial_source_lang=active_partial_source_lang,
                items=[source_item],
                visible_items=visible_items,
                line1=visible_items[0].text if visible_items else "",
                line2="",
            )

        payload = completed_translation_payload or SubtitlePayloadEvent(
            sequence=0,
            source_lang=str(config.get("source_lang", "auto")) if isinstance(config, dict) else "auto",
            source_text="",
            provider=None,
            preset=str(overlay.get("preset", "single")) if isinstance(overlay, dict) else "single",
            compact=bool(overlay.get("compact", False)) if isinstance(overlay, dict) else False,
            display_order=display_order,
            show_source=bool(subtitle_output.get("show_source", True)) if isinstance(subtitle_output, dict) else True,
            show_translations=bool(subtitle_output.get("show_translations", True)) if isinstance(subtitle_output, dict) else True,
            max_translation_languages=max(0, min(5, int(subtitle_output.get("max_translation_languages", 0) or 0))) if isinstance(subtitle_output, dict) else 0,
            style=resolve_effective_subtitle_style(config.get("subtitle_style", {}) if isinstance(config, dict) else {}),
        )

        # Merge partial with completed translations if needed.
        if active_partial_text and completed_translation_payload is not None:
            preserve_completed_translations = bool(core._subtitle_lifecycle_config().get("keep_completed_translation_during_active_partial", True))  # type: ignore[attr-defined]
            if not preserve_completed_translations and completed_translation_payload.visible_items:
                self.increment_counter_metric("overlay_payload_mismatch_count", 1)

            show_source = bool(subtitle_output.get("show_source", True)) if isinstance(subtitle_output, dict) else True
            show_translations = bool(subtitle_output.get("show_translations", True)) if isinstance(subtitle_output, dict) else True
            max_translation_languages = (
                max(0, min(5, int(subtitle_output.get("max_translation_languages", 0) or 0)))
                if isinstance(subtitle_output, dict)
                else 0
            )
            active_source_lang = active_partial_source_lang or payload.source_lang
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
            for code in display_order:
                if code == "source":
                    items.append(source_item)
                    if source_item.visible and source_item.text:
                        visible_items.append(source_item)
                    continue

                translation_item = next(
                    (
                        item
                        for item in payload.items
                        if item.kind == "translation" and str(item.slot_id or item.lang).lower() == code
                    ),
                    None,
                )
                if translation_item is None:
                    continue
                can_show = (
                    preserve_completed_translations
                    and show_translations
                    and len([item for item in visible_items if item.kind == "translation"]) < max_translation_languages
                    and bool(translation_item.success)
                    and bool(translation_item.text)
                )
                if not preserve_completed_translations and bool(translation_item.text):
                    self.increment_counter_metric("overlay_stale_translation_suppressed", 1)
                updated_translation_item = translation_item.model_copy(
                    update={"visible": can_show, "style_slot": code if can_show else None}
                )
                items.append(updated_translation_item)
                if updated_translation_item.visible and updated_translation_item.text:
                    visible_items.append(updated_translation_item)

            line1 = visible_items[0].text if visible_items else ""
            line2 = "\n".join(item.text for item in visible_items[1:]) if len(visible_items) > 1 else ""
            payload = payload.model_copy(
                update={
                    "sequence": active_partial_sequence or payload.sequence,
                    "source_text": active_partial_text,
                    "source_lang": str(active_source_lang),
                    "provider": str(active_partial.get("provider")) if active_partial and active_partial.get("provider") else payload.provider,
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

        completed_block_visible = completed_payload is not None and bool(completed_payload.visible_items)
        return payload.model_copy(
            update={
                "lifecycle_state": lifecycle_state,
                "completed_block_visible": completed_block_visible,
                "completed_expires_at_utc": core.completed_expires_at_utc,
                "active_partial_text": visible_partial_text,
                "active_partial_sequence": active_partial_sequence,
                "active_partial_source_lang": active_partial_source_lang,
            }
        )

