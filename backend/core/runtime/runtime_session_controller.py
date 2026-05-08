from __future__ import annotations

from typing import Any, Callable


class RuntimeSessionController:
    """
    Owns runtime session identity/timestamps and export record bookkeeping.

    Behavior is preserved: the goal is to centralize session/export state mutation
    while keeping runtime/export payload shapes and timestamps identical.
    """

    name = "runtime_session"

    def __init__(
        self,
        *,
        bump_asr_runtime_generation: Callable[[], None],
        set_sequence_zero: Callable[[], None],
        new_session_id: Callable[[], str],
        now_utc_iso: Callable[[], str],
        now_monotonic: Callable[[], float],
        reset_metrics: Callable[[], None],
        reset_in_flight_transcribe_count: Callable[[], None],
        clear_runtime_loop: Callable[[], None],
    ) -> None:
        self._bump_asr_runtime_generation = bump_asr_runtime_generation
        self._set_sequence_zero = set_sequence_zero
        self._new_session_id = new_session_id
        self._now_utc_iso = now_utc_iso
        self._now_monotonic = now_monotonic
        self._reset_metrics = reset_metrics
        self._reset_in_flight_transcribe_count = reset_in_flight_transcribe_count
        self._clear_runtime_loop = clear_runtime_loop

        self._session_id: str | None = None
        self._session_started_at_utc: str | None = None
        self._session_started_at_monotonic: float | None = None
        self._session_export_records: list[dict[str, object]] = []

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def session_started_at_utc(self) -> str | None:
        return self._session_started_at_utc

    @property
    def session_started_at_monotonic(self) -> float | None:
        return self._session_started_at_monotonic

    @property
    def session_export_records(self) -> list[dict[str, object]]:
        return self._session_export_records

    def start_new_session(self) -> str:
        # Mirrors previous start() side effects ordering.
        self.reset_export_session()
        self._set_sequence_zero()
        self._bump_asr_runtime_generation()
        started_at = self._now_utc_iso()
        session_id = self._new_session_id()
        started_at_monotonic = self._now_monotonic()
        self._session_id = session_id
        self._session_started_at_utc = started_at
        self._session_started_at_monotonic = started_at_monotonic
        return started_at

    def stop_cleanup(self) -> None:
        self.reset_export_session()
        self._reset_metrics()
        self._reset_in_flight_transcribe_count()
        self._clear_runtime_loop()

    def reset_export_session(self) -> None:
        self._session_id = None
        self._session_started_at_utc = None
        self._session_started_at_monotonic = None
        self._session_export_records.clear()

    def add_completed_export_record(self, record: dict[str, Any]) -> None:
        if not isinstance(record, dict):
            return
        if not self._session_id:
            return
        finalized_at_monotonic = record.get("finalized_at_monotonic")
        if self._session_started_at_monotonic is None or not isinstance(finalized_at_monotonic, (int, float)):
            return

        end_offset_ms = max(
            0,
            int(round((float(finalized_at_monotonic) - self._session_started_at_monotonic) * 1000.0)),
        )
        duration_ms_raw = record.get("duration_ms")
        duration_ms = int(duration_ms_raw) if isinstance(duration_ms_raw, (int, float)) and int(duration_ms_raw) > 0 else None
        start_offset_ms = max(0, end_offset_ms - duration_ms) if duration_ms is not None else max(0, end_offset_ms - 1200)

        export_record: dict[str, object] = dict(record)
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

    def has_exportable_records(self) -> bool:
        return bool(self._session_id and self._session_started_at_utc and self._session_export_records)

    def build_session_export_payload(
        self,
        config: dict[str, Any],
        *,
        stopped_at_utc: str,
    ) -> tuple[dict[str, object], list[dict[str, object]]] | None:
        if not self.has_exportable_records():
            return None

        cfg = config if isinstance(config, dict) else {}
        translation_config = cfg.get("translation", {}) if isinstance(cfg.get("translation"), dict) else {}
        subtitle_output = cfg.get("subtitle_output", {}) if isinstance(cfg.get("subtitle_output"), dict) else {}

        session_row: dict[str, object] = {
            "type": "session",
            "session_id": self._session_id,
            "started_at_utc": self._session_started_at_utc,
            "stopped_at_utc": stopped_at_utc,
            "profile": str(cfg.get("profile", "default") or "default"),
            "source_lang": str(cfg.get("source_lang", "auto") or "auto"),
            "translation_enabled": bool(translation_config.get("enabled", False)),
            "target_languages": list(translation_config.get("target_languages", [])),
            "subtitle_output": dict(subtitle_output),
            "record_count": len(self._session_export_records),
        }
        # Return a shallow copy of records to reduce accidental external mutation.
        return session_row, [dict(r) for r in self._session_export_records]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "session_id": self._session_id,
            "has_active_session": bool(self._session_id),
            "session_started_at_utc": self._session_started_at_utc,
            "record_count": len(self._session_export_records),
        }

