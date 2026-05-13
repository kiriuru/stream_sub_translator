from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.core.compact_log_line import format_backend_log_line
from backend.core.redaction import redact_text


_HANDLER_NAME = "sst-backend-log"


class CompactRedactingFormatter(logging.Formatter):
    """Streamer.bot-style lines: ``[YYYY-MM-DD HH:MM:SS.mmm INF] Translation Dispatcher :: ...``."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_text(format_backend_log_line(record))


def configure_backend_logging(logs_dir: Path) -> Path:
    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)
    log_path = logs_path / "backend.log"

    root_logger = logging.getLogger()
    existing_handlers = [
        handler for handler in list(root_logger.handlers) if getattr(handler, "_sst_handler_name", None) == _HANDLER_NAME
    ]
    for handler in existing_handlers:
        handler_path = Path(getattr(handler, "baseFilename", "")).resolve() if getattr(handler, "baseFilename", None) else None
        if handler_path == log_path.resolve():
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("httpcore").setLevel(logging.WARNING)
            return log_path
        root_logger.removeHandler(handler)
        try:
            handler.flush()
        except Exception:
            pass
        try:
            handler.close()
        except Exception:
            pass

    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler._sst_handler_name = _HANDLER_NAME
    handler.setLevel(logging.INFO)
    handler.setFormatter(CompactRedactingFormatter())

    if root_logger.level == logging.NOTSET or root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    root_logger.addHandler(handler)
    return log_path
