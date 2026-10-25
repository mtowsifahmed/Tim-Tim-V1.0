"""One conversation turn: charge the daily cap, run the agent graph, stream tokens to every device and
speak sentence-by-sentence on the device that asked."""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid

from . import db, memory_store, policy, websearch
from .auth import CurrentUser
from .chunker import SentenceChunker
from .config import settings
from .hub import Conn, Hub
from .providers import tts as tts_mod
from .providers.errors import NoProviderAvailable, ProviderError
from .providers.rotation import Rotation

TURN_TIMEOUT = 90           # seconds; a stalled provider must not leave the app spinning
ACTION_TIMEOUT = 60         # how long the desktop gets to approve an action before the turn moves on
TTS_GRACE = 20              # speech may lag the text, but it can never hold the reply open
DEFAULT_PERSONA = {"tone": 60, "humor": 40, "formal": 30, "voice": "expressive_female", "tz": "UTC", "uname": "", "lang": "en-US", "web": "auto"}
_REMEMBER = re.compile(r"^\s*(?:please\s+)?remember\s+(?:that\s+)?(.{3,300})$", re.I | re.S)


async def charge_turn(user: CurrentUser, plans: dict, extra_rotation: bool = False) -> bool:
    """One daily turn is charged if ANY capability this turn runs on the app's rotation. Staff are never charged."""
    cap = policy.daily_cap(user.role, settings.free_daily_cap, settings.pro_rotation_daily_cap)
    if cap is None or not (extra_rotation or any(p and p[0].source == "rotation" for p in plans.values())):
        return True
    return await db.pool().fetchval("select public.consume_turn($1,$2)", user.id, cap) != -1


class TurnIO:
    def __init__(self, hub: Hub, origin: Conn, user: CurrentUser, rot: Rotation, plans: dict, persona: dict, speak: bool):
        self.hub, self.origin, self.user, self.rot, self.plans, self.persona, self.speak = hub, origin, user, rot, plans, persona, speak
        self.chunker, self.tts_q, self.sender, self.seq, self.tts_warned = SentenceChunker(), asyncio.Queue(), None, 0, False
        self.reply_so_far: list[str] = []
        self.started_at, self._first_token = time.monotonic(), False
        self._search_key: str | None = None          # resolved once per turn, on the first search
        if speak:
            self.sender = asyncio.create_task(self._send_audio())

    # ---- events ----
    async def emit(self, msg: dict) -> None:
        await self.hub.broadcast(self.user.id, msg)

    async def announce(self, cap: str) -> None:
        p = self.plans.get(cap)
        if p:
            await self.emit({"type": "provider", "capability": cap, "name": p[0].name, "source": p[0].source})

    # ---- LLM ----
    async def _provider(self, r) -> None:
        await self.emit({"type": "provider", "capability": "llm", "name": r.name, "source": r.source})

    def llm_stream(self, messages):
        return self.rot.stream_llm(self.plans["llm"], messages, self._provider)

    async def llm_collect(self, messages) -> str:
        return "".join([t async for t in self.rot.stream_llm(self.plans["llm"], messages, _noop)])

    async def search_key(self) -> str:
        """This account's Tavily key ("" when it has none). The owner's .env key is never lent to another account."""
        if self._search_key is None:
            self._search_key = await websearch.user_key(self.user.id, self.user.role)
        return self._search_key

    async def memory_search(self, query: str, scopes: list[str]) -> list[str]:
        try:
            return await memory_store.search(self.rot, self.user.id, query, scopes)
        except Exception:
            return []

    # ---- tokens -> text + speech ----
    async def on_token(self, tok: str) -> None:
        if not self._first_token:
            self._first_token = True
            logging.getLogger("timtim.turn").info("first token in %d ms", int((time.monotonic() - self.started_at) * 1000))
        self.reply_so_far.append(tok)
        await self.emit({"type": "token", "text": tok})
        if self.speak:
            for s in self.chunker.feed(tok):
                self.tts_q.put_nowait(asyncio.create_task(self._synth(s)))

    async def _synth(self, sentence: str):
        voice_key = self.persona.get("voice", "expressive_female")
        try:
            r, (audio, mime) = await self.rot.run(self.plans["tts"], lambda r: tts_mod.synth(self.rot.http, r.spec, r.api_key, sentence, r.spec.voice_for(voice_key)))
            return sentence, audio, mime, r.name
        except (ProviderError, NoProviderAvailable):
            if not self.tts_warned:
                self.tts_warned = True
                await self.origin.send({"type": "tts_error", "message": "Voice is unavailable right now; showing text only."})
            return None

    async def _send_audio(self) -> None:
        while True:
            fut = await self.tts_q.get()
            if fut is None:
                return
            res = await fut
            if res:
                sentence, audio, mime, prov = res
                self.seq += 1
                await self.origin.send_audio({"type": "audio", "seq": self.seq, "mime": mime, "text": sentence, "provider": prov}, audio)

    async def finish(self) -> None:
        if self.speak:
            for s in self.chunker.flush():
                self.tts_q.put_nowait(asyncio.create_task(self._synth(s)))
            self.tts_q.put_nowait(None)
            await self.sender

    async def abort(self) -> None:
        if self.sender:
            self.sender.cancel()
        while not self.tts_q.empty():
            f = self.tts_q.get_nowait()
            if f:
                f.cancel()

    # ---- desktop automation ----
    async def request_action(self, skill: str, args: dict, agent: str = "chat") -> dict:
        desk = self.hub.desktop(self.user.id)
        if not desk and skill in ("set_reminder", "open_url", "search_web", "whatsapp_open", "whatsapp_message") and self.origin.device in ("mobile", "desktop"):
            desk = self.origin                                      # these run inside the app itself, so the device you are talking on can do them
        if not desk:
            return {"ok": False, "error": "No desktop app is connected, so I can't do that on the computer."}
        aid = uuid.uuid4().hex[:12]
        fut = asyncio.get_running_loop().create_future()
        self.hub.pending[aid] = (self.user.id, fut)
        await _log_action(self.user.id, agent, skill, args, "proposed")
        await desk.send({"type": "action_request", "id": aid, "skill": skill, "args": args, "agent": agent})
        try:
            res = await asyncio.wait_for(fut, ACTION_TIMEOUT)
        except asyncio.TimeoutError:
            res = {"ok": False, "error": "timed out waiting for confirmation"}
        finally:
            self.hub.pending.pop(aid, None)
        await _log_action(self.user.id, agent, skill, args, "done" if res.get("ok") else "denied" if res.get("denied") else "failed")
        return res


