from __future__ import annotations

import httpx

from .errors import ProviderError
from .errors import raise_for
from .registry import ProviderSpec


async def embed(client: httpx.AsyncClient, spec: ProviderSpec, key: str, text: str) -> list[float]:
    body = {"model": spec.model, "input": text}
    if spec.dimensions:
        body["dimensions"] = spec.dimensions
    r = await client.post(f"{spec.base_url}/embeddings", headers={"Authorization": f"Bearer {key}"}, json=body, timeout=30)
    raise_for(r.status_code, r.headers, r.text if r.status_code >= 400 else '')
    try:
        vec = r.json()["data"][0]["embedding"]
    except (KeyError, IndexError, ValueError) as e:
        raise ProviderError("unexpected embeddings response") from e
    if spec.dimensions and len(vec) != spec.dimensions:
        raise ProviderError("embedding size mismatch")
    return vec
