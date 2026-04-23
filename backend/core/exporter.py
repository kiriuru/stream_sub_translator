from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Exporter:
    def __init__(self, export_dir: Path) -> None:
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def build_session_basename(
        self,
        *,
        session_started_at_utc: str | None,
        session_id: str,
        profile: str | None = None,
    ) -> str:
        timestamp_label = session_id
        if session_started_at_utc:
            try:
                parsed = datetime.fromisoformat(session_started_at_utc.replace("Z", "+00:00"))
                timestamp_label = parsed.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
            except ValueError:
                timestamp_label = session_id

        safe_profile = self._safe_name_fragment(profile or "default")
        safe_session_id = self._safe_name_fragment(session_id)
        return f"session-{timestamp_label}-{safe_profile}-{safe_session_id}"

    def export_jsonl(self, filename: str, rows: list[dict[str, Any]]) -> Path:
        target = self.export_dir / filename
        with target.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return target

    def export_srt(self, filename: str, records: list[dict[str, Any]]) -> Path:
        cues: list[str] = []
        cue_index = 1
        for record in records:
            text = str(record.get("srt_text", "") or "").strip()
            if not text:
                continue

            start_ms = max(0, int(record.get("start_offset_ms", 0) or 0))
            end_ms = max(0, int(record.get("end_offset_ms", 0) or 0))
            duration_ms = max(0, int(record.get("duration_ms", 0) or 0))
            if end_ms <= start_ms:
                end_ms = start_ms + max(500, duration_ms or 1500)

            cues.append(
                f"{cue_index}\n"
                f"{self._format_srt_timestamp(start_ms)} --> {self._format_srt_timestamp(end_ms)}\n"
                f"{text}\n"
            )
            cue_index += 1

        if not cues:
            raise ValueError("No exportable finalized subtitle records for SRT export.")

        target = self.export_dir / filename
        target.write_text("\n".join(cues).rstrip() + "\n", encoding="utf-8")
        return target

    def export_session(
        self,
        *,
        base_filename: str,
        session_row: dict[str, Any],
        records: list[dict[str, Any]],
    ) -> list[Path]:
        meaningful_records = [dict(record) for record in records if str(record.get("srt_text", "") or "").strip()]
        if not meaningful_records:
            return []

        jsonl_rows = [dict(session_row), *meaningful_records]
        return [
            self.export_jsonl(f"{base_filename}.jsonl", jsonl_rows),
            self.export_srt(f"{base_filename}.srt", meaningful_records),
        ]

    def _format_srt_timestamp(self, total_ms: int) -> str:
        hours, remainder = divmod(max(0, int(total_ms)), 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, milliseconds = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def _safe_name_fragment(self, value: str) -> str:
        collapsed = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
        collapsed = collapsed.strip(".-")
        return collapsed or "default"
