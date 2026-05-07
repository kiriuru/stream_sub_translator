from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from backend.config.defaults import build_default_config
from backend.config.normalizers.asr import normalize_asr_config
from backend.config.normalizers.obs import normalize_obs_closed_captions_config
from backend.config.normalizers.remote import normalize_remote_config
from backend.config.normalizers.subtitles import (
    normalize_subtitle_lifecycle_config,
    normalize_subtitle_output_config,
)
from backend.config.normalizers.translation import normalize_translation_config
from backend.config.secrets import (
    normalize_google_translate_api_key,
    normalize_provider_secret,
    normalize_provider_text_value,
)
from backend.core.config_migrations import migrate_config
from backend.core.font_catalog import build_font_catalog
from backend.core.paths import APP_PATHS, ensure_app_layout
from backend.core.subtitle_style import merge_style_presets, normalize_subtitle_style_config
from backend.schemas.config_schema import ConfigSchema, CURRENT_CONFIG_VERSION


def configure_project_local_environment() -> None:
    ensure_app_layout(APP_PATHS)
    cache_root = APP_PATHS.cache_root
    temp_root = APP_PATHS.temp_root
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
    data_dir: Path = APP_PATHS.user_data_dir

    @property
    def project_root(self) -> Path:
        return APP_PATHS.project_root

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def install_profile_path(self) -> Path:
        return self.data_dir / "install_profile.txt"

    @property
    def models_dir(self) -> Path:
        return APP_PATHS.models_dir

    @property
    def logs_dir(self) -> Path:
        return APP_PATHS.logs_dir

    @property
    def project_fonts_dir(self) -> Path:
        return APP_PATHS.fonts_dir

    @property
    def local_base_url(self) -> str:
        public_host = self.app_host
        if public_host in {"0.0.0.0", "::"}:
            public_host = "127.0.0.1"
        return f"http://{public_host}:{self.app_port}"


class LocalConfigManager:
    def __init__(self, app_settings: AppSettings) -> None:
        self.app_settings = app_settings
        self.app_settings.data_dir.mkdir(parents=True, exist_ok=True)

    def default_config(self) -> dict[str, Any]:
        return build_default_config(self._default_prefer_gpu())

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
        return self._read_install_profile() != "cpu"

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

    def _normalize_ui_config(self, payload: Any) -> dict[str, Any]:
        defaults = self.default_config()["ui"]
        current = payload if isinstance(payload, dict) else {}
        language = str(current.get("language", defaults["language"]) or "").strip().lower()
        if language not in {"en", "ru"}:
            language = ""
        return {"language": language}

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self.default_config()
        incoming = migrate_config(dict(payload or {}))
        incoming.pop("runtime", None)
        incoming.pop("name", None)
        normalized.update(incoming)
        normalized["config_version"] = CURRENT_CONFIG_VERSION

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
        normalized["ui"] = self._normalize_ui_config(normalized.get("ui", {}))
        normalized["remote"] = normalize_remote_config(
            normalized.get("remote", {}),
            defaults=self.default_config()["remote"],
        )
        normalized["updates"] = self._normalize_updates_config(normalized.get("updates", {}))
        normalized["obs_closed_captions"] = normalize_obs_closed_captions_config(
            normalized.get("obs_closed_captions", {}),
            defaults=self.default_config()["obs_closed_captions"],
        )
        normalized["asr"] = normalize_asr_config(
            normalized.get("asr", {}),
            defaults=self.default_config()["asr"],
        )
        normalized["translation"] = normalize_translation_config(
            normalized.get("translation", {}),
            defaults=self.default_config()["translation"],
            fallback_targets=normalized.get("targets", ["en"]),
        )
        normalized["targets"] = list(normalized["translation"]["target_languages"])
        normalized["subtitle_output"] = normalize_subtitle_output_config(
            normalized.get("subtitle_output", {}),
            translation_lines=normalized["translation"]["lines"],
        )
        normalized["subtitle_style"] = normalize_subtitle_style_config(normalized.get("subtitle_style", {}))
        normalized["subtitle_lifecycle"] = normalize_subtitle_lifecycle_config(
            normalized.get("subtitle_lifecycle", {}),
            defaults=self.default_config()["subtitle_lifecycle"],
            fallback_realtime=normalized["asr"]["realtime"],
            fallback_realtime_defaults=self.default_config()["asr"]["realtime"],
        )
        normalized["asr"]["realtime"]["finalization_hold_ms"] = normalized["subtitle_lifecycle"]["pause_to_finalize_ms"]
        normalized["asr"]["realtime"]["max_segment_ms"] = normalized["subtitle_lifecycle"]["hard_max_phrase_ms"]
        normalized["config_version"] = CURRENT_CONFIG_VERSION
        return ConfigSchema.model_validate(normalized).model_dump(mode="json")

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

    def normalize_profile_payload(self, payload: dict[str, Any], *, profile_name: str | None = None) -> dict[str, Any]:
        normalized = self._normalize(payload)
        if profile_name:
            normalized["profile"] = profile_name
        return ConfigSchema.model_validate(normalized).model_dump(mode="json")

    def subtitle_style_presets(self, payload: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
        current_payload = payload if isinstance(payload, dict) else self.load()
        subtitle_style = current_payload.get("subtitle_style", {}) if isinstance(current_payload, dict) else {}
        custom_presets = subtitle_style.get("custom_presets", {}) if isinstance(subtitle_style, dict) else {}
        return merge_style_presets(custom_presets)

    def font_catalog(self) -> dict[str, Any]:
        return build_font_catalog(self.app_settings.project_fonts_dir)


settings = AppSettings()
