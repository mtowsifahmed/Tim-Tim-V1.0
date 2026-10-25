"""Mobile pairing: the desktop shows a short-lived code (and QR); the phone, signed into the SAME account, claims it."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth import CurrentUser, current_user

router = APIRouter(prefix="/pair")


class ClaimIn(BaseModel):
    code: str


@router.post("/create")
async def create(request: Request, user: CurrentUser = Depends(current_user)):
    hub = request.app.state.hub
    if not hub.desktop(user.id):
        raise HTTPException(409, "Open the desktop app first, then pair from its settings")
    return {"code": hub.new_pair_code(user.id), "expires_in": 300}


@router.post("/claim")
async def claim(body: ClaimIn, request: Request, user: CurrentUser = Depends(current_user)):
    hub = request.app.state.hub
    if not hub.claim_pair_code(body.code, user.id):
        raise HTTPException(400, "That code is wrong, expired, or belongs to a different account")
    d = hub.desktop(user.id)
    return {"paired": True, "desktop_name": d.name if d else "", "desktop_online": bool(d)}
