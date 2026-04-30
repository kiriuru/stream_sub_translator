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
        self.temp_dir.cleanup()

    def test_set_translation_uses_atomic_replace_and_cleans_temp_file(self) -> None:
        with mock.patch("backend.core.cache_manager.os.replace", side_effect=os.replace) as replace_mock:
            self.cache.set_translation("hello", "en", "fr", "bonjour")
        self.assertTrue(replace_mock.called)
        self.assertFalse((self.cache_dir / "translation_cache.tmp").exists())
        stored = json.loads((self.cache_dir / "translation_cache.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["en::fr::hello"], "bonjour")

    def test_corrupted_cache_is_quarantined_and_recovers_as_empty(self) -> None:
        cache_path = self.cache_dir / "translation_cache.json"
        cache_path.write_text("{broken json", encoding="utf-8")

        value = self.cache.get_translation("hello", "en", "fr")

        self.assertIsNone(value)
        recovered = json.loads(cache_path.read_text(encoding="utf-8"))
        self.assertEqual(recovered, {})
        backups = list(self.cache_dir.glob("translation_cache.corrupt-*.json"))
        self.assertEqual(len(backups), 1)


if __name__ == "__main__":
    unittest.main()
