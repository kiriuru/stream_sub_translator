from __future__ import annotations

import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module
from helpers import AppStateSandbox


class RemoteFlowTests(unittest.TestCase):
    def test_pairing_verify_and_heartbeat_contracts(self) -> None:
        config = {"remote": {"enabled": True, "role": "controller"}}
        with AppStateSandbox(config=config) as sandbox, TestClient(app_module.app) as client:
            created = client.post("/api/remote/pair/create", json={"ttl_seconds": 120}).json()
            session_id = created["session_id"]
            pair_code = created["pair_code"]

            self.assertEqual(created["pairing"]["session_id"], session_id)
            self.assertEqual(sandbox.config_manager.saved_payloads[-1]["remote"]["session_id"], session_id)
            self.assertEqual(sandbox.config_manager.saved_payloads[-1]["remote"]["pair_code"], pair_code)

            verified = client.post(
                "/api/remote/pair/verify",
                json={"session_id": session_id, "pair_code": pair_code},
            ).json()
            self.assertTrue(verified["accepted"])
            self.assertTrue(verified["pairing"]["worker_online"])

            heartbeat = client.post(
                "/api/remote/heartbeat",
                json={"session_id": session_id, "role": "controller"},
            ).json()
            self.assertTrue(heartbeat["accepted"])
            self.assertEqual(heartbeat["pairing"]["session_id"], session_id)

    def test_remote_signaling_relays_between_controller_and_worker(self) -> None:
        with AppStateSandbox(config={"remote": {"enabled": True, "role": "controller"}}) as _sandbox, TestClient(
            app_module.app
        ) as client:
            pair = client.post("/api/remote/pair/create", json={"ttl_seconds": 120}).json()
            session_id = pair["session_id"]
            pair_code = pair["pair_code"]
            query = f"session_id={session_id}&pair_code={pair_code}"

            with client.websocket_connect(f"/ws/remote/signaling?{query}&role=controller") as controller:
                controller_first = controller.receive_json()
                controller_second = controller.receive_json()
                self.assertEqual(controller_first["type"], "peer_state")
                self.assertEqual(controller_second["type"], "hello")

                with client.websocket_connect(f"/ws/remote/signaling?{query}&role=worker") as worker:
                    worker_first = worker.receive_json()
                    worker_second = worker.receive_json()
                    controller_peer_update = controller.receive_json()

                    self.assertEqual(worker_first["type"], "peer_state")
                    self.assertEqual(worker_second["type"], "hello")
                    self.assertTrue(controller_peer_update["worker_connected"])

                    controller.send_json({"type": "signal", "payload": {"sdp": "offer-1"}})
                    relayed = worker.receive_json()
                    self.assertEqual(relayed["type"], "signal")
                    self.assertEqual(relayed["from_role"], "controller")
                    self.assertEqual(relayed["payload"], {"sdp": "offer-1"})

                    worker.send_json({"type": "heartbeat"})
                    heartbeat_ack = worker.receive_json()
                    self.assertEqual(heartbeat_ack["type"], "heartbeat_ack")
                    self.assertTrue(heartbeat_ack["accepted"])

    def test_remote_audio_and_result_ingest_reach_runtime_orchestrator(self) -> None:
        with AppStateSandbox(config={"remote": {"enabled": True, "role": "controller"}}) as sandbox, TestClient(
            app_module.app
        ) as client:
            pair = client.post("/api/remote/pair/create", json={"ttl_seconds": 120}).json()
            session_id = pair["session_id"]
            pair_code = pair["pair_code"]

            with client.websocket_connect(
                f"/ws/remote/audio_ingest?session_id={session_id}&pair_code={pair_code}"
            ) as websocket:
                hello = websocket.receive_json()
                self.assertEqual(hello["message"], "remote_audio_ingest_connected")
                websocket.send_bytes(b"\x01\x02\x03")
                websocket.send_json({"type": "ping"})
                pong = websocket.receive_json()
                self.assertEqual(pong["type"], "pong")

            self.assertEqual(sandbox.runtime_orchestrator.remote_audio_connected, [session_id])
            self.assertEqual(sandbox.runtime_orchestrator.remote_audio_chunks, [b"\x01\x02\x03"])
            self.assertEqual(sandbox.runtime_orchestrator.remote_audio_disconnected, 1)

            with client.websocket_connect("/ws/remote/result_ingest") as websocket:
                hello = websocket.receive_json()
                self.assertEqual(hello["message"], "remote_result_ingest_connected")
                websocket.send_json({"type": "transcript_update", "payload": {"sequence": 3, "text": "privet"}})
                websocket.send_json(
                    {
                        "type": "translation_update",
                        "payload": {"sequence": 3, "translations": [{"target_lang": "en", "text": "hello"}]},
                    }
                )
                websocket.send_json({"type": "ping"})
                self.assertEqual(websocket.receive_json(), {"type": "pong"})

            self.assertEqual(sandbox.runtime_orchestrator.remote_transcript_payloads, [{"sequence": 3, "text": "privet"}])
            self.assertEqual(
                sandbox.runtime_orchestrator.remote_translation_payloads,
                [{"sequence": 3, "translations": [{"target_lang": "en", "text": "hello"}]}],
            )

    def test_worker_settings_sync_forces_local_asr_mode(self) -> None:
        config = {
            "source_lang": "ru",
            "translation": {"enabled": True, "target_languages": ["en", "de"]},
            "subtitle_output": {"show_source": False, "show_translations": True, "max_translation_languages": 2},
            "remote": {
                "enabled": True,
                "role": "controller",
                "controller": {"worker_url": "http://worker.local:8765"},
            },
        }
        captured_payloads: list[dict] = []

        async def fake_proxy(request, *, method, path, json_payload=None):
            _ = request
            if method == "GET" and path == "/api/settings/load":
                return "http://worker.local:8765", {"payload": {"asr": {"mode": "browser_google"}}}, None
            if method == "POST" and path == "/api/settings/save":
                captured_payloads.append(dict(json_payload))
                return "http://worker.local:8765", {"payload": dict(json_payload.get("payload", {}))}, None
            raise AssertionError(f"Unexpected proxy call: {method} {path}")

        with AppStateSandbox(config=config) as _sandbox, TestClient(app_module.app) as client:
            with mock.patch("backend.api.routes_remote._proxy_worker_request", side_effect=fake_proxy):
                response = client.post("/api/remote/worker/settings/sync")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["worker_asr_mode"], "local")
        self.assertEqual(body["worker_target_languages"], ["en", "de"])
        self.assertEqual(captured_payloads[0]["payload"]["asr"]["mode"], "local")
        self.assertEqual(captured_payloads[0]["payload"]["translation"]["target_languages"], ["en", "de"])


if __name__ == "__main__":
    unittest.main()
