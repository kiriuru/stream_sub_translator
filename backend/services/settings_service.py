from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import FastAPI

from backend.core.redaction import redact_data, redact_mapping
from backend.models import (
    RemoteWorkerSettingsSyncResponse,
    SettingsLoadResponse,
    SettingsSaveRequest,
    SettingsSaveResponse,
)


class SettingsService:
    def __init__(self, app: FastAPI) -> None:
        self._app = app

    def _config_payload(self) -> dict[str, Any]:
        payload = getattr(self._app.state, "config", {})
        return payload if isinstance(payload, dict) else {}

    def _log_event(self, event: str, *, payload: dict[str, Any] | None = None) -> None:
        logger = getattr(self._app.state, "structured_runtime_logger", None)
        if logger is None:
            return
        logger.log(
            "runtime_metrics",
            event,
            source="settings_service",
            payload=payload or None,
        )

    def _sync_remote_pairing_session(self) -> None:
        manager = getattr(self._app.state, "remote_session_manager", None)
        if manager is None:
            return
        remote = self._config_payload().get("remote", {})
        if not isinstance(remote, dict):
            remote = {}
        manager.preload(
            session_id=str(remote.get("session_id", "") or "").strip() or None,
            pair_code=str(remote.get("pair_code", "") or "").strip() or None,
        )

    def load(self) -> SettingsLoadResponse:
        config_manager = self._app.state.config_manager
        payload = config_manager.load()
        self._app.state.config = payload
        self._sync_remote_pairing_session()
        self._log_event(
            "settings_loaded",
            payload={
                "config_path": str(self._app.state.app_settings.config_path),
                "payload": redact_data(payload),
            },
        )
        return SettingsLoadResponse(
            payload=payload,
            subtitle_style_presets=config_manager.subtitle_style_presets(payload),
            font_catalog=config_manager.font_catalog(),
            loaded_from=str(self._app.state.app_settings.config_path),
        )

    async def save(self, payload: SettingsSaveRequest) -> SettingsSaveResponse:
        config_manager = self._app.state.config_manager
        saved_payload = config_manager.save(payload.payload)
        self._app.state.config = saved_payload
        self._sync_remote_pairing_session()
        self._log_event(
            "settings_saved",
            payload={
                "config_path": str(self._app.state.app_settings.config_path),
                "payload": redact_data(saved_payload),
            },
        )
        live_applied = False
        runtime_orchestrator = getattr(self._app.state, "runtime_orchestrator", None)
        if runtime_orchestrator is not None:
            await runtime_orchestrator.apply_live_settings(saved_payload)
            live_applied = True
        return SettingsSaveResponse(
            saved_to=str(self._app.state.app_settings.config_path),
            payload=saved_payload,
            subtitle_style_presets=config_manager.subtitle_style_presets(saved_payload),
            font_catalog=config_manager.font_catalog(),
            live_applied=live_applied,
        )

    def save_remote_pairing_state(
        self,
        *,
        session_id: str,
        pair_code: str,
        enabled: bool = True,
        role: str = "controller",
    ) -> dict[str, Any]:
        config_manager = self._app.state.config_manager
        payload = deepcopy(self._config_payload())
        remote = payload.get("remote", {})
        if not isinstance(remote, dict):
            remote = {}
        remote["enabled"] = bool(enabled)
        remote["role"] = str(role or "controller")
        remote["session_id"] = str(session_id or "").strip()
        remote["pair_code"] = str(pair_code or "").strip()
        payload["remote"] = remote
        saved_payload = config_manager.save(payload)
        self._app.state.config = saved_payload
        self._sync_remote_pairing_session()
        self._log_event(
            "remote_pairing_saved",
            payload={
                "config_path": str(self._app.state.app_settings.config_path),
                "remote": redact_mapping(saved_payload.get("remote", {})) if isinstance(saved_payload, dict) else {},
            },
        )
        return saved_payload

    def build_worker_sync_sections(self) -> tuple[dict[str, Any], list[str]]:
        config = self._config_payload()
        sync_payload: dict[str, Any] = {}
        sections: list[str] = []

        translation = config.get("translation", {})
        if isinstance(translation, dict):
            sync_payload["translation"] = deepcopy(translation)
            sections.append("translation")

        subtitle_output = config.get("subtitle_output", {})
        if isinstance(subtitle_output, dict):
            sync_payload["subtitle_output"] = deepcopy(subtitle_output)
            sections.append("subtitle_output")

        source_lang = str(config.get("source_lang", "auto") or "").strip() or "auto"
        sync_payload["source_lang"] = source_lang
        sections.append("source_lang")

        sync_payload["asr"] = {
            "mode": "local",
            "provider_preference": "official_eu_parakeet_low_latency",
        }
        sections.append("asr.mode")
        return sync_payload, sections

    @staticmethod
    def merge_worker_settings_payload(worker_payload: dict[str, Any], sync_payload: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(worker_payload)

        translation = sync_payload.get("translation")
        if isinstance(translation, dict):
            merged["translation"] = deepcopy(translation)

        subtitle_output = sync_payload.get("subtitle_output")
        if isinstance(subtitle_output, dict):
            merged["subtitle_output"] = deepcopy(subtitle_output)

        if "source_lang" in sync_payload:
            merged["source_lang"] = str(sync_payload.get("source_lang", "auto") or "auto")

        current_asr = merged.get("asr", {})
        if not isinstance(current_asr, dict):
            current_asr = {}
        current_asr["mode"] = "local"
        current_asr["provider_preference"] = "official_eu_parakeet_low_latency"
        merged["asr"] = current_asr
        return merged

    async def worker_settings_sync(self) -> RemoteWorkerSettingsSyncResponse:
        sync_payload, sections = self.build_worker_sync_sections()
        runtime_service = self._app.state.runtime_service

        worker_url, worker_settings, load_error = await runtime_service._proxy_worker_request(
            method="GET",
            path="/api/settings/load",
        )
        if load_error:
            return RemoteWorkerSettingsSyncResponse(
                ok=False,
                worker_url=worker_url,
                synced_sections=sections,
                error=load_error,
            )

        worker_payload = worker_settings.get("payload", {}) if isinstance(worker_settings, dict) else {}
        if not isinstance(worker_payload, dict):
            return RemoteWorkerSettingsSyncResponse(
                ok=False,
                worker_url=worker_url,
                synced_sections=sections,
                error="Worker settings payload is missing or invalid.",
            )

        merged_payload = self.merge_worker_settings_payload(worker_payload, sync_payload)
        worker_url, worker_save_response, save_error = await runtime_service._proxy_worker_request(
            method="POST",
            path="/api/settings/save",
            json_payload={"payload": merged_payload},
        )
        if save_error:
            return RemoteWorkerSettingsSyncResponse(
                ok=False,
                worker_url=worker_url,
                synced_sections=sections,
                error=save_error,
            )

        saved_payload = worker_save_response.get("payload", {}) if isinstance(worker_save_response, dict) else {}
        translation = saved_payload.get("translation", {}) if isinstance(saved_payload, dict) else {}
        target_languages: list[str] = []
        if isinstance(translation, dict):
            raw_targets = translation.get("target_languages", [])
            if isinstance(raw_targets, list):
                target_languages = [str(item).strip().lower() for item in raw_targets if str(item).strip()]
        asr = saved_payload.get("asr", {}) if isinstance(saved_payload, dict) else {}
        asr_mode = str(asr.get("mode", "local") or "local") if isinstance(asr, dict) else "local"
        translation_enabled = bool(translation.get("enabled")) if isinstance(translation, dict) else None

        return RemoteWorkerSettingsSyncResponse(
            ok=True,
            worker_url=worker_url,
            synced_sections=sections,
            worker_translation_enabled=translation_enabled,
            worker_target_languages=target_languages,
            worker_asr_mode=asr_mode,
            error=None,
        )
