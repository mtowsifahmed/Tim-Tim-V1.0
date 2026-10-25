"""Per-account API keys (BYOK). Since v1 the free plan runs only on the user's own key, so this
is no longer a Pro feature: anybody signed in can add one. Keys are validated with one harmless
call, encrypted, and only ever shown masked."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import crypto, db, policy
from ..auth import CurrentUser, current_user
from ..providers.errors import AuthError, ProviderError, QuotaError
from ..providers.validate import validate_key

router = APIRouter(prefix="/keys")

CAPS = ("llm", "stt", "tts")


class KeyIn(BaseModel):
    provider: str
    key: str = Field(min_length=8, max_length=512)


class OneKeyIn(BaseModel):
    key: str = Field(min_length=8, max_length=512)


def _gate(user: CurrentUser):
    if not policy.can_use_byok(user.role):
        raise HTTPException(403, "This account cannot add its own API keys")


async def _check(rot, spec, key: str) -> None:
    try:
        await validate_key(rot.http, spec, key)
    except AuthError:
        raise HTTPException(400, "That key was rejected by the provider") from None
    except QuotaError:
        raise HTTPException(429, "Provider is rate-limiting this key right now; try again shortly") from None
    except ProviderError as e:
        raise HTTPException(502, str(e)) from e


async def _store(user_id: str, capability: str, provider: str, key: str) -> str:
    try:
        cipher, l4 = crypto.encrypt(key), crypto.last4(key)
    except crypto.KeySecretError as e:
        # encryption is misconfigured on the server, not a problem with the user's key: say so plainly
        raise HTTPException(500, str(e)) from e
    await db.pool().execute(
        "insert into public.api_keys(user_id,capability,provider,key_cipher,last4) values($1,$2,$3,$4,$5) "
        "on conflict (user_id,capability) do update set provider=excluded.provider, "
        "key_cipher=excluded.key_cipher, last4=excluded.last4, created_at=now()",
        user_id, capability, provider, cipher, l4)
    return l4


@router.get("")
async def list_keys(user: CurrentUser = Depends(current_user)):
    _gate(user)
    rows = await db.pool().fetch(
        "select capability, provider, last4, created_at from public.api_keys where user_id=$1", user.id)
    return [{"capability": r["capability"], "provider": r["provider"], "masked": crypto.mask(r["last4"]),
             "added": r["created_at"].isoformat()} for r in rows]


@router.post("/{capability}/validate")
async def validate(capability: str, body: KeyIn, request: Request, user: CurrentUser = Depends(current_user)):
    _gate(user)
    rot = request.app.state.rotation
    spec = rot.spec_by_name(capability, body.provider) if capability in CAPS else None
    if not spec:
        raise HTTPException(404, "Unknown provider for that capability")
    await _check(rot, spec, body.key.strip())
    return {"valid": True}


@router.put("/{capability}")
async def save(capability: str, body: KeyIn, request: Request, user: CurrentUser = Depends(current_user)):
    """Validates first, then stores. A key that fails validation is never saved."""
    if capability not in CAPS:
        raise HTTPException(404, "Unknown capability")
    await validate(capability, body, request, user)
    l4 = await _store(user.id, capability, body.provider, body.key.strip())
    return {"saved": True, "masked": crypto.mask(l4)}


@router.post("/one-key")
async def save_one_key(body: OneKeyIn, request: Request, user: CurrentUser = Depends(current_user)):
    """One Google AI Studio key for chat, speech recognition and voice. That is the whole free-plan setup:
    the same key covers every capability, so a new account never needs to visit three boxes."""
    _gate(user)
    rot = request.app.state.rotation
    key = body.key.strip()
    specs = {cap: next((s for s in rot.registry[cap] if s.kind == "gemini"), None) for cap in CAPS}
    if not specs.get("llm"):
        raise HTTPException(404, "This server has no Gemini provider configured")
    await _check(rot, specs["llm"], key)
    for cap, spec in specs.items():
        if spec:
            l4 = await _store(user.id, cap, spec.name, key)
    return {"saved": True, "masked": crypto.mask(l4), "capabilities": [c for c, s in specs.items() if s]}


@router.delete("/{capability}")
async def remove(capability: str, user: CurrentUser = Depends(current_user)):
    _gate(user)
    await db.pool().execute("delete from public.api_keys where user_id=$1 and capability=$2", user.id, capability)
    return {"removed": True}
