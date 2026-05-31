from __future__ import annotations

import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module
from helpers import AppStateSandbox


class _FakeHttpxResponse:
    def __init__(self, status_code: int, json_payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._json_payload = json_payload or {}
        self.text = text

    def json(self):
        return self._json_payload


class _FakeAsyncClient:
    def __init__(self, get_map: dict[str, _FakeHttpxResponse], post_map: dict[str, _FakeHttpxResponse]) -> None:
        self._get_map = get_map
        self._post_map = post_map

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):
        return self._get_map.get(url) or _FakeHttpxResponse(404, text="not mocked")

    async def post(self, url, headers=None, json=None):
        model = (json or {}).get("model")
        key = f"{url}::{model}"
        return self._post_map.get(key) or _FakeHttpxResponse(404, json_payload={"error": {"code": "not_mocked"}}, text="not mocked")


class OpenAIModelsRouteTests(unittest.TestCase):
    def test_models_route_requires_api_key(self) -> None:
        with AppStateSandbox() as _sandbox, TestClient(app_module.app) as client:
            response = client.post("/api/openai/models", json={"api_key": ""})
            self.assertEqual(response.status_code, 400)
            self.assertIn("empty", response.json().get("detail", "").lower())

    def test_models_route_returns_sorted_and_filters_recommended_by_default(self) -> None:
        fake_payload = {
            "object": "list",
            "data": [
                {"id": "text-embedding-3-small", "owned_by": "openai", "created": 1},
                {"id": "gpt-4o-mini", "owned_by": "openai", "created": 2},
                {"id": "o1-mini", "owned_by": "openai", "created": 3},
                {"id": "whisper-1", "owned_by": "openai", "created": 4},
            ],
        }
        base_url = "https://api.openai.com/v1"
        fake_response = _FakeHttpxResponse(status_code=200, json_payload=fake_payload)

        with AppStateSandbox() as _sandbox, TestClient(app_module.app) as client:
            with mock.patch(
                "backend.api.routes_openai_models.httpx.AsyncClient",
                autospec=True,
                side_effect=lambda *args, **kwargs: _FakeAsyncClient(
                    get_map={f"{base_url}/models": fake_response},
                    post_map={},
                ),
            ):
                response = client.post(
                    "/api/openai/models",
                    json={"api_key": "sk-test", "base_url": base_url},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body.get("ok"))
        models = body.get("models") or []
        ids = [item.get("id") for item in models]
        # Default behavior is recommended-only, sorted by id
        self.assertEqual(ids, sorted(ids))
        self.assertIn("gpt-4o-mini", ids)
        self.assertIn("o1-mini", ids)
        self.assertNotIn("text-embedding-3-small", ids)
        self.assertNotIn("whisper-1", ids)

    def test_models_route_show_all_returns_everything(self) -> None:
        fake_payload = {
            "object": "list",
            "data": [
                {"id": "whisper-1", "owned_by": "openai", "created": 4},
                {"id": "gpt-4o-mini", "owned_by": "openai", "created": 2},
            ],
        }
        base_url = "https://api.openai.com/v1"
        fake_response = _FakeHttpxResponse(status_code=200, json_payload=fake_payload)

        with AppStateSandbox() as _sandbox, TestClient(app_module.app) as client:
            with mock.patch(
                "backend.api.routes_openai_models.httpx.AsyncClient",
                autospec=True,
                side_effect=lambda *args, **kwargs: _FakeAsyncClient(
                    get_map={f"{base_url}/models": fake_response},
                    post_map={},
                ),
            ):
                response = client.post(
                    "/api/openai/models",
                    json={"api_key": "sk-test", "base_url": base_url, "show_all": True},
                )

        self.assertEqual(response.status_code, 200)
        ids = [item.get("id") for item in response.json().get("models") or []]
        self.assertEqual(ids, ["gpt-4o-mini", "whisper-1"])

    def test_usable_models_probes_responses_and_sorts_preferred(self) -> None:
        base_url = "https://api.openai.com/v1"
        models_payload = {
            "object": "list",
            "data": [
                {"id": "gpt-4.1", "owned_by": "openai", "created": 1},
                {"id": "gpt-4o-mini", "owned_by": "openai", "created": 2},
                {"id": "text-embedding-3-small", "owned_by": "openai", "created": 3},
                {"id": "whisper-1", "owned_by": "openai", "created": 4},
            ],
        }
        get_models_response = _FakeHttpxResponse(200, json_payload=models_payload)
        post_map = {
            f"{base_url}/responses::gpt-4.1": _FakeHttpxResponse(404, json_payload={"error": {"code": "model_not_found"}}, text="nope"),
            f"{base_url}/responses::gpt-4o-mini": _FakeHttpxResponse(200, json_payload={"id": "resp_1"}),
        }

        with AppStateSandbox() as _sandbox, TestClient(app_module.app) as client:
            with mock.patch(
                "backend.api.routes_openai_models.httpx.AsyncClient",
                autospec=True,
                side_effect=lambda *args, **kwargs: _FakeAsyncClient(
                    get_map={f"{base_url}/models": get_models_response},
                    post_map=post_map,
                ),
            ):
                response = client.post(
                    "/api/openai/usable-models",
                    json={"api_key": "sk-test", "base_url": base_url, "test_all": False, "force_refresh": True},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("usable_models"), ["gpt-4o-mini"])
        self.assertEqual(body.get("checked_count"), 2)  # only the likely-text models were probed
        unavailable = body.get("unavailable_models") or []
        self.assertTrue(any(item.get("id") == "gpt-4.1" for item in unavailable))

    def test_recommended_models_endpoint_returns_static_list(self) -> None:
        with AppStateSandbox() as _sandbox, TestClient(app_module.app) as client:
            response = client.get("/api/openai/recommended-models")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body.get("ok"))
        models = body.get("models") or []
        self.assertIn("gpt-4o-mini", models)

    def test_models_route_blocks_private_base_url_when_lan_bind(self) -> None:
        from backend.config import settings

        with AppStateSandbox() as _sandbox, TestClient(app_module.app) as client:
            with mock.patch.object(settings, "app_host", "0.0.0.0"):
                response = client.post(
                    "/api/openai/models",
                    json={"api_key": "sk-test", "base_url": "http://127.0.0.1:1234/v1"},
                )
        self.assertEqual(response.status_code, 400)
        self.assertIn("LAN bind", response.json().get("detail", ""))

