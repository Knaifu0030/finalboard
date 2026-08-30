"""OpenAI-compatible model providers used by Billboard Games.

Credentials are resolved from environment variable names stored in the catalog. Raw
keys are never persisted in MongoDB or returned by public serializers.
"""
import asyncio
import json
import os
import time
from urllib.parse import urlparse

import httpx


class ProviderError(RuntimeError):
    pass


def _allowed_host(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        return False
    allowed = [x.strip().lower() for x in os.environ.get(
        "MODEL_ENDPOINT_ALLOWLIST", "api.tokenfactory.nebius.com"
    ).split(",") if x.strip()]
    host = parsed.hostname.lower()
    return any(host == item or host.endswith("." + item) for item in allowed)


def public_model(doc: dict) -> dict:
    return {
        "id": doc.get("id"),
        "provider": doc.get("provider", "openai-compatible"),
        "label": doc.get("label") or doc.get("model"),
        "model": doc.get("model"),
        "enabled": bool(doc.get("enabled", True)),
    }


async def enabled_models(db) -> list[dict]:
    rows = [m async for m in db.model_catalog.find({"enabled": {"$ne": False}}).sort("label", 1)]
    if rows:
        return rows
    model = os.environ.get("NEBIUS_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
    return [{
        "id": "nebius-default",
        "provider": "nebius",
        "label": "Nebius · " + model.split("/")[-1],
        "model": model,
        "base_url": os.environ.get("NEBIUS_API_BASE", "https://api.tokenfactory.nebius.com/v1"),
        "credential_env": "NEBIUS_API_KEY",
        "enabled": True,
    }]


async def get_model(db, model_id: str | None) -> dict:
    if model_id:
        doc = await db.model_catalog.find_one({"id": model_id, "enabled": {"$ne": False}})
        if doc:
            return doc
    models = await enabled_models(db)
    if not models:
        raise ProviderError("No model is enabled.")
    return models[0]


def _extract_json(text: str):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        start, end = text.find("["), text.rfind("]")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
    raise ProviderError("Model returned invalid JSON.")


async def chat_json(db, model_doc: dict, *, system: str, payload: dict,
                    purpose: str, timeout: float = 40, retries: int = 1):
    base = str(model_doc.get("base_url") or "").rstrip("/")
    if not _allowed_host(base):
        raise ProviderError("Model endpoint is not allowlisted.")
    key = os.environ.get(str(model_doc.get("credential_env") or ""), "")
    if not key:
        raise ProviderError("Model credential is not configured.")
    body = {
        "model": model_doc["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0.85,
        "response_format": {"type": "json_object"},
    }
    started = time.perf_counter()
    error = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                response = await client.post(
                    base + "/chat/completions",
                    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                    json=body,
                )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = _extract_json(content)
            await db.model_usage.insert_one({
                "provider": model_doc.get("provider"), "model": model_doc.get("model"),
                "purpose": purpose, "ok": True,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "usage": data.get("usage") or {}, "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            })
            return parsed
        except Exception as exc:
            error = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 400:
                # Some vLLM/OpenAI-compatible deployments do not implement
                # response_format even though they otherwise support chat completions.
                body.pop("response_format", None)
            if attempt < retries:
                await asyncio.sleep(0.4 * (attempt + 1))
    await db.model_usage.insert_one({
        "provider": model_doc.get("provider"), "model": model_doc.get("model"),
        "purpose": purpose, "ok": False, "error": str(error)[:300],
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    })
    raise ProviderError(str(error))


async def health(model_doc: dict) -> dict:
    base = str(model_doc.get("base_url") or "").rstrip("/")
    if not _allowed_host(base):
        return {"ok": False, "error": "endpoint not allowlisted"}
    key = os.environ.get(str(model_doc.get("credential_env") or ""), "")
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            response = await client.get(base + "/models", headers={"Authorization": "Bearer " + key})
        response.raise_for_status()
        return {"ok": True, "models": len((response.json() or {}).get("data") or [])}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}
