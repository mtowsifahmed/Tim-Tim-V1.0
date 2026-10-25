"""Speed-ups that change no behaviour, only how long you wait for the first word.

1. Provider ORDER: the fastest free providers go first (LLM: Groq, Cerebras before Gemini; STT: Groq Whisper first; TTS: Deepgram first).
   Override with LLM_PRIORITY / STT_PRIORITY / TTS_PRIORITY in .env (comma-separated provider names). A Pro user's own key is never reordered.
2. Short-lived caches for things asked on every message: the provider plan (about nine database round-trips before the AI even started),
   the user row and the personality settings.
3. Timing in the log ("first word after N ms") so you can see where time goes.
Loaded once from main.py; safe to import twice."""
from __future__ import annotations

import logging
import os
import time

from . import auth as auth_mod
from . import turn as turn_mod
from . import ws as ws_mod
from .providers.rotation import Rotation

log = logging.getLogger("timtim.speed")
PLAN_TTL, USER_TTL = 8.0, 5.0
DEFAULTS = {
    "llm": "groq,cerebras,gemini,sambanova,openrouter,mistral,nvidia,custom",
    "stt": "groq-whisper,deepgram,cloudflare-whisper,elevenlabs-scribe,gemini-stt,custom",
    "tts": "deepgram-aura,groq-tts,elevenlabs,cloudflare-voice,gemini-tts,custom,edge-tts",
}
_orig: dict = {}
_plans: dict = {}
_users: dict = {}
_personas: dict = {}


def priority(cap: str) -> list[str]:
    raw = os.getenv(f"{cap.upper()}_PRIORITY", "").strip() or DEFAULTS.get(cap, "")
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def prioritize(cap: str, plan: list) -> list:
    if not plan or any(getattr(r, "source", "") == "byok" for r in plan):
        return plan
    order = {n: i for i, n in enumerate(priority(cap))}
    return sorted(plan, key=lambda r: order.get(r.name.lower(), len(order)))        # stable: unknown names keep their relative order, at the end


async def _plan(self, capability, user_id, role):
    key, now = (capability, user_id, role), time.time()
    hit = _plans.get(key)
    if hit and now - hit[0] < PLAN_TTL:
        return list(hit[1])
    res = prioritize(capability, await _orig["plan"](self, capability, user_id, role))
    _plans[key] = (now, res)
    return list(res)


async def _mark(self, resolved, err):
    out = await _orig["mark"](self, resolved, err)
    _plans.clear()                                                                   # a provider just hit a limit: re-plan immediately
    return out


def _cached(store: dict, ttl: float, key_orig: str):
    async def wrapper(uid):
        hit, now = store.get(uid), time.time()
        if hit and now - hit[0] < ttl:
            return hit[1]
        val = await _orig[key_orig](uid)
        store[uid] = (now, val)
        return val
    return wrapper


def install() -> None:
    if _orig:
        return
    _orig.update(plan=Rotation.plan, mark=Rotation.mark_exhausted, load_user=auth_mod.load_user, load_persona=ws_mod.load_persona)
    Rotation.plan, Rotation.mark_exhausted = _plan, _mark
    auth_mod.load_user = ws_mod.load_user = _cached(_users, USER_TTL, "load_user")
    ws_mod.load_persona = _cached(_personas, USER_TTL, "load_persona")

    init, tok = turn_mod.TurnIO.__init__, turn_mod.TurnIO.on_token

    def timed_init(self, *a, **k):
        init(self, *a, **k)
        self._t0, self._first = time.time(), False

    async def timed_tok(self, t):
        if not getattr(self, "_first", True):
            self._first = True
            log.info("first word after %d ms", (time.time() - self._t0) * 1000)
        return await tok(self, t)
    turn_mod.TurnIO.__init__, turn_mod.TurnIO.on_token = timed_init, timed_tok


install()
