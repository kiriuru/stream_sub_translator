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

    def test_empty_delta_final_waits_behind_pending_partials(self) -> None:
        queue = SegmentQueue()
        queue.push(
            AsrWorkItem(
                kind="partial",
                audio=b"pcm",
                duration_ms=100,
                segment_id="seg-1",
                audio_is_delta=True,
            )
        )
        queue.push(
            AsrWorkItem(
                kind="final",
                audio=b"",
                duration_ms=200,
                segment_id="seg-1",
                audio_is_delta=True,
            )
        )

        first = queue.pop(timeout=0.01)
        second = queue.pop(timeout=0.01)

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        assert first is not None
        assert second is not None
        self.assertEqual((first.kind, first.audio), ("partial", b"pcm"))
        self.assertEqual((second.kind, second.audio), ("final", b""))

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
        self.assertEqual((first.segment_id, first.kind, first.audio), ("seg-1", "final", b"final"))
        self.assertEqual((second.segment_id, second.audio), ("seg-2", b"keep"))
        self.assertIsNone(queue.pop(timeout=0.01))

    def test_queue_is_bounded_and_drops_partial_work(self) -> None:
        queue = SegmentQueue(maxsize=2)
        queue.push(AsrWorkItem(kind="partial", audio=b"one", duration_ms=10, segment_id="seg-1"))
        queue.push(AsrWorkItem(kind="partial", audio=b"two", duration_ms=10, segment_id="seg-2"))
        queue.push(AsrWorkItem(kind="partial", audio=b"three", duration_ms=10, segment_id="seg-3"))

        self.assertEqual(queue.qsize(), 2)
        self.assertEqual(queue.partial_jobs_dropped, 1)

    def test_clear_wakes_blocked_pop(self) -> None:
        queue = SegmentQueue()
        queue.clear()

        self.assertIsNone(queue.pop(timeout=0.01))


if __name__ == "__main__":
    unittest.main()
