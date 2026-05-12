from __future__ import annotations

import unittest

from backend.core.structured_log_compact import compact_for_runtime_log, compact_mapping_for_runtime_log


class StructuredLogCompactTests(unittest.TestCase):
    def test_truncates_long_strings(self) -> None:
        raw = "x" * 500
        out = compact_for_runtime_log(raw, max_str=20)
        self.assertTrue(str(out).endswith("…"))
        self.assertLessEqual(len(str(out)), 20)

    def test_summarizes_long_lists(self) -> None:
        out = compact_for_runtime_log(list(range(50)), max_list=4)
        self.assertIsInstance(out, dict)
        assert isinstance(out, dict)
        self.assertEqual(out.get("_items_len"), 50)
        self.assertEqual(len(out.get("_items_preview", [])), 4)

    def test_drops_none_values_in_dicts(self) -> None:
        out = compact_mapping_for_runtime_log({"a": 1, "b": None, "c": "ok"})
        self.assertEqual(out.get("a"), 1)
        self.assertNotIn("b", out)
        self.assertEqual(out.get("c"), "ok")

    def test_mapping_empty(self) -> None:
        self.assertEqual(compact_mapping_for_runtime_log(None), {})
        self.assertEqual(compact_mapping_for_runtime_log({}), {})


if __name__ == "__main__":
    unittest.main()
