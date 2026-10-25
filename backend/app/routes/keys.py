"""Pro-only BYOK keys. Keys are validated with one harmless call, encrypted, and only ever shown masked."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import crypto, db, policy
from ..auth import CurrentUser, current_user
from ..providers.errors import AuthError, ProviderError, QuotaError
from ..providers.validate import validate_key

router = APIRouter(prefix="/keys")


class KeyIn(BaseModel):
    provider: str
    key: str = Field(min_length=8, max_length=512)


def _gate(user: CurrentUser):
    if not policy.can_use_byok(user.role):
        raise HTTPException(403, "Adding your own API keys is a Pro feature")


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
    spec = rot.spec_by_name(capability, body.provider) if capability in ("llm", "stt", "tts") else None
    if not spec:
        raise HTTPException(404, "Unknown provider for that capability")
    try:
        await validate_key(rot.http, spec, body.key.strip())
    except AuthError:
        raise HTTPException(400, "That key was rejected by the provider")
    except QuotaError:
        raise HTTPException(429, "Provider is rate-limiting this key right now; try again shortly")
    except ProviderError as e:
        raise HTTPException(502, str(e))
    return {"valid": True}


@router.put("/{capability}")
async def save(capability: str, body: KeyIn, request: Request, user: CurrentUser = Depends(current_user)):
    """Validates first, then stores. A key that fails validation is never saved."""
    await validate(capability, body, request, user)
    key = body.key.strip()
    try:
        cipher, l4 = crypto.encrypt(key), crypto.last4(key)
    except crypto.KeySecretError as e:
        # encryption is misconfigured on the server, not a problem with the user's key: say so plainly
        raise HTTPException(500, str(e)) from e
    await db.pool().execute(
        "insert into public.api_keys(user_id,capability,provider,key_cipher,last4) values($1,$2,$3,$4,$5) "
        "on conflict (user_id,capability) do update set provider=excluded.provider, "
        "key_cipher=excluded.key_cipher, last4=excluded.last4, created_at=now()",
        user.id, capability, body.provider, cipher, l4)
    return {"saved": True, "masked": crypto.mask(l4)}


@router.delete("/{capability}")
async def remove(capability: str, user: CurrentUser = Depends(current_user)):
    _gate(user)
    await db.pool().execute("delete from public.api_keys where user_id=$1 and capability=$2", user.id, capability)
    return {"removed": True}
