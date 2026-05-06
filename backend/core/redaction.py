from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


REDACTED_VALUE = "[redacted]"
SENSITIVE_KEYS = {
    "api_key",
    "token",
    "secret",
    "password",
    "authorization",
    "credential",
    "credentials",
    "pair_code",
    "local_admin_token",
    "bearer",
}
SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "token",
    "secret",
    "password",
    "authorization",
    "credential",
    "pair_code",
    "local_admin_token",
    "bearer",
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+([^\s,;]+)")
_QUERY_PARAM_PATTERN = re.compile(
    r"(?i)\b(api_key|token|secret|password|authorization|credential|credentials|pair_code|local_admin_token|bearer)=([^&\s]+)"
)


def is_sensitive_key(key: str | None) -> bool:
    normalized = str(key or "").strip().lower()
    if not normalized:
        return False
    if normalized in SENSITIVE_KEYS:
        return True
    return any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    try:
        parsed = urlsplit(raw)
    except Exception:
        return redact_text(raw)

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    changed = False
    redacted_pairs: list[tuple[str, str]] = []
    for key, entry_value in query_pairs:
        if is_sensitive_key(key):
            redacted_pairs.append((key, REDACTED_VALUE))
            changed = True
        else:
            redacted_pairs.append((key, entry_value))

    fragment = parsed.fragment
    if "=" in fragment:
        fragment_pairs = parse_qsl(fragment, keep_blank_values=True)
        if fragment_pairs:
            fragment = urlencode(
                [(key, REDACTED_VALUE if is_sensitive_key(key) else entry_value) for key, entry_value in fragment_pairs],
                doseq=True,
            )
            changed = changed or any(is_sensitive_key(key) for key, _ in fragment_pairs)

    if not changed:
        return raw
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(redacted_pairs, doseq=True),
            fragment,
        )
    )


def redact_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return text
    text = _BEARER_PATTERN.sub("Bearer [redacted]", text)
    text = _QUERY_PARAM_PATTERN.sub(lambda match: f"{match.group(1)}={REDACTED_VALUE}", text)
    return text


def redact_value(value: Any, *, key: str | None = None) -> Any:
    if is_sensitive_key(key):
        return REDACTED_VALUE
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, set):
        return [redact_value(item) for item in sorted(value, key=lambda item: str(item))]
    if isinstance(value, str):
        normalized_key = str(key or "").strip().lower()
        if normalized_key == "endpoint":
            redacted_url = redact_url(value)
            if redacted_url != value:
                return redacted_url
            if "secret" in value.lower():
                return REDACTED_VALUE
        return redact_text(value)
    return value


def redact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        normalized_key = str(key)
        sanitized[normalized_key] = redact_value(value, key=normalized_key)
    return sanitized


def redact_data(value: Any) -> Any:
    return redact_value(value)
