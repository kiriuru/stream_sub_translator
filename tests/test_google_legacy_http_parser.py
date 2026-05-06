from __future__ import annotations

import unittest

from backend.core.google_legacy_http_parser import parse_google_legacy_http_message


class GoogleLegacyHttpParserTests(unittest.TestCase):
    def test_parses_interim_result_shape(self) -> None:
        parsed = parse_google_legacy_http_message(
            '{"result":[{"alternative":[{"transcript":"hello","confidence":0.8}],"final":false}],"result_index":0}'
        )

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].text, "hello")
        self.assertTrue(parsed[0].is_partial)
        self.assertFalse(parsed[0].is_final)

    def test_parses_final_result_shape(self) -> None:
        parsed = parse_google_legacy_http_message(
            '{"result":[{"alternative":[{"transcript":"hello world","confidence":0.9}],"final":true}],"lang":"en-US"}'
        )

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].text, "hello world")
        self.assertFalse(parsed[0].is_partial)
        self.assertTrue(parsed[0].is_final)
        self.assertEqual(parsed[0].language, "en-US")

    def test_parses_alternate_results_shape(self) -> None:
        parsed = parse_google_legacy_http_message(
            '{"results":[{"alternatives":[{"transcript":"shape two"}],"isFinal":true}]}'
        )

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].text, "shape two")
        self.assertTrue(parsed[0].is_final)

    def test_malformed_json_returns_empty_list(self) -> None:
        self.assertEqual(parse_google_legacy_http_message("not-json"), [])


if __name__ == "__main__":
    unittest.main()
