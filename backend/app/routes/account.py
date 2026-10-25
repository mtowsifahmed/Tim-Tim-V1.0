"""Your data: download everything Tim-Tim stores about you, or delete your account. Required for a public release."""
from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import db
from ..auth import CurrentUser, current_user

router = APIRouter(prefix="/account")


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _rows(rows, *cols):
    return [{c: _iso(r[c]) for c in cols} for r in rows]


@router.get("/export")
async def export(user: CurrentUser = Depends(current_user)):
    p = db.pool()
    me = await p.fetchrow("select email, role, plan, created_at from public.users where id=$1", user.id)
    settings = await p.fetchval("select persona from public.settings where user_id=$1", user.id)
    return {
        "account": {"email": me["email"], "role": me["role"], "plan": me["plan"], "created_at": _iso(me["created_at"])},
        "settings": settings if isinstance(settings, dict) else (__import__("json").loads(settings) if settings else {}),
        "memory": _rows(await p.fetch("select fact, scope, created_at from public.memory_facts where user_id=$1 order by created_at", user.id), "fact", "scope", "created_at"),
        "daily_usage": _rows(await p.fetch("select day, turns from public.usage_daily where user_id=$1 order by day desc limit 90", user.id), "day", "turns"),
        "computer_actions": _rows(await p.fetch("select agent, skill, status, at from public.automation_log where user_id=$1 order by at desc limit 500", user.id), "agent", "skill", "status", "at"),
        "api_keys": _rows(await p.fetch("select capability, provider, last4, created_at from public.api_keys where user_id=$1", user.id), "capability", "provider", "last4", "created_at"),
        "note": "Saved API keys are encrypted on our server and are not included here (only the last 4 characters are shown).",
    }


class DeleteIn(BaseModel):
    confirm: str


@router.post("/delete")
async def delete_account(body: DeleteIn, request: Request, user: CurrentUser = Depends(current_user)):
    """Deletes the sign-in account and, through cascades, your settings, memory, usage, keys and action log."""
    if body.confirm != "DELETE":
        raise HTTPException(400, 'Type DELETE to confirm')
    if user.role == "owner":
        raise HTTPException(403, "The owner account can't be deleted from the app")
    try:
        await db.pool().execute("delete from auth.users where id=$1", user.id)
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(409, "This account appears in the admin history. Please ask the owner to remove it.")
    hub = request.app.state.hub
    hub.histories.pop(user.id, None)
    for c in hub.of(user.id):
        try:
            await c.ws.close(4401)
        except Exception:                                                    # noqa: BLE001 - already closed
            pass
    return {"deleted": True}
