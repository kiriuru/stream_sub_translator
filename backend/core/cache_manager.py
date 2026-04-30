from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from datetime import datetime, timezone


class CacheManager:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_file = cache_dir / "translation_cache.json"
        self._lock = Lock()
        cache_dir.mkdir(parents=True, exist_ok=True)
        if not self.cache_file.exists():
            self.cache_file.write_text("{}", encoding="utf-8")

    def _read(self) -> dict[str, str]:
        try:
            payload = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._quarantine_corrupted_cache()
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write(self, payload: dict[str, str]) -> None:
        temp_path = self.cache_file.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, self.cache_file)

    def _quarantine_corrupted_cache(self) -> None:
        if not self.cache_file.exists():
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path = self.cache_file.with_name(f"{self.cache_file.stem}.corrupt-{timestamp}{self.cache_file.suffix}")
        try:
            os.replace(self.cache_file, backup_path)
        except OSError:
            pass
        try:
            self.cache_file.write_text("{}", encoding="utf-8")
        except OSError:
            pass

    def make_translation_key(self, source_text: str, source_lang: str, target_lang: str) -> str:
        return f"{source_lang}::{target_lang}::{source_text}"

    def get_translation(self, source_text: str, source_lang: str, target_lang: str) -> str | None:
        key = self.make_translation_key(source_text, source_lang, target_lang)
        with self._lock:
            payload = self._read()
            return payload.get(key)

    def set_translation(self, source_text: str, source_lang: str, target_lang: str, value: str) -> None:
        key = self.make_translation_key(source_text, source_lang, target_lang)
        with self._lock:
            payload = self._read()
            payload[key] = value
            self._write(payload)

    def clear_translation_cache(self) -> None:
        with self._lock:
            self._write({})
