from __future__ import annotations

import unittest

from backend.versioning import (
    _is_remote_version_newer,
    _parse_semver,
    build_version_info_payload,
    extract_latest_github_release_version,
)


class VersioningTests(unittest.TestCase):
    def test_parse_semver_accepts_four_part_versions(self) -> None:
        self.assertEqual(_parse_semver("0.2.9.0"), (0, 2, 9, 0))
        self.assertEqual(_parse_semver("v2.8.3"), (2, 8, 3, 0))

    def test_update_check_compares_four_part_versions(self) -> None:
        self.assertTrue(_is_remote_version_newer("0.2.8.9", "0.2.9.0"))
        self.assertFalse(_is_remote_version_newer("0.2.9.0", "0.2.9.0"))

    def test_build_version_payload_exposes_four_part_version(self) -> None:
        payload = build_version_info_payload(
            {
                "updates": {
                    "enabled": True,
                    "provider": "github_releases",
                    "github_repo": "example/repo",
                    "latest_known_version": "0.4.3",
                }
            }
        )

        self.assertEqual(payload["current_version"], "0.4.2")
        self.assertTrue(payload["sync"]["update_available"])

    def test_extract_latest_release_prefers_highest_semver(self) -> None:
        releases = [
            {"tag_name": "v0.3.2", "draft": False, "prerelease": False},
            {"tag_name": "v0.4.1", "draft": False, "prerelease": True},
            {"tag_name": "0.3.10", "draft": False, "prerelease": False},
        ]
        latest, _ = extract_latest_github_release_version(releases, release_channel="stable")
        self.assertEqual(latest, "0.3.10")

    def test_extract_latest_release_allows_prereleases(self) -> None:
        releases = [
            {"tag_name": "0.3.2", "draft": False, "prerelease": False},
            {"tag_name": "0.4.1", "draft": False, "prerelease": True},
        ]
        latest, _ = extract_latest_github_release_version(releases, release_channel="prerelease")
        self.assertEqual(latest, "0.4.1")

    def test_extract_latest_release_ignores_drafts_and_unparseable(self) -> None:
        releases = [
            {"tag_name": "v0.3.2", "draft": True, "prerelease": False},
            {"tag_name": "not-a-version", "draft": False, "prerelease": False},
        ]
        latest, message = extract_latest_github_release_version(releases, release_channel="stable")
        self.assertIsNone(latest)
        self.assertIn("No usable", message)


if __name__ == "__main__":
    unittest.main()
