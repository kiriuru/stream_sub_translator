"""Shared UI locale normalization for desktop shell and splash."""

from __future__ import annotations

SUPPORTED_UI_LANGUAGES = frozenset({"en", "ru", "ja", "ko", "zh"})


def normalize_ui_language(value: str | None) -> str:
    current = str(value or "").strip().lower()
    if current in SUPPORTED_UI_LANGUAGES:
        return current
    if current.startswith("ru"):
        return "ru"
    if current.startswith("zh"):
        return "zh"
    if current.startswith("ja"):
        return "ja"
    if current.startswith("ko"):
        return "ko"
    if current.startswith("en"):
        return "en"
    return "en"
