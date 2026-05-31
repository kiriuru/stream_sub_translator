from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.core.bind_policy import resolve_bind_host


class BindPolicyTests(unittest.TestCase):
    def test_defaults_to_localhost_without_lan(self) -> None:
        with patch("backend.core.bind_policy.settings") as settings:
            settings.app_host = "127.0.0.1"
            host = resolve_bind_host(host=None, allow_lan=False)
        self.assertEqual(host, "127.0.0.1")

    def test_allow_lan_uses_wildcard_bind(self) -> None:
        host = resolve_bind_host(host=None, allow_lan=True, default_host="127.0.0.1")
        self.assertEqual(host, "0.0.0.0")

    def test_explicit_host_wins(self) -> None:
        host = resolve_bind_host(host="192.168.1.10", allow_lan=True)
        self.assertEqual(host, "192.168.1.10")


if __name__ == "__main__":
    unittest.main()
