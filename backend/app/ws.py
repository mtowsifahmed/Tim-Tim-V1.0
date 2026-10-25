"""WebSocket session (desktop and mobile). Protocol, JSON text frames unless noted:
 client -> {"type":"auth","token":"…","device":"desktop|mobile","name":"…"}      first message
 client -> {"type":"text","text":"…","speak":false}                                typed turn
 client -> {"type":"audio_start"} · binary PCM16 16 kHz mono frames · {"type":"audio_end","wake":"hey tim"?} · {"type":"audio_cancel"}
 client -> {"type":"interrupt"}                                                    barge-in / stop
 client -> {"type":"remote_command","text":"…","speak":true}                       mobile -> desktop agent
 client -> {"type":"action_result","id":"…","ok":true,"output":"…"} / {"denied":true} / {"error":"…"}
 server -> ready | status | presence | provider | transcript | agent | token | audio(+binary) | action_request
           | done | interrupted | error{code,message} | stt_empty | wake_ignored | tts_error | pong
"""
from __future__ import annotations

import asyncio
import json

from fastapi import HTTPException, WebSocket

import time

from . import db
from .audio import MAX_UTTERANCE_BYTES, looks_invented, is_silent, pcm_to_wav, trim_silence
from .auth import CurrentUser, load_user, verify_token
from .hub import Conn
from .providers import stt as stt_mod
from .providers.errors import NoProviderAvailable, ProviderError
from .status import build_status
from .turn import DEFAULT_PERSONA, TurnIO, TurnTimeout, charge_turn, execute_turn_timed

CAP_MSG = ("You've used all of today's free voice turns. They reset at midnight UTC, "
           "or ask the owner about upgrading to Pro.")


PERSONA_TTL = 30.0
_persona_cache: dict[str, tuple[float, dict]] = {}


def drop_persona_cache(user_id: str) -> None:
    """Called when someone saves their settings, so a change applies on the very next reply."""
    _persona_cache.pop(user_id, None)


async def load_persona(user_id: str) -> dict:
    hit = _persona_cache.get(user_id)
    if hit and hit[0] > time.monotonic():
        return dict(hit[1])
    try:
        raw = await db.pool().fetchval("select persona from public.settings where user_id=$1", user_id)
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        data = {}
    persona = {**DEFAULT_PERSONA, **{k: data[k] for k in DEFAULT_PERSONA if k in data}}
    _persona_cache[user_id] = (time.monotonic() + PERSONA_TTL, persona)
    return dict(persona)


