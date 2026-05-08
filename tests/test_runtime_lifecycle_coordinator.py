from __future__ import annotations

import unittest

from backend.core.runtime.runtime_lifecycle_coordinator import RuntimeLifecycleCoordinator


class RuntimeLifecycleCoordinatorOrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_order_is_canonical(self) -> None:
        calls: list[str] = []

        async def a(name: str):
            calls.append(name)

        def s(name: str):
            calls.append(name)

        coordinator = RuntimeLifecycleCoordinator(
            pre_start=lambda: s("pre_start"),
            pre_stop=lambda: s("pre_stop"),
            select_speech_source=lambda: s("select_speech_source"),
            start_translation=lambda: a("start_translation"),
            stop_translation=lambda: a("stop_translation"),
            start_obs_captions=lambda: a("start_obs_captions"),
            stop_obs_captions=lambda: a("stop_obs_captions"),
            apply_obs_settings=lambda: a("apply_obs_settings"),
            reset_subtitles=lambda: a("reset_subtitles"),
            on_start_reset=lambda: s("on_start_reset"),
            init_asr_runtime_if_needed=lambda: a("init_asr_runtime_if_needed"),
            start_session=lambda: (calls.append("start_session") or "started_at"),
            capture_asr_mode_for_start=lambda: s("capture_asr_mode_for_start"),
            start_speech_source=lambda: a("start_speech_source"),
            stop_speech_source=lambda: a("stop_speech_source"),
            safe_stop_audio=lambda: a("safe_stop_audio"),
            shutdown_remote_audio=lambda: a("shutdown_remote_audio"),
            stop_session_cleanup=lambda: s("stop_session_cleanup"),
            try_export_on_stop=lambda: (calls.append("try_export_on_stop") or None),
            unload_asr_runtime_state=lambda: a("unload_asr_runtime_state"),
            broadcast_runtime=lambda: a("broadcast_runtime"),
            clear_after_stop=lambda: s("clear_after_stop"),
        )

        started_at = await coordinator.start()
        self.assertEqual(started_at, "started_at")
        self.assertEqual(
            calls,
            [
                "pre_start",
                "select_speech_source",
                "start_translation",
                "start_obs_captions",
                "apply_obs_settings",
                "reset_subtitles",
                "on_start_reset",
                "init_asr_runtime_if_needed",
                "start_session",
                "capture_asr_mode_for_start",
                "start_speech_source",
            ],
        )

    async def test_stop_order_is_canonical_and_returns_export_error(self) -> None:
        calls: list[str] = []

        async def a(name: str):
            calls.append(name)

        def s(name: str):
            calls.append(name)

        coordinator = RuntimeLifecycleCoordinator(
            pre_start=lambda: s("pre_start"),
            pre_stop=lambda: s("pre_stop"),
            select_speech_source=lambda: s("select_speech_source"),
            start_translation=lambda: a("start_translation"),
            stop_translation=lambda: a("stop_translation"),
            start_obs_captions=lambda: a("start_obs_captions"),
            stop_obs_captions=lambda: a("stop_obs_captions"),
            apply_obs_settings=lambda: a("apply_obs_settings"),
            reset_subtitles=lambda: a("reset_subtitles"),
            on_start_reset=lambda: s("on_start_reset"),
            init_asr_runtime_if_needed=lambda: a("init_asr_runtime_if_needed"),
            start_session=lambda: (calls.append("start_session") or "started_at"),
            capture_asr_mode_for_start=lambda: s("capture_asr_mode_for_start"),
            start_speech_source=lambda: a("start_speech_source"),
            stop_speech_source=lambda: a("stop_speech_source"),
            safe_stop_audio=lambda: a("safe_stop_audio"),
            shutdown_remote_audio=lambda: a("shutdown_remote_audio"),
            stop_session_cleanup=lambda: s("stop_session_cleanup"),
            try_export_on_stop=lambda: (calls.append("try_export_on_stop") or "disk full"),
            unload_asr_runtime_state=lambda: a("unload_asr_runtime_state"),
            broadcast_runtime=lambda: a("broadcast_runtime"),
            clear_after_stop=lambda: s("clear_after_stop"),
        )

        export_error = await coordinator.stop()
        self.assertEqual(export_error, "disk full")
        self.assertEqual(
            calls,
            [
                "pre_stop",
                "stop_speech_source",
                "safe_stop_audio",
                "reset_subtitles",
                "stop_translation",
                "stop_obs_captions",
                "try_export_on_stop",
                "unload_asr_runtime_state",
                "shutdown_remote_audio",
                "stop_session_cleanup",
                "broadcast_runtime",
                "clear_after_stop",
            ],
        )


if __name__ == "__main__":
    unittest.main()

