from __future__ import annotations

from typing import Any

from backend.core.subtitle_style import build_style_from_preset
from backend.schemas.config_schema import CURRENT_CONFIG_VERSION


def build_default_config(prefer_gpu_default: bool) -> dict[str, Any]:
    return {
        "config_version": CURRENT_CONFIG_VERSION,
        "profile": "default",
        "ui": {
            "language": "",
            "layout": "standard",
            "show_remote_tools": False,
            "theme": "dark",
            "palette": {
                "accent": "#6cc7ff",
                "accent_secondary": "#ff6ce6",
                "accent_tertiary": "#7ce3ad",
            },
        },
        "source_lang": "auto",
        "targets": ["en"],
        "asr": {
            "mode": "local",
            "provider_preference": "official_eu_parakeet_low_latency",
            "prefer_gpu": prefer_gpu_default,
            "model_load_mode": "auto",
            "model_revision": "",
            "rnnoise_enabled": False,
            "rnnoise_strength": 70,
            "browser": {
                "recognition_language": "ru-RU",
                "worker_launch_browser": "auto",
                "interim_results": True,
                "continuous_results": True,
                "force_finalization_enabled": True,
                "force_finalization_timeout_ms": 1600,
                "minimum_reconnect_interval_ms": 500,
                "normal_restart_delay_ms": 350,
                "no_speech_restart_delay_ms": 350,
                "network_reconnect_initial_ms": 1000,
                "network_reconnect_max_ms": 30000,
                "stuck_stopping_timeout_ms": 2500,
                "max_browser_session_age_ms": 180000,
                "prepare_cycle_before_ms": 15000,
                "force_final_on_interruption": True,
                "force_final_min_chars": 3,
                "force_final_min_stable_ms": 700,
                "experimental": {
                    "start_with_audio_track": True,
                    "fallback_to_default_start": True,
                    "keep_stream_alive": True,
                    "audio_track_constraints": {
                        "echoCancellation": False,
                        "noiseSuppression": False,
                        "autoGainControl": False,
                    },
                },
            },
            "realtime": {
                "latency_preset": "balanced",
                "vad_mode": 3,
                "energy_gate_enabled": False,
                "min_rms_for_recognition": 0.0018,
                "min_voiced_ratio": 0.0,
                "first_partial_min_speech_ms": 180,
                "partial_emit_interval_ms": 450,
                "min_speech_ms": 180,
                "max_segment_ms": 5500,
                "silence_hold_ms": 180,
                "finalization_hold_ms": 350,
                "chunk_window_ms": 0,
                "chunk_overlap_ms": 0,
                "partial_min_delta_chars": 4,
                "partial_coalescing_ms": 160,
            },
        },
        "overlay": {
            "preset": "single",
            "compact": False,
        },
        "obs_closed_captions": {
            "enabled": False,
            "output_mode": "disabled",
            "connection": {
                "host": "127.0.0.1",
                "port": 4455,
                "password": "",
            },
            "debug_mirror": {
                "enabled": False,
                "input_name": "CC_DEBUG",
                "send_partials": True,
            },
            "timing": {
                "send_partials": True,
                "partial_throttle_ms": 250,
                "min_partial_delta_chars": 3,
                "final_replace_delay_ms": 0,
                "clear_after_ms": 2500,
                "avoid_duplicate_text": True,
            },
        },
        "audio": {
            "input_device_id": None,
        },
        "remote": {
            "enabled": False,
            "role": "disabled",
            "session_id": "",
            "pair_code": "",
            "lan": {
                "bind_enabled": False,
                "bind_host": "0.0.0.0",
                "port": 8876,
            },
            "controller": {
                "worker_url": "",
                "connect_timeout_ms": 8000,
                "reconnect_delay_ms": 2000,
            },
            "worker": {
                "allow_unpaired": False,
                "heartbeat_timeout_ms": 15000,
            },
        },
        "updates": {
            "enabled": False,
            "provider": "github_releases",
            "github_repo": "kiriuru/stream_sub_translator",
            "release_channel": "stable",
            "check_interval_hours": 12,
            "last_checked_utc": "",
            "latest_known_version": "",
        },
        "translation": {
            "enabled": False,
            "provider": "google_translate_v2",
            "target_languages": ["en"],
            "lines": [
                {
                    "slot_id": "translation_1",
                    "enabled": True,
                    "target_lang": "en",
                    "provider": "google_translate_v2",
                    "label": "EN",
                }
            ],
            "timeout_ms": 10000,
            "queue_max_size": 8,
            "max_concurrent_jobs": 2,
            "provider_settings": {
                "google_translate_v2": {
                    "api_key": "",
                },
                "google_cloud_translation_v3": {
                    "project_id": "",
                    "access_token": "",
                    "location": "global",
                    "model": "",
                },
                "google_gas_url": {
                    "gas_url": "",
                },
                "google_web": {},
                "azure_translator": {
                    "api_key": "",
                    "endpoint": "https://api.cognitive.microsofttranslator.com",
                    "region": "",
                },
                "deepl": {
                    "api_key": "",
                    "api_url": "https://api-free.deepl.com/v2/translate",
                },
                "libretranslate": {
                    "api_key": "",
                    "api_url": "https://libretranslate.com/translate",
                },
                "openai": {
                    "api_key": "",
                    "base_url": "https://api.openai.com/v1",
                    "model": "",
                    "custom_prompt": "",
                },
                "openrouter": {
                    "api_key": "",
                    "base_url": "https://openrouter.ai/api/v1",
                    "model": "",
                    "custom_prompt": "",
                },
                "lm_studio": {
                    "api_key": "",
                    "base_url": "http://127.0.0.1:1234/v1",
                    "model": "",
                    "custom_prompt": "",
                },
                "ollama": {
                    "api_key": "",
                    "base_url": "http://127.0.0.1:11434/v1",
                    "model": "",
                    "custom_prompt": "",
                },
                "public_libretranslate_mirror": {
                    "api_url": "https://translate.fedilab.app/translate",
                },
                "free_web_translate": {},
            },
            "cache": {
                "enabled": True,
                "persist": True,
                "max_entries": 5000,
            },
        },
        "subtitle_output": {
            "show_source": True,
            "show_translations": True,
            "max_translation_languages": 2,
            "display_order": ["source", "translation_1"],
        },
        "subtitle_style": build_style_from_preset("clean_default"),
        "subtitle_lifecycle": {
            "completed_block_ttl_ms": 4500,
            "completed_source_ttl_ms": 4500,
            "completed_translation_ttl_ms": 4500,
            "pause_to_finalize_ms": 350,
            "allow_early_replace_on_next_final": True,
            "sync_source_and_translation_expiry": True,
            "keep_completed_translation_during_active_partial": True,
            "hard_max_phrase_ms": 5500,
        },
        "source_text_replacement": {
            "enabled": False,
            "include_builtin": True,
            "case_insensitive": True,
            "whole_words": True,
            "pairs": [],
        },
    }
