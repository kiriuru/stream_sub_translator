from __future__ import annotations

import atexit
import json
import logging
import os
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


logger = logging.getLogger(__name__)


_DEFAULT_MAX_ENTRIES = 5000
_DEFAULT_FLUSH_INTERVAL_SECONDS = 2.0


class CacheManager:
    """In-memory LRU translation cache with debounced disk persistence.

    The previous implementation parsed and rewrote the entire JSON cache file
    on every get/set call, which forced blocking I/O on the asyncio event loop
    and made the cache an unbounded artifact. This rewrite keeps an in-memory
    LRU bounded by `max_entries`, persists to disk on a debounced background
    thread, and supports being turned off entirely via `enabled`/`persist`.
    """

    def __init__(
        self,
        cache_dir: Path,
        *,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
        enabled: bool = True,
        persist: bool = True,
        flush_interval_seconds: float = _DEFAULT_FLUSH_INTERVAL_SECONDS,
    ) -> None:
        self.cache_file = cache_dir / "translation_cache.json"
        self._lock = threading.Lock()
        self._cache: "OrderedDict[str, str]" = OrderedDict()
        self._loaded = False
        self._dirty = False
        self._enabled = bool(enabled)
        self._persist = bool(persist)
        self._max_entries = max(0, int(max_entries))
        self._flush_interval_seconds = max(0.1, float(flush_interval_seconds))
        self._flush_timer: threading.Timer | None = None
        self._closed = False
        cache_dir.mkdir(parents=True, exist_ok=True)
        if not self.cache_file.exists():
            try:
                self.cache_file.write_text("{}", encoding="utf-8")
            except OSError:
                pass
        atexit.register(self._atexit_flush)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def persist(self) -> bool:
        return self._persist

    @property
    def max_entries(self) -> int:
        return self._max_entries

    def update_settings(
        self,
        *,
        enabled: bool | None = None,
        persist: bool | None = None,
        max_entries: int | None = None,
    ) -> None:
        flush_after = False
        clear_after = False
        cancel_pending_flush = False
        with self._lock:
            if enabled is not None:
                new_enabled = bool(enabled)
                if new_enabled != self._enabled:
                    self._enabled = new_enabled
                    if not new_enabled:
                        clear_after = True
            if persist is not None:
                new_persist = bool(persist)
                if new_persist != self._persist:
                    self._persist = new_persist
                    if not new_persist:
                        cancel_pending_flush = True
                    elif self._dirty:
                        flush_after = True
            if max_entries is not None:
                normalized = max(0, int(max_entries))
                if normalized != self._max_entries:
                    self._max_entries = normalized
                    self._evict_to_limit_locked()
                    if self._persist and self._dirty:
                        flush_after = True
        if cancel_pending_flush:
            self._cancel_flush_timer()
        if clear_after:
            self.clear_translation_cache()
        elif flush_after:
            self._schedule_flush()

    def make_translation_key(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        provider_name: str | None = None,
    ) -> str:
        if provider_name:
            return f"{provider_name}::{source_lang}::{target_lang}::{source_text}"
        return f"{source_lang}::{target_lang}::{source_text}"

    def get_translation(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        provider_name: str | None = None,
    ) -> str | None:
        if not self._enabled:
            return None
        key = self.make_translation_key(source_text, source_lang, target_lang, provider_name)
        with self._lock:
            self._ensure_loaded_locked()
            value = self._cache.get(key)
            if value is None:
                return None
            self._cache.move_to_end(key)
            return value

    def set_translation(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        value: str,
        provider_name: str | None = None,
    ) -> None:
        if not self._enabled:
            return
        if self._max_entries == 0:
            return
        key = self.make_translation_key(source_text, source_lang, target_lang, provider_name)
        with self._lock:
            self._ensure_loaded_locked()
            if key in self._cache:
                self._cache.move_to_end(key)
                if self._cache[key] == value:
                    return
                self._cache[key] = value
            else:
                self._cache[key] = value
                self._evict_to_limit_locked()
            self._dirty = True
            should_schedule = self._persist
        if should_schedule:
            self._schedule_flush()

    def clear_translation_cache(self) -> None:
        with self._lock:
            self._cache.clear()
            self._loaded = True
            self._dirty = False
        self._cancel_flush_timer()
        if self._persist:
            try:
                self._write_payload_atomic({})
            except OSError as exc:
                logger.warning("Failed to clear translation cache on disk: %s", exc)

    def flush_now(self) -> None:
        if not self._persist:
            return
        self._cancel_flush_timer()
        with self._lock:
            if not self._dirty:
                return
            snapshot = dict(self._cache)
            self._dirty = False
        try:
            self._write_payload_atomic(snapshot)
        except OSError as exc:
            logger.warning("Failed to persist translation cache: %s", exc)
            with self._lock:
                self._dirty = True

    def close(self) -> None:
        self._closed = True
        self._cancel_flush_timer()
        self.flush_now()

    def _atexit_flush(self) -> None:
        try:
            self.flush_now()
        except Exception:
            pass

    def _evict_to_limit_locked(self) -> None:
        if self._max_entries <= 0:
            self._cache.clear()
            self._dirty = True
            return
        while len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)
            self._dirty = True

    def _ensure_loaded_locked(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            raw = self.cache_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError as exc:
            logger.warning("Failed to read translation cache file: %s", exc)
            return
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            self._quarantine_corrupted_cache_locked()
            return
        if not isinstance(payload, dict):
            return
        for key, value in payload.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            self._cache[key] = value
        self._evict_to_limit_locked()
        if self._dirty and self._persist:
            self._schedule_flush()

    def _quarantine_corrupted_cache_locked(self) -> None:
        if not self.cache_file.exists():
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path = self.cache_file.with_name(
            f"{self.cache_file.stem}.corrupt-{timestamp}{self.cache_file.suffix}"
        )
        try:
            os.replace(self.cache_file, backup_path)
        except OSError:
            pass
        try:
            self.cache_file.write_text("{}", encoding="utf-8")
        except OSError:
            pass

    def _schedule_flush(self) -> None:
        if self._closed or not self._persist:
            return
        with self._lock:
            existing = self._flush_timer
            if existing is not None and existing.is_alive():
                return
            timer = threading.Timer(self._flush_interval_seconds, self._on_flush_timer_fire)
            timer.daemon = True
            self._flush_timer = timer
        timer.start()

    def _cancel_flush_timer(self) -> None:
        with self._lock:
            timer = self._flush_timer
            self._flush_timer = None
        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass

    def _on_flush_timer_fire(self) -> None:
        with self._lock:
            self._flush_timer = None
            if not self._persist or not self._dirty:
                return
            snapshot = dict(self._cache)
            self._dirty = False
        try:
            self._write_payload_atomic(snapshot)
        except OSError as exc:
            logger.warning("Deferred translation cache flush failed: %s", exc)
            with self._lock:
                self._dirty = True
            self._schedule_flush()

    def _write_payload_atomic(self, payload: dict[str, str]) -> None:
        temp_path = self.cache_file.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, self.cache_file)
