"""Admin panel API. Role checks use the DB role of the caller (never client-sent) via policy.py."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .. import db, policy
from ..auth import CurrentUser, require_staff

router = APIRouter(prefix="/admin")


@router.get("/users")
async def search_users(email: str = Query("", max_length=200), actor: CurrentUser = Depends(require_staff)):
    rows = await db.pool().fetch(
        "select id, email, role, plan, granted_by, granted_at from public.users "
        "where email ilike $1 order by email limit 25", f"%{email.strip()}%")
    return [{**dict(r), "id": str(r["id"]), "granted_by": str(r["granted_by"]) if r["granted_by"] else None,
             "granted_at": r["granted_at"].isoformat() if r["granted_at"] else None} for r in rows]


class PlanIn(BaseModel):
    plan: str  # 'pro' | 'free'


@router.post("/users/{user_id}/plan")
async def set_plan(user_id: str, body: PlanIn, actor: CurrentUser = Depends(require_staff)):
    if body.plan not in ("pro", "free"):
        raise HTTPException(400, "plan must be 'pro' or 'free'")
    async with db.pool().acquire() as conn, conn.transaction():
        t = await conn.fetchrow("select id, role, plan from public.users where id=$1 for update", user_id)
        if not t:
            raise HTTPException(404, "User not found")
        if not policy.can_change_plan(actor.role, t["role"]):
            raise HTTPException(403, "You can't change this account's plan")
        await conn.execute(
            "update public.users set plan=$2, role=$2, granted_by=$3, granted_at=now() where id=$1",
            user_id, body.plan, actor.id)
        await conn.execute(
            "insert into public.admin_audit_log(actor_id,target_id,action,detail) values($1,$2,$3,$4::jsonb)",
            actor.id, user_id, "grant_pro" if body.plan == "pro" else "revoke_pro",
            f'{{"from":"{t["plan"]}","to":"{body.plan}"}}')
    return {"ok": True, "plan": body.plan}


class ModIn(BaseModel):
    enabled: bool


@router.post("/users/{user_id}/moderator")
async def set_moderator(user_id: str, body: ModIn, actor: CurrentUser = Depends(require_staff)):
    async with db.pool().acquire() as conn, conn.transaction():
        t = await conn.fetchrow("select id, role, plan from public.users where id=$1 for update", user_id)
        if not t:
            raise HTTPException(404, "User not found")
        if not policy.can_set_moderator(actor.role, t["role"], body.enabled):
            raise HTTPException(403, "Only the owner can do this, and not for this account")
        new_role = "moderator" if body.enabled else policy.role_after_moderator_removed(t["plan"])
        await conn.execute("update public.users set role=$2 where id=$1", user_id, new_role)
        await conn.execute(
            "insert into public.admin_audit_log(actor_id,target_id,action,detail) values($1,$2,$3,'{}'::jsonb)",
            actor.id, user_id, "add_moderator" if body.enabled else "remove_moderator")
    return {"ok": True, "role": new_role}


@router.get("/audit")
async def audit(actor: CurrentUser = Depends(require_staff)):
    rows = await db.pool().fetch(
        "select a.at, a.action, ac.email as actor, tg.email as target from public.admin_audit_log a "
        "join public.users ac on ac.id=a.actor_id join public.users tg on tg.id=a.target_id "
        "order by a.at desc limit 100")
    return [{"at": r["at"].isoformat(), "action": r["action"], "actor": r["actor"], "target": r["target"]}
            for r in rows]
