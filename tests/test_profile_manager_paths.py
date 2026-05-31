from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.core.profile_manager import ProfileManager


class ProfileManagerPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = ProfileManager(Path(self.temp_dir.name) / "profiles")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_default_profile_path_resolves_under_profiles_dir(self) -> None:
        path = self.manager._profile_path("default")
        self.assertTrue(path.resolve().is_relative_to(self.manager.profiles_dir.resolve()))

    def test_traversal_like_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.manager._profile_path("../escape")
        with self.assertRaises(ValueError):
            self.manager._profile_path("bad/name")

    def test_empty_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.manager._profile_path("   ")


if __name__ == "__main__":
    unittest.main()
