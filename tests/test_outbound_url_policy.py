from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.core.outbound_url_policy import (
    assert_openai_base_url_allowed,
    is_elevated_network_exposure,
    is_restricted_outbound_host,
)


class OutboundUrlPolicyTests(unittest.TestCase):
    def test_restricted_hosts_include_loopback_and_private(self) -> None:
        self.assertTrue(is_restricted_outbound_host("127.0.0.1"))
        self.assertTrue(is_restricted_outbound_host("::1"))
        self.assertTrue(is_restricted_outbound_host("10.0.0.1"))
        self.assertTrue(is_restricted_outbound_host("192.168.1.5"))
        self.assertTrue(is_restricted_outbound_host("169.254.169.254"))
        self.assertTrue(is_restricted_outbound_host("localhost"))
        self.assertTrue(is_restricted_outbound_host("api.local"))

    def test_public_host_not_restricted(self) -> None:
        self.assertFalse(is_restricted_outbound_host("api.openai.com"))

    def test_elevated_when_allow_lan_or_wildcard_bind(self) -> None:
        self.assertTrue(is_elevated_network_exposure(bind_host="127.0.0.1", allow_lan=True))
        self.assertTrue(is_elevated_network_exposure(bind_host="0.0.0.0", allow_lan=False))
        self.assertFalse(is_elevated_network_exposure(bind_host="127.0.0.1", allow_lan=False))

    def test_private_base_url_allowed_on_localhost_bind(self) -> None:
        allowed = assert_openai_base_url_allowed(
            "http://127.0.0.1:1234/v1",
            bind_host="127.0.0.1",
            allow_lan=False,
        )
        self.assertEqual(allowed, "http://127.0.0.1:1234/v1")

    def test_private_base_url_blocked_on_lan_bind(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            assert_openai_base_url_allowed(
                "http://127.0.0.1:1234/v1",
                bind_host="0.0.0.0",
                allow_lan=False,
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("LAN bind", ctx.exception.detail)

    def test_private_base_url_blocked_when_allow_lan_env(self) -> None:
        with patch.dict("os.environ", {"SST_ALLOW_LAN": "1"}, clear=False):
            with self.assertRaises(HTTPException):
                assert_openai_base_url_allowed(
                    "http://192.168.0.10:8080/v1",
                    bind_host="127.0.0.1",
                )


if __name__ == "__main__":
    unittest.main()
