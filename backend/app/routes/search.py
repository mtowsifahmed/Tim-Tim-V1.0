"""Per-account Tavily key for live web search.

The app owner's key lives only in backend/.env and is never sent to a client and never used for another account.
Everyone else can paste their own free Tavily key; it is checked once, then encrypted exactly like the other BYOK keys.
Without a key Tim-Tim still searches, using the keyless sources (Google News, GDELT, DuckDuckGo).
"""
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import crypto, db
from ..auth import CurrentUser, current_user

router = APIRouter(prefix="/search")

PLACEHOLDER = "tvly-…"          # what the app shows when no key is saved for this account
CHECK_URL = "https://api.tavily.com/search"


class KeyIn(BaseModel):
    key: str = Field(min_length=8, max_length=200)


async def _check(key: str) -> bool:
    """True if Tavily accepted the key. Raises 400/429 on a clear answer; False when Tavily can't be reached
    (a blocked network must not stop you saving a key that works for the search path later)."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(CHECK_URL, headers={"Authorization": f"Bearer {key}"},
                             json={"query": "tim-tim key check", "max_results": 1, "search_depth": "basic"})
    except httpx.HTTPError:
        return False
    if r.status_code in (401, 403):
        raise HTTPException(400, "Tavily rejected that key")
    if r.status_code == 429:
        raise HTTPException(429, "Tavily is rate-limiting this key right now; try again shortly")
    if r.status_code >= 400:
        raise HTTPException(502, f"Tavily returned HTTP {r.status_code}")
    return True


@router.get("/key")
async def get_key(user: CurrentUser = Depends(current_user)):
    row = await db.pool().fetchrow(
        "select last4 from public.api_keys where user_id=$1 and capability='search'", user.id)
    # The owner runs on the app's own key from .env; that key is never lent to any other account.
    shared = user.role == "owner" and not row and bool(os.getenv("TAVILY_API_KEY", "").strip())
    return {"configured": bool(row), "masked": crypto.mask(row["last4"]) if row else None,
            "shared": shared, "placeholder": PLACEHOLDER}


@router.put("/key")
async def save_key(body: KeyIn, user: CurrentUser = Depends(current_user)):
    key = body.key.strip()
    checked = await _check(key)
    try:
        cipher, l4 = crypto.encrypt(key), crypto.last4(key)
    except crypto.KeySecretError as e:
        raise HTTPException(500, str(e)) from e
    await db.pool().execute(
        "insert into public.api_keys(user_id,capability,provider,key_cipher,last4) values($1,'search','tavily',$2,$3) "
        "on conflict (user_id,capability) do update set key_cipher=excluded.key_cipher, last4=excluded.last4, created_at=now()",
        user.id, cipher, l4)
    return {"saved": True, "masked": crypto.mask(l4), "checked": checked}


@router.delete("/key")
async def remove_key(user: CurrentUser = Depends(current_user)):
    await db.pool().execute(
        "delete from public.api_keys where user_id=$1 and capability='search'", user.id)
    return {"removed": True}
