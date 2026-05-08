from __future__ import annotations

from typing import Any, Callable

from backend.core.runtime.asr_runtime_controller import (
    browser_asr_config,
    browser_asr_source_lang,
    browser_worker_provider_name,
    current_asr_mode,
    current_local_provider_preference,
    current_remote_role,
    is_browser_asr_mode,
    is_remote_enabled,
    resolved_asr_provider,
    uses_remote_audio_source,
    uses_remote_event_source,
)


class AsrModeController:
    """
    Stage 2 controller: owns ASR mode/provider resolution and derived flags.

    It preserves the current behavior where, while runtime is running, the effective resolved ASR config
    is pinned to the mode/provider captured at start (active_runtime_mode / active_local_provider_preference).
    """

    name = "asr_mode"

    def __init__(self, config_getter: Callable[[], dict]) -> None:
        self._config_getter = config_getter
        self._active_runtime_mode: str | None = None
        self._active_local_provider_preference: str | None = None

    def reset_active(self) -> None:
        self._active_runtime_mode = None
        self._active_local_provider_preference = None

    def resolve(self, *, state_is_running: bool) -> dict[str, Any]:
        return resolved_asr_provider(
            config_getter=self._config_getter,
            state_is_running=bool(state_is_running),
            active_runtime_mode=self._active_runtime_mode,
            active_local_provider_preference=self._active_local_provider_preference,
        )

    def capture_for_start(self, *, state_is_running: bool) -> dict[str, Any]:
        resolved = self.resolve(state_is_running=state_is_running)
        self._active_runtime_mode = current_asr_mode(resolved)
        self._active_local_provider_preference = current_local_provider_preference(resolved)
        return resolved

    def current_mode(self, *, state_is_running: bool) -> str:
        return current_asr_mode(self.resolve(state_is_running=state_is_running))

    def is_browser_mode(self, *, state_is_running: bool, mode: str | None = None) -> bool:
        return is_browser_asr_mode(mode or self.current_mode(state_is_running=state_is_running))

    def current_local_provider_preference(self, *, state_is_running: bool) -> str:
        return current_local_provider_preference(self.resolve(state_is_running=state_is_running))

    def browser_config(self) -> dict[str, object]:
        return browser_asr_config(self._config_getter())

    def browser_source_lang(self) -> str:
        return browser_asr_source_lang(self._config_getter())

    def browser_worker_provider_name(self, *, state_is_running: bool) -> str:
        return browser_worker_provider_name(self.current_mode(state_is_running=state_is_running))

    def current_remote_role(self) -> str:
        return current_remote_role(self._config_getter)

    def is_remote_enabled(self) -> bool:
        return is_remote_enabled(self._config_getter)

    def uses_remote_audio_source(self, *, state_is_running: bool) -> bool:
        return uses_remote_audio_source(
            mode=self.current_mode(state_is_running=state_is_running),
            remote_role=self.current_remote_role(),
        )

    def uses_remote_event_source(self, *, state_is_running: bool) -> bool:
        return uses_remote_event_source(
            mode=self.current_mode(state_is_running=state_is_running),
            remote_enabled=self.is_remote_enabled(),
            remote_role=self.current_remote_role(),
        )

    def diagnostics(self, *, state_is_running: bool) -> dict[str, Any]:
        return {
            "active_runtime_mode": self._active_runtime_mode,
            "active_local_provider_preference": self._active_local_provider_preference,
            "resolved": dict(self.resolve(state_is_running=state_is_running)),
        }

