from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from backend.core.redaction import redact_data


@dataclass(slots=True)
class GoogleLegacyHttpParsedResult:
    text: str
    is_partial: bool
    is_final: bool
    confidence: float | None = None
    language: str | None = None
    raw_debug: dict[str, Any] | None = None


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_raw_debug(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    debug_payload: dict[str, Any] = {}
    for key in ("result_index", "result", "results", "final", "isFinal", "stability", "language", "lang"):
        if key in payload:
            debug_payload[key] = payload.get(key)
    return redact_data(debug_payload) if debug_payload else None


def _parse_google_result_entry(entry: dict[str, Any], *, language: str | None, raw_debug: dict[str, Any] | None) -> list[GoogleLegacyHttpParsedResult]:
    alternatives = entry.get("alternative")
    if not isinstance(alternatives, list):
        alternatives = entry.get("alternatives")
    if not isinstance(alternatives, list):
        alternatives = []
    transcripts: list[tuple[str, float | None]] = []
    for alternative in alternatives:
        if not isinstance(alternative, dict):
            continue
        text = _normalized_text(alternative.get("transcript") or alternative.get("text"))
        if not text:
            continue
        transcripts.append((text, _to_float(alternative.get("confidence"))))
    if not transcripts:
        direct_text = _normalized_text(entry.get("transcript") or entry.get("text"))
        if direct_text:
            transcripts.append((direct_text, _to_float(entry.get("confidence"))))
    if not transcripts:
        return []

    is_final = bool(entry.get("final", entry.get("isFinal", False)))
    best_text, best_confidence = transcripts[0]
    return [
        GoogleLegacyHttpParsedResult(
            text=best_text,
            is_partial=not is_final,
            is_final=is_final,
            confidence=best_confidence,
            language=language,
            raw_debug=raw_debug,
        )
    ]


def _parse_shape(payload: Any) -> list[GoogleLegacyHttpParsedResult]:
    if isinstance(payload, list):
        parsed_results: list[GoogleLegacyHttpParsedResult] = []
        for item in payload:
            parsed_results.extend(_parse_shape(item))
        return parsed_results

    if not isinstance(payload, dict):
        return []

    language = _normalized_text(payload.get("language") or payload.get("lang")) or None
    raw_debug = _build_raw_debug(payload)

    if isinstance(payload.get("result"), list):
        parsed_results: list[GoogleLegacyHttpParsedResult] = []
        for entry in payload["result"]:
            if isinstance(entry, dict):
                parsed_results.extend(_parse_google_result_entry(entry, language=language, raw_debug=raw_debug))
        return parsed_results

    if isinstance(payload.get("results"), list):
        parsed_results = []
        for entry in payload["results"]:
            if isinstance(entry, dict):
                parsed_results.extend(_parse_google_result_entry(entry, language=language, raw_debug=raw_debug))
        return parsed_results

    direct_text = _normalized_text(payload.get("transcript") or payload.get("text"))
    if direct_text:
        is_final = bool(payload.get("final", payload.get("isFinal", payload.get("type") == "final")))
        return [
            GoogleLegacyHttpParsedResult(
                text=direct_text,
                is_partial=not is_final,
                is_final=is_final,
                confidence=_to_float(payload.get("confidence")),
                language=language,
                raw_debug=raw_debug,
            )
        ]
    return []


def parse_google_legacy_http_message(raw_message: str) -> list[GoogleLegacyHttpParsedResult]:
    text = str(raw_message or "").strip()
    if not text:
        return []
    candidate = text
    if candidate.startswith(")]}'"):
        candidate = candidate[4:].lstrip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    return _parse_shape(payload)
