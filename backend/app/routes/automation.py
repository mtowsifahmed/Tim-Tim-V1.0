from fastapi import APIRouter, Depends

from .. import db
from ..auth import CurrentUser, current_user

router = APIRouter(prefix="/automation")


@router.get("")
async def recent(user: CurrentUser = Depends(current_user)):
    """The user's own action history (review what Tim-Tim proposed/did). File contents are never stored."""
    rows = await db.pool().fetch("select id, agent, skill, args, status, at from public.automation_log where user_id=$1 order by at desc limit 40", user.id)
    return {"actions": [{"id": r["id"], "agent": r["agent"], "skill": r["skill"], "args": r["args"] if isinstance(r["args"], str) else __import__("json").dumps(r["args"]),
                         "status": r["status"], "at": r["at"].isoformat()} for r in rows]}
