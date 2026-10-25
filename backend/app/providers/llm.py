from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from .errors import raise_for


async def stream_chat(client: httpx.AsyncClient, *, base_url: str, api_key: str, model: str,
                      messages: list[dict]) -> AsyncIterator[str]:
    """Token stream from any OpenAI-compatible /chat/completions endpoint
    (Gemini, Groq, Cerebras, SambaNova, OpenRouter, Mistral, NVIDIA, custom gateway...)."""
    async with client.stream(
        "POST", f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": messages, "stream": True},
    ) as r:
        if r.status_code >= 400:
            body = (await r.aread()).decode("utf-8", "replace")
            raise_for(r.status_code, r.headers, body)
        async for line in r.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                delta = json.loads(data)["choices"][0]["delta"].get("content")
            except (KeyError, IndexError, json.JSONDecodeError, TypeError):
                continue
            if delta:
                yield delta


async def list_models(client: httpx.AsyncClient, base_url: str, api_key: str) -> list[str]:
    """Model ids the key can use (for self-healing when a model name is retired)."""
    r = await client.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=20)
    raise_for(r.status_code, r.headers, r.text)
    data = r.json().get("data") or r.json().get("models") or []
    return [str(m.get("id") or m.get("name", "")).removeprefix("models/") for m in data if isinstance(m, dict)]
