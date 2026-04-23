from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel

from backend.core.font_catalog import build_font_catalog
from backend.core.obs_caption_output import OBS_CC_OUTPUT_MODES
from backend.core.subtitle_style import (
    build_style_from_preset,
    merge_style_presets,
    normalize_subtitle_style_config,
)
from backend.runtime_paths import RUNTIME_PATHS, ensure_runtime_layout


def configure_project_local_environment() -> None:
    ensure_runtime_layout(RUNTIME_PATHS)
    cache_root = RUNTIME_PATHS.cache_root
    temp_root = RUNTIME_PATHS.temp_root
    huggingface_root = cache_root / "huggingface"

    directories = (
        cache_root,
        cache_root / "pip",
        cache_root / "torch",
        cache_root / "matplotlib",
        cache_root / "numba",
        cache_root / "xdg",
        cache_root / "cuda",
        huggingface_root,
        huggingface_root / "hub",
        huggingface_root / "transformers",
        huggingface_root / "datasets",
        temp_root,
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    os.environ["PYTHONNOUSERSITE"] = "1"
    os.environ["PIP_CACHE_DIR"] = str(cache_root / "pip")
    os.environ["HF_HOME"] = str(huggingface_root)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(huggingface_root / "hub")
    os.environ["TRANSFORMERS_CACHE"] = str(huggingface_root / "transformers")
    os.environ["HF_DATASETS_CACHE"] = str(huggingface_root / "datasets")
    os.environ["TORCH_HOME"] = str(cache_root / "torch")
    os.environ["MPLCONFIGDIR"] = str(cache_root / "matplotlib")
    os.environ["NUMBA_CACHE_DIR"] = str(cache_root / "numba")
    os.environ["XDG_CACHE_HOME"] = str(cache_root / "xdg")
    os.environ["CUDA_CACHE_PATH"] = str(cache_root / "cuda")
    os.environ["TMP"] = str(temp_root)
    os.environ["TEMP"] = str(temp_root)


configure_project_local_environment()


class AppSettings(BaseModel):
    app_host: str = "127.0.0.1"
    app_port: int = 8765
    app_name: str = "Stream Subtitle Translator"
    data_dir: Path = RUNTIME_PATHS.data_dir

    @property
    def project_root(self) -> Path:
        return RUNTIME_PATHS.project_root

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def install_profile_path(self) -> Path:
        return self.data_dir / "install_profile.txt"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def logs_dir(self) -> Path:
        return RUNTIME_PATHS.logs_dir

    @property
    def project_fonts_dir(self) -> Path:
        return RUNTIME_PATHS.fonts_dir

    @property
    def local_base_url(self) -> str:
        public_host = self.app_host
        if public_host in {"0.0.0.0", "::"}:
            public_host = "127.0.0.1"
        return f"http://{public_host}:{self.app_port}"


def normalize_google_translate_api_key(raw_value: Any) -> str:
    trimmed = str(raw_value or "").strip()
    normalized = trimmed

    if "key=" in trimmed:
        parsed = urlparse(trimmed)
        query_values = parse_qs(parsed.query or trimmed)
        candidate = (query_values.get("key") or [""])[0].strip()
        if candidate:
            normalized = candidate

    if normalized.startswith("AIza") and "&" in normalized:
        candidate = normalized.split("&", 1)[0].strip()
        if candidate:
            normalized = candidate

    return normalized


def normalize_provider_secret(raw_value: Any, *, query_keys: tuple[str, ...] = ("key", "api_key")) -> str:
    trimmed = str(raw_value or "").strip()
    normalized = trimmed

    lowered = normalized.lower()
    if lowered.startswith("bearer "):
        normalized = normalized[7:].strip()

    if any(f"{key}=" in normalized for key in query_keys):
        parsed = urlparse(normalized)
        query_values = parse_qs(parsed.query or normalized)
        for key in query_keys:
            candidate = (query_values.get(key) or [""])[0].strip()
            if candidate:
                normalized = candidate
                break

    if "#" in normalized:
        normalized = normalized.split("#", 1)[0].strip()

    if "&" in normalized:
        candidate = normalized.split("&", 1)[0].strip()
        if candidate:
            normalized = candidate

    return normalized


def normalize_provider_text_value(raw_value: Any) -> str:
    return str(raw_value or "").strip()


class LocalConfigManager:
    def __init__(self, app_settings: AppSettings) -> None:
        self.app_settings = app_settings
        self.app_settings.data_dir.mkdir(parents=True, exist_ok=True)

    def default_config(self) -> dict[str, Any]:
        prefer_gpu_default = self._default_prefer_gpu()
        return {
            "profile": "default",
            "source_lang": "auto",
            "targets": ["en"],
            "asr": {
                "mode": "local",
                "provider_preference": "official_eu_parakeet_realtime",
                "prefer_gpu": prefer_gpu_default,
                "rnnoise_enabled": False,
                "rnnoise_strength": 70,
                "browser": {
                    "recognition_language": "ru-RU",
                    "interim_results": True,
                    "continuous_results": True,
                    "force_finalization_enabled": True,
                    "force_finalization_timeout_ms": 1600,
                },
                "realtime": {
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
                "github_repo": "",
                "release_channel": "stable",
                "check_interval_hours": 12,
                "last_checked_utc": "",
                "latest_known_version": "",
            },
            "translation": {
                "enabled": False,
                "provider": "google_translate_v2",
                "target_languages": ["en"],
                "provider_settings": {
                    "google_translate_v2": {
                        "api_key": "",
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
                    "mymemory": {},
                    "public_libretranslate_mirror": {
                        "api_url": "https://translate.fedilab.app/translate",
                    },
                    "free_web_translate": {},
                },
            },
            "subtitle_output": {
                "show_source": True,
                "show_translations": True,
                "max_translation_languages": 2,
                "display_order": ["source", "en"],
            },
            "subtitle_style": build_style_from_preset("clean_default"),
            "subtitle_lifecycle": {
                "completed_block_ttl_ms": 4500,
                "completed_source_ttl_ms": 4500,
                "completed_translation_ttl_ms": 4500,
                "pause_to_finalize_ms": 350,
                "allow_early_replace_on_next_final": True,
                "sync_source_and_translation_expiry": True,
                "hard_max_phrase_ms": 5500,
            },
        }

    def _read_install_profile(self) -> str | None:
        path = self.app_settings.install_profile_path
        if not path.exists():
            return None
        try:
            value = path.read_text(encoding="utf-8").strip().lower()
        except OSError:
            return None
        if value in {"cpu", "nvidia"}:
            return value
        return None

    def _default_prefer_gpu(self) -> bool:
        install_profile = self._read_install_profile()
        if install_profile == "cpu":
            return False
        return True

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self.default_config()
        incoming = dict(payload or {})
        incoming.pop("runtime", None)
        incoming.pop("name", None)
        normalized.update(incoming)

        profile = normalized.get("profile")
        if not isinstance(profile, str) or not profile.strip():
            normalized["profile"] = "default"

        overlay = normalized.get("overlay", {})
        if not isinstance(overlay, dict):
            overlay = {}
        preset = overlay.get("preset", "single")
        if preset not in {"single", "dual-line", "stacked"}:
            preset = "single"
        normalized["overlay"] = {
            "preset": preset,
            "compact": bool(overlay.get("compact", False)),
        }

        audio = normalized.get("audio", {})
        if not isinstance(audio, dict):
            audio = {}
        normalized["audio"] = {
            "input_device_id": audio.get("input_device_id"),
        }
        normalized["remote"] = self._normalize_remote_config(normalized.get("remote", {}))
        normalized["updates"] = self._normalize_updates_config(normalized.get("updates", {}))

        obs_closed_captions = normalized.get("obs_closed_captions", {})
        if not isinstance(obs_closed_captions, dict):
            obs_closed_captions = {}
        obs_connection = obs_closed_captions.get("connection", {})
        if not isinstance(obs_connection, dict):
            obs_connection = {}
        obs_debug_mirror = obs_closed_captions.get("debug_mirror", {})
        if not isinstance(obs_debug_mirror, dict):
            obs_debug_mirror = {}
        obs_timing = obs_closed_captions.get("timing", {})
        if not isinstance(obs_timing, dict):
            obs_timing = {}
        try:
            obs_port = int(obs_connection.get("port", 4455) or 4455)
        except (TypeError, ValueError):
            obs_port = 4455
        def clamp_obs_int(key: str, default: int) -> int:
            try:
                value = int(obs_timing.get(key, default) or default)
            except (TypeError, ValueError):
                value = default
            return max(0, value)
        output_mode = str(obs_closed_captions.get("output_mode", "disabled") or "disabled").strip().lower()
        if output_mode not in OBS_CC_OUTPUT_MODES:
            output_mode = "disabled"
        normalized["obs_closed_captions"] = {
            "enabled": bool(obs_closed_captions.get("enabled", False)),
            "output_mode": output_mode,
            "connection": {
                "host": str(obs_connection.get("host", "127.0.0.1") or "127.0.0.1").strip() or "127.0.0.1",
                "port": max(1, min(65535, obs_port)),
                "password": str(obs_connection.get("password", "") or ""),
            },
            "debug_mirror": {
                "enabled": bool(obs_debug_mirror.get("enabled", False)),
                "input_name": str(obs_debug_mirror.get("input_name", "CC_DEBUG") or "CC_DEBUG").strip(),
                "send_partials": bool(obs_debug_mirror.get("send_partials", True)),
            },
            "timing": {
                "send_partials": bool(obs_timing.get("send_partials", True)),
                "partial_throttle_ms": clamp_obs_int("partial_throttle_ms", 250),
                "min_partial_delta_chars": clamp_obs_int("min_partial_delta_chars", 3),
                "final_replace_delay_ms": clamp_obs_int("final_replace_delay_ms", 0),
                "clear_after_ms": clamp_obs_int("clear_after_ms", 2500),
                "avoid_duplicate_text": bool(obs_timing.get("avoid_duplicate_text", True)),
            },
        }

        asr = normalized.get("asr", {})
        if not isinstance(asr, dict):
            asr = {}
        asr_mode = str(asr.get("mode", "local")).strip().lower()
        if asr_mode not in {"local", "browser_google"}:
            asr_mode = "local"
        provider_preference = str(asr.get("provider_preference", "official_eu_parakeet_realtime")).strip().lower()
        if provider_preference not in {"auto", "official_eu_parakeet", "official_eu_parakeet_realtime"}:
            provider_preference = "official_eu_parakeet_realtime"
        browser = asr.get("browser", {})
        if not isinstance(browser, dict):
            browser = {}
        recognition_language = str(browser.get("recognition_language", "ru-RU")).strip() or "ru-RU"
        try:
            force_finalization_timeout_ms = int(browser.get("force_finalization_timeout_ms", 1600) or 1600)
        except (TypeError, ValueError):
            force_finalization_timeout_ms = 1600
        try:
            rnnoise_strength = int(asr.get("rnnoise_strength", 70) or 70)
        except (TypeError, ValueError):
            rnnoise_strength = 70
        normalized["asr"] = {
            "mode": asr_mode,
            "provider_preference": provider_preference,
            "prefer_gpu": bool(asr.get("prefer_gpu", True)),
            "rnnoise_enabled": bool(
                asr.get("rnnoise_enabled", asr.get("experimental_noise_reduction_enabled", False))
            ),
            "rnnoise_strength": max(0, min(100, rnnoise_strength)),
            "browser": {
                "recognition_language": recognition_language,
                "interim_results": bool(browser.get("interim_results", True)),
                "continuous_results": True,
                "force_finalization_enabled": bool(browser.get("force_finalization_enabled", True)),
                "force_finalization_timeout_ms": max(300, min(15000, force_finalization_timeout_ms)),
            },
            "realtime": self._normalize_realtime_asr_config(asr.get("realtime", {})),
        }

        translation = normalized.get("translation", {})
        if not isinstance(translation, dict):
            translation = {}
        provider = translation.get("provider", "google_translate_v2")
        if provider not in {
            "google_translate_v2",
            "google_gas_url",
            "google_web",
            "azure_translator",
            "deepl",
            "libretranslate",
            "openai",
            "openrouter",
            "lm_studio",
            "ollama",
            "mymemory",
            "public_libretranslate_mirror",
            "free_web_translate",
        }:
            provider = "google_translate_v2"
        target_languages = translation.get("target_languages", normalized.get("targets", ["en"]))
        if not isinstance(target_languages, list):
            target_languages = ["en"]
        normalized["translation"] = {
            "enabled": bool(translation.get("enabled", False)),
            "provider": provider,
            "target_languages": [str(item).lower() for item in target_languages if str(item).strip()],
            "provider_settings": self._normalize_provider_settings(translation.get("provider_settings", {})),
        }
        normalized["targets"] = list(normalized["translation"]["target_languages"])

        subtitle_output = normalized.get("subtitle_output", {})
        if not isinstance(subtitle_output, dict):
            subtitle_output = {}
        display_order = subtitle_output.get("display_order", ["source", *normalized["translation"]["target_languages"]])
        if not isinstance(display_order, list):
            display_order = ["source", *normalized["translation"]["target_languages"]]
        try:
            max_translation_languages = int(subtitle_output.get("max_translation_languages", 2) or 0)
        except (TypeError, ValueError):
            max_translation_languages = 2
        normalized["subtitle_output"] = {
            "show_source": bool(subtitle_output.get("show_source", True)),
            "show_translations": bool(subtitle_output.get("show_translations", True)),
            "max_translation_languages": max(0, min(5, max_translation_languages)),
            "display_order": self._normalize_display_order(
                display_order=display_order,
                target_languages=normalized["translation"]["target_languages"],
            ),
        }
        normalized["subtitle_style"] = normalize_subtitle_style_config(normalized.get("subtitle_style", {}))
        subtitle_lifecycle = normalized.get("subtitle_lifecycle", {})
        if not isinstance(subtitle_lifecycle, dict):
            subtitle_lifecycle = {}
        normalized["subtitle_lifecycle"] = self._normalize_subtitle_lifecycle_config(
            subtitle_lifecycle,
            fallback_realtime=normalized["asr"]["realtime"],
        )
        normalized["asr"]["realtime"]["finalization_hold_ms"] = normalized["subtitle_lifecycle"]["pause_to_finalize_ms"]
        normalized["asr"]["realtime"]["max_segment_ms"] = normalized["subtitle_lifecycle"]["hard_max_phrase_ms"]
        return normalized

    def _normalize_updates_config(self, payload: Any) -> dict[str, Any]:
        defaults = self.default_config()["updates"]
        current = payload if isinstance(payload, dict) else {}

        provider = str(current.get("provider", defaults["provider"]) or defaults["provider"]).strip().lower()
        if provider not in {"github_releases"}:
            provider = defaults["provider"]

        release_channel = str(
            current.get("release_channel", defaults["release_channel"]) or defaults["release_channel"]
        ).strip().lower()
        if release_channel not in {"stable", "prerelease"}:
            release_channel = defaults["release_channel"]

        github_repo = str(current.get("github_repo", defaults["github_repo"]) or "").strip()
        last_checked_utc = str(current.get("last_checked_utc", defaults["last_checked_utc"]) or "").strip()
        latest_known_version = str(current.get("latest_known_version", defaults["latest_known_version"]) or "").strip()

        try:
            check_interval_hours = int(
                current.get("check_interval_hours", defaults["check_interval_hours"])
                or defaults["check_interval_hours"]
            )
        except (TypeError, ValueError):
            check_interval_hours = int(defaults["check_interval_hours"])

        return {
            "enabled": bool(current.get("enabled", defaults["enabled"])),
            "provider": provider,
            "github_repo": github_repo,
            "release_channel": release_channel,
            "check_interval_hours": max(1, min(168, check_interval_hours)),
            "last_checked_utc": last_checked_utc,
            "latest_known_version": latest_known_version,
        }

    def _normalize_remote_config(self, payload: Any) -> dict[str, Any]:
        defaults = self.default_config()["remote"]
        current = payload if isinstance(payload, dict) else {}
        enabled = bool(current.get("enabled", defaults["enabled"]))
        role = str(current.get("role", defaults["role"]) or defaults["role"]).strip().lower()
        if role not in {"disabled", "controller", "worker"}:
            role = "disabled"
        if not enabled:
            role = "disabled"

        lan = current.get("lan", {})
        if not isinstance(lan, dict):
            lan = {}
        controller = current.get("controller", {})
        if not isinstance(controller, dict):
            controller = {}
        worker = current.get("worker", {})
        if not isinstance(worker, dict):
            worker = {}

        try:
            lan_port = int(lan.get("port", defaults["lan"]["port"]) or defaults["lan"]["port"])
        except (TypeError, ValueError):
            lan_port = int(defaults["lan"]["port"])
        try:
            controller_connect_timeout_ms = int(
                controller.get("connect_timeout_ms", defaults["controller"]["connect_timeout_ms"])
                or defaults["controller"]["connect_timeout_ms"]
            )
        except (TypeError, ValueError):
            controller_connect_timeout_ms = int(defaults["controller"]["connect_timeout_ms"])
        try:
            controller_reconnect_delay_ms = int(
                controller.get("reconnect_delay_ms", defaults["controller"]["reconnect_delay_ms"])
                or defaults["controller"]["reconnect_delay_ms"]
            )
        except (TypeError, ValueError):
            controller_reconnect_delay_ms = int(defaults["controller"]["reconnect_delay_ms"])
        try:
            worker_heartbeat_timeout_ms = int(
                worker.get("heartbeat_timeout_ms", defaults["worker"]["heartbeat_timeout_ms"])
                or defaults["worker"]["heartbeat_timeout_ms"]
            )
        except (TypeError, ValueError):
            worker_heartbeat_timeout_ms = int(defaults["worker"]["heartbeat_timeout_ms"])

        bind_host = str(lan.get("bind_host", defaults["lan"]["bind_host"]) or defaults["lan"]["bind_host"]).strip()
        if not bind_host:
            bind_host = defaults["lan"]["bind_host"]

        worker_url = str(controller.get("worker_url", defaults["controller"]["worker_url"]) or "").strip()
        session_id = str(current.get("session_id", defaults["session_id"]) or "").strip()
        pair_code = str(current.get("pair_code", defaults["pair_code"]) or "").strip()

        return {
            "enabled": enabled,
            "role": role,
            "session_id": session_id,
            "pair_code": pair_code,
            "lan": {
                "bind_enabled": bool(lan.get("bind_enabled", defaults["lan"]["bind_enabled"])),
                "bind_host": bind_host,
                "port": max(1, min(65535, lan_port)),
            },
            "controller": {
                "worker_url": worker_url,
                "connect_timeout_ms": max(1000, min(120000, controller_connect_timeout_ms)),
                "reconnect_delay_ms": max(100, min(30000, controller_reconnect_delay_ms)),
            },
            "worker": {
                "allow_unpaired": bool(worker.get("allow_unpaired", defaults["worker"]["allow_unpaired"])),
                "heartbeat_timeout_ms": max(1000, min(120000, worker_heartbeat_timeout_ms)),
            },
        }

    def _normalize_realtime_asr_config(self, payload: Any) -> dict[str, Any]:
        defaults = self.default_config()["asr"]["realtime"]
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

        return {
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

    def _normalize_subtitle_lifecycle_config(self, payload: Any, *, fallback_realtime: dict[str, int] | None = None) -> dict[str, Any]:
        defaults = self.default_config()["subtitle_lifecycle"]
        current = payload if isinstance(payload, dict) else {}
        realtime = fallback_realtime if isinstance(fallback_realtime, dict) else self.default_config()["asr"]["realtime"]

        def clamp_int_value(raw: Any, *, default: int, minimum: int, maximum: int) -> int:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                value = int(default)
            return max(minimum, min(maximum, value))

        pause_default = int(realtime.get("finalization_hold_ms", defaults["pause_to_finalize_ms"]))
        hard_max_default = int(realtime.get("max_segment_ms", defaults["hard_max_phrase_ms"]))
        completed_ttl_default = clamp_int_value(
            current.get("completed_block_ttl_ms", defaults["completed_block_ttl_ms"]),
            default=defaults["completed_block_ttl_ms"],
            minimum=500,
            maximum=20000,
        )
        source_ttl = clamp_int_value(
            current.get("completed_source_ttl_ms", completed_ttl_default),
            default=completed_ttl_default,
            minimum=500,
            maximum=20000,
        )
        translation_ttl = clamp_int_value(
            current.get("completed_translation_ttl_ms", completed_ttl_default),
            default=completed_ttl_default,
            minimum=500,
            maximum=20000,
        )

        return {
            "completed_block_ttl_ms": max(source_ttl, translation_ttl),
            "completed_source_ttl_ms": source_ttl,
            "completed_translation_ttl_ms": translation_ttl,
            "pause_to_finalize_ms": clamp_int_value(
                current.get("pause_to_finalize_ms", pause_default),
                default=pause_default,
                minimum=120,
                maximum=5000,
            ),
            "allow_early_replace_on_next_final": bool(
                current.get("allow_early_replace_on_next_final", defaults["allow_early_replace_on_next_final"])
            ),
            "sync_source_and_translation_expiry": bool(
                current.get("sync_source_and_translation_expiry", defaults["sync_source_and_translation_expiry"])
            ),
            "hard_max_phrase_ms": clamp_int_value(
                current.get("hard_max_phrase_ms", hard_max_default),
                default=hard_max_default,
                minimum=1000,
                maximum=30000,
            ),
        }

    def _normalize_provider_settings(self, payload: Any) -> dict[str, dict[str, str]]:
        defaults = self.default_config()["translation"]["provider_settings"]
        if not isinstance(payload, dict):
            return defaults

        normalized: dict[str, dict[str, str]] = {}
        for provider_name, provider_defaults in defaults.items():
            current = payload.get(provider_name, {})
            if not isinstance(current, dict):
                current = {}
            normalized[provider_name] = {
                key: str(current.get(key, provider_defaults[key]))
                for key in provider_defaults
            }
            if provider_name == "google_translate_v2":
                normalized[provider_name]["api_key"] = normalize_google_translate_api_key(
                    normalized[provider_name].get("api_key", "")
                )
            else:
                for key in list(normalized[provider_name].keys()):
                    value = normalized[provider_name][key]
                    if key == "api_key":
                        normalized[provider_name][key] = normalize_provider_secret(value)
                    else:
                        normalized[provider_name][key] = normalize_provider_text_value(value)
        return normalized

    def _normalize_display_order(self, *, display_order: list[Any], target_languages: list[str]) -> list[str]:
        normalized_order: list[str] = []
        for item in display_order:
            value = str(item).lower()
            if value == "source" or value in target_languages:
                if value not in normalized_order:
                    normalized_order.append(value)
        if "source" not in normalized_order:
            normalized_order.append("source")
        for target_lang in target_languages:
            if target_lang not in normalized_order:
                normalized_order.append(target_lang)
        return normalized_order

    def load(self) -> dict[str, Any]:
        path = self.app_settings.config_path
        if not path.exists():
            return self.save(self.default_config())
        payload = json.loads(path.read_text(encoding="utf-8"))
        normalized = self._normalize(payload)
        if normalized != payload:
            self.save(normalized)
        return normalized

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        path = self.app_settings.config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = self._normalize(payload)
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        return normalized

    def subtitle_style_presets(self, payload: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
        current_payload = payload if isinstance(payload, dict) else self.load()
        subtitle_style = current_payload.get("subtitle_style", {}) if isinstance(current_payload, dict) else {}
        custom_presets = subtitle_style.get("custom_presets", {}) if isinstance(subtitle_style, dict) else {}
        return merge_style_presets(custom_presets)

    def font_catalog(self) -> dict[str, Any]:
        return build_font_catalog(self.app_settings.project_fonts_dir)


settings = AppSettings()
