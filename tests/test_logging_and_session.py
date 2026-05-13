from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.config import AppSettings, LocalConfigManager
from backend.core.logging_setup import configure_backend_logging
from backend.core.redaction import redact_text
from backend.core.session_logger import SessionLogManager
from backend.services.export_service import ExportService
from backend.services.settings_service import SettingsService


class LoggingAndSessionTests(unittest.TestCase):
    def test_redaction_hides_google_translate_query_text(self) -> None:
        message = "GET https://translate.googleapis.com/translate_a/single?q=hello&sl=ru&tl=en&key=secret"
        redacted = redact_text(message)

        self.assertIn("q=[redacted]", redacted)
        self.assertIn("key=[redacted]", redacted)
        self.assertNotIn("q=hello", redacted)

    def test_session_latest_keeps_raw_lines_without_contextless_repeat_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SessionLogManager(Path(temp_dir))
            manager.log("dashboard", "same event", source="ui")
            manager.log("dashboard", "same event", source="ui")
            manager.log("dashboard", "same event", source="ui")

            lines = (Path(temp_dir) / "session-latest.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 3)
        self.assertTrue(all("previous entry repeated" not in line for line in lines))

    def test_settings_service_logs_compact_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app_settings = AppSettings(data_dir=Path(temp_dir))
            config_manager = LocalConfigManager(app_settings)

            logged: list[tuple[str, dict]] = []

            class _Logger:
                def log(self, channel, event, *, source=None, payload=None, **fields):
                    _ = (channel, source, fields)
                    logged.append((event, payload or {}))

            app = SimpleNamespace(
                state=SimpleNamespace(
                    config_manager=config_manager,
                    app_settings=app_settings,
                    config={},
                    structured_runtime_logger=_Logger(),
                    remote_session_manager=None,
                )
            )
            service = SettingsService(app)
            service.load()

        self.assertEqual(logged[0][0], "settings_loaded")
        payload = logged[0][1]
        self.assertIn("settings_summary", payload)
        self.assertNotIn("payload", payload)
        self.assertIn("effective_provider", payload["settings_summary"])

    def test_export_manifest_lists_runtime_and_session_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            logs_dir = root / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / "backend.log").write_text("", encoding="utf-8")
            (logs_dir / "runtime-events.log").write_text("", encoding="utf-8")
            (logs_dir / "session-latest.jsonl").write_text("", encoding="utf-8")

            app = SimpleNamespace(
                state=SimpleNamespace(
                    app_settings=SimpleNamespace(data_dir=root, config_path=root / "config.json"),
                    paths=SimpleNamespace(
                        logs_dir=logs_dir,
                        models_dir=root / "models",
                        project_root=root,
                        user_data_dir=root,
                    ),
                    runtime_service=SimpleNamespace(status=lambda: SimpleNamespace(model_dump=lambda mode="json": {"status": "idle"})),
                    diagnostics_service=SimpleNamespace(health=lambda: SimpleNamespace(model_dump=lambda mode="json": {})),
                    config={},
                    cache_manager=None,
                    version_info=SimpleNamespace(current_version="1.0.0"),
                    structured_runtime_logger=SimpleNamespace(log=lambda *args, **kwargs: None),
                )
            )
            service = ExportService(app)
            manifest = service._build_manifest()  # noqa: SLF001

        self.assertIn("backend.log", manifest["files"])
        self.assertIn("runtime-events.log", manifest["files"])
        self.assertIn("session-latest.jsonl", manifest["files"])

    def test_backend_log_uses_streamer_bot_style_compact_lines(self) -> None:
        import logging

        from backend.core.logging_setup import CompactRedactingFormatter

        record = logging.LogRecord(
            name="backend.core.translation_dispatcher",
            level=logging.INFO,
            pathname="x",
            lineno=1,
            msg="Dropping stale translation result for sequence=%s target=%s",
            args=(42, "ja"),
            exc_info=None,
        )
        line = CompactRedactingFormatter().format(record)
        self.assertRegex(
            line,
            r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} INF\] Translation Dispatcher :: "
            r"Dropping stale translation result for sequence=42 target=ja$",
        )

    def test_backend_logging_configures_httpx_warning_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            import logging
            from backend.core.logging_setup import _HANDLER_NAME

            configure_backend_logging(Path(temp_dir))

            self.assertGreaterEqual(logging.getLogger("httpx").level, logging.WARNING)
            self.assertGreaterEqual(logging.getLogger("httpcore").level, logging.WARNING)
            root_logger = logging.getLogger()
            for handler in list(root_logger.handlers):
                if getattr(handler, "_sst_handler_name", None) != _HANDLER_NAME:
                    continue
                root_logger.removeHandler(handler)
                handler.close()


if __name__ == "__main__":
    unittest.main()
