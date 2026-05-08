from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


@dataclass(slots=True)
class RuntimeExportController:
    """
    Centralizes stop-time export attempt and error capture.
    """

    export_session_files: Callable[[str], None]

    def try_export_on_stop(self) -> tuple[str, str | None]:
        stopped_at_utc = datetime.now(timezone.utc).isoformat()
        export_error: str | None = None
        try:
            self.export_session_files(stopped_at_utc)
        except Exception as exc:  # noqa: BLE001 - behavior preserved (stringify any export exception)
            export_error = str(exc)
        return stopped_at_utc, export_error

