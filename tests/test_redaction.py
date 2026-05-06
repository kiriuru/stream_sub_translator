from __future__ import annotations

import unittest

from urllib.parse import urlsplit, parse_qs

from backend.core.redaction import REDACTED_VALUE, redact_data, redact_text


class RedactionTests(unittest.TestCase):
    def test_redacts_nested_sensitive_keys_and_endpoint_query_values(self) -> None:
        payload = {
            "translation": {
                "api_key": "secret-value",
                "endpoint": "https://example.test/translate?token=abc123&mode=fast",
            },
            "asr": {
                "google_legacy_http": {
                    "api_key": "legacy-secret",
                    "endpoint_host": "https://www.google.com",
                }
            },
            "remote": {
                "pair_code": "123456",
                "controller": {
                    "worker_url": "http://192.168.1.10:8765",
                },
            },
        }

        redacted = redact_data(payload)
        self.assertEqual(redacted["translation"]["api_key"], REDACTED_VALUE)
        self.assertEqual(redacted["asr"]["google_legacy_http"]["api_key"], REDACTED_VALUE)
        endpoint_query = parse_qs(urlsplit(redacted["translation"]["endpoint"]).query)
        self.assertEqual(endpoint_query["token"][0], REDACTED_VALUE)
        self.assertEqual(redacted["remote"]["pair_code"], REDACTED_VALUE)
        self.assertEqual(redacted["remote"]["controller"]["worker_url"], "http://192.168.1.10:8765")

    def test_redacts_bearer_tokens_in_text(self) -> None:
        text = "Authorization failed for Bearer super-secret-token"
        self.assertEqual(redact_text(text), "Authorization failed for Bearer [redacted]")


if __name__ == "__main__":
    unittest.main()
