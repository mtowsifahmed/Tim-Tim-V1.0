from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .. import memory_store
from ..auth import CurrentUser, current_user

router = APIRouter(prefix="/memory")


class FactIn(BaseModel):
    fact: str = Field(min_length=1, max_length=500)
    scope: str = "global"


@router.get("")
async def list_memory(q: str = Query("", max_length=100), user: CurrentUser = Depends(current_user)):
    return {"facts": await memory_store.list_facts(user.id, q)}


@router.post("")
async def add_memory(body: FactIn, request: Request, user: CurrentUser = Depends(current_user)):
    row = await memory_store.add(request.app.state.rotation, user.id, body.fact, body.scope)
    if not row:
        raise HTTPException(400, "Could not save (empty, bad scope, or the 500-fact limit is reached)")
    return row


@router.patch("/{fact_id}")
async def edit_memory(fact_id: str, body: FactIn, request: Request, user: CurrentUser = Depends(current_user)):
    if not await memory_store.update(request.app.state.rotation, user.id, fact_id, body.fact):
        raise HTTPException(404, "Not found")
    return {"ok": True}


@router.delete("/{fact_id}")
async def delete_memory(fact_id: str, user: CurrentUser = Depends(current_user)):
    if not await memory_store.delete(user.id, fact_id):
        raise HTTPException(404, "Not found")
    return {"ok": True}
