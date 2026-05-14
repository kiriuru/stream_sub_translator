from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.models import TranscriptEvent, TranscriptSegment

_BUILTIN_PATH = Path(__file__).resolve().parent.parent / "data" / "source_text_builtin_pairs.json"


@lru_cache(maxsize=1)
def _load_builtin_pairs_raw() -> tuple[tuple[str, str], ...]:
    try:
        raw = _BUILTIN_PATH.read_text(encoding="utf-8")
    except OSError:
        return ()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(data, list):
        return ()
    out: list[tuple[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "")).strip()
        target = str(item.get("target", ""))
        if not source:
            continue
        out.append((source, target))
    return tuple(out)


def _normalize_custom_pairs(pairs: Any) -> list[tuple[str, str]]:
    if not isinstance(pairs, list):
        return []
    out: list[tuple[str, str]] = []
    for item in pairs:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "")).strip()
        target = str(item.get("target", ""))
        if not source:
            continue
        out.append((source, target))
    return out[:100]


def effective_replacement_pairs(config: dict[str, Any] | None) -> list[tuple[str, str]]:
    root = config if isinstance(config, dict) else {}
    block = root.get("source_text_replacement", {})
    if not isinstance(block, dict) or not bool(block.get("enabled")):
        return []
    case_insensitive = bool(block.get("case_insensitive", True))
    include_builtin = bool(block.get("include_builtin", True))
    custom = _normalize_custom_pairs(block.get("pairs"))

    def _key(source: str) -> str:
        return source.casefold() if case_insensitive else source

    by_key: dict[str, tuple[str, str]] = {}
    for source, target in custom:
        by_key[_key(source)] = (source, target)
    if include_builtin:
        for source, target in _load_builtin_pairs_raw():
            k = _key(source)
            if k not in by_key:
                by_key[k] = (source, target)
    merged = list(by_key.values())
    merged.sort(key=lambda item: len(item[0]), reverse=True)
    return merged


def apply_replacement_rules(
    text: str,
    pairs: list[tuple[str, str]],
    *,
    case_insensitive: bool,
    whole_words: bool,
) -> str:
    if not text or not pairs:
        return text
    sorted_pairs = sorted(pairs, key=lambda item: len(item[0]), reverse=True)
    flags = re.IGNORECASE if case_insensitive else 0
    result = text
    for source, target in sorted_pairs:
        if not source:
            continue
        escaped = re.escape(source)
        if whole_words:
            pattern = rf"(?<!\w){escaped}(?!\w)"
        else:
            pattern = escaped
        rx = re.compile(pattern, flags=flags)
        result = rx.sub(lambda _m: target, result)
    return result


def apply_source_text_replacement(text: str, config: dict[str, Any] | None) -> str:
    root = config if isinstance(config, dict) else {}
    block = root.get("source_text_replacement", {})
    if not isinstance(block, dict) or not bool(block.get("enabled")):
        return text
    pairs = effective_replacement_pairs(root)
    if not pairs:
        return text
    return apply_replacement_rules(
        text,
        pairs,
        case_insensitive=bool(block.get("case_insensitive", True)),
        whole_words=bool(block.get("whole_words", True)),
    )


def apply_to_transcript_event(event: TranscriptEvent, config: dict[str, Any] | None) -> TranscriptEvent:
    block = (config or {}).get("source_text_replacement", {}) if isinstance(config, dict) else {}
    if not isinstance(block, dict) or not bool(block.get("enabled")):
        return event
    new_text = apply_source_text_replacement(str(event.text or ""), config if isinstance(config, dict) else {})
    if new_text == event.text:
        return event
    segment = event.segment
    new_segment: TranscriptSegment | None = None
    if segment is not None:
        new_segment = segment.model_copy(update={"text": new_text})
    return event.model_copy(update={"text": new_text, "segment": new_segment})
