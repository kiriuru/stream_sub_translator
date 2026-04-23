from __future__ import annotations

import gc
import importlib
import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np


OFFICIAL_EU_PARAKEET_REPO = "nvidia/parakeet-tdt-0.6b-v3"
OFFICIAL_EU_PARAKEET_FILENAME = "parakeet-tdt-0.6b-v3.nemo"
OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME = "parakeet-tdt-0.6b-v3"
OFFICIAL_EU_PARAKEET_URL = (
    f"https://huggingface.co/{OFFICIAL_EU_PARAKEET_REPO}/resolve/main/{OFFICIAL_EU_PARAKEET_FILENAME}?download=true"
)
ASR_PROVIDER_OFFICIAL = "official_eu_parakeet"
ASR_PROVIDER_REALTIME = "official_eu_parakeet_realtime"
_MODEL_INSTALL_LOCK = threading.Lock()
ProgressCallback = Callable[[str], None]


class AsrProviderError(Exception):
    pass


def _make_divisible_by(num: int, factor: int) -> int:
    return (num // factor) * factor


def ensure_official_eu_parakeet_model(
    models_dir: Path,
    *,
    progress_callback: ProgressCallback | None = None,
    max_attempts: int = 3,
) -> Path:
    target_dir = models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / OFFICIAL_EU_PARAKEET_FILENAME
    manifest_file = target_dir / "manifest.json"

    if target_file.exists():
        return target_file

    with _MODEL_INSTALL_LOCK:
        if target_file.exists():
            return target_file

        max_attempts = max(1, int(max_attempts or 1))
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            with tempfile.NamedTemporaryFile(
                suffix=f".{OFFICIAL_EU_PARAKEET_FILENAME}.part",
                delete=False,
                dir=str(target_dir),
            ) as temp_file:
                temp_path = Path(temp_file.name)

            try:
                request = urllib.request.Request(
                    OFFICIAL_EU_PARAKEET_URL,
                    headers={"User-Agent": "stream-sub-translator/1.0"},
                )
                attempt_suffix = f" (attempt {attempt}/{max_attempts})" if max_attempts > 1 else ""
                start_message = (
                    f"[asr-model] Downloading official model {OFFICIAL_EU_PARAKEET_REPO} "
                    f"to {target_file}{attempt_suffix}"
                )
                print(start_message)
                if progress_callback is not None:
                    progress_callback(start_message)
                with urllib.request.urlopen(request, timeout=120) as response, temp_path.open("wb") as file_handle:
                    total_bytes = int(response.headers.get("Content-Length", "0") or 0)
                    downloaded = 0
                    chunk_size = 1024 * 1024
                    last_reported_percent = -1
                    last_reported_mb = -1
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        file_handle.write(chunk)
                        downloaded += len(chunk)
                        if total_bytes > 0:
                            percent = downloaded * 100.0 / total_bytes
                            print(
                                f"\r[asr-model] Downloading: {percent:6.2f}% ({downloaded}/{total_bytes} bytes)",
                                end="",
                                flush=True,
                            )
                            progress_percent = int(percent)
                            if progress_callback is not None and progress_percent != last_reported_percent:
                                last_reported_percent = progress_percent
                                progress_callback(
                                    f"Downloading Parakeet model... {percent:5.1f}% ({downloaded / (1024 * 1024):.0f} MB / {total_bytes / (1024 * 1024):.0f} MB)"
                                )
                        else:
                            print(
                                f"\r[asr-model] Downloading: {downloaded} bytes",
                                end="",
                                flush=True,
                            )
                            downloaded_mb = downloaded // (1024 * 1024)
                            if progress_callback is not None and downloaded_mb != last_reported_mb:
                                last_reported_mb = downloaded_mb
                                progress_callback(f"Downloading Parakeet model... {downloaded_mb} MB")
                print()
                if progress_callback is not None:
                    progress_callback("Finalizing local Parakeet model files...")
                shutil.move(str(temp_path), str(target_file))
                manifest = {
                    "repo_id": OFFICIAL_EU_PARAKEET_REPO,
                    "filename": OFFICIAL_EU_PARAKEET_FILENAME,
                    "local_path": str(target_file),
                    "download_url": OFFICIAL_EU_PARAKEET_URL,
                }
                manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"[asr-model] Installed official model to {target_file}")
                if progress_callback is not None:
                    progress_callback("Parakeet model download completed.")
                return target_file
            except Exception as exc:
                last_error = exc
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                is_retryable_http = isinstance(exc, urllib.error.HTTPError) and exc.code in {408, 429, 500, 502, 503, 504}
                is_retryable_non_http = not isinstance(exc, urllib.error.HTTPError)
                should_retry = attempt < max_attempts and (is_retryable_http or is_retryable_non_http)
                if progress_callback is not None:
                    progress_callback(
                        f"Parakeet model download failed on attempt {attempt}/{max_attempts}: {type(exc).__name__}: {exc}"
                    )
                if should_retry:
                    retry_delay_seconds = min(6, 2 * attempt)
                    retry_message = (
                        f"Retrying the Parakeet model download in {retry_delay_seconds} seconds..."
                    )
                    print(f"[asr-model] {retry_message}")
                    if progress_callback is not None:
                        progress_callback(retry_message)
                    time.sleep(retry_delay_seconds)
                    continue
                raise

        if last_error is not None:
            raise last_error


