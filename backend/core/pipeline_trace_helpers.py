from __future__ import annotations

import time
from typing import Any


def audio_bytes_metrics(audio: bytes | None) -> dict[str, Any]:
    data = audio or b""
    byte_len = len(data)
    fields: dict[str, Any] = {"audio_byte_len": byte_len}
    if byte_len < 2:
        return fields
    try:
        import numpy as np

        samples = np.frombuffer(data, dtype=np.int16)
        if samples.size:
            fields["audio_rms"] = round(float(np.sqrt(np.mean(samples.astype(np.float64) ** 2))), 2)
            fields["audio_peak"] = int(np.max(np.abs(samples)))
    except Exception:
        pass
    return fields


def audio_chunk_metrics(chunk: Any | None) -> dict[str, Any]:
    if chunk is None:
        return {"chunk_present": False}
    level = getattr(chunk, "level", None)
    data = getattr(chunk, "data", b"") or b""
    fields: dict[str, Any] = {
        "chunk_present": True,
        "capture_level": round(float(level), 4) if level is not None else None,
        "frame_count": getattr(chunk, "frame_count", None),
        "sample_rate": getattr(chunk, "sample_rate", None),
    }
    fields.update(audio_bytes_metrics(data if isinstance(data, (bytes, bytearray)) else b""))
    return fields


def vad_segment_metrics(segment: Any) -> dict[str, Any]:
    audio = getattr(segment, "audio", b"") or b""
    return {
        "kind": getattr(segment, "kind", None),
        "duration_ms": getattr(segment, "duration_ms", None),
        "voiced_ratio": round(float(getattr(segment, "voiced_ratio", 0.0) or 0.0), 4),
        "average_rms": round(float(getattr(segment, "average_rms", 0.0) or 0.0), 2),
        **audio_bytes_metrics(audio if isinstance(audio, (bytes, bytearray)) else b""),
    }


def text_outcome_metrics(text: str | None) -> dict[str, Any]:
    normalized = str(text or "")
    return {
        "text_len": len(normalized),
        "text_nonempty": bool(normalized.strip()),
        "text_preview": normalized[:80] if normalized else "",
    }


class PipelineTraceHeartbeat:
    """Emit at most one heartbeat per interval (monotonic clock)."""

    def __init__(self, interval_ms: float = 1000.0) -> None:
        self._interval_s = max(0.05, float(interval_ms) / 1000.0)
        self._last_emit = 0.0

    def due(self) -> bool:
        now = time.perf_counter()
        if now - self._last_emit >= self._interval_s:
            self._last_emit = now
            return True
        return False

    def reset(self) -> None:
        self._last_emit = 0.0
