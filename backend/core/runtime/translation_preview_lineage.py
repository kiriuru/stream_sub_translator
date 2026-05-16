"""Domain C — translation preview supersession keyed by source lineage (segment + revision)."""

from __future__ import annotations

class TranslationPreviewLineage:
    """Tracks which preview generation is current for a (segment_id, revision) Domain B key."""

    def __init__(self) -> None:
        self._generation_by_key: dict[str, int] = {}

    @staticmethod
    def lineage_key(segment_id: str | None, revision: int | None) -> str | None:
        if not segment_id or revision is None:
            return None
        return f"{segment_id}:{int(revision)}"

    def supersede(self, key: str | None) -> int:
        """
        Mark a new preview wave for `key`. Returns monotonic generation id for this key.
        Callers should cancel or ignore stale work with generation < returned value.
        """
        if not key:
            return 0
        cur = self._generation_by_key.get(key, 0) + 1
        self._generation_by_key[key] = cur
        return cur

    def generation(self, key: str | None) -> int:
        if not key:
            return 0
        return int(self._generation_by_key.get(key, 0))


__all__ = ["TranslationPreviewLineage"]
