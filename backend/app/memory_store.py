"""Long-term memory: facts per user, searched semantically (pgvector) when an embedding provider works,
by keywords otherwise. All access is scoped by user_id; clients never touch the table directly."""
from __future__ import annotations

import asyncio
import re

from . import db
from .providers import embed as embed_mod
from .providers.errors import ProviderError
from .providers.rotation import Rotation

MAX_FACTS = 500
SMALL = 12
SCOPES = {"global", "research", "coding", "creative", "planner"}
_STOP = {"the", "a", "an", "is", "are", "to", "of", "and", "or", "my", "i", "you", "me", "it", "in", "on", "for", "what", "do"}


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


async def embed_text(rot: Rotation, text: str) -> str | None:
    try:
        plan = await rot.plan("embed", "", "free")
        _, v = await rot.run(plan, lambda r: embed_mod.embed(rot.http, r.spec, r.api_key, text))
        return _vec(v)
    except ProviderError:
        return None


async def add(rot: Rotation, user_id: str, fact: str, scope: str = "global") -> dict | None:
    fact = fact.strip()[:500]
    if not fact or scope not in SCOPES:
        return None
    if await db.pool().fetchval("select count(*) from public.memory_facts where user_id=$1", user_id) >= MAX_FACTS:
        return None
    v = await embed_text(rot, fact)
    row = await db.pool().fetchrow(
        "insert into public.memory_facts(user_id,fact,scope,embedding) values($1,$2,$3,$4::vector) returning id,fact,scope,created_at",
        user_id, fact, scope, v)
    return _row(row)


async def update(rot: Rotation, user_id: str, fact_id: str, fact: str) -> bool:
    fact = fact.strip()[:500]
    if not fact:
        return False
    v = await embed_text(rot, fact)
    r = await db.pool().execute("update public.memory_facts set fact=$3, embedding=$4::vector where id=$1 and user_id=$2",
                                fact_id, user_id, fact, v)
    return r.endswith("1")


async def delete(user_id: str, fact_id: str) -> bool:
    return (await db.pool().execute("delete from public.memory_facts where id=$1 and user_id=$2", fact_id, user_id)).endswith("1")


async def list_facts(user_id: str, q: str = "") -> list[dict]:
    if q.strip():
        rows = await db.pool().fetch("select id,fact,scope,created_at from public.memory_facts where user_id=$1 and fact ilike $2 order by created_at desc limit 200",
                                     user_id, f"%{q.strip()}%")
    else:
        rows = await db.pool().fetch("select id,fact,scope,created_at from public.memory_facts where user_id=$1 order by created_at desc limit 200", user_id)
    return [_row(r) for r in rows]


async def search(rot: Rotation, user_id: str, query: str, scopes: list[str], k: int = 6) -> list[str]:
    """Relevant facts for the current message, limited to the scopes this agent may see.
    Fast path: with a handful of facts we just return them all (no embedding call = a quicker first word)."""
    rows = await db.pool().fetch("select fact from public.memory_facts where user_id=$1 and scope=any($2::text[]) order by created_at desc limit $3",
                                 user_id, scopes, SMALL + 1)
    if 0 < len(rows) <= SMALL:
        return [r["fact"] for r in rows]
    if not rows:
        return []
    try:
        v = await asyncio.wait_for(embed_text(rot, query), 1.5)
    except asyncio.TimeoutError:
        v = None
    if v:
        rows = await db.pool().fetch(
            "select fact from public.memory_facts where user_id=$1 and scope=any($2::text[]) and embedding is not null "
            "order by embedding <=> $3::vector limit $4", user_id, scopes, v, k)
        if rows:
            return [r["fact"] for r in rows]
    words = [w for w in re.findall(r"[a-zA-Z0-9]{3,}", query.lower()) if w not in _STOP][:6]
    if words:
        rows = await db.pool().fetch(
            "select fact from public.memory_facts where user_id=$1 and scope=any($2::text[]) and fact ilike any($3::text[]) limit $4",
            user_id, scopes, [f"%{w}%" for w in words], k)
        if rows:
            return [r["fact"] for r in rows]
    rows = await db.pool().fetch("select fact from public.memory_facts where user_id=$1 and scope=any($2::text[]) order by created_at desc limit 4",
                                 user_id, scopes)
    return [r["fact"] for r in rows]


def _row(r) -> dict:
    return {"id": str(r["id"]), "fact": r["fact"], "scope": r["scope"], "created_at": r["created_at"].isoformat()}
