from __future__ import annotations

from typing import Any


def normalize_source_text_replacement_config(
    payload: Any,
    *,
    defaults: dict[str, Any],
) -> dict[str, Any]:
    base = defaults if isinstance(defaults, dict) else {}
    current = payload if isinstance(payload, dict) else {}
    out = {
        "enabled": bool(current.get("enabled", base.get("enabled", False))),
        "include_builtin": bool(current.get("include_builtin", base.get("include_builtin", True))),
        "case_insensitive": bool(current.get("case_insensitive", base.get("case_insensitive", True))),
        "whole_words": bool(current.get("whole_words", base.get("whole_words", True))),
        "pairs": [],
    }
    raw_pairs = current.get("pairs", base.get("pairs", []))
    pairs: list[dict[str, str]] = []
    if isinstance(raw_pairs, list):
        for item in raw_pairs[:100]:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "")).strip()
            if not source:
                continue
            target = str(item.get("target", ""))
            pairs.append({"source": source, "target": target})
    out["pairs"] = pairs
    return out
