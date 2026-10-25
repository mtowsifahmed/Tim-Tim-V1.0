"""Tracks every signed-in device (desktop/mobile) per account so replies fan out and mobile can drive the desktop."""
from __future__ import annotations

import asyncio
import itertools
import secrets
import time
from dataclasses import dataclass, field

from fastapi import WebSocket

_ids = itertools.count(1)


@dataclass
class Conn:
    ws: WebSocket
    user_id: str
    device: str                    # 'desktop' | 'mobile'
    name: str = ""
    id: int = field(default_factory=lambda: next(_ids))
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    task: asyncio.Task | None = None
    pcm: bytearray | None = None   # utterance being recorded (None = not recording)

    async def send(self, msg: dict) -> bool:
        try:
            async with self.lock:
                await self.ws.send_json(msg)
            return True
        except Exception:
            return False

    async def send_bytes(self, data: bytes) -> bool:
        try:
            async with self.lock:
                await self.ws.send_bytes(data)
            return True
        except Exception:
            return False

    async def send_audio(self, meta: dict, data: bytes) -> bool:
        """JSON header immediately followed by the bytes, atomically (no interleaving)."""
        try:
            async with self.lock:
                await self.ws.send_json(meta)
                await self.ws.send_bytes(data)
            return True
        except Exception:
            return False


class Hub:
    def __init__(self):
        self.conns: dict[str, list[Conn]] = {}
        self.pending: dict[str, tuple[str, asyncio.Future]] = {}      # action_id -> (user_id, future)
        self.histories: dict[str, list[dict]] = {}
        self.pair_codes: dict[str, tuple[str, float]] = {}            # code -> (user_id, expires)

    def add(self, c: Conn) -> None:
        self.conns.setdefault(c.user_id, []).append(c)

    def remove(self, c: Conn) -> None:
        lst = self.conns.get(c.user_id, [])
        if c in lst:
            lst.remove(c)
        if not lst:
            self.conns.pop(c.user_id, None)

    def of(self, user_id: str) -> list[Conn]:
        return list(self.conns.get(user_id, []))

    def desktop(self, user_id: str) -> Conn | None:
        return next((c for c in self.of(user_id) if c.device == "desktop"), None)

    def presence(self, user_id: str) -> dict:
        d = self.of(user_id)
        return {"type": "presence", "desktop_online": any(c.device == "desktop" for c in d),
                "mobile_online": any(c.device == "mobile" for c in d)}

    async def broadcast(self, user_id: str, msg: dict) -> None:
        for c in self.of(user_id):
            await c.send(msg)

    def history(self, user_id: str) -> list[dict]:
        return self.histories.setdefault(user_id, [])

    # ---- pairing (in-memory, 5 minute codes; fine for a single backend instance) ----
    def new_pair_code(self, user_id: str) -> str:
        now = time.time()
        self.pair_codes = {k: v for k, v in self.pair_codes.items() if v[1] > now}
        code = "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(8))
        self.pair_codes[code] = (user_id, now + 300)
        return code

    def claim_pair_code(self, code: str, user_id: str) -> bool:
        hit = self.pair_codes.get(code.strip().upper())
        if not hit or hit[1] < time.time() or hit[0] != user_id:
            return False
        del self.pair_codes[code.strip().upper()]
        return True
