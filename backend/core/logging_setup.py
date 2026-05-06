from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.core.redaction import redact_text


_HANDLER_NAME = "sst-backend-log"


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))


def configure_backend_logging(logs_dir: Path) -> Path:
    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)
    log_path = logs_path / "backend.log"

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if getattr(handler, "_sst_handler_name", None) == _HANDLER_NAME:
            return log_path

    handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler._sst_handler_name = _HANDLER_NAME
    handler.setLevel(logging.INFO)
    handler.setFormatter(RedactingFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    if root_logger.level == logging.NOTSET or root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    return log_path
