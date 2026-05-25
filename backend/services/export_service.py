from __future__ import annotations

import json
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI

from backend.core.redaction import redact_data
from backend.core.translation_engine import TranslationEngine
from backend.models import ExportFileInfo, ExportsListResponse
from backend.preflight import _likely_asr_mode, _torch_summary
from backend.versioning import PROJECT_VERSION


class ExportService:
    def __init__(self, app: FastAPI) -> None:
        self._app = app

    def list_exports(self) -> ExportsListResponse:
        export_dir = self._app.state.app_settings.data_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        items = sorted(
            (path for path in export_dir.glob("*") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        files = [
            ExportFileInfo(
                name=path.name,
                size_bytes=path.stat().st_size,
                modified_utc=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
            )
            for path in items
        ]
        return ExportsListResponse(exports=[item.name for item in files], files=files)

    def export_diagnostics_bundle(self) -> Path:
        export_dir = self._app.state.app_settings.data_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        bundle_name = f"diagnostics-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
        bundle_path = export_dir / bundle_name

        runtime_payload = self._app.state.runtime_service.status().model_dump(mode="json")
        health_payload = self._app.state.diagnostics_service.health().model_dump(mode="json")
        asr_diagnostics = runtime_payload.get("asr_diagnostics") or {}

        model_manifest_path = self._resolve_model_manifest_path(asr_diagnostics)
        logs_dir = self._app.state.paths.logs_dir
        latest_session_log = logs_dir / "session-latest.jsonl"
        backend_log = logs_dir / "backend.log"
        runtime_events_log = logs_dir / "runtime-events.log"
        trace_logs = (
            ("pipeline-trace.jsonl", logs_dir / "pipeline-trace.jsonl"),
            ("api-trace.jsonl", logs_dir / "api-trace.jsonl"),
            ("ui-trace.jsonl", logs_dir / "ui-trace.jsonl"),
            ("subprocess-trace.jsonl", logs_dir / "subprocess-trace.jsonl"),
            ("startup-journey.jsonl", logs_dir / "startup-journey.jsonl"),
        )

        with zipfile.ZipFile(bundle_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("runtime_status.json", self._json_text(runtime_payload))
            archive.writestr("preflight_report.json", self._json_text(self._build_preflight_report()))
            archive.writestr("config_redacted.json", self._json_text(redact_data(self._app.state.config)))
            archive.writestr("model_manifest.json", self._json_text(self._read_json_file(model_manifest_path)))
            archive.writestr("model_integrity.json", self._json_text(self._build_model_integrity_payload(asr_diagnostics)))
            archive.writestr("last_errors.json", self._json_text(self._build_last_errors(runtime_payload, health_payload)))
            archive.writestr("environment.txt", self._build_environment_text())
            archive.writestr("diagnostics-manifest.json", self._json_text(self._build_manifest()))
            self._write_file_if_present(archive, latest_session_log, "latest_session.jsonl")
            self._write_file_if_present(archive, runtime_events_log, "runtime-events.log")
            self._write_file_if_present(archive, backend_log, "backend.log")
            for archive_name, source_path in trace_logs:
                self._write_file_if_present(archive, source_path, archive_name)

        self._app.state.structured_runtime_logger.log(
            "runtime_metrics",
            "diagnostics_bundle_exported",
            source="export_service",
            payload={
                "bundle_path": str(bundle_path),
                "runtime_status": runtime_payload.get("status"),
            },
        )
        return bundle_path

    @staticmethod
    def _json_text(payload: object) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _read_json_file(path: Path | None) -> dict:
        if path is None or not path.exists():
            return {"present": False}
        try:
            return {"present": True, "path": str(path), "payload": json.loads(path.read_text(encoding="utf-8"))}
        except Exception as exc:
            return {"present": False, "path": str(path), "error": str(exc)}

    def _resolve_model_manifest_path(self, asr_diagnostics: dict) -> Path | None:
        raw_model_path = str(asr_diagnostics.get("model_path", "") or "").strip()
        if raw_model_path:
            model_path = Path(raw_model_path)
            candidate = model_path.parent / "manifest.json"
            if candidate.exists():
                return candidate
        manifests = sorted(self._app.state.paths.models_dir.glob("*/manifest.json"))
        return manifests[0] if manifests else None

    def _build_model_integrity_payload(self, asr_diagnostics: dict) -> dict:
        raw_model_path = str(asr_diagnostics.get("model_path", "") or "").strip()
        model_path = Path(raw_model_path) if raw_model_path else None
        model_present = bool(model_path and model_path.exists())
        model_size_bytes = None
        if model_present and model_path is not None:
            try:
                model_size_bytes = model_path.stat().st_size
            except OSError:
                model_size_bytes = None
        return {
            "provider": asr_diagnostics.get("provider"),
            "model_repo": asr_diagnostics.get("model_repo"),
            "model_revision": asr_diagnostics.get("model_revision"),
            "model_load_mode": asr_diagnostics.get("model_load_mode"),
            "model_path": str(model_path) if model_path is not None else None,
            "model_present": model_present,
            "model_size_bytes": model_size_bytes,
            "model_integrity_state": asr_diagnostics.get("model_integrity_state"),
            "degraded_mode": bool(asr_diagnostics.get("degraded_mode")),
            "fallback_reason": asr_diagnostics.get("fallback_reason"),
            "cpu_fallback_reason": asr_diagnostics.get("cpu_fallback_reason"),
        }

    def _build_preflight_report(self) -> dict:
        config = self._app.state.config if isinstance(self._app.state.config, dict) else {}
        translation_engine = TranslationEngine(self._app.state.cache_manager)
        translation_summary = translation_engine.summarize_readiness(config.get("translation", {}))
        torch_info = _torch_summary()
        model_path = self._app.state.paths.models_dir / "parakeet-tdt-0.6b-v3" / "parakeet-tdt-0.6b-v3.nemo"
        mode_label, mode_reason = _likely_asr_mode(config, model_path, torch_info)
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "python_executable": sys.executable,
            "venv_path": str(Path(sys.executable).parent.parent),
            "config_path": str(self._app.state.app_settings.config_path),
            "model_path": str(model_path),
            "model_present": model_path.exists(),
            "torch": torch_info,
            "asr": {
                "mode": config.get("asr", {}).get("mode", "local"),
                "provider_preference": config.get("asr", {}).get("provider_preference", "official_eu_parakeet_low_latency"),
                "prefer_gpu": bool(config.get("asr", {}).get("prefer_gpu", True)),
                "likely_runtime_mode": mode_label,
                "note": mode_reason,
            },
            "translation": translation_summary.model_dump(mode="json"),
        }

    @staticmethod
    def _build_last_errors(runtime_payload: dict, health_payload: dict) -> dict:
        errors: list[dict[str, str | None]] = []

        if runtime_payload.get("last_error"):
            errors.append(
                {
                    "source": "runtime",
                    "status": str(runtime_payload.get("status")),
                    "message": str(runtime_payload.get("last_error")),
                }
            )
        if runtime_payload.get("status") == "error" and runtime_payload.get("status_message"):
            errors.append(
                {
                    "source": "runtime_status",
                    "status": "error",
                    "message": str(runtime_payload.get("status_message")),
                }
            )

        translation = runtime_payload.get("translation_diagnostics") or {}
        if translation.get("status") in {"error", "degraded"}:
            errors.append(
                {
                    "source": "translation",
                    "status": str(translation.get("status")),
                    "message": str(translation.get("reason") or translation.get("summary") or ""),
                }
            )

        obs = runtime_payload.get("obs_caption_diagnostics") or {}
        if obs.get("last_error"):
            errors.append(
                {
                    "source": "obs_closed_captions",
                    "status": "error",
                    "message": str(obs.get("last_error")),
                }
            )

        if health_payload.get("asr_message") and health_payload.get("asr_ready") is False:
            errors.append(
                {
                    "source": "health.asr",
                    "status": "degraded",
                    "message": str(health_payload.get("asr_message")),
                }
            )

        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "errors": errors,
        }

    def _build_environment_text(self) -> str:
        lines = [
            f"generated_at_utc={datetime.now(timezone.utc).isoformat()}",
            f"python={sys.executable}",
            f"python_version={sys.version.splitlines()[0]}",
            f"platform={platform.platform()}",
            f"project_root={self._app.state.paths.project_root}",
            f"user_data_dir={self._app.state.paths.user_data_dir}",
            f"logs_dir={self._app.state.paths.logs_dir}",
            f"models_dir={self._app.state.paths.models_dir}",
            f"config_path={self._app.state.app_settings.config_path}",
            f"local_base_url={self._app.state.app_settings.local_base_url}",
            f"app_host={self._app.state.app_settings.app_host}",
            f"app_port={self._app.state.app_settings.app_port}",
            f"remote_role={self._app.state.config.get('remote', {}).get('role', 'disabled') if isinstance(self._app.state.config, dict) else 'disabled'}",
        ]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _write_file_if_present(archive: zipfile.ZipFile, source_path: Path, archive_name: str) -> None:
        if source_path.exists() and source_path.is_file():
            archive.write(source_path, arcname=archive_name)
        else:
            archive.writestr(archive_name, "")

    def _build_manifest(self) -> dict:
        version_info = getattr(self._app.state, "version_info", None)
        app_version = getattr(version_info, "current_version", None) or PROJECT_VERSION
        return {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "app_version": app_version,
            "files": {
                "backend.log": "backend log, redacted, normal verbosity",
                "runtime-events.log": "structured runtime events, compact text lines, redacted",
                "session-latest.jsonl": "readable session timeline, raw bounded ring buffer",
                "pipeline-trace.jsonl": "capture/VAD/ASR/runtime lifecycle trace (high frequency)",
                "api-trace.jsonl": "HTTP and websocket API trace",
                "ui-trace.jsonl": "dashboard/desktop UI trace",
                "subprocess-trace.jsonl": "desktop bootstrap and subprocess trace",
                "startup-journey.jsonl": "startup journey milestones",
                "config_redacted.json": "redacted config snapshot",
                "runtime_status.json": "runtime status snapshot",
                "preflight_report.json": "preflight and environment report",
            },
        }
