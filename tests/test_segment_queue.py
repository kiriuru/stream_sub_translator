from __future__ import annotations

import unittest

from backend.core.segment_queue import AsrWorkItem, SegmentQueue


class SegmentQueueTests(unittest.TestCase):
    def test_new_partial_replaces_older_partial_for_same_segment(self) -> None:
        queue = SegmentQueue()
        queue.push(AsrWorkItem(kind="partial", audio=b"a", duration_ms=100, segment_id="seg-1"))
        queue.push(AsrWorkItem(kind="partial", audio=b"b", duration_ms=120, segment_id="seg-1"))

        item = queue.pop(timeout=0.01)

        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.audio, b"b")
        self.assertIsNone(queue.pop(timeout=0.01))

    def test_final_prunes_queued_partial_for_same_segment(self) -> None:
        queue = SegmentQueue()
        queue.push(AsrWorkItem(kind="partial", audio=b"partial", duration_ms=100, segment_id="seg-1"))
        queue.push(AsrWorkItem(kind="final", audio=b"final", duration_ms=200, segment_id="seg-1"))

        item = queue.pop(timeout=0.01)

        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.kind, "final")
        self.assertEqual(item.audio, b"final")
        self.assertIsNone(queue.pop(timeout=0.01))

    def test_final_for_one_segment_keeps_other_segment_work_items(self) -> None:
        queue = SegmentQueue()
        queue.push(AsrWorkItem(kind="partial", audio=b"keep", duration_ms=80, segment_id="seg-2"))
        queue.push(AsrWorkItem(kind="partial", audio=b"drop", duration_ms=100, segment_id="seg-1"))
        queue.push(AsrWorkItem(kind="final", audio=b"final", duration_ms=200, segment_id="seg-1"))

        first = queue.pop(timeout=0.01)
        second = queue.pop(timeout=0.01)

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        assert first is not None
        assert second is not None
        self.assertEqual((first.segment_id, first.audio), ("seg-2", b"keep"))
        self.assertEqual((second.segment_id, second.kind, second.audio), ("seg-1", "final", b"final"))
        self.assertIsNone(queue.pop(timeout=0.01))


if __name__ == "__main__":
    unittest.main()
