from __future__ import annotations

import queue
import threading
from importlib import import_module
from collections import deque
from dataclasses import dataclass

import numpy as np
import sounddevice as sd


@dataclass
class AudioChunk:
    data: bytes
    frame_count: int
    sample_rate: int
    level: float


class AudioRingBuffer:
    def __init__(self, max_chunks: int = 64) -> None:
        self._chunks: deque[bytes] = deque(maxlen=max_chunks)
        self._lock = threading.Lock()

    def append(self, chunk: bytes) -> None:
        with self._lock:
            self._chunks.append(chunk)

    def snapshot(self) -> bytes:
        with self._lock:
            return b"".join(self._chunks)

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()


@dataclass
class RNNoiseStatus:
    enabled: bool
    strength: int
    backend_available: bool
    backend_name: str | None
    active: bool
    uses_resample: bool
    input_sample_rate: int
    processing_sample_rate: int | None
    frame_size_samples: int | None
    message: str


class RNNoiseRecognitionProcessor:
    """Recognition-only RNNoise path with explicit sample-rate conversion."""

    _BACKEND_NAME = "pyrnnoise"
    _DEFAULT_PROCESSING_SAMPLE_RATE = 48000
    _DEFAULT_FRAME_SIZE_SAMPLES = 480

    def __init__(self, *, sample_rate: int, channels: int = 1) -> None:
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.enabled = False
        self.strength = 70
        self._backend_loaded = False
        self._backend_available = False
        self._backend_error: str | None = None
        self._backend = None
        self._processing_sample_rate = self._DEFAULT_PROCESSING_SAMPLE_RATE
        self._frame_size_samples = self._DEFAULT_FRAME_SIZE_SAMPLES

    def configure(self, *, enabled: bool, strength: int) -> None:
        self.enabled = bool(enabled)
        self.strength = max(0, min(100, int(strength)))

    def status(self) -> RNNoiseStatus:
        self._ensure_backend_loaded()
        uses_resample = self.sample_rate != self._processing_sample_rate
        active = self.enabled and self._backend_available and self._format_supported() and self.strength > 0

        if not self.enabled:
            message = "RNNoise disabled; raw recognition audio path is active."
        elif not self._backend_available:
            message = f"RNNoise requested but backend is unavailable: {self._backend_error or 'unknown error'}"
        elif not self._format_supported():
            message = "RNNoise requested but the recognition path is not mono int16 audio."
        elif self.strength <= 0:
            message = "RNNoise enabled with 0% strength; raw recognition audio remains effectively unchanged."
        elif uses_resample:
            message = (
                f"RNNoise active with explicit resample "
                f"{self.sample_rate} Hz -> {self._processing_sample_rate} Hz -> {self.sample_rate} Hz."
            )
        else:
            message = f"RNNoise active on native {self._processing_sample_rate} Hz recognition audio."

        return RNNoiseStatus(
            enabled=self.enabled,
            strength=self.strength,
            backend_available=self._backend_available,
            backend_name=self._BACKEND_NAME if self._backend_available else None,
            active=active,
            uses_resample=uses_resample,
            input_sample_rate=self.sample_rate,
            processing_sample_rate=self._processing_sample_rate if self._backend_available else None,
            frame_size_samples=self._frame_size_samples if self._backend_available else None,
            message=message,
        )

    def process(self, audio: bytes) -> bytes:
        status = self.status()
        if not status.active or not audio or len(audio) % np.dtype(np.int16).itemsize != 0:
            return audio

        original = np.frombuffer(audio, dtype=np.int16).copy()
        if original.size == 0:
            return audio

        processing_input = (
            self._resample_int16(original, from_rate=self.sample_rate, to_rate=self._processing_sample_rate)
            if status.uses_resample
            else original
        )
        denoised = self._run_rnnoise(processing_input)
        mixed = self._mix_wet_dry(processing_input, denoised)
        restored = (
            self._resample_int16(
                mixed,
                from_rate=self._processing_sample_rate,
                to_rate=self.sample_rate,
                target_length=original.size,
            )
            if status.uses_resample
            else mixed
        )
        return restored.astype(np.int16, copy=False).tobytes()

    def _format_supported(self) -> bool:
        return self.channels == 1 and self.sample_rate > 0

    def _ensure_backend_loaded(self) -> None:
        if self._backend_loaded:
            return
        self._backend_loaded = True
        try:
            backend = import_module("pyrnnoise.rnnoise")
            self._backend = backend
            self._processing_sample_rate = int(getattr(backend, "SAMPLE_RATE", self._DEFAULT_PROCESSING_SAMPLE_RATE))
            self._frame_size_samples = int(getattr(backend, "FRAME_SIZE", self._DEFAULT_FRAME_SIZE_SAMPLES))
            self._backend_available = self._processing_sample_rate > 0 and self._frame_size_samples > 0
            if not self._backend_available:
                self._backend_error = "invalid RNNoise backend constants"
        except Exception as exc:
            self._backend_available = False
            self._backend_error = str(exc)
            self._backend = None

    def _run_rnnoise(self, samples: np.ndarray) -> np.ndarray:
        assert self._backend is not None
        state = self._backend.create()
        frames: list[np.ndarray] = []
        try:
            for start in range(0, samples.size, self._frame_size_samples):
                frame = samples[start : start + self._frame_size_samples]
                denoised_frame, _speech_prob = self._backend.process_mono_frame(state, frame)
                frames.append(denoised_frame.astype(np.int16, copy=False))
        finally:
            self._backend.destroy(state)

        if not frames:
            return samples.astype(np.int16, copy=True)
        return np.concatenate(frames)[: samples.size].astype(np.int16, copy=False)

    def _mix_wet_dry(self, original: np.ndarray, denoised: np.ndarray) -> np.ndarray:
        wet = self.strength / 100.0
        dry = 1.0 - wet
        mixed = (original.astype(np.float32) * dry) + (denoised.astype(np.float32) * wet)
        return np.clip(np.round(mixed), -32768, 32767).astype(np.int16)

    def _resample_int16(
        self,
        samples: np.ndarray,
        *,
        from_rate: int,
        to_rate: int,
        target_length: int | None = None,
    ) -> np.ndarray:
        if samples.size == 0:
            return samples.astype(np.int16, copy=True)
        if from_rate == to_rate and (target_length is None or target_length == samples.size):
            return samples.astype(np.int16, copy=True)

        if target_length is None:
            target_length = max(1, int(round(samples.size * (float(to_rate) / float(from_rate)))))
        if samples.size == 1:
            return np.full(target_length, int(samples[0]), dtype=np.int16)

        source_positions = np.linspace(0.0, 1.0, num=samples.size, endpoint=True, dtype=np.float64)
        target_positions = np.linspace(0.0, 1.0, num=target_length, endpoint=True, dtype=np.float64)
        resampled = np.interp(target_positions, source_positions, samples.astype(np.float32))
        return np.clip(np.round(resampled), -32768, 32767).astype(np.int16)