async def _noop(_r) -> None:
    return None


async def _log_action(user_id: str, agent: str, skill: str, args: dict, status: str) -> None:
    import json
    safe = {k: (v if k != "content" else f"<{len(v)} chars>") for k, v in args.items()}
    try:
        await db.pool().execute("insert into public.automation_log(user_id,agent,skill,args,status) values($1,$2,$3,$4::jsonb,$5)",
                                user_id, agent, skill, json.dumps(safe), status)
    except Exception:
        pass                                    # logging must never break a turn


async def execute_turn_timed(io: TurnIO, graph, text: str) -> None:
    """A provider that stalls must never leave the app 'thinking' forever: give the whole turn a hard ceiling."""
    try:
        await asyncio.wait_for(execute_turn(io, graph, text), timeout=TURN_TIMEOUT)
    except asyncio.TimeoutError:
        await io.abort()
        raise TurnTimeout() from None


class TurnTimeout(Exception):
    """The turn exceeded TURN_TIMEOUT seconds."""


async def execute_turn(io: TurnIO, graph, text: str) -> None:
    history = io.hub.history(io.user.id)
    notes = []
    m = _REMEMBER.match(text)
    if m:
        try:
            saved = await memory_store.add(io.rot, io.user.id, m.group(1), "global")
            notes.append(f"You just saved this to the user's memory: {m.group(1).strip()[:200]}" if saved else "You could not save that to memory (limit reached).")
        except Exception:
            notes.append("You could not save that to memory right now.")
    state = {"text": text, "history": list(history), "persona": io.persona, "notes": notes}
    try:
        await graph.ainvoke(state, config={"configurable": {"io": io}})
    except asyncio.CancelledError:
        await io.abort()
        raise
    finally:
        reply = "".join(io.reply_so_far).strip()
        if reply:
            history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
            del history[:-40]
    try:
        await asyncio.wait_for(io.finish(), TTS_GRACE)      # a slow/blocked voice provider must not delay the text reply
    except asyncio.TimeoutError:
        await io.abort()
