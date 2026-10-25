from fastapi import APIRouter, Depends, Request

from ..auth import CurrentUser, current_user
from ..status import build_status

router = APIRouter()


@router.get("/me")
async def me(request: Request, user: CurrentUser = Depends(current_user)):
    return await build_status(user, request.app.state.rotation)


@router.get("/providers")
async def providers(request: Request, user: CurrentUser = Depends(current_user)):
    """Providers a Pro user can attach their own key to (the keyless fallback and the custom gateway are excluded)."""
    reg = request.app.state.rotation.registry
    return {cap: [s.name for s in reg[cap] if s.name != "custom" and not s.no_key] for cap in ("llm", "stt", "tts")}
