from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.models import AudioInputDevice
from backend.services.runtime_service import RuntimeService


class RuntimeServiceDeviceResolutionTests(unittest.TestCase):
    def _service(self, *, configured_device_id: str | None) -> RuntimeService:
        app = SimpleNamespace(
            state=SimpleNamespace(
                config={"audio": {"input_device_id": configured_device_id}},
                config_state_service=None,
            )
        )
        return RuntimeService(app)  # type: ignore[arg-type]

    @staticmethod
    def _devices() -> list[AudioInputDevice]:
        return [
            AudioInputDevice(id="default-mic", name="Default Mic", is_default=True),
            AudioInputDevice(id="2", name="Legacy Mic", is_default=False),
        ]

    def test_desktop_prefers_default_when_request_is_empty(self) -> None:
        service = self._service(configured_device_id="2")
        with patch.dict(os.environ, {"SST_DESKTOP_LAUNCHER": "1"}, clear=False):
            resolved = service._resolve_runtime_start_device_id(None, self._devices())
        self.assertEqual(resolved, "default-mic")

    def test_non_desktop_keeps_configured_device_when_request_is_empty(self) -> None:
        service = self._service(configured_device_id="2")
        with patch.dict(os.environ, {"SST_DESKTOP_LAUNCHER": "0"}, clear=False):
            resolved = service._resolve_runtime_start_device_id(None, self._devices())
        self.assertEqual(resolved, "2")

    def test_explicit_requested_device_wins_in_desktop_mode(self) -> None:
        service = self._service(configured_device_id="2")
        with patch.dict(os.environ, {"SST_DESKTOP_LAUNCHER": "1"}, clear=False):
            resolved = service._resolve_runtime_start_device_id("2", self._devices())
        self.assertEqual(resolved, "2")

    def test_desktop_falls_back_to_default_when_requested_id_missing(self) -> None:
        service = self._service(configured_device_id="2")
        with patch.dict(os.environ, {"SST_DESKTOP_LAUNCHER": "1"}, clear=False):
            resolved = service._resolve_runtime_start_device_id("99", self._devices())
        self.assertEqual(resolved, "default-mic")


if __name__ == "__main__":
    unittest.main()
