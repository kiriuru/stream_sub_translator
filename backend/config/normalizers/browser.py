from __future__ import annotations

from typing import Any


def normalize_browser_asr_config(payload: Any, *, defaults: dict[str, Any]) -> dict[str, Any]:
    browser = payload if isinstance(payload, dict) else {}
    recognition_language = str(browser.get("recognition_language", "ru-RU")).strip() or "ru-RU"
    try:
        force_finalization_timeout_ms = int(browser.get("force_finalization_timeout_ms", 1600) or 1600)
    except (TypeError, ValueError):
        force_finalization_timeout_ms = 1600

    def clamp_browser_int(key: str, minimum: int, maximum: int) -> int:
        try:
            value = int(browser.get(key, defaults[key]) or defaults[key])
        except (TypeError, ValueError):
            value = int(defaults[key])
        return max(minimum, min(maximum, value))

    experimental_browser = browser.get("experimental", {})
    if not isinstance(experimental_browser, dict):
        experimental_browser = {}
    audio_track_constraints = experimental_browser.get("audio_track_constraints", {})
    if not isinstance(audio_track_constraints, dict):
        audio_track_constraints = {}

    _allowed_launch = {"auto", "google_chrome"}
    _raw_launch = str(browser.get("worker_launch_browser", "auto") or "auto").strip().lower()
    if _raw_launch == "chromium":
        _raw_launch = "auto"
    if _raw_launch == "microsoft_edge":
        _raw_launch = "google_chrome"
    worker_launch_browser = _raw_launch if _raw_launch in _allowed_launch else "auto"

    return {
        "recognition_language": recognition_language,
        "worker_launch_browser": worker_launch_browser,
        "interim_results": bool(browser.get("interim_results", True)),
        "continuous_results": bool(browser.get("continuous_results", True)),
        "force_finalization_enabled": bool(browser.get("force_finalization_enabled", True)),
        "force_finalization_timeout_ms": max(300, min(15000, force_finalization_timeout_ms)),
        "minimum_reconnect_interval_ms": clamp_browser_int("minimum_reconnect_interval_ms", 100, 60000),
        "normal_restart_delay_ms": clamp_browser_int("normal_restart_delay_ms", 0, 60000),
        "no_speech_restart_delay_ms": clamp_browser_int("no_speech_restart_delay_ms", 0, 60000),
        "network_reconnect_initial_ms": clamp_browser_int("network_reconnect_initial_ms", 100, 120000),
        "network_reconnect_max_ms": clamp_browser_int("network_reconnect_max_ms", 100, 300000),
        "stuck_stopping_timeout_ms": clamp_browser_int("stuck_stopping_timeout_ms", 500, 30000),
        "max_browser_session_age_ms": clamp_browser_int("max_browser_session_age_ms", 10000, 3600000),
        "prepare_cycle_before_ms": clamp_browser_int("prepare_cycle_before_ms", 0, 600000),
        "force_final_on_interruption": bool(
            browser.get("force_final_on_interruption", defaults["force_final_on_interruption"])
        ),
        "force_final_min_chars": clamp_browser_int("force_final_min_chars", 1, 256),
        "force_final_min_stable_ms": clamp_browser_int("force_final_min_stable_ms", 0, 60000),
        "experimental": {
            "start_with_audio_track": bool(experimental_browser.get("start_with_audio_track", True)),
            "fallback_to_default_start": bool(experimental_browser.get("fallback_to_default_start", True)),
            "keep_stream_alive": bool(experimental_browser.get("keep_stream_alive", True)),
            "audio_track_constraints": {
                "echoCancellation": bool(audio_track_constraints.get("echoCancellation", False)),
                "noiseSuppression": bool(audio_track_constraints.get("noiseSuppression", False)),
                "autoGainControl": bool(audio_track_constraints.get("autoGainControl", False)),
            },
        },
    }
