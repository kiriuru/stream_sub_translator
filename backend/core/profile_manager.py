from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.config import (
    normalize_google_translate_api_key,
    normalize_provider_secret,
    normalize_provider_text_value,
)


class ProfileManager:
    def __init__(self, profiles_dir: Path) -> None:
        self.profiles_dir = profiles_dir
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[str]:
        return sorted(p.stem for p in self.profiles_dir.glob("*.json"))

    def _profile_path(self, name: str) -> Path:
        safe_name = name.strip().replace("..", "").replace("/", "").replace("\\", "")
        if not safe_name:
            raise ValueError("Profile name cannot be empty.")
        return self.profiles_dir / f"{safe_name}.json"

    def load_profile(self, name: str) -> dict[str, Any]:
        path = self._profile_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Profile '{name}' does not exist.")
        raw_payload = json.loads(path.read_text(encoding="utf-8"))
        payload = dict(raw_payload)
        payload.pop("name", None)
        payload["profile"] = name
        normalized = self._normalize_translation_secrets(payload)
        if normalized != payload:
            path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        return normalized

    def _normalize_translation_secrets(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload or {})
        translation = normalized.get("translation", {})
        if not isinstance(translation, dict):
            return normalized
        provider_settings = translation.get("provider_settings", {})
        if not isinstance(provider_settings, dict):
            return normalized
        normalized_provider_settings: dict[str, dict[str, Any]] = {}
        for provider_name, provider_config in provider_settings.items():
            if not isinstance(provider_config, dict):
                continue
            current_provider_config = dict(provider_config)
            for key, value in list(current_provider_config.items()):
                if key == "api_key":
                    if provider_name == "google_translate_v2":
                        current_provider_config[key] = normalize_google_translate_api_key(value)
                    else:
                        current_provider_config[key] = normalize_provider_secret(value)
                else:
                    current_provider_config[key] = normalize_provider_text_value(value)
            normalized_provider_settings[provider_name] = current_provider_config

        provider_settings = dict(provider_settings)
        provider_settings.update(normalized_provider_settings)
        translation = dict(translation)
        translation["provider_settings"] = provider_settings
        normalized["translation"] = translation
        return normalized

    def save_profile(self, name: str, payload: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
        path = self._profile_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        sanitized_payload = dict(payload or {})
        sanitized_payload.pop("name", None)
        sanitized_payload["profile"] = name
        stored_payload = self._normalize_translation_secrets(sanitized_payload)
        path.write_text(json.dumps(stored_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path, stored_payload

    def delete_profile(self, name: str) -> bool:
        if name == "default":
            raise ValueError("Default profile cannot be deleted.")
        path = self._profile_path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def ensure_default_profile(self) -> None:
        default_profile = self.profiles_dir / "default.json"
        if default_profile.exists():
            return
        self.save_profile("default", {"source_lang": "auto", "targets": ["en"]})
