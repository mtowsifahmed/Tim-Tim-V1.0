"""Abuse protection for a public release: a person (or script) can't start turns faster than TURN_MIN_GAP seconds apart.
Each turn can cost free-tier quota, so a flood would hurt every other user. Interrupts are never blocked."""
from __future__ import annotations

import asyncio
import os
import time

from . import ws as ws_mod

MIN_GAP = float(os.getenv("TURN_MIN_GAP", "1.0"))
_last: dict[str, float] = {}
_orig = {}


def allowed(user_id: str, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    if now - _last.get(user_id, 0.0) < MIN_GAP:
        return False
    _last[user_id] = now
    if len(_last) > 5000:                                                    # keep memory bounded
        for k in [k for k, v in _last.items() if now - v > 60]:
            _last.pop(k, None)
    return True


def install() -> None:
    if _orig:
        return
    _orig["spawn"] = ws_mod._spawn

    def spawn(websocket, conn, coro_fn, *args):
        if not allowed(conn.user_id):
            asyncio.create_task(ws_mod._error(conn, "slow_down", "One moment: you're sending messages very quickly."))
            return
        return _orig["spawn"](websocket, conn, coro_fn, *args)
    ws_mod._spawn = spawn


install()
