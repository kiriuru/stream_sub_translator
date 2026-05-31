from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import settings
from backend.core.outbound_url_policy import assert_openai_base_url_allowed

router = APIRouter(prefix="/api/openai", tags=["openai"])

RECOMMENDED_OPENAI_TEXT_MODELS = [
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4.1",
]

_USABLE_MODELS_CACHE_TTL_S = 10 * 60
_usable_models_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class OpenAIModelsRequest(BaseModel):
    api_key: str = Field(default="", description="OpenAI (or compatible) API key")
    base_url: str | None = Field(default=None, description="Base URL, e.g. https://api.openai.com/v1")
    show_all: bool = Field(default=False, description="Return all models instead of recommended subset")

class OpenAIUsableModelsRequest(BaseModel):
    api_key: str = Field(default="", description="OpenAI (or compatible) API key")
    base_url: str | None = Field(default=None, description="Base URL, e.g. https://api.openai.com/v1")
    test_all: bool = Field(default=False, description="Probe every listed model (can be slower / cost more).")
    force_refresh: bool = Field(default=False, description="Ignore cache and re-probe.")
    max_checks: int = Field(
        default=25,
        ge=1,
        le=200,
        description="Maximum number of models to probe (ignored when test_all=true).",
    )


def _normalize_base_url(value: str | None) -> str:
    base = (value or "https://api.openai.com/v1").strip().rstrip("/")
    if not base:
        base = "https://api.openai.com/v1"
    if not (base.startswith("http://") or base.startswith("https://")):
        raise HTTPException(status_code=400, detail="base_url must start with http:// or https://")
    return assert_openai_base_url_allowed(
        base,
        bind_host=settings.app_host,
    )


def _is_likely_text_model(model_id: str) -> bool:
    model_id = (model_id or "").strip().lower()
    if not model_id:
        return False
    allow = model_id.startswith("gpt-") or model_id.startswith("o") or "chat" in model_id
    deny = any(
        token in model_id
        for token in (
            "embedding",
            "tts",
            "whisper",
            "image",
            "realtime",
            "audio",
            "moderation",
            "dall",
            "transcribe",
            "speech",
            "vision-preview",
        )
    )
    return allow and not deny


def _cache_key(api_key: str, base_url: str, test_all: bool) -> str:
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    return f"{base_url}::{digest}::test_all={1 if test_all else 0}"


def _cache_get(key: str) -> dict[str, Any] | None:
    entry = _usable_models_cache.get(key)
    if not entry:
        return None
    expires_at, payload = entry
    if time.time() >= expires_at:
        _usable_models_cache.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    _usable_models_cache[key] = (time.time() + _USABLE_MODELS_CACHE_TTL_S, payload)


def _extract_error_reason(response: Any) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            error = data.get("error") or {}
            if isinstance(error, dict):
                param = error.get("param")
                code = error.get("code")
                message = error.get("message")
                base = str(code or message or "unknown_error")
                if param:
                    return f"{base} (param={param})"
                return base
    except Exception:
        pass
    return str(getattr(response, "text", "") or "")[:300] or "unknown_error"


async def _probe_model(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    model_id: str,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    async with semaphore:
        try:
            response = await client.post(
                f"{base_url}/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "input": "Reply with exactly: OK",
                    # Some deployments (notably Azure OpenAI) enforce a minimum (often 16),
                    # and respond with integer_below_min_value if lower.
                    "max_output_tokens": 16,
                    "store": False,
                },
            )
            if response.status_code == 200:
                return {"id": model_id, "usable": True, "status": 200, "reason": None}
            return {
                "id": model_id,
                "usable": False,
                "status": response.status_code,
                "reason": _extract_error_reason(response),
            }
        except Exception as exc:
            return {"id": model_id, "usable": False, "status": None, "reason": str(exc)}