@dataclass
class AsrSegmentResult:
    text: str
    is_partial: bool = False
    is_final: bool = False
    start_ms: int | None = None
    end_ms: int | None = None
    source_lang: str = "auto"
    revision: int = 0


@dataclass
class AsrResult:
    segments: list[AsrSegmentResult] = field(default_factory=list)

    @property
    def partial(self) -> str:
        for segment in reversed(self.segments):
            if segment.is_partial and segment.text:
                return segment.text
        return ""

    @property
    def final(self) -> str:
        for segment in reversed(self.segments):
            if segment.is_final and segment.text:
                return segment.text
        return ""


@dataclass
class AsrProviderCapabilities:
    provider_name: str
    supports_gpu: bool = False
    supports_partials: bool = False
    supports_streaming: bool = False
    supports_word_timestamps: bool = False


@dataclass
class AsrProviderDiagnostics:
    provider_name: str
    requested_provider: str | None = None
    requested_device_policy: str | None = None
    model_path: str | None = None
    supports_gpu: bool = False
    supports_partials: bool = False
    supports_streaming: bool = False
    supports_word_timestamps: bool = False
    gpu_requested: bool = False
    gpu_available: bool = False
    torch_version: str | None = None
    torch_built_with_cuda: bool = False
    torch_cuda_is_available: bool = False
    torch_cuda_version: str | None = None
    torch_device_count: int = 0
    first_gpu_name: str | None = None
    python_executable: str | None = None
    venv_path: str | None = None
    degraded_mode: bool = False
    fallback_reason: str | None = None
    cpu_fallback_reason: str | None = None
    actual_selected_device: str | None = None
    actual_execution_provider: str | None = None
    message: str = ""
    ready: bool = False
    using_mock: bool = False
    runtime_initialized: bool = False


@dataclass
class AsrProviderStatus:
    provider: str
    ready: bool
    message: str
    requested_provider: str | None = None
    requested_device_policy: str | None = None
    model_path: str | None = None
    supports_gpu: bool = False
    supports_partials: bool = False
    supports_streaming: bool = False
    supports_word_timestamps: bool = False
    gpu_requested: bool = False
    gpu_available: bool = False
    torch_version: str | None = None
    torch_built_with_cuda: bool = False
    torch_cuda_is_available: bool = False
    torch_cuda_version: str | None = None
    torch_device_count: int = 0
    first_gpu_name: str | None = None
    python_executable: str | None = None
    venv_path: str | None = None
    degraded_mode: bool = False
    fallback_reason: str | None = None
    cpu_fallback_reason: str | None = None
    selected_device: str | None = None
    selected_execution_provider: str | None = None
    partials_supported: bool = False
    using_mock: bool = False
    runtime_initialized: bool = False

    @classmethod
    def from_diagnostics(cls, diagnostics: AsrProviderDiagnostics) -> "AsrProviderStatus":
        return cls(
            provider=diagnostics.provider_name,
            requested_provider=diagnostics.requested_provider,
            requested_device_policy=diagnostics.requested_device_policy,
            ready=diagnostics.ready,
            message=diagnostics.message,
            model_path=diagnostics.model_path,
            supports_gpu=diagnostics.supports_gpu,
            supports_partials=diagnostics.supports_partials,
            supports_streaming=diagnostics.supports_streaming,
            supports_word_timestamps=diagnostics.supports_word_timestamps,
            gpu_requested=diagnostics.gpu_requested,
            gpu_available=diagnostics.gpu_available,
            torch_version=diagnostics.torch_version,
            torch_built_with_cuda=diagnostics.torch_built_with_cuda,
            torch_cuda_is_available=diagnostics.torch_cuda_is_available,
            torch_cuda_version=diagnostics.torch_cuda_version,
            torch_device_count=diagnostics.torch_device_count,
            first_gpu_name=diagnostics.first_gpu_name,
            python_executable=diagnostics.python_executable,
            venv_path=diagnostics.venv_path,
            degraded_mode=diagnostics.degraded_mode,
            fallback_reason=diagnostics.fallback_reason,
            cpu_fallback_reason=diagnostics.cpu_fallback_reason,
            selected_device=diagnostics.actual_selected_device,
            selected_execution_provider=diagnostics.actual_execution_provider,
            partials_supported=diagnostics.supports_partials,
            using_mock=diagnostics.using_mock,
            runtime_initialized=diagnostics.runtime_initialized,
        )


class BaseAsrProvider:
    provider_name = "base"

    def transcribe(
        self,
        audio_segment: bytes,
        *,
        sample_rate: int,
        is_final: bool,
        segment_id: str | None = None,
    ) -> AsrResult:
        raise NotImplementedError

    def capabilities(self) -> AsrProviderCapabilities:
        raise NotImplementedError

    def diagnostics(self, *, include_runtime_state: bool = False) -> AsrProviderDiagnostics:
        raise NotImplementedError

    def status(self, *, include_runtime_state: bool = False) -> AsrProviderStatus:
        return AsrProviderStatus.from_diagnostics(self.diagnostics(include_runtime_state=include_runtime_state))

    def initialize_runtime(self) -> AsrProviderStatus:
        return self.status(include_runtime_state=True)

    def reset_runtime_state(self) -> None:
        return

    def unload_runtime(self) -> None:
        self.reset_runtime_state()


