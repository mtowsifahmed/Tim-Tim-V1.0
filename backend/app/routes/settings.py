import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db
from ..auth import CurrentUser, current_user

router = APIRouter(prefix="/settings")


class SettingsIn(BaseModel):
    persona: dict


@router.get("")
async def get_settings(user: CurrentUser = Depends(current_user)):
    raw = await db.pool().fetchval("select persona from public.settings where user_id=$1", user.id)
    return {"persona": json.loads(raw) if isinstance(raw, str) else (raw or {})}


@router.put("")
async def put_settings(body: SettingsIn, user: CurrentUser = Depends(current_user)):
    blob = json.dumps(body.persona)
    if len(blob) > 8000:
        raise HTTPException(413, "Settings are too large")
    await db.pool().execute(
        "insert into public.settings(user_id, persona, updated_at) values($1,$2::jsonb,now()) "
        "on conflict (user_id) do update set persona=excluded.persona, updated_at=now()", user.id, blob)
    from ..ws import drop_persona_cache          # the next reply must use the new voice/settings, not a cached copy
    drop_persona_cache(user.id)
    return {"saved": True}
