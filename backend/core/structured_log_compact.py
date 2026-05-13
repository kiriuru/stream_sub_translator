from __future__ import annotations

from typing import Any, Mapping

# Structured runtime JSONL should stay small: one line per event, safe on slow disks / network shares.
_DEFAULT_MAX_STR = 160
_DEFAULT_MAX_LIST = 10
_DEFAULT_MAX_DEPTH = 4


def compact_for_runtime_log(
    obj: Any,
    *,
    max_str: int = _DEFAULT_MAX_STR,
    max_list: int = _DEFAULT_MAX_LIST,
    depth: int = 0,
    max_depth: int = _DEFAULT_MAX_DEPTH,
) -> Any:
    """
    Shrink values for runtime-events.log: truncate long strings, summarize long lists,
    cap nesting depth. None is returned as None and typically dropped by the caller.
    """
    if obj is None:
        return None
    if isinstance(obj, str):
        if len(obj) <= max_str:
            return obj
        return f"{obj[: max_str - 1]}…"
    if isinstance(obj, (bool, int, float)):
        return obj
    if depth >= max_depth:
        if isinstance(obj, (list, tuple)):
            return f"<list len={len(obj)}>"
        if isinstance(obj, dict):
            return f"<dict keys={len(obj)}>"
        return (str(obj))[:max_str]
    if isinstance(obj, (list, tuple)):
        if len(obj) <= max_list:
            return [
                compact_for_runtime_log(v, max_str=max_str, max_list=max_list, depth=depth + 1, max_depth=max_depth)
                for v in obj
            ]
        head = [
            compact_for_runtime_log(v, max_str=max_str, max_list=max_list, depth=depth + 1, max_depth=max_depth)
            for v in obj[:max_list]
        ]
        return {"_items_len": len(obj), "_items_preview": head}
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, val in obj.items():
            k = str(key)
            cv = compact_for_runtime_log(val, max_str=max_str, max_list=max_list, depth=depth + 1, max_depth=max_depth)
            if cv is not None:
                out[k] = cv
        return out
    return (str(obj))[:max_str]


def compact_mapping_for_runtime_log(mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    if not mapping:
        return {}
    compacted = compact_for_runtime_log(dict(mapping))
    return compacted if isinstance(compacted, dict) else {"_value": compacted}
