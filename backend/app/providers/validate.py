"""'Validate' button: one harmless, read-only call per provider kind. Never logs the key."""
import httpx

from .errors import AuthError, ProviderError, QuotaError, ModelError
from .registry import ProviderSpec


async def validate_key(client: httpx.AsyncClient, spec: ProviderSpec, key: str) -> None:
    if spec.kind == "openai":
        r = await client.get(f"{spec.base_url}/models", headers={"Authorization": f"Bearer {key}"})
    elif spec.kind == "gemini":
        r = await client.get(f"{spec.base_url}/models", headers={"x-goog-api-key": key})
    elif spec.kind == "deepgram":
        r = await client.get(f"{spec.base_url}/v1/projects", headers={"Authorization": f"Token {key}"})
    elif spec.kind == "elevenlabs":
        r = await client.get(f"{spec.base_url}/v1/user", headers={"xi-api-key": key})
    elif spec.kind == "cloudflare":
        root = spec.base_url.split("/ai/run")[0]
        r = await client.get(f"{root}/tokens/verify", headers={"Authorization": f"Bearer {key}"})
    elif spec.kind == "edge":
        return                                   # no key to validate
    else:
        raise ProviderError(f"unknown provider kind {spec.kind}")
    if r.status_code in (401, 403):
        raise AuthError("that key was rejected by the provider")
    if r.status_code == 429:
        raise QuotaError("provider is rate-limiting this key right now")
    if r.status_code >= 400:
        raise ProviderError(f"provider returned HTTP {r.status_code}")
