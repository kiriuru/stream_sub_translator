from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


class CacheManager:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_file = cache_dir / "translation_cache.json"
        self._lock = Lock()
        cache_dir.mkdir(parents=True, exist_ok=True)
        if not self.cache_file.exists():
            self.cache_file.write_text("{}", encoding="utf-8")

    def _read(self) -> dict[str, str]:
        return json.loads(self.cache_file.read_text(encoding="utf-8"))

    def _write(self, payload: dict[str, str]) -> None:
        self.cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

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
