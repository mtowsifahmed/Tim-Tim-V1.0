import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .agents import build_graph
from .hub import Hub
from .providers.rotation import Rotation
from .routes import admin, automation, keys, me, memory, pair, search, settings, world
from .ws import handle_session
from . import speed  # noqa: F401  (faster replies: provider order + short caches)
from . import guard  # noqa: F401  (turn-flood protection)
from .routes import account as account_routes


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=60)) as http:
        app.state.rotation = Rotation(http)
        app.state.hub = Hub()
        app.state.graph = build_graph()
        yield
    await db.close_pool()


app = FastAPI(title="Tim-Tim backend", lifespan=lifespan)
# Auth is a Bearer header (no cookies), so cross-origin calls from the desktop webview are safe to allow.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["authorization", "content-type"])
app.include_router(me.router)
app.include_router(keys.router)
app.include_router(search.router)
app.include_router(admin.router)
app.include_router(world.router)
app.include_router(account_routes.router)
app.include_router(settings.router)
app.include_router(memory.router)
app.include_router(pair.router)
app.include_router(automation.router)


@app.get("/health")
async def health():
    return {"ok": True}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await handle_session(ws)
