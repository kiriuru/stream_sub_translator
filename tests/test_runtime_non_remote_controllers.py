from __future__ import annotations

import asyncio
import unittest

from backend.core.runtime.audio_capture_controller import AudioCaptureController
from backend.core.runtime.browser_speech_source import BrowserSpeechSource
from backend.core.runtime.local_parakeet_speech_source import LocalParakeetSpeechSource, _LocalParakeetHooks
from backend.core.runtime.processing_tasks_controller import ProcessingTasksController


class _FakeTask:
    def __init__(self, done: bool = False) -> None:
        self._done = done
        self.cancel_called = 0

    def done(self) -> bool:
        return self._done

    def cancel(self) -> None:
        self.cancel_called += 1


class NonRemoteControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_speech_source_start_stop_does_not_require_audio_capture(self) -> None:
        class _Gateway:
            def diagnostics(self):
                class _D:
                    stale_worker_events_ignored = 0

                return _D()

            def update_status(self, payload):
                _ = payload

            def note_partial(self, **kw):
                _ = kw

            def note_final(self, **kw):
                _ = kw

        async def _no_event(*args, **kwargs):
            _ = args, kwargs
            return None

        called = []

        async def _noop_async(*args, **kwargs):
            called.append("noop")
            _ = args, kwargs

        source = BrowserSpeechSource(
            gateway=_Gateway(),
            hooks=type(
                "_Hooks",
                (),
                {
                    "browser_worker_connected": lambda: _noop_async(),
                    "browser_worker_disconnected": lambda: _noop_async(),
                    "update_browser_worker_status": lambda payload: _noop_async(payload),
                    "build_partial_event": _no_event,
                    "build_final_event": _no_event,
                    "transcript_sink_partial": lambda event: _noop_async(event),
                    "transcript_sink_final": lambda event: _noop_async(event),
                    "browser_source_lang": lambda: "auto",
                    "note_worker_event": lambda: None,
                },
            )(),
        )

        caps = source.capabilities()
        self.assertFalse(caps.uses_backend_audio_capture)
        await source.start()
        await source.stop()

    async def test_local_parakeet_speech_source_start_stop_calls_hooks_once(self) -> None:
        calls: list[str] = []

        async def start():
            calls.append("start")

        async def stop():
            calls.append("stop")

        source = LocalParakeetSpeechSource(_LocalParakeetHooks(start=start, stop=stop))
        await source.start()
        await source.stop()
        self.assertEqual(calls, ["start", "stop"])

    async def test_audio_capture_controller_owns_state_and_read_chunk_safe(self) -> None:
        class _Capture:
            def __init__(self) -> None:
                self.started = 0
                self.stopped = 0
                self.sample_rate = 16000

            def start(self, *, device_id: str) -> None:
                self.started += 1
                self.device_id = device_id

            def stop(self) -> None:
                self.stopped += 1

            def read_chunk(self, seconds: float) -> bytes:
                _ = seconds
                return b"abc"

        created: list[_Capture] = []

        def create() -> _Capture:
            cap = _Capture()
            created.append(cap)
            return cap

        async def stop_in_thread(cap: _Capture) -> None:
            cap.stop()

        ctl = AudioCaptureController(create_capture=create, stop_in_thread=stop_in_thread)
        self.assertIsNone(await ctl.read_chunk(0.1))
        ctl.start_if_needed()  # no device id
        self.assertIsNone(ctl.capture)

        ctl.set_device_id("mic0")
        ctl.start_if_needed()
        self.assertIsNotNone(ctl.capture)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].started, 1)

        ctl.start_if_needed()
        self.assertEqual(created[0].started, 1)  # idempotent

        self.assertEqual(await ctl.read_chunk(0.1), b"abc")
        await ctl.stop_if_running()
        self.assertIsNone(ctl.capture)
        self.assertEqual(created[0].stopped, 1)

        await ctl.stop_if_running()  # idempotent

    async def test_processing_tasks_controller_owns_task_refs(self) -> None:
        created = {"capture": 0, "asr": 0}

        def create_capture():
            created["capture"] += 1
            return _FakeTask(done=False)

        def create_asr():
            created["asr"] += 1
            return _FakeTask(done=False)

        async def await_task(task: object) -> None:
            _ = task
            await asyncio.sleep(0)

        ctl = ProcessingTasksController(
            create_capture_task=create_capture,
            create_asr_task=create_asr,
            await_task=await_task,
        )
        ctl.ensure_started()
        self.assertIsNotNone(ctl.capture_task)
        self.assertIsNotNone(ctl.asr_task)
        self.assertEqual(created, {"capture": 1, "asr": 1})

        # done tasks should be recreated
        ctl._capture_task = _FakeTask(done=True)  # type: ignore[attr-defined]
        ctl.ensure_started()
        self.assertEqual(created["capture"], 2)

        await ctl.stop()
        self.assertIsNone(ctl.capture_task)
        self.assertIsNone(ctl.asr_task)

        ctl.clear_refs()
        self.assertIsNone(ctl.capture_task)
        self.assertIsNone(ctl.asr_task)


if __name__ == "__main__":
    unittest.main()