class MockParakeetProvider(BaseAsrProvider):
    provider_name = "mock_parakeet"

    def __init__(self) -> None:
        self._final_sequence = 0

    def capabilities(self) -> AsrProviderCapabilities:
        return AsrProviderCapabilities(
            provider_name=self.provider_name,
            supports_gpu=False,
            supports_partials=True,
            supports_streaming=True,
            supports_word_timestamps=False,
        )

    def diagnostics(self, *, include_runtime_state: bool = False) -> AsrProviderDiagnostics:
        caps = self.capabilities()
        return AsrProviderDiagnostics(
            provider_name=caps.provider_name,
            supports_gpu=caps.supports_gpu,
            supports_partials=caps.supports_partials,
            supports_streaming=caps.supports_streaming,
            supports_word_timestamps=caps.supports_word_timestamps,
            gpu_requested=False,
            gpu_available=False,
            actual_selected_device="cpu",
            actual_execution_provider="mock",
            ready=True,
            using_mock=True,
            message="Mock ASR provider is enabled explicitly for local development.",
            runtime_initialized=True,
        )

    def transcribe(
        self,
        audio_segment: bytes,
        *,
        sample_rate: int,
        is_final: bool,
        segment_id: str | None = None,
    ) -> AsrResult:
        samples = np.frombuffer(audio_segment, dtype=np.int16)
        duration_seconds = len(samples) / float(sample_rate) if sample_rate else 0.0
        rms = float(np.sqrt(np.mean(np.square(samples.astype(np.float32))))) if samples.size else 0.0

        if is_final:
            self._final_sequence += 1
            return AsrResult(
                segments=[
                    AsrSegmentResult(
                        text=f"[mock-parakeet] utterance {self._final_sequence}: {duration_seconds:.1f}s, level {rms:.0f}",
                        is_final=True,
                    )
                ]
            )

        return AsrResult(
            segments=[
                AsrSegmentResult(
                    text=f"[mock-parakeet] listening... {duration_seconds:.1f}s",
                    is_partial=True,
                )
            ]
        )