class AudioCapture:
    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        channels: int = 1,
        frame_duration_ms: int = 30,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_duration_ms = frame_duration_ms
        self.blocksize = int(self.sample_rate * self.frame_duration_ms / 1000)
        self._queue: queue.Queue[AudioChunk] = queue.Queue()
        self._stream: sd.RawInputStream | None = None
        self._ring_buffer = AudioRingBuffer()

    @property
    def ring_buffer(self) -> AudioRingBuffer:
        return self._ring_buffer

    def _callback(self, indata: bytes, frames: int, _time: object, status: sd.CallbackFlags) -> None:
        if status:
            return
        chunk_bytes = bytes(indata)
        if not chunk_bytes:
            return
        samples = np.frombuffer(chunk_bytes, dtype=np.int16)
        level = float(np.abs(samples).mean()) if samples.size else 0.0
        chunk = AudioChunk(
            data=chunk_bytes,
            frame_count=frames,
            sample_rate=self.sample_rate,
            level=level,
        )
        self._ring_buffer.append(chunk_bytes)
        self._queue.put(chunk)

    def start(self, device_id: str | None = None) -> None:
        if self._stream is not None:
            return
        device: int | None = int(device_id) if device_id not in (None, "") else None
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            channels=self.channels,
            dtype="int16",
            device=device,
            callback=self._callback,
        )
        self._stream.start()

    def read_chunk(self, timeout: float = 0.25) -> AudioChunk | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._ring_buffer.clear()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
