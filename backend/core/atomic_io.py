from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """
    Write a file atomically (Windows-safe) using a same-directory temp file + os.replace().

    Guarantees that the destination path is either the old content or the new
    content after completion (no partial writes). Best-effort flushes to disk.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    tmp_fd = None
    tmp_path: str | None = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=f".{destination.name}.tmp-",
            suffix=".txt",
            dir=str(destination.parent),
        )
        with os.fdopen(tmp_fd, "w", encoding=encoding, newline="\n") as handle:
            tmp_fd = None
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, destination)
        tmp_path = None
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def atomic_write_json(path: Path, payload: Any, *, indent: int = 2, encoding: str = "utf-8") -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=indent)
    atomic_write_text(Path(path), text, encoding=encoding)