class BaseOfficialEuParakeetNemoProvider(BaseAsrProvider):
    execution_provider_name = "nemo"

    def __init__(
        self,
        models_dir: Path,
        *,
        prefer_gpu: bool = False,
        config_getter: Callable[[], dict] | None = None,
        runtime_status_callback: ProgressCallback | None = None,
    ) -> None:
        self.models_dir = models_dir
        self.model_dir = self.models_dir / OFFICIAL_EU_PARAKEET_LOCAL_DIRNAME
        self.model_path = self.model_dir / OFFICIAL_EU_PARAKEET_FILENAME
        self._config_getter = config_getter
        self._model: Any | None = None
        self._nemo_available: bool | None = None
        self._nemo_import_error: str | None = None
        self._gpu_requested = bool(prefer_gpu)
        self._gpu_available = self._detect_gpu_available()
        self._actual_selected_device: str | None = None
        self._runtime_note: str | None = None
        self._cpu_fallback_reason: str | None = None
        self._runtime_status_callback = runtime_status_callback

    def _report_runtime_status(self, message: str) -> None:
        if self._runtime_status_callback is None:
            return
        try:
            self._runtime_status_callback(str(message))
        except Exception:
            pass

    def unload_runtime(self) -> None:
        self.reset_runtime_state()
        self._model = None
        self._actual_selected_device = None
        self._release_torch_memory()

    def _release_torch_memory(self) -> None:
        try:
            gc.collect()
        except Exception:
            pass
        try:
            torch = importlib.import_module("torch")
            cuda = getattr(torch, "cuda", None)
            if cuda is None or not callable(getattr(cuda, "is_available", None)) or not cuda.is_available():
                return
            empty_cache = getattr(cuda, "empty_cache", None)
            if callable(empty_cache):
                empty_cache()
            ipc_collect = getattr(cuda, "ipc_collect", None)
            if callable(ipc_collect):
                ipc_collect()
        except Exception:
            pass

    def capabilities(self) -> AsrProviderCapabilities:
        return AsrProviderCapabilities(
            provider_name=self.provider_name,
            supports_gpu=True,
            supports_partials=False,
            supports_streaming=False,
            supports_word_timestamps=False,
        )

    def diagnostics(self, *, include_runtime_state: bool = False) -> AsrProviderDiagnostics:
        caps = self.capabilities()
        torch_diag = self._collect_torch_diagnostics()
        runtime_initialized = self._model is not None
        if not self.model_path.exists() and not include_runtime_state:
            return AsrProviderDiagnostics(
                provider_name=caps.provider_name,
                model_path=str(self.model_path),
                supports_gpu=caps.supports_gpu,
                supports_partials=caps.supports_partials,
                supports_streaming=caps.supports_streaming,
                supports_word_timestamps=caps.supports_word_timestamps,
                gpu_requested=self._gpu_requested,
                gpu_available=self._gpu_available,
                torch_version=torch_diag["torch_version"],
                torch_built_with_cuda=torch_diag["torch_built_with_cuda"],
                torch_cuda_is_available=torch_diag["torch_cuda_is_available"],
                torch_cuda_version=torch_diag["torch_cuda_version"],
                torch_device_count=torch_diag["torch_device_count"],
                first_gpu_name=torch_diag["first_gpu_name"],
                python_executable=torch_diag["python_executable"],
                venv_path=torch_diag["venv_path"],
                cpu_fallback_reason=self._cpu_fallback_reason or self._infer_cpu_fallback_reason(torch_diag),
                actual_selected_device=self._resolved_device_name(),
                actual_execution_provider=self.execution_provider_name,
                ready=False,
                message=(
                    f"Official EU multilingual model '{OFFICIAL_EU_PARAKEET_REPO}' is not installed yet. "
                    "It will be downloaded automatically on the first runtime start. "
                    f"Expected local file: '{self.model_path}'."
                ),
                runtime_initialized=runtime_initialized,
            )
        if include_runtime_state or runtime_initialized or self._nemo_available is False:
            dependency_available = self._nemo_dependency_available(probe_only=False)
            if not dependency_available:
                return AsrProviderDiagnostics(
                    provider_name=caps.provider_name,
                    model_path=str(self.model_path),
                    supports_gpu=caps.supports_gpu,
                    supports_partials=caps.supports_partials,
                    supports_streaming=caps.supports_streaming,
                    supports_word_timestamps=caps.supports_word_timestamps,
                    gpu_requested=self._gpu_requested,
                    gpu_available=self._gpu_available,
                    torch_version=torch_diag["torch_version"],
                    torch_built_with_cuda=torch_diag["torch_built_with_cuda"],
                    torch_cuda_is_available=torch_diag["torch_cuda_is_available"],
                    torch_cuda_version=torch_diag["torch_cuda_version"],
                    torch_device_count=torch_diag["torch_device_count"],
                    first_gpu_name=torch_diag["first_gpu_name"],
                    python_executable=torch_diag["python_executable"],
                    venv_path=torch_diag["venv_path"],
                    cpu_fallback_reason=self._cpu_fallback_reason or self._infer_cpu_fallback_reason(torch_diag),
                    actual_selected_device=self._resolved_device_name(),
                    actual_execution_provider=self.execution_provider_name,
                    ready=False,
                    message=(
                        "NeMo ASR runtime dependencies are not installed. "
                        f"Import detail: {self._nemo_import_error or 'unknown import failure.'}"
                    ),
                    runtime_initialized=runtime_initialized,
                )
        if include_runtime_state and not runtime_initialized:
            try:
                self._ensure_loaded()
                runtime_initialized = self._model is not None
            except AsrProviderError as exc:
                return AsrProviderDiagnostics(
                    provider_name=caps.provider_name,
                    model_path=str(self.model_path),
                    supports_gpu=caps.supports_gpu,
                    supports_partials=caps.supports_partials,
                    supports_streaming=caps.supports_streaming,
                    supports_word_timestamps=caps.supports_word_timestamps,
                    gpu_requested=self._gpu_requested,
                    gpu_available=self._gpu_available,
                    torch_version=torch_diag["torch_version"],
                    torch_built_with_cuda=torch_diag["torch_built_with_cuda"],
                    torch_cuda_is_available=torch_diag["torch_cuda_is_available"],
                    torch_cuda_version=torch_diag["torch_cuda_version"],
                    torch_device_count=torch_diag["torch_device_count"],
                    first_gpu_name=torch_diag["first_gpu_name"],
                    python_executable=torch_diag["python_executable"],
                    venv_path=torch_diag["venv_path"],
                    cpu_fallback_reason=self._cpu_fallback_reason or self._infer_cpu_fallback_reason(torch_diag),
                    actual_selected_device=self._actual_selected_device or self._resolved_device_name(),
                    actual_execution_provider=self.execution_provider_name,
                    ready=False,
                    message=str(exc),
                    runtime_initialized=False,
                )
        if runtime_initialized:
            ready_message = (
                f"Ready with official EU multilingual model '{OFFICIAL_EU_PARAKEET_REPO}' via "
                f"{self.execution_provider_name} on {self._actual_selected_device or 'cpu'}."
            )
            if self._runtime_note:
                ready_message = f"{ready_message} {self._runtime_note}"
        else:
            ready_message = (
                f"ASR provider '{self.provider_name}' passed lightweight readiness checks. "
                "Dependency import and full runtime initialization are deferred until runtime start."
            )
        return AsrProviderDiagnostics(
            provider_name=caps.provider_name,
            model_path=str(self.model_path),
            supports_gpu=caps.supports_gpu,
            supports_partials=caps.supports_partials,
            supports_streaming=caps.supports_streaming,
            supports_word_timestamps=caps.supports_word_timestamps,
            gpu_requested=self._gpu_requested,
            gpu_available=self._gpu_available,
            torch_version=torch_diag["torch_version"],
            torch_built_with_cuda=torch_diag["torch_built_with_cuda"],
            torch_cuda_is_available=torch_diag["torch_cuda_is_available"],
            torch_cuda_version=torch_diag["torch_cuda_version"],
            torch_device_count=torch_diag["torch_device_count"],
            first_gpu_name=torch_diag["first_gpu_name"],
            python_executable=torch_diag["python_executable"],
            venv_path=torch_diag["venv_path"],
            cpu_fallback_reason=self._cpu_fallback_reason or self._infer_cpu_fallback_reason(torch_diag),
            actual_selected_device=self._actual_selected_device if runtime_initialized else None,
            actual_execution_provider=self.execution_provider_name,
            ready=True,
            message=ready_message,
            runtime_initialized=runtime_initialized,
        )

    def _resolved_device_name(self) -> str:
        if self._gpu_requested and self._gpu_available:
            return "cuda"
        if self._gpu_requested and not self._gpu_available:
            return "cpu"
        return "cpu"

    def _ensure_loaded(self):
        if self._model is not None:
            return self._model
        if not self._nemo_dependency_available():
            detail = f" Import detail: {self._nemo_import_error}" if self._nemo_import_error else ""
            raise AsrProviderError(
                "NeMo ASR runtime dependencies are not installed for the official EU multilingual model."
                f"{detail}"
            )
        if not self.model_path.exists():
            try:
                self._report_runtime_status("Preparing the first local Parakeet model download...")
                self.model_path = ensure_official_eu_parakeet_model(
                    self.models_dir,
                    progress_callback=self._report_runtime_status,
                )
            except Exception as exc:
                raise AsrProviderError(
                    "Failed to download the official EU multilingual model automatically. "
                    f"Source: '{OFFICIAL_EU_PARAKEET_URL}'. Error: {exc}"
                ) from exc

        preferred_device = self._resolved_device_name()
        if self._gpu_requested and not self._gpu_available:
            self._cpu_fallback_reason = self._infer_cpu_fallback_reason(self._collect_torch_diagnostics())
            self._runtime_note = self._cpu_fallback_reason or "GPU was requested but CUDA is not available, so CPU fallback is active."

        try:
            self._report_runtime_status(
                "Loading Parakeet model on NVIDIA GPU..." if preferred_device == "cuda" else "Loading Parakeet model on CPU..."
            )
            self._model = self._load_model_on_device(preferred_device)
            self._actual_selected_device = preferred_device
            self._report_runtime_status(
                "Parakeet model loaded on NVIDIA GPU." if preferred_device == "cuda" else "Parakeet model loaded on CPU."
            )
            return self._model
        except Exception as exc:
            if preferred_device == "cuda":
                self._cpu_fallback_reason = (
                    f"CUDA initialization failed for the ASR provider: {type(exc).__name__}: {exc}"
                )
                self._runtime_note = (
                    f"GPU was requested and CUDA was detected, but model initialization on CUDA failed ({type(exc).__name__}: {exc}). "
                    "CPU fallback is active."
                )
                try:
                    self._report_runtime_status("CUDA initialization failed. Falling back to CPU model load...")
                    self._model = self._load_model_on_device("cpu")
                    self._actual_selected_device = "cpu"
                    self._report_runtime_status("Parakeet model loaded on CPU fallback.")
                    return self._model
                except Exception as fallback_exc:
                    self._model = None
                    raise AsrProviderError(
                        f"Failed to load official EU multilingual model on CUDA and CPU fallback also failed: {fallback_exc}"
                    ) from fallback_exc

            self._model = None
            raise AsrProviderError(
                f"Failed to load official EU multilingual model '{self.model_path.name}': {exc}"
            ) from exc

    def _load_model_on_device(self, device_name: str):
        asr_models = importlib.import_module("nemo.collections.asr.models")
        asr_model_cls = getattr(asr_models, "ASRModel")
        map_location: Any = device_name
        if device_name == "cuda":
            torch = importlib.import_module("torch")
            map_location = torch.device("cuda")
        model = asr_model_cls.restore_from(
            restore_path=str(self.model_path),
            map_location=map_location,
        )
        if device_name == "cuda":
            if hasattr(model, "to"):
                moved_model = model.to(map_location)
                if moved_model is not None:
                    model = moved_model
            elif hasattr(model, "cuda"):
                moved_model = model.cuda()
                if moved_model is not None:
                    model = moved_model
        if hasattr(model, "freeze"):
            model.freeze()
        if hasattr(model, "eval"):
            model.eval()
        return model

    def _nemo_dependency_available(self, *, probe_only: bool = False) -> bool:
        if self._nemo_available is not None:
            return self._nemo_available
        try:
            if probe_only:
                self._nemo_available = importlib.util.find_spec("nemo.collections.asr.models") is not None
                self._nemo_import_error = None if self._nemo_available else "find_spec returned None for nemo.collections.asr.models"
            else:
                importlib.import_module("nemo.collections.asr.models")
                self._nemo_available = True
                self._nemo_import_error = None
        except Exception as exc:
            self._nemo_available = False
            self._nemo_import_error = f"{type(exc).__name__}: {exc}"
        return self._nemo_available

    def _detect_gpu_available(self) -> bool:
        try:
            torch = importlib.import_module("torch")
            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def _collect_torch_diagnostics(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "torch_version": None,
            "torch_built_with_cuda": False,
            "torch_cuda_is_available": False,
            "torch_cuda_version": None,
            "torch_device_count": 0,
            "first_gpu_name": None,
            "python_executable": sys.executable,
            "venv_path": os.environ.get("VIRTUAL_ENV") or (sys.prefix if sys.prefix != getattr(sys, "base_prefix", sys.prefix) else None),
        }
        try:
            torch = importlib.import_module("torch")
            info["torch_version"] = getattr(torch, "__version__", None)
            info["torch_cuda_version"] = getattr(getattr(torch, "version", None), "cuda", None)
            info["torch_built_with_cuda"] = bool(info["torch_cuda_version"])
            info["torch_cuda_is_available"] = bool(torch.cuda.is_available())
            if info["torch_cuda_is_available"]:
                info["torch_device_count"] = int(torch.cuda.device_count())
                if info["torch_device_count"] > 0:
                    try:
                        info["first_gpu_name"] = str(torch.cuda.get_device_name(0))
                    except Exception:
                        info["first_gpu_name"] = None
        except Exception:
            pass

        if not info["first_gpu_name"]:
            smi_gpu = self._query_first_gpu_name_from_nvidia_smi()
            if smi_gpu:
                info["first_gpu_name"] = smi_gpu
        return info

    def _query_first_gpu_name_from_nvidia_smi(self) -> str | None:
        nvidia_smi = shutil.which("nvidia-smi")
        if not nvidia_smi:
            return None
        try:
            completed = subprocess.run(
                [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            return None
        if completed.returncode != 0:
            return None
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        return lines[0] if lines else None

    def _infer_cpu_fallback_reason(self, torch_diag: dict[str, Any]) -> str | None:
        if not self._gpu_requested:
            return None
        if not torch_diag.get("torch_version"):
            return "PyTorch is not importable in the current project environment, so CUDA cannot be used."
        if not torch_diag.get("torch_built_with_cuda"):
            version = torch_diag.get("torch_version") or "unknown"
            return (
                f"Installed PyTorch build is CPU-only ({version}); torch.version.cuda is None, "
                "so this environment cannot use CUDA."
            )
        if not torch_diag.get("torch_cuda_is_available"):
            cuda_version = torch_diag.get("torch_cuda_version") or "unknown"
            gpu_name = torch_diag.get("first_gpu_name")
            if gpu_name:
                return (
                    f"PyTorch was built with CUDA {cuda_version}, but torch.cuda.is_available() is False "
                    f"even though the system reports GPU '{gpu_name}'. This points to an environment or runtime mismatch."
                )
            return (
                f"PyTorch was built with CUDA {cuda_version}, but torch.cuda.is_available() is False, "
                "so CUDA runtime initialization failed or no usable CUDA device is available."
            )
        return None

    def _write_wav(self, path: Path, audio_segment: bytes, sample_rate: int) -> None:
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_segment)

    def _audio_bytes_to_float32(self, audio_segment: bytes) -> np.ndarray:
        if not audio_segment:
            return np.zeros(0, dtype=np.float32)
        samples = np.frombuffer(audio_segment, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return np.zeros(0, dtype=np.float32)
        return samples / 32768.0

    def _extract_first_hypothesis(self, hypotheses: Any) -> Any | None:
        if hypotheses is None:
            return None
        if isinstance(hypotheses, tuple):
            if not hypotheses:
                return None
            hypotheses = hypotheses[0]
        if isinstance(hypotheses, list):
            return hypotheses[0] if hypotheses else None
        return hypotheses

    def _extract_text(self, hypotheses: Any) -> str:
        first = self._extract_first_hypothesis(hypotheses)
        if first is None:
            return ""
        if isinstance(first, str):
            return first.strip()
        if hasattr(first, "text"):
            return str(first.text).strip()
        return str(first).strip()


class OfficialEuParakeetProvider(BaseOfficialEuParakeetNemoProvider):
    provider_name = ASR_PROVIDER_OFFICIAL
    execution_provider_name = "nemo_file"

    def transcribe(
        self,
        audio_segment: bytes,
        *,
        sample_rate: int,
        is_final: bool,
        segment_id: str | None = None,
    ) -> AsrResult:
        if not is_final or not audio_segment:
            return AsrResult()

        model = self._ensure_loaded()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            wav_path = Path(tmp_file.name)
        try:
            self._write_wav(wav_path, audio_segment, sample_rate)
            hypotheses = model.transcribe([str(wav_path)], batch_size=1, verbose=False)
            text = self._extract_text(hypotheses)
            if not text:
                return AsrResult()
            return AsrResult(
                segments=[
                    AsrSegmentResult(
                        text=text,
                        is_final=True,
                    )
                ]
            )
        except AsrProviderError:
            raise
        except Exception as exc:
            raise AsrProviderError(f"Official EU Parakeet transcription failed: {exc}") from exc
        finally:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass


class OfficialEuParakeetRealtimeProvider(BaseOfficialEuParakeetNemoProvider):
    provider_name = ASR_PROVIDER_REALTIME
    execution_provider_name = "nemo_direct"

    @dataclass
    class _StreamingSegmentState:
        buffer: Any
        current_batched_hyps: Any | None
        decoder_state: Any | None
        first_step: bool
        pending_audio: np.ndarray
        current_text: str
        processed_samples: int

    def __init__(
        self,
        models_dir: Path,
        *,
        prefer_gpu: bool = False,
        config_getter: Callable[[], dict] | None = None,
        runtime_status_callback: ProgressCallback | None = None,
    ) -> None:
        super().__init__(
            models_dir,
            prefer_gpu=prefer_gpu,
            config_getter=config_getter,
            runtime_status_callback=runtime_status_callback,
        )
        self._stream_states: dict[str, OfficialEuParakeetRealtimeProvider._StreamingSegmentState] = {}
        self._streaming_context_samples: Any | None = None
        self._encoder_frame2audio_samples: int | None = None
        self._streaming_sample_rate: int | None = None

    def capabilities(self) -> AsrProviderCapabilities:
        return AsrProviderCapabilities(
            provider_name=self.provider_name,
            supports_gpu=True,
            supports_partials=True,
            supports_streaming=False,
            supports_word_timestamps=False,
        )

    def reset_runtime_state(self) -> None:
        self._stream_states.clear()
        self._streaming_context_samples = None
        self._encoder_frame2audio_samples = None
        self._streaming_sample_rate = None

    def unload_runtime(self) -> None:
        self.reset_runtime_state()
        super().unload_runtime()

    def _realtime_config(self) -> dict[str, Any]:
        config = self._config_getter() if self._config_getter is not None else {}
        asr_config = config.get("asr", {}) if isinstance(config, dict) else {}
        realtime = asr_config.get("realtime", {}) if isinstance(asr_config, dict) else {}
        return realtime if isinstance(realtime, dict) else {}

    def _resolved_streaming_window_ms(self) -> tuple[int, int, int]:
        realtime = self._realtime_config()
        partial_emit_interval_ms = max(120, int(realtime.get("partial_emit_interval_ms", 450) or 450))
        chunk_window_ms = int(realtime.get("chunk_window_ms", 0) or 0)
        chunk_overlap_ms = int(realtime.get("chunk_overlap_ms", 0) or 0)

        if chunk_window_ms <= 0:
            chunk_window_ms = max(640, min(1200, int(round(partial_emit_interval_ms * 1.6))))
        if chunk_overlap_ms <= 0:
            chunk_overlap_ms = max(160, min(320, chunk_window_ms // 3))

        chunk_overlap_ms = min(chunk_overlap_ms, max(0, chunk_window_ms - 80))
        left_context_ms = max(1800, min(6000, chunk_window_ms * 3))
        return chunk_window_ms, chunk_overlap_ms, left_context_ms

    def _ensure_streaming_runtime(self, model: Any, *, sample_rate: int) -> None:
        if (
            self._streaming_context_samples is not None
            and self._encoder_frame2audio_samples is not None
            and self._streaming_sample_rate == sample_rate
        ):
            return

        from nemo.collections.asr.parts.submodules.rnnt_decoding import RNNTDecodingConfig
        from nemo.collections.asr.parts.utils.streaming_utils import ContextSize

        decoding_cfg = RNNTDecodingConfig(strategy="greedy_batch")
        decoding_cfg.greedy.loop_labels = True
        decoding_cfg.greedy.preserve_alignments = False
        decoding_cfg.tdt_include_token_duration = False
        decoding_cfg.fused_batch_size = -1
        decoding_cfg.beam.return_best_hypothesis = True
        model.change_decoding_strategy(decoding_cfg)

        model_cfg = model._cfg
        feature_stride_sec = float(model_cfg.preprocessor["window_stride"])
        features_per_sec = 1.0 / feature_stride_sec
        encoder_subsampling_factor = int(model.encoder.subsampling_factor)

        features_frame2audio_samples = _make_divisible_by(
            int(sample_rate * feature_stride_sec),
            factor=encoder_subsampling_factor,
        )
        encoder_frame2audio_samples = features_frame2audio_samples * encoder_subsampling_factor

        chunk_window_ms, chunk_overlap_ms, left_context_ms = self._resolved_streaming_window_ms()
        context_encoder_frames = ContextSize(
            left=int((left_context_ms / 1000.0) * features_per_sec / encoder_subsampling_factor),
            chunk=int((chunk_window_ms / 1000.0) * features_per_sec / encoder_subsampling_factor),
            right=int((chunk_overlap_ms / 1000.0) * features_per_sec / encoder_subsampling_factor),
        )
        context_samples = ContextSize(
            left=context_encoder_frames.left * encoder_subsampling_factor * features_frame2audio_samples,
            chunk=context_encoder_frames.chunk * encoder_subsampling_factor * features_frame2audio_samples,
            right=context_encoder_frames.right * encoder_subsampling_factor * features_frame2audio_samples,
        )
        if int(context_samples.chunk) <= 0:
            raise AsrProviderError("Realtime Parakeet streaming chunk window resolved to zero samples.")

        self._streaming_context_samples = context_samples
        self._encoder_frame2audio_samples = encoder_frame2audio_samples
        self._streaming_sample_rate = sample_rate
        self._runtime_note = (
            f"Incremental streaming decode is active "
            f"(chunk {chunk_window_ms} ms, overlap {chunk_overlap_ms} ms, left context {left_context_ms} ms)."
        )

    def _build_stream_state(self, *, device: Any) -> _StreamingSegmentState:
        from nemo.collections.asr.parts.utils.streaming_utils import StreamingBatchedAudioBuffer
        torch = importlib.import_module("torch")

        assert self._streaming_context_samples is not None
        return self._StreamingSegmentState(
            buffer=StreamingBatchedAudioBuffer(
                batch_size=1,
                context_samples=self._streaming_context_samples,
                dtype=torch.float32,
                device=device,
            ),
            current_batched_hyps=None,
            decoder_state=None,
            first_step=True,
            pending_audio=np.zeros((0,), dtype=np.float32),
            current_text="",
            processed_samples=0,
        )

    def _model_device(self, model: Any) -> Any:
        device = getattr(model, "device", None)
        if device is not None:
            return device
        torch = importlib.import_module("torch")
        return torch.device(self._actual_selected_device or self._resolved_device_name())

    def _get_text_from_hyps(self, model: Any, hyps: Any | None) -> str:
        if hyps is None:
            return ""
        from nemo.collections.asr.parts.utils.rnnt_utils import batched_hyps_to_hypotheses

        hypothesis = batched_hyps_to_hypotheses(hyps, alignments=None, batch_size=1)[0]
        return str(model.tokenizer.ids_to_text(hypothesis.y_sequence.tolist())).strip()

    def _decode_step(
        self,
        *,
        model: Any,
        state: _StreamingSegmentState,
        chunk_audio: np.ndarray,
        is_last_chunk: bool,
    ) -> str:
        assert self._streaming_context_samples is not None
        assert self._encoder_frame2audio_samples is not None

        torch = importlib.import_module("torch")
        decoding_computer = model.decoding.decoding.decoding_computer
        model_device = self._model_device(model)
        audio_t = torch.from_numpy(chunk_audio).unsqueeze(0).to(device=model_device, dtype=torch.float32)
        audio_lengths = torch.tensor([audio_t.shape[1]], device=model_device, dtype=torch.long)
        is_last_chunk_batch = torch.tensor([is_last_chunk], device=model_device, dtype=torch.bool)

        state.buffer.add_audio_batch_(
            audio_t,
            audio_lengths=audio_lengths,
            is_last_chunk=is_last_chunk,
            is_last_chunk_batch=is_last_chunk_batch,
        )

        encoder_output, encoder_output_len = model(
            input_signal=state.buffer.samples,
            input_signal_length=state.buffer.context_size_batch.total(),
        )
        encoder_output = encoder_output.transpose(1, 2)

        encoder_context = state.buffer.context_size.subsample(factor=self._encoder_frame2audio_samples)
        encoder_context_batch = state.buffer.context_size_batch.subsample(factor=self._encoder_frame2audio_samples)
        encoder_output = encoder_output[:, encoder_context.left :]

        out_len = torch.where(
            is_last_chunk_batch,
            encoder_output_len - encoder_context_batch.left,
            encoder_context_batch.chunk,
        )
        call_params = inspect.signature(decoding_computer.__call__).parameters
        if "multi_biasing_ids" in call_params:
            chunk_hyps, _, state.decoder_state = decoding_computer(
                x=encoder_output,
                out_len=out_len,
                prev_batched_state=state.decoder_state,
                multi_biasing_ids=None,
            )
        else:
            chunk_hyps, _, state.decoder_state = decoding_computer(
                x=encoder_output,
                out_len=out_len,
                prev_batched_state=state.decoder_state,
            )

        if state.current_batched_hyps is None:
            state.current_batched_hyps = chunk_hyps
        else:
            state.current_batched_hyps.merge_(chunk_hyps)
        return self._get_text_from_hyps(model, state.current_batched_hyps)

    def _decode_available_audio(self, *, model: Any, state: _StreamingSegmentState) -> None:
        assert self._streaming_context_samples is not None

        required = (
            int(self._streaming_context_samples.chunk + self._streaming_context_samples.right)
            if state.first_step
            else int(self._streaming_context_samples.chunk)
        )
        while state.pending_audio.shape[0] >= required:
            chunk = state.pending_audio[:required]
            state.pending_audio = state.pending_audio[required:]
            state.current_text = self._decode_step(
                model=model,
                state=state,
                chunk_audio=chunk,
                is_last_chunk=False,
            )
            state.first_step = False
            required = int(self._streaming_context_samples.chunk)

    def _flush_final_audio(self, *, model: Any, state: _StreamingSegmentState, sample_rate: int) -> None:
        if state.pending_audio.shape[0] > int(sample_rate * 0.05):
            state.current_text = self._decode_step(
                model=model,
                state=state,
                chunk_audio=state.pending_audio,
                is_last_chunk=True,
            )
        state.pending_audio = np.zeros((0,), dtype=np.float32)
        state.current_batched_hyps = None
        state.decoder_state = None

    def transcribe(
        self,
        audio_segment: bytes,
        *,
        sample_rate: int,
        is_final: bool,
        segment_id: str | None = None,
    ) -> AsrResult:
        if not audio_segment:
            return AsrResult()

        model = self._ensure_loaded()
        audio_array = self._audio_bytes_to_float32(audio_segment)
        if audio_array.size == 0:
            return AsrResult()

        try:
            hypotheses = model.transcribe(
                [audio_array],
                batch_size=1,
                return_hypotheses=True,
                verbose=False,
            )
        except Exception as exc:
            raise AsrProviderError(f"Official EU Parakeet realtime transcription failed: {exc}") from exc

        text = self._extract_text(hypotheses)
        if not text:
            return AsrResult()
        return AsrResult(
            segments=[
                AsrSegmentResult(
                    text=text,
                    is_partial=not is_final,
                    is_final=is_final,
                )
            ]
        )


def allow_mock_asr() -> bool:
    return os.getenv("STREAM_SUB_TRANSLATOR_ALLOW_MOCK_ASR", "").strip().lower() in {"1", "true", "yes"}


def get_asr_provider_override() -> str | None:
    value = os.getenv("STREAM_SUB_TRANSLATOR_ASR_PROVIDER", "").strip().lower()
    return value or None
