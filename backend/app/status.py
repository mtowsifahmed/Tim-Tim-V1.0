"""Builds the 'which mode am I in / who is serving me' status shown in the UI at all times."""
from __future__ import annotations

from . import db, policy
from .auth import CurrentUser
from .config import settings
from .providers.rotation import Rotation


async def build_status(user: CurrentUser, rot: Rotation) -> dict:
    plans = {cap: await rot.plan(cap, user.id, user.role) for cap in ("llm", "stt", "tts")}
    providers = {cap: (p[0].name if p else None) for cap, p in plans.items()}
    sources = {cap: (p[0].source if p else None) for cap, p in plans.items()}
    uses_rotation = any(s == "rotation" for s in sources.values())

    cap = policy.daily_cap(user.role, settings.free_daily_cap, settings.pro_rotation_daily_cap)
    used = await db.pool().fetchval(
        "select coalesce(turns,0) from public.usage_daily where user_id=$1 and day=(now() at time zone 'utc')::date",
        user.id) or 0
    remaining = None if cap is None else max(cap - used, 0)

    if user.role == "owner":
        mode = "owner"
    elif user.role == "moderator":
        mode = "moderator"
    elif user.role == "pro" and not uses_rotation:
        mode = "pro_own_keys"
    elif user.role == "pro":
        mode = "pro_mixed"
    else:
        mode = "free"
    return {"email": user.email, "role": user.role, "plan": user.plan, "mode": mode,
            "daily_cap": cap, "used_today": used, "remaining_today": remaining,
            "providers": providers, "key_source": sources}
