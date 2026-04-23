from __future__ import annotations

from typing import Any

import sounddevice as sd

from backend.models import AudioInputDevice


class AudioDeviceManager:
    def list_input_devices(self) -> list[AudioInputDevice]:
        try:
            devices: list[dict[str, Any]] = sd.query_devices()
            default_input_index = sd.default.device[0] if sd.default.device else None
        except Exception:
            return []

        result: list[AudioInputDevice] = []
        for index, item in enumerate(devices):
            max_inputs = int(item.get("max_input_channels", 0) or 0)
            if max_inputs <= 0:
                continue
            is_default = default_input_index == index
            result.append(
                AudioInputDevice(
                    id=str(index),
                    name=str(item.get("name", f"Input {index}")),
                    is_default=is_default,
                    max_input_channels=max_inputs,
                    default_samplerate=float(item.get("default_samplerate", 0) or 0),
                )
            )
        return result

