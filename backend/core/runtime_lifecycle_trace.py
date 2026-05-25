from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from backend.core.asr_provider_selection import resolve_effective_asr_provider
from backend.core.diagnostic_flags import is_runtime_lifecycle_trace_enabled
from backend.core.redaction import redact_data
from backend.core.structured_runtime_logger import StructuredRuntimeLogger


def runtime_trace(
    logger: StructuredRuntimeLogger | None,
    event: str,
    *,
    source: str = "runtime_lifecycle",
    payload: Mapping[str, Any] | None = None,
    **fields: Any,
) -> None:
    if logger is None:
        return
    # runtime_lifecycle.* is an opt-in diagnostic channel — by default we do not
    # append extra rows to runtime-events.log (this matches 0.4.1 baseline).
    if not is_runtime_lifecycle_trace_enabled():
        return
    normalized_event = str(event or "").strip()
    if not normalized_event:
        return
    logger.log("runtime_lifecycle", normalized_event, source=source, payload=payload, **fields)


def summarize_runtime_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    cfg = config if isinstance(config, Mapping) else {}
    resolved_asr = resolve_effective_asr_provider(dict(cfg))
    asr = cfg.get("asr") if isinstance(cfg.get("asr"), Mapping) else {}
    audio = cfg.get("audio") if isinstance(cfg.get("audio"), Mapping) else {}
    translation = cfg.get("translation") if isinstance(cfg.get("translation"), Mapping) else {}
    realtime = asr.get("realtime") if isinstance(asr, Mapping) and isinstance(asr.get("realtime"), Mapping) else {}
    target_languages = translation.get("target_languages") if isinstance(translation, Mapping) else []
    config_hash = hashlib.sha256(
        json.dumps(redact_data(dict(cfg)), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "config_version": cfg.get("config_version"),
        "config_hash": config_hash,
        "asr.mode": resolved_asr.get("mode"),
        "asr.provider_preference": resolved_asr.get("provider_preference"),
        "asr.effective_provider": resolved_asr.get("effective_provider"),
        "asr.uses_backend_audio_capture": bool(resolved_asr.get("uses_backend_audio_capture")),
        "asr.prefer_gpu": bool(asr.get("prefer_gpu")) if isinstance(asr, Mapping) else False,
        "asr.latency_preset": realtime.get("latency_preset") if isinstance(realtime, Mapping) else None,
        "audio.input_device_id": audio.get("input_device_id") if isinstance(audio, Mapping) else None,
        "translation.enabled": bool(translation.get("enabled")) if isinstance(translation, Mapping) else False,
        "translation.provider": translation.get("provider") if isinstance(translation, Mapping) else None,
        "target_languages_count": len([item for item in target_languages if str(item).strip()])
        if isinstance(target_languages, list)
        else 0,
        "remote.role": (
            (cfg.get("remote") or {}).get("role")
            if isinstance(cfg.get("remote"), Mapping)
            else None
        ),
    }


def summarize_device_resolution(
    *,
    requested_device_id: str | None,
    resolved_device_id: str | None,
    audio_input_count: int,
    configured_device_id: str | None = None,
) -> dict[str, Any]:
    return {
        "requested_device_id": requested_device_id,
        "configured_device_id": configured_device_id,
        "resolved_device_id": resolved_device_id,
        "audio_input_count": int(audio_input_count),
        "resolution": (
            "request"
            if requested_device_id
            else "config"
            if configured_device_id and resolved_device_id == configured_device_id
            else "default"
            if resolved_device_id
            else "none"
        ),
    }


def summarize_metrics_snapshot(metrics: Mapping[str, Any] | None) -> dict[str, Any]:
    data = metrics if isinstance(metrics, Mapping) else {}
    keys = (
        "vad_segments_partial",
        "vad_segments_final",
        "asr_queue_depth",
        "partial_updates_emitted",
        "finals_emitted",
        "in_flight_transcribe_count",
        "vad_dropped_segments",
        "vad_ms",
    )
    return {key: data.get(key) for key in keys if key in data}


def summarize_asr_diagnostics_snapshot(diagnostics: Mapping[str, Any] | None) -> dict[str, Any]:
    data = diagnostics if isinstance(diagnostics, Mapping) else {}
    keys = (
        "sample_rate",
        "model_loaded",
        "runtime_initialized",
        "selected_device",
        "device_active",
        "actual_execution_provider",
        "torch_version",
        "torch_cuda_is_available",
        "capture_sample_rate",
    )
    snapshot = {key: data.get(key) for key in keys if key in data}
    if "capture_sample_rate" not in snapshot and data.get("sample_rate") is not None:
        snapshot["capture_sample_rate"] = data.get("sample_rate")
    return snapshot
