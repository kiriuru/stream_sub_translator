from __future__ import annotations

from typing import Any

from backend.config.normalizers.browser import normalize_browser_asr_config


def normalize_realtime_asr_config(payload: Any, *, defaults: dict[str, Any]) -> dict[str, Any]:
    current = payload if isinstance(payload, dict) else {}

    def clamp_int(key: str, minimum: int, maximum: int) -> int:
        raw = current.get(key, defaults[key])
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = int(defaults[key])
        return max(minimum, min(maximum, value))

    def clamp_float(key: str, minimum: float, maximum: float) -> float:
        raw = current.get(key, defaults[key])
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = float(defaults[key])
        return max(minimum, min(maximum, value))

    silence_hold_ms = clamp_int("silence_hold_ms", 60, 3000)
    finalization_hold_ms = clamp_int("finalization_hold_ms", silence_hold_ms, 5000)
    chunk_window_ms = clamp_int("chunk_window_ms", 0, 10000)
    chunk_overlap_ms = clamp_int("chunk_overlap_ms", 0, max(0, chunk_window_ms))
    min_speech_ms = clamp_int("min_speech_ms", 0, 5000)
    first_partial_min_speech_ms = clamp_int("first_partial_min_speech_ms", min_speech_ms, 5000)
    latency_preset = str(current.get("latency_preset", defaults.get("latency_preset", "balanced")) or "balanced").strip().lower()
    if latency_preset not in {"ultra_low_latency", "balanced", "quality", "custom"}:
        latency_preset = str(defaults.get("latency_preset", "balanced") or "balanced").strip().lower() or "balanced"
    if latency_preset not in {"ultra_low_latency", "balanced", "quality", "custom"}:
        latency_preset = "balanced"

    return {
        "latency_preset": latency_preset,
        "vad_mode": clamp_int("vad_mode", 0, 3),
        "energy_gate_enabled": bool(current.get("energy_gate_enabled", defaults["energy_gate_enabled"])),
        "min_rms_for_recognition": clamp_float("min_rms_for_recognition", 0.0, 0.05),
        "min_voiced_ratio": clamp_float("min_voiced_ratio", 0.0, 1.0),
        "first_partial_min_speech_ms": first_partial_min_speech_ms,
        "partial_emit_interval_ms": clamp_int("partial_emit_interval_ms", 60, 2000),
        "min_speech_ms": min_speech_ms,
        "max_segment_ms": clamp_int("max_segment_ms", 500, 15000),
        "silence_hold_ms": silence_hold_ms,
        "finalization_hold_ms": finalization_hold_ms,
        "chunk_window_ms": chunk_window_ms,
        "chunk_overlap_ms": chunk_overlap_ms,
        "partial_min_delta_chars": clamp_int("partial_min_delta_chars", 0, 64),
        "partial_coalescing_ms": clamp_int("partial_coalescing_ms", 0, 2000),
    }


def normalize_asr_config(payload: Any, *, defaults: dict[str, Any]) -> dict[str, Any]:
    asr = payload if isinstance(payload, dict) else {}
    asr_mode = str(asr.get("mode", "local")).strip().lower()
    if asr_mode not in {"local", "browser_google", "browser_google_experimental"}:
        asr_mode = "local"

    provider_preference = str(asr.get("provider_preference", "official_eu_parakeet_low_latency")).strip().lower()
    if provider_preference not in {"official_eu_parakeet", "official_eu_parakeet_low_latency"}:
        provider_preference = "official_eu_parakeet_low_latency"

    try:
        rnnoise_strength = int(asr.get("rnnoise_strength", 70) or 70)
    except (TypeError, ValueError):
        rnnoise_strength = 70

    model_load_mode = str(asr.get("model_load_mode", defaults.get("model_load_mode", "auto")) or "auto").strip().lower()
    if model_load_mode not in {"auto", "local_nemo", "from_pretrained"}:
        model_load_mode = str(defaults.get("model_load_mode", "auto") or "auto").strip().lower() or "auto"
    if model_load_mode not in {"auto", "local_nemo", "from_pretrained"}:
        model_load_mode = "auto"
    model_revision = str(asr.get("model_revision", defaults.get("model_revision", "")) or "").strip()

    profile_lock = str(asr.get("desktop_profile_lock", "") or "").strip().lower()
    if profile_lock != "browser_speech":
        profile_lock = ""
    elif asr_mode not in {"browser_google", "browser_google_experimental"}:
        asr_mode = "browser_google"

    normalized: dict[str, Any] = {
        "mode": asr_mode,
        "provider_preference": provider_preference,
        "prefer_gpu": bool(asr.get("prefer_gpu", True)),
        "model_load_mode": model_load_mode,
        "model_revision": model_revision,
        "rnnoise_enabled": bool(
            asr.get("rnnoise_enabled", asr.get("experimental_noise_reduction_enabled", False))
        ),
        "rnnoise_strength": max(0, min(100, rnnoise_strength)),
        "browser": normalize_browser_asr_config(asr.get("browser", {}), defaults=defaults["browser"]),
        "realtime": normalize_realtime_asr_config(asr.get("realtime", {}), defaults=defaults["realtime"]),
    }
    if profile_lock:
        normalized["desktop_profile_lock"] = profile_lock
    return normalized
