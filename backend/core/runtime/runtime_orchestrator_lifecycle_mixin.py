"""Runtime lifecycle/start-stop helpers extracted from RuntimeOrchestrator."""

from __future__ import annotations

import asyncio
from pathlib import Path

from backend.core.asr_provider_selection import BROWSER_GOOGLE_EXPERIMENTAL_MODE
from backend.core.audio_capture import AudioCapture
from backend.core.pipeline_trace_log import pipeline_trace
from backend.core.remote_mode import REMOTE_ROLE_WORKER
from backend.models import RuntimeState


class RuntimeOrchestratorLifecycleMixin:
    def _build_startup_status_message(self) -> str:
        if self._is_browser_asr_mode():
            browser_lang = str(self._browser_asr_config().get("recognition_language", "ru-RU") or "ru-RU")
            if self._current_asr_mode() == BROWSER_GOOGLE_EXPERIMENTAL_MODE:
                return (
                    f"Preparing experimental browser speech worker mode for {browser_lang}. "
                    "The popup window will open a live microphone track before recognition starts."
                )
            return f"Preparing browser speech worker mode for {browser_lang}. The popup window will capture audio."
        if self._uses_remote_event_source():
            return "Initializing controller relay mode and waiting for remote worker transcript events."
        if self._uses_remote_audio_source():
            return "Initializing worker ASR runtime and waiting for remote controller audio stream."
        asr_status = self._asr_engine.status()
        model_path = Path(asr_status.model_path) if asr_status.model_path else None
        if model_path is not None and not model_path.exists():
            return (
                "Preparing the first local Parakeet model download. "
                "In desktop mode there is no console, so watch the runtime log panel for status updates."
            )
        return "Initializing the ASR runtime and loading the Parakeet model."

    async def _capture_loop(self) -> None:
        await self._local_asr_pipeline.run_capture_loop()

    async def _asr_loop(self) -> None:
        await self._local_asr_pipeline.run_asr_loop()

    async def start(self, *, has_audio_inputs: bool, device_id: str | None) -> RuntimeState:
        pipeline_trace(
            "runtime_api",
            "runtime_orchestrator",
            "orchestrator_start_enter",
            has_audio_inputs=has_audio_inputs,
            device_id=device_id,
            already_running=self._state.is_running,
            status=self._state.status,
        )
        if self._state.is_running:
            pipeline_trace(
                "runtime_api",
                "runtime_orchestrator",
                "orchestrator_start_ignored_already_running",
                status=self._state.status,
            )
            return self._state

        asr_mode = self._current_asr_mode()
        if self._current_remote_role() == REMOTE_ROLE_WORKER and self._is_browser_asr_mode(asr_mode):
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=None,
                last_error="Remote worker mode supports AI runtime only. Browser speech mode is not allowed.",
                status_message=None,
            )
            return self._state
        use_remote_audio_source = self._uses_remote_audio_source()
        use_remote_event_source = self._uses_remote_event_source()
        if (
            not self._is_browser_asr_mode(asr_mode)
            and not use_remote_audio_source
            and not use_remote_event_source
            and not has_audio_inputs
        ):
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=None,
                last_error="No input audio devices found.",
            )
            return self._state

        await self._set_runtime_state(
            is_running=False,
            status="starting",
            started_at_utc=None,
            status_message=self._build_startup_status_message(),
        )

        try:
            self._device_id = "remote_webrtc_controller" if use_remote_audio_source else device_id
            self._local_audio_device_id = device_id
            self._audio_capture_ctl.set_device_id(device_id)
            if not self._is_browser_asr_mode(asr_mode):
                self._browser_worker_state.mark_disconnected()
            started_at = await self._lifecycle.start()
            await self._set_runtime_state(
                is_running=True,
                status="listening",
                started_at_utc=started_at,
                status_message=(
                    "Controller relay mode is ready and waiting for remote worker events."
                    if use_remote_event_source
                    else "Worker runtime is ready and waiting for remote WebRTC audio."
                    if use_remote_audio_source
                    else (
                        (
                            "Experimental browser speech worker connected. Press Start Recognition in the popup window."
                            if asr_mode == BROWSER_GOOGLE_EXPERIMENTAL_MODE
                            else "Browser speech worker connected. Press Start Recognition in the popup window."
                        )
                        if self._browser_worker_state.external_worker_connected
                        else (
                            "Waiting for the experimental browser speech worker window to connect."
                            if asr_mode == BROWSER_GOOGLE_EXPERIMENTAL_MODE
                            else "Waiting for the browser speech worker window to connect."
                        )
                    )
                    if self._is_browser_asr_mode(asr_mode)
                    else None
                ),
            )
        except Exception as exc:
            await self._safe_stop_audio()
            await self._lifecycle.stop()
            await self._set_runtime_state(
                is_running=False,
                status="error",
                started_at_utc=None,
                last_error=str(exc),
                status_message=None,
            )
        return self._state

    async def _init_asr_runtime_if_needed(self) -> None:
        asr_mode = self._current_asr_mode()
        use_remote_event_source = self._uses_remote_event_source()
        if self._is_browser_asr_mode(asr_mode) or use_remote_event_source:
            return
        asr_status = await asyncio.to_thread(self._asr_engine.initialize_runtime)
        self._apply_vad_tuning()
        if not asr_status.ready:
            raise RuntimeError(asr_status.message)

    async def stop(self) -> RuntimeState:
        pipeline_trace(
            "runtime_api",
            "runtime_orchestrator",
            "orchestrator_stop_enter",
            status=self._state.status,
            is_running=self._state.is_running,
        )
        export_error = await self._lifecycle.stop()
        if export_error:
            self._state = self._state.model_copy(update={"last_error": f"Export error: {export_error}"})
        pipeline_trace(
            "runtime_api",
            "runtime_orchestrator",
            "orchestrator_stop_complete",
            status=self._state.status,
            is_running=self._state.is_running,
            export_error=export_error,
        )
        return self._state

    async def _safe_stop_audio(self) -> None:
        # Some tests construct RuntimeOrchestrator via __new__ and bypass __init__.
        if not hasattr(self, "_audio_capture_ctl") or self._audio_capture_ctl is None:  # type: ignore[attr-defined]
            if self._audio_capture is not None:
                await asyncio.to_thread(self._audio_capture.stop)
                self._audio_capture = None
            return
        await self._audio_capture_ctl.stop_if_running()  # type: ignore[attr-defined]

    async def _start_processing_tasks_impl(self) -> None:
        if not hasattr(self, "_processing_tasks") or self._processing_tasks is None:  # type: ignore[attr-defined]
            if self._capture_task is None or self._capture_task.done():
                self._capture_task = asyncio.create_task(self._local_asr_pipeline.run_capture_loop())
            if self._asr_task is None or self._asr_task.done():
                self._asr_task = asyncio.create_task(self._local_asr_pipeline.run_asr_loop())
            return
        self._processing_tasks.ensure_started()  # type: ignore[attr-defined]
        self._capture_task = self._processing_tasks.capture_task  # type: ignore[attr-defined]
        self._asr_task = self._processing_tasks.asr_task  # type: ignore[attr-defined]

    async def _stop_processing_tasks_impl(self) -> None:
        if not hasattr(self, "_processing_tasks") or self._processing_tasks is None:  # type: ignore[attr-defined]
            tasks = [task for task in (self._capture_task, self._asr_task) if task is not None]
            for task in tasks:
                task.cancel()
            for task in tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._capture_task = None
            self._asr_task = None
            return
        await self._processing_tasks.stop()  # type: ignore[attr-defined]
        self._capture_task = None
        self._asr_task = None

    async def _start_audio_capture_impl(self) -> None:
        if not hasattr(self, "_audio_capture_ctl") or self._audio_capture_ctl is None:  # type: ignore[attr-defined]
            if self._audio_capture is not None:
                pipeline_trace(
                    "capture",
                    "runtime_orchestrator",
                    "start_audio_capture_skipped_legacy_already_open",
                    device_id=self._local_audio_device_id,
                )
                return
            device_id = self._local_audio_device_id
            if device_id is None:
                pipeline_trace(
                    "capture",
                    "runtime_orchestrator",
                    "start_audio_capture_skipped_legacy_no_device",
                )
                return
            self._audio_capture = AudioCapture()
            self._audio_capture.start(device_id=device_id)
            pipeline_trace(
                "capture",
                "runtime_orchestrator",
                "start_audio_capture_legacy_opened",
                device_id=device_id,
            )
            return
        self._audio_capture_ctl.set_device_id(self._local_audio_device_id)  # type: ignore[attr-defined]
        self._audio_capture_ctl.start_if_needed()  # type: ignore[attr-defined]
        self._audio_capture = self._audio_capture_ctl.capture  # type: ignore[attr-defined]
        pipeline_trace(
            "capture",
            "runtime_orchestrator",
            "start_audio_capture_controller",
            device_id=self._local_audio_device_id,
            capture_open=self._audio_capture is not None,
        )

    async def _stop_audio_capture_impl(self) -> None:
        await self._safe_stop_audio()

    async def _init_remote_audio_impl(self) -> None:
        await self._remote_audio_state.init_for_start()

    async def _shutdown_remote_audio_impl(self) -> None:
        await self._remote_audio_state.shutdown_for_stop()

    async def _init_browser_worker_impl(self) -> None:
        # When starting browser speech mode, clear any stale worker generation/session tracking.
        self._browser_worker_state.reset_for_start()

    async def _shutdown_browser_worker_impl(self) -> None:
        # Teardown browser worker session state and clear active partial.
        self._browser_worker_state.reset_for_stop()
        await self.subtitle_router.clear_active_partial()

    async def _start_local_parakeet_impl(self) -> None:
        # Use the same hook-based lifecycle as factory local source.
        await self._start_audio_capture_impl()
        await self._start_processing_tasks_impl()

    async def _stop_local_parakeet_impl(self) -> None:
        await self._stop_processing_tasks_impl()
        await self._stop_audio_capture_impl()
