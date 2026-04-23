from __future__ import annotations

from pathlib import Path
from typing import Callable

from backend.core.parakeet_provider import (
    AsrProviderDiagnostics,
    AsrProviderCapabilities,
    AsrProviderStatus,
    AsrResult,
    ASR_PROVIDER_OFFICIAL,
    ASR_PROVIDER_REALTIME,
    BaseAsrProvider,
    MockParakeetProvider,
    OfficialEuParakeetProvider,
    OfficialEuParakeetRealtimeProvider,
    allow_mock_asr,
    get_asr_provider_override,
)
from backend.runtime_paths import RUNTIME_PATHS


class AsrEngine:
    def __init__(
        self,
        provider: BaseAsrProvider | None = None,
        *,
        sample_rate: int = 16000,
        models_dir: Path | None = None,
        config_getter: Callable[[], dict] | None = None,
        runtime_status_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self._models_dir = models_dir or (RUNTIME_PATHS.data_dir / "models")
        self._config_getter = config_getter
        self._runtime_status_callback = runtime_status_callback
        self._provider_signature: tuple[str, bool] | None = None
        self._requested_provider: str | None = None
        self._requested_device_policy: str | None = None
        self._degraded_mode = False
        self._fallback_reason: str | None = None
        self.provider = provider or self._build_default_provider()

    def _provider_preferences(self) -> tuple[str, bool]:
        override = get_asr_provider_override()
        if override in {ASR_PROVIDER_OFFICIAL, ASR_PROVIDER_REALTIME, "auto"}:
            config = self._config_getter() if self._config_getter is not None else {}
            asr_config = config.get("asr", {}) if isinstance(config, dict) else {}
            prefer_gpu = bool(asr_config.get("prefer_gpu", True)) if isinstance(asr_config, dict) else True
            return override, prefer_gpu

        config = self._config_getter() if self._config_getter is not None else {}
        asr_config = config.get("asr", {}) if isinstance(config, dict) else {}
        provider_preference = ASR_PROVIDER_REALTIME
        prefer_gpu = True
        if isinstance(asr_config, dict):
            configured_provider = str(asr_config.get("provider_preference", ASR_PROVIDER_REALTIME)).strip().lower()
            if configured_provider in {ASR_PROVIDER_OFFICIAL, ASR_PROVIDER_REALTIME, "auto"}:
                provider_preference = configured_provider
            prefer_gpu = bool(asr_config.get("prefer_gpu", True))
        return provider_preference, prefer_gpu

    def _provider_runtime_initialized(self, provider: BaseAsrProvider) -> bool:
        try:
            return bool(provider.diagnostics(include_runtime_state=False).runtime_initialized)
        except Exception:
            return False

    def _build_default_provider_with_status(
        self,
        *,
        initialize_runtime: bool = False,
    ) -> tuple[BaseAsrProvider, AsrProviderStatus | None]:
        allow_mock = allow_mock_asr()
        provider_preference, prefer_gpu = self._provider_preferences()
        self._provider_signature = (provider_preference, prefer_gpu)
        self._requested_provider = provider_preference
        self._requested_device_policy = "gpu_preferred" if prefer_gpu else "cpu_preferred"
        self._degraded_mode = False
        self._fallback_reason = None

        candidates: list[BaseAsrProvider] = []
        if provider_preference == ASR_PROVIDER_REALTIME:
            candidates.extend(
                [
                    OfficialEuParakeetRealtimeProvider(
                        models_dir=self._models_dir,
                        prefer_gpu=prefer_gpu,
                        config_getter=self._config_getter,
                        runtime_status_callback=self._runtime_status_callback,
                    ),
                    OfficialEuParakeetProvider(
                        models_dir=self._models_dir,
                        prefer_gpu=prefer_gpu,
                        config_getter=self._config_getter,
                        runtime_status_callback=self._runtime_status_callback,
                    ),
                ]
            )
        elif provider_preference == ASR_PROVIDER_OFFICIAL:
            candidates.append(
                OfficialEuParakeetProvider(
                    models_dir=self._models_dir,
                    prefer_gpu=prefer_gpu,
                    config_getter=self._config_getter,
                    runtime_status_callback=self._runtime_status_callback,
                )
            )
        else:
            candidates.extend(
                [
                    OfficialEuParakeetRealtimeProvider(
                        models_dir=self._models_dir,
                        prefer_gpu=prefer_gpu,
                        config_getter=self._config_getter,
                        runtime_status_callback=self._runtime_status_callback,
                    ),
                    OfficialEuParakeetProvider(
                        models_dir=self._models_dir,
                        prefer_gpu=prefer_gpu,
                        config_getter=self._config_getter,
                        runtime_status_callback=self._runtime_status_callback,
                    ),
                ]
            )

        last_provider: BaseAsrProvider | None = None
        last_status: AsrProviderStatus | None = None
        realtime_failure_reason: str | None = None
        for provider in candidates:
            last_provider = provider
            status = provider.status(include_runtime_state=initialize_runtime)
            last_status = status
            if status.ready:
                if provider_preference == ASR_PROVIDER_REALTIME and status.provider != ASR_PROVIDER_REALTIME:
                    self._degraded_mode = True
                    self._fallback_reason = (
                        f"Requested realtime provider '{ASR_PROVIDER_REALTIME}' was not ready. "
                        f"Baseline fallback '{status.provider}' is active."
                    )
                    if realtime_failure_reason:
                        self._fallback_reason = f"{self._fallback_reason} Realtime failure: {realtime_failure_reason}"
                if provider_preference == "auto" and status.provider != ASR_PROVIDER_REALTIME:
                    self._degraded_mode = True
                    self._fallback_reason = (
                        f"Automatic provider selection could not activate realtime mode. "
                        f"Fallback provider '{status.provider}' is active."
                    )
                    if realtime_failure_reason:
                        self._fallback_reason = f"{self._fallback_reason} Realtime failure: {realtime_failure_reason}"
                return provider, status
            if (
                initialize_runtime
                and status.message
                and "Failed to download the official EU multilingual model automatically." in status.message
            ):
                # Realtime and baseline providers share the same local model file. If the
                # download itself failed, trying the fallback provider immediately only
                # repeats the same large download again.
                return provider, status
            if status.provider == ASR_PROVIDER_REALTIME and status.message:
                realtime_failure_reason = status.message
        if allow_mock:
            self._degraded_mode = True
            self._fallback_reason = "No real ASR provider was ready. Explicit mock ASR fallback is active."
            mock_provider = MockParakeetProvider()
            return mock_provider, mock_provider.status(include_runtime_state=initialize_runtime)
        fallback_provider = last_provider or OfficialEuParakeetProvider(
            models_dir=self._models_dir,
            prefer_gpu=prefer_gpu,
            config_getter=self._config_getter,
            runtime_status_callback=self._runtime_status_callback,
        )
        return fallback_provider, last_status

    def _build_default_provider(self, *, initialize_runtime: bool = False) -> BaseAsrProvider:
        provider, _status = self._build_default_provider_with_status(initialize_runtime=initialize_runtime)
        return provider

    def _ensure_provider(self, *, initialize_runtime: bool = False) -> BaseAsrProvider:
        if isinstance(self.provider, MockParakeetProvider):
            return self.provider
        signature = self._provider_preferences()
        if self._provider_signature != signature:
            self.provider = self._build_default_provider(initialize_runtime=initialize_runtime)
            return self.provider
        if initialize_runtime and not self._provider_runtime_initialized(self.provider):
            self.provider = self._build_default_provider(initialize_runtime=True)
        return self.provider

    def status(self) -> AsrProviderStatus:
        status = self._ensure_provider().status()
        status.requested_provider = self._requested_provider
        status.requested_device_policy = self._requested_device_policy
        status.degraded_mode = self._degraded_mode or status.selected_device == "cpu" and self._requested_device_policy == "gpu_preferred"
        fallback_reasons = [reason for reason in (self._fallback_reason, status.cpu_fallback_reason) if reason]
        status.fallback_reason = " ".join(fallback_reasons) if fallback_reasons else None
        return status

    def initialize_runtime(self) -> AsrProviderStatus:
        signature = self._provider_preferences()
        if isinstance(self.provider, MockParakeetProvider):
            status = self.provider.status(include_runtime_state=True)
        elif self._provider_signature != signature or not self._provider_runtime_initialized(self.provider):
            self.provider, status = self._build_default_provider_with_status(initialize_runtime=True)
            if status is None:
                status = self.provider.status(include_runtime_state=True)
        else:
            status = self.provider.status(include_runtime_state=True)
        status.requested_provider = self._requested_provider
        status.requested_device_policy = self._requested_device_policy
        status.degraded_mode = self._degraded_mode or status.selected_device == "cpu" and self._requested_device_policy == "gpu_preferred"
        fallback_reasons = [reason for reason in (self._fallback_reason, status.cpu_fallback_reason) if reason]
        status.fallback_reason = " ".join(fallback_reasons) if fallback_reasons else None
        return status

    def capabilities(self) -> AsrProviderCapabilities:
        return self._ensure_provider().capabilities()

    def diagnostics(self) -> AsrProviderDiagnostics:
        diagnostics = self._ensure_provider().diagnostics()
        diagnostics.requested_provider = self._requested_provider
        diagnostics.requested_device_policy = self._requested_device_policy
        diagnostics.degraded_mode = self._degraded_mode or diagnostics.actual_selected_device == "cpu" and self._requested_device_policy == "gpu_preferred"
        fallback_reasons = [reason for reason in (self._fallback_reason, diagnostics.cpu_fallback_reason) if reason]
        diagnostics.fallback_reason = " ".join(fallback_reasons) if fallback_reasons else None
        return diagnostics

    def run(self, audio_segment: bytes, *, is_final: bool, segment_id: str | None = None) -> AsrResult:
        return self._ensure_provider().transcribe(
            audio_segment,
            sample_rate=self.sample_rate,
            is_final=is_final,
            segment_id=segment_id,
        )

    def reset_runtime_state(self) -> None:
        provider = self._ensure_provider()
        reset_method = getattr(provider, "reset_runtime_state", None)
        if callable(reset_method):
            reset_method()

    def unload_runtime_state(self) -> None:
        provider = self.provider
        unload_method = getattr(provider, "unload_runtime", None)
        if callable(unload_method):
            unload_method()
            return
        reset_method = getattr(provider, "reset_runtime_state", None)
        if callable(reset_method):
            reset_method()