async def _no_provider_message(rot, cap: str, e: NoProviderAvailable, role: str) -> str:
    """Say what is actually wrong instead of always claiming a limit was reached."""
    try:
        info = await rot.explain(cap)
    except Exception:
        info = {"configured": [], "cooling": {}, "none_configured": False}
    label = {"llm": "AI", "stt": "speech-recognition", "tts": "voice"}[cap]
    if info["none_configured"]:
        key = {"llm": "GEMINI_API_KEY (or GROQ_API_KEY)",
               "stt": "GEMINI_API_KEY (or GROQ_API_KEY)",
               "tts": "GEMINI_API_KEY (or ELEVENLABS_API_KEY)"}[cap]
        return f"No {label} key is set up on the server yet. Add {key} to backend/.env and restart the backend."
    cooling = info["cooling"]
    if cooling and set(info["configured"]) <= set(cooling):
        from datetime import datetime, timezone
        mins = max(1, int((min(cooling.values()) - datetime.now(timezone.utc)).total_seconds() // 60) + 1)
        return f"All free {label} services have reached their limits for now. The soonest one is available again in about {mins} min."
    msg = f"The {label} services returned errors, so I couldn't answer. The backend log shows the exact reason."
    if role in ("owner", "moderator") and e.reasons:
        msg += " Details: " + " | ".join(r[:140] for r in e.reasons[:3])
    return msg


async def _error(conn: Conn, code: str, message: str) -> None:
    await conn.send({"type": "error", "code": code, "message": message})


async def run_turn(ws: WebSocket, conn: Conn, text: str, speak: bool, stt_rotation: bool = False) -> None:
    hub, rot, graph = ws.app.state.hub, ws.app.state.rotation, ws.app.state.graph
    user = await load_user(conn.user_id)                              # role may have changed (e.g. Pro just granted)
    persona = await load_persona(user.id)
    plans = {"llm": await rot.plan("llm", user.id, user.role)}
    if speak:
        plans["tts"] = await rot.plan("tts", user.id, user.role)
    if not await charge_turn(user, plans, stt_rotation):
        await _error(conn, "daily_cap_reached", CAP_MSG)
        await hub.broadcast(user.id, {"type": "status", **await build_status(user, rot)})
        return
    io = TurnIO(hub, conn, user, rot, plans, persona, speak)
    await hub.broadcast(user.id, {"type": "turn_start", "origin": conn.device, "text": text})
    for cap in plans:
        await io.announce(cap)
    try:
        await execute_turn_timed(io, graph, text)
        await hub.broadcast(user.id, {"type": "done"})
    except TurnTimeout:
        await _error(conn, "timeout", "That reply took longer than two minutes, so I stopped it. Please try again — "
                                       "if it keeps happening the AI provider is being slow right now.")
    except NoProviderAvailable as e:
        await io.abort(); await _error(conn, "no_provider", await _no_provider_message(rot, "llm", e, user.role))
    except ProviderError as e:
        await io.abort(); await _error(conn, "provider_error", str(e))
    except asyncio.CancelledError:
        await io.abort(); await conn.send({"type": "interrupted"}); raise
    finally:
        try:
            await hub.broadcast(user.id, {"type": "status", **await build_status(user, rot)})
        except Exception:
            pass


async def run_voice_turn(ws: WebSocket, conn: Conn, pcm: bytes, wake: str | None) -> None:
    hub, rot = ws.app.state.hub, ws.app.state.rotation
    # An empty or near-empty clip must never be sent to speech-to-text: that is exactly what makes a model
    # answer "thank you" to silence. Trimming also removes the long quiet head/tail that provokes it.
    pcm = trim_silence(bytes(pcm))
    if is_silent(pcm):
        await conn.send({"type": "stt_empty"}); return
    user = await load_user(conn.user_id)
    wav = pcm_to_wav(bytes(pcm))
    try:
        plan = await rot.plan("stt", user.id, user.role)
        r, text = await rot.run(plan, lambda r: stt_mod.transcribe(rot.http, r.spec, r.api_key, wav))
    except NoProviderAvailable as e:
        await _error(conn, "no_provider", await _no_provider_message(rot, "stt", e, user.role) + " You can type instead."); return
    except ProviderError as e:
        await _error(conn, "provider_error", str(e)); return
    await conn.send({"type": "provider", "capability": "stt", "name": r.name, "source": r.source})
    text = (text or "").strip()
    if not text or looks_invented(text, pcm):
        await conn.send({"type": "stt_empty"}); return
    if wake:
        w = wake.lower().strip()
        if w not in text.lower():
            await conn.send({"type": "wake_ignored"}); return
        i = text.lower().index(w); text = (text[i + len(w):].lstrip(" ,.!?:;-") or text).strip()
    await hub.broadcast(user.id, {"type": "transcript", "text": text, "final": True, "origin": conn.device})
    await run_turn(ws, conn, text, True, stt_rotation=(r.source == "rotation"))


def _spawn(ws: WebSocket, conn: Conn, coro_fn, *a) -> None:
    async def runner():
        try:
            await coro_fn(ws, conn, *a)
        except asyncio.CancelledError:
            pass
        except Exception:
            await _error(conn, "internal", "Something went wrong on my side. Please try again.")
    if conn.task and not conn.task.done():
        conn.task.cancel()                                           # a new turn interrupts the old one
    conn.task = asyncio.create_task(runner())


async def handle_session(ws: WebSocket) -> None:
    await ws.accept()
    hub, rot = ws.app.state.hub, ws.app.state.rotation
    try:
        first = await asyncio.wait_for(ws.receive_json(), timeout=15)
        if first.get("type") != "auth":
            await ws.close(4401); return
        user: CurrentUser = await load_user(await verify_token(first.get("token", "")))
    except HTTPException as e:
        await ws.close(1013 if e.status_code >= 500 else 4401); return          # 1013 = auth service busy: client retries, stays signed in
    except (asyncio.TimeoutError, ValueError, KeyError):
        await ws.close(4401); return
    device = first.get("device") if first.get("device") in ("desktop", "mobile") else "desktop"
    conn = Conn(ws, user.id, device, str(first.get("name", ""))[:40])
    hub.add(conn)
    await conn.send({**hub.presence(user.id), "type": "ready", "device": device, "status": await build_status(user, rot)})
    await hub.broadcast(user.id, hub.presence(user.id))
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                if conn.pcm is not None and len(conn.pcm) + len(msg["bytes"]) <= MAX_UTTERANCE_BYTES:
                    conn.pcm += msg["bytes"]
                continue
            try:
                data = json.loads(msg.get("text") or "{}")
            except ValueError:
                continue
            t = data.get("type")
            if t == "audio_start":
                if conn.task and not conn.task.done():
                    conn.task.cancel(); await conn.send({"type": "interrupted"})
                conn.pcm = bytearray()
            elif t == "audio_end" and conn.pcm is not None:
                pcm, conn.pcm = bytes(conn.pcm), None
                wake = str(data.get("wake") or "")[:40] or None
                _spawn(ws, conn, run_voice_turn, pcm, wake)
            elif t == "audio_cancel":
                conn.pcm = None                                  # a tapped Space key throws the clip away, no turn
            elif t in ("text", "remote_command"):
                text = str(data.get("text", "")).strip()[:4000]
                if text:
                    _spawn(ws, conn, run_turn, text, bool(data.get("speak")))
            elif t == "interrupt":
                if conn.task and not conn.task.done():
                    conn.task.cancel()
                await conn.send({"type": "interrupted"})
            elif t == "action_result":
                hit = hub.pending.get(str(data.get("id", "")))
                if hit and hit[0] == user.id and not hit[1].done():
                    hit[1].set_result({k: data.get(k) for k in ("ok", "denied", "output", "error") if k in data})
            elif t == "ping":
                await conn.send({"type": "pong"})
    finally:
        if conn.task and not conn.task.done():
            conn.task.cancel()
        hub.remove(conn)
        await hub.broadcast(user.id, hub.presence(user.id))
