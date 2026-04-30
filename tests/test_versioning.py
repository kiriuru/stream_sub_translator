from __future__ import annotations

import unittest

from backend.versioning import _is_remote_version_newer, _parse_semver, build_version_info_payload


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
                    "latest_known_version": "0.2.9.3",
                }
            }
        )

        self.assertEqual(payload["current_version"], "0.2.9.2")
        self.assertTrue(payload["sync"]["update_available"])


if __name__ == "__main__":
    unittest.main()
