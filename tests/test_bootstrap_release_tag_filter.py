from __future__ import annotations

import unittest

from desktop.bootstrap_payload import is_github_release_tag_relevant_for_local


class BootstrapReleaseTagFilterTests(unittest.TestCase):
    def test_zero_line_ignores_legacy_two_x(self) -> None:
        self.assertFalse(is_github_release_tag_relevant_for_local("0.3.0", "2.8.3"))
        self.assertFalse(is_github_release_tag_relevant_for_local("0.3.0", "v2.8.3"))

    def test_zero_line_keeps_zero_line(self) -> None:
        self.assertTrue(is_github_release_tag_relevant_for_local("0.3.0", "0.3.1"))
        self.assertTrue(is_github_release_tag_relevant_for_local("0.3.0", "v0.3.1"))

    def test_unparsed_tags_not_filtered(self) -> None:
        self.assertTrue(is_github_release_tag_relevant_for_local("", "2.8.3"))
        self.assertTrue(is_github_release_tag_relevant_for_local("0.3.0", "not-a-semver"))


if __name__ == "__main__":
    unittest.main()
