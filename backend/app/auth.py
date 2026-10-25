"""Identity comes from Supabase, the role comes from OUR users table. Nothing about role is ever read from the client.

Tokens are verified LOCALLY (signature via the project's public JWKS, or the legacy HS256 secret), so a normal request never
calls Supabase and can't be hit by its rate limits. If local verification isn't possible we fall back to asking Supabase,
and if Supabase is rate-limiting or unreachable we answer 503 (client retries, user stays signed in) rather than 401."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx
import jwt
from fastapi import Depends, HTTPException, Request

from . import db
from .config import settings

log = logging.getLogger("timtim.auth")
_cache: dict[str, tuple[float, str]] = {}          # token -> (valid_until, user_id)
_jwks: dict = {"keys": [], "at": 0.0}


class _Fallback(Exception):
    """Local verification not possible; use the network check."""


@dataclass
class CurrentUser:
    id: str
    email: str
    role: str
    plan: str


async def _load_jwks(force: bool = False) -> list[dict]:
    if not force and _jwks["keys"] and time.time() - _jwks["at"] < 3600:
        return _jwks["keys"]
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", headers={"apikey": settings.supabase_anon_key})
    if r.status_code != 200:
        raise _Fallback()
    _jwks.update(keys=r.json().get("keys", []), at=time.time())
    return _jwks["keys"]


async def _local_verify(token: str) -> tuple[str, float]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, "Invalid session") from e
    alg, kid = header.get("alg", ""), header.get("kid")
    try:
        if alg in ("ES256", "RS256"):
            keys = await _load_jwks()
            jwk = next((k for k in keys if k.get("kid") == kid), None)
            if jwk is None:
                jwk = next((k for k in await _load_jwks(force=True) if k.get("kid") == kid), None)
            if jwk is None:
                raise _Fallback()
            key = jwt.PyJWK(jwk).key
        elif alg == "HS256" and settings.supabase_jwt_secret:
            key = settings.supabase_jwt_secret
        else:
            raise _Fallback()
        payload = jwt.decode(token, key, algorithms=[alg], audience="authenticated", leeway=15,
                             options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(401, "Session expired") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, "Invalid session") from e
    except httpx.HTTPError as e:
        raise _Fallback() from e
    iss = str(payload.get("iss", "")).rstrip("/")
    if settings.supabase_url and iss and iss != f"{settings.supabase_url.rstrip('/')}/auth/v1":
        raise HTTPException(401, "Invalid session")
    return str(payload["sub"]), float(payload["exp"])


async def _network_verify(token: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{settings.supabase_url}/auth/v1/user", headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_anon_key})
    except httpx.HTTPError as e:
        raise HTTPException(503, "Sign-in service unreachable; retrying") from e
    if r.status_code == 200:
        return r.json()["id"]
    if r.status_code in (401, 403):
        raise HTTPException(401, "Invalid or expired session")
    raise HTTPException(503, "Sign-in service is busy; retrying")        # 429 and 5xx: NOT the user's fault


async def verify_token(token: str) -> str:
    now = time.time()
    hit = _cache.get(token)
    if hit and hit[0] > now:
        return hit[1]
    try:
        uid, exp = await _local_verify(token)
        _cache[token] = (min(exp, now + 3600), uid)
        return uid
    except _Fallback:
        pass
    try:
        uid = await _network_verify(token)
        _cache[token] = (now + 300, uid)
        return uid
    except HTTPException as e:
        if e.status_code == 503 and hit:                                 # sticky: a token we already trusted stays trusted briefly
            log.warning("auth service busy; reusing the earlier verification of this token")
            return hit[1]
        raise


async def load_user(user_id: str) -> CurrentUser:
    row = await db.pool().fetchrow("select id, email, role, plan from public.users where id = $1", user_id)
    if not row:
        raise HTTPException(403, "No account record for this user")
    return CurrentUser(str(row["id"]), row["email"], row["role"], row["plan"])


async def current_user(request: Request) -> CurrentUser:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    return await load_user(await verify_token(auth[7:]))


async def require_staff(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if user.role not in ("owner", "moderator"):
        raise HTTPException(403, "Staff only")
    return user