@router.post("/models")
async def list_openai_models(payload: OpenAIModelsRequest) -> dict[str, Any]:
    api_key = (payload.api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key is empty")

    base_url = _normalize_base_url(payload.base_url)
    url = f"{base_url}/models"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid API key")
        if response.status_code == 403:
            raise HTTPException(status_code=403, detail="Access forbidden for this API key")
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Rate limit or quota issue")
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text[:500])

        data = response.json()
        raw_items = data.get("data", [])
        if not isinstance(raw_items, list):
            raw_items = []

        models: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "").strip()
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "owned_by": item.get("owned_by"),
                    "created": item.get("created"),
                    "recommended": _is_likely_text_model(model_id),
                }
            )

        models.sort(key=lambda entry: entry["id"])
        if not payload.show_all:
            models = [entry for entry in models if entry.get("recommended")]

        return {"ok": True, "models": models}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {exc}") from exc


@router.get("/recommended-models")
async def list_recommended_openai_models() -> dict[str, Any]:
    return {"ok": True, "models": RECOMMENDED_OPENAI_TEXT_MODELS}


@router.post("/usable-models")
async def list_usable_openai_models(payload: OpenAIUsableModelsRequest) -> dict[str, Any]:
    api_key = (payload.api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key is empty")

    base_url = _normalize_base_url(payload.base_url)
    key = _cache_key(api_key=api_key, base_url=base_url, test_all=payload.test_all)
    if not payload.force_refresh:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    models_url = f"{base_url}/models"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            models_response = await client.get(
                models_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

            if models_response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid API key")
            if models_response.status_code == 403:
                raise HTTPException(status_code=403, detail="Access forbidden for this API key")
            if models_response.status_code == 429:
                raise HTTPException(status_code=429, detail="Rate limit or quota issue")
            if models_response.status_code >= 400:
                raise HTTPException(status_code=models_response.status_code, detail=models_response.text[:500])

            data = models_response.json()
            raw_items = data.get("data", [])
            if not isinstance(raw_items, list):
                raw_items = []

            ids: list[str] = []
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                model_id = str(item.get("id") or "").strip()
                if model_id:
                    ids.append(model_id)
            ids = sorted(set(ids))
            likely_text = [mid for mid in ids if _is_likely_text_model(mid)]

            preferred_order = [
                "gpt-4o-mini",
                "gpt-4.1-mini",
                "gpt-4.1-nano",
                "gpt-4o",
                "gpt-4.1",
            ]

            if payload.test_all:
                candidate_ids = ids
            else:
                # Fast UX path: try a short preferred shortlist first, then fill from other likely-text models.
                shortlist = [mid for mid in preferred_order if mid in likely_text]
                remaining = [mid for mid in likely_text if mid not in shortlist]
                cap = int(payload.max_checks or 25)
                candidate_ids = (shortlist + remaining)[:cap]

            semaphore = asyncio.Semaphore(3)
            probe_results = await asyncio.gather(
                *[
                    _probe_model(
                        client=client,
                        base_url=base_url,
                        api_key=api_key,
                        model_id=model_id,
                        semaphore=semaphore,
                    )
                    for model_id in candidate_ids
                ]
            )

        usable = [item["id"] for item in probe_results if item.get("usable")]
        unavailable = [item for item in probe_results if not item.get("usable")]

        usable_sorted = sorted(
            usable,
            key=lambda model_id: (
                preferred_order.index(model_id) if model_id in preferred_order else 999,
                model_id,
            ),
        )

        result = {
            "ok": True,
            "base_url": base_url,
            "usable_models": usable_sorted,
            "unavailable_models": unavailable,
            "listed_count": len(ids),
            "checked_count": len(probe_results),
            "check_cap": None if payload.test_all else int(payload.max_checks or 25),
            "cached": False,
            "cache_ttl_s": _USABLE_MODELS_CACHE_TTL_S,
        }
        _cache_set(key, {**result, "cached": True})
        return result

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to probe models: {exc}") from exc

