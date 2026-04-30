from __future__ import annotations

import asyncio
import unittest

from fastapi.testclient import TestClient

from backend import app as app_module
from helpers import AppStateSandbox


class ApiAndWebSocketTests(unittest.TestCase):
    def test_api_route_contracts_cover_health_runtime_settings_version_and_exports(self) -> None:
        config = {
            "source_lang": "ru",
            "ui": {"language": "en"},
            "translation": {"enabled": True, "target_languages": ["en", "de"]},
            "subtitle_output": {"show_source": True, "show_translations": True},
            "profile": "streamer",
            "remote": {"enabled": False, "role": "disabled"},
        }
        with AppStateSandbox(config=config) as sandbox, TestClient(app_module.app) as client:
            export_dir = sandbox.paths.data_dir / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "sample.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["asr_provider"], "fake_asr")

            version = client.get("/api/version")
            self.assertEqual(version.status_code, 200)
            self.assertIn("current_version", version.json())

            runtime_status = client.get("/api/runtime/status")
            self.assertEqual(runtime_status.status_code, 200)
            self.assertEqual(runtime_status.json()["status"], "idle")

            runtime_start = client.post("/api/runtime/start", json={"device_id": "mic0"})
            self.assertEqual(runtime_start.status_code, 200)
            self.assertEqual(runtime_start.json()["runtime"]["status"], "listening")
            self.assertEqual(sandbox.runtime_orchestrator.start_calls[-1]["device_id"], "mic0")

            runtime_stop = client.post("/api/runtime/stop")
            self.assertEqual(runtime_stop.status_code, 200)
            self.assertEqual(runtime_stop.json()["runtime"]["status"], "idle")

            settings_save = client.post(
                "/api/settings/save",
                json={"payload": {**config, "source_lang": "ja", "ui": {"language": "ru"}}},
            )
            self.assertEqual(settings_save.status_code, 200)
            self.assertTrue(settings_save.json()["live_applied"])
            self.assertEqual(settings_save.json()["payload"]["source_lang"], "ja")
            self.assertEqual(settings_save.json()["payload"]["ui"]["language"], "ru")
            self.assertEqual(sandbox.runtime_orchestrator.apply_live_settings_calls[-1]["source_lang"], "ja")

            settings_load = client.get("/api/settings/load")
            self.assertEqual(settings_load.status_code, 200)
            self.assertEqual(settings_load.json()["payload"]["source_lang"], "ja")
            self.assertEqual(settings_load.json()["payload"]["ui"]["language"], "ru")

            obs_url = client.get("/api/obs/url")
            self.assertEqual(obs_url.status_code, 200)
            self.assertEqual(obs_url.json()["overlay_url"], "http://127.0.0.1:8765/overlay")

            exports = client.get("/api/exports")
            self.assertEqual(exports.status_code, 200)
            self.assertEqual(exports.json()["exports"], ["sample.srt"])
            self.assertEqual(exports.json()["files"][0]["name"], "sample.srt")

            devices = client.get("/api/devices/audio-inputs")
            self.assertEqual(devices.status_code, 200)
            self.assertEqual(devices.json()["devices"][0]["id"], "mic0")

    def test_ws_events_replays_latest_runtime_subtitle_and_overlay_messages(self) -> None:
        with AppStateSandbox() as sandbox, TestClient(app_module.app) as client:
            asyncio.run(sandbox.ws_manager.broadcast({"type": "runtime_update", "payload": {"status": "listening"}}))
            asyncio.run(
                sandbox.ws_manager.broadcast(
                    {"type": "subtitle_payload_update", "payload": {"sequence": 7, "line1": "Hello"}}
                )
            )
            asyncio.run(
                sandbox.ws_manager.broadcast({"type": "overlay_update", "payload": {"visible": True, "line1": "Hello"}})
            )

            with client.websocket_connect("/ws/events") as websocket:
                messages = [websocket.receive_json() for _ in range(4)]

            self.assertEqual(messages[0]["type"], "hello")
            self.assertEqual(messages[1], {"type": "runtime_update", "payload": {"status": "listening"}})
            self.assertEqual(
                messages[2],
                {"type": "subtitle_payload_update", "payload": {"sequence": 7, "line1": "Hello"}},
            )
            self.assertEqual(
                messages[3],
                {"type": "overlay_update", "payload": {"visible": True, "line1": "Hello"}},
            )

    def test_ws_asr_worker_forwards_external_updates_and_tracks_lifecycle(self) -> None:
        with AppStateSandbox() as sandbox, TestClient(app_module.app) as client:
            with client.websocket_connect("/ws/asr_worker") as websocket:
                hello = websocket.receive_json()
                self.assertEqual(hello["type"], "hello")
                self.assertEqual(hello["message"], "browser_asr_worker_connected")
                websocket.send_json(
                    {
                        "type": "external_asr_update",
                        "partial": "par",
                        "final": "final text",
                        "is_final": True,
                        "source_lang": "en-US",
                    }
                )

            self.assertEqual(sandbox.runtime_orchestrator.browser_worker_connected, 1)
            self.assertEqual(sandbox.runtime_orchestrator.browser_worker_disconnected, 1)
            self.assertEqual(
                sandbox.runtime_orchestrator.external_updates,
                [
                    {
                        "partial": "par",
                        "final": "final text",
                        "is_final": True,
                        "source_lang": "en-US",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
