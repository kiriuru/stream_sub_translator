from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.core.cache_manager import CacheManager


class CacheManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)
        self.cache = CacheManager(self.cache_dir)

    def tearDown(self) -> None:
        self.cache.close()
        self.temp_dir.cleanup()

    def test_set_translation_uses_atomic_replace_and_cleans_temp_file(self) -> None:
        with mock.patch("backend.core.cache_manager.os.replace", side_effect=os.replace) as replace_mock:
            self.cache.set_translation("hello", "en", "fr", "bonjour")
            self.cache.flush_now()
        self.assertTrue(replace_mock.called)
        self.assertFalse((self.cache_dir / "translation_cache.tmp").exists())
        stored = json.loads((self.cache_dir / "translation_cache.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["en::fr::hello"], "bonjour")

    def test_provider_name_partitions_translation_cache_entries(self) -> None:
        self.cache.set_translation("hello", "en", "fr", "bonjour-google", provider_name="google_translate_v2")
        self.cache.set_translation("hello", "en", "fr", "bonjour-openai", provider_name="openai")

        self.assertEqual(
            self.cache.get_translation("hello", "en", "fr", provider_name="google_translate_v2"),
            "bonjour-google",
        )
        self.assertEqual(
            self.cache.get_translation("hello", "en", "fr", provider_name="openai"),
            "bonjour-openai",
        )
        self.assertIsNone(self.cache.get_translation("hello", "en", "fr"))

    def test_corrupted_cache_is_quarantined_and_recovers_as_empty(self) -> None:
        cache_path = self.cache_dir / "translation_cache.json"
        cache_path.write_text("{broken json", encoding="utf-8")

        value = self.cache.get_translation("hello", "en", "fr")

        self.assertIsNone(value)
        recovered = json.loads(cache_path.read_text(encoding="utf-8"))
        self.assertEqual(recovered, {})
        backups = list(self.cache_dir.glob("translation_cache.corrupt-*.json"))
        self.assertEqual(len(backups), 1)


class CacheManagerToggleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_disabled_cache_does_not_store_or_return_entries(self) -> None:
        cache = CacheManager(self.cache_dir, enabled=False)
        try:
            cache.set_translation("hello", "en", "fr", "bonjour")
            cache.flush_now()
            self.assertIsNone(cache.get_translation("hello", "en", "fr"))
            stored = json.loads((self.cache_dir / "translation_cache.json").read_text(encoding="utf-8"))
            self.assertEqual(stored, {})
        finally:
            cache.close()

    def test_update_settings_disable_clears_in_memory_cache(self) -> None:
        cache = CacheManager(self.cache_dir)
        try:
            cache.set_translation("hello", "en", "fr", "bonjour")
            self.assertEqual(cache.get_translation("hello", "en", "fr"), "bonjour")
            cache.update_settings(enabled=False)
            self.assertIsNone(cache.get_translation("hello", "en", "fr"))
            cache.update_settings(enabled=True)
            # Disable clears entries, so it should still be missing.
            self.assertIsNone(cache.get_translation("hello", "en", "fr"))
        finally:
            cache.close()

    def test_persist_disabled_keeps_entries_in_memory_only(self) -> None:
        cache = CacheManager(self.cache_dir, persist=False)
        try:
            cache.set_translation("hello", "en", "fr", "bonjour")
            # In-memory lookup still works.
            self.assertEqual(cache.get_translation("hello", "en", "fr"), "bonjour")
            cache.flush_now()
            stored = json.loads((self.cache_dir / "translation_cache.json").read_text(encoding="utf-8"))
            self.assertEqual(stored, {})
        finally:
            cache.close()

    def test_lru_eviction_drops_oldest_entry_when_capacity_reached(self) -> None:
        cache = CacheManager(self.cache_dir, max_entries=2)
        try:
            cache.set_translation("a", "en", "fr", "A")
            cache.set_translation("b", "en", "fr", "B")
            cache.set_translation("c", "en", "fr", "C")
            self.assertIsNone(cache.get_translation("a", "en", "fr"))
            self.assertEqual(cache.get_translation("b", "en", "fr"), "B")
            self.assertEqual(cache.get_translation("c", "en", "fr"), "C")
        finally:
            cache.close()

    def test_lru_recency_promotes_accessed_entries(self) -> None:
        cache = CacheManager(self.cache_dir, max_entries=2)
        try:
            cache.set_translation("a", "en", "fr", "A")
            cache.set_translation("b", "en", "fr", "B")
            # Touching "a" promotes it to most-recent; "b" becomes the next victim.
            self.assertEqual(cache.get_translation("a", "en", "fr"), "A")
            cache.set_translation("c", "en", "fr", "C")
            self.assertEqual(cache.get_translation("a", "en", "fr"), "A")
            self.assertIsNone(cache.get_translation("b", "en", "fr"))
            self.assertEqual(cache.get_translation("c", "en", "fr"), "C")
        finally:
            cache.close()

    def test_clear_translation_cache_drops_memory_and_disk(self) -> None:
        cache = CacheManager(self.cache_dir)
        try:
            cache.set_translation("hello", "en", "fr", "bonjour")
            cache.flush_now()
            cache.clear_translation_cache()
            self.assertIsNone(cache.get_translation("hello", "en", "fr"))
            stored = json.loads((self.cache_dir / "translation_cache.json").read_text(encoding="utf-8"))
            self.assertEqual(stored, {})
        finally:
            cache.close()


if __name__ == "__main__":
    unittest.main()
