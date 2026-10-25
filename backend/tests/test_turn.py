import asyncio
import json

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from app import agents, skills, ws as ws_mod
from app.auth import CurrentUser
from app.chunker import SentenceChunker, clean_for_speech
from app.hub import Hub
from app.providers.errors import NoProviderAvailable


# ---------- pure pieces ----------
def test_clean_for_speech_strips_markdown_and_code():
    assert clean_for_speech("**Hi** `x` [site](http://a.b) ```print(1)```") == "Hi x site (code omitted)"


def test_chunker_yields_early_first_sentence_and_flushes_tail():
    c, out = SentenceChunker(), []
    for tok in ["Sure, I can do that for you. ", "Here is the second part of my answer, ", "which is a bit longer. ", "tail"]:
        out += c.feed(tok)
    out += c.flush()
    assert out[0] == "Sure, I can do that for you." and out[-1] == "tail" and len(out) == 3


def test_skill_validation_blocks_bad_input():
    assert skills.validate("open_app", {"app": " notepad "}, "chat") == {"app": "notepad"}
    for name, args, agent in [("rm_rf", {}, "chat"), ("run_shell", {"command": "ls"}, "chat"),     # agent may not use it
                              ("open_url", {"url": "file:///etc/passwd"}, "chat"), ("open_url", {"url": "javascript:alert(1)"}, "chat"),
                              ("open_app", {"app": "calc & del /q *"}, "chat"), ("open_app", {}, "chat"), ("open_app", {"app": "x" * 500}, "chat")]:
        with pytest.raises(ValueError):
            skills.validate(name, args, agent)
    assert skills.validate("run_shell", {"command": "dir"}, "coding") == {"command": "dir"}


def test_classification_parsing_and_fallbacks():
    a, s = agents.parse_classification('Sure: {"agent":"chat","skill":{"name":"open_app","args":{"app":"notepad"}}}', "open notepad")
    assert a == "chat" and s == {"name": "open_app", "args": {"app": "notepad"}}
    a, s = agents.parse_classification('{"agent":"coding","skill":{"name":"run_shell","args":{"command":"dir"}}}', "x")
    assert a == "coding" and s["name"] == "run_shell"
    a, s = agents.parse_classification('{"agent":"chat","skill":{"name":"run_shell","args":{"command":"dir"}}}', "x")
    assert s is None                                                       # chat agent can't run shell
    assert agents.parse_classification("not json", "fix this python bug") == ("coding", None)
    assert agents.parse_classification('{"agent":"bogus"}', "write me a poem")[0] == "creative"


def test_persona_style_and_memory_scopes():
    assert "serious, no jokes" in agents.persona_style({"tone": 10, "humor": 0, "formal": 90})
    assert "playful" in agents.persona_style({"humor": 90})
    assert agents.AGENTS["coding"]["scopes"] == ["global", "coding"]


def test_pair_codes_are_single_use_and_account_bound():
    h = Hub(); code = h.new_pair_code("u1")
    assert not h.claim_pair_code(code, "u2") and h.claim_pair_code(code, "u1") and not h.claim_pair_code(code, "u1")


# ---------- end-to-end session with a fake provider layer ----------
class FakeResolved:
    def __init__(self, name="fake", source="rotation"):
        self.name, self.source = name, source
        self.spec = type("S", (), {"voice_for": lambda s, k: "v"})()
        self.api_key = "k"


class FakeRot:
    http = None

    def __init__(self, classify_json, reply, fail_llm=False):
        self.classify_json, self.reply, self.fail_llm, self.tts_calls = classify_json, reply, fail_llm, []

    async def plan(self, cap, uid, role):
        return [FakeResolved()]

    async def explain(self, cap):
        return self.info if hasattr(self, "info") else {"configured": ["gemini"], "cooling": {}, "none_configured": False}

    async def run(self, plan, fn):
        if plan is None:
            raise NoProviderAvailable()
        return plan[0], (b"AUDIO", "audio/mpeg")

    async def stream_llm(self, plan, messages, on_provider):
        if self.fail_llm:
            raise NoProviderAvailable("none")
        await on_provider(plan[0])
        text = self.classify_json if messages[0]["content"].startswith("You are the orchestrator") else self.reply
        for w in text.split(" "):
            yield w + " "


def make_client(monkeypatch, rot, user_role="free"):
    app = FastAPI(); app.state.hub, app.state.rotation, app.state.graph = Hub(), rot, agents.build_graph()
    user = CurrentUser("u1", "a@b.com", user_role, "free")

    async def fake_verify(t): return "u1"
    async def fake_load(uid): return user
    async def fake_status(u, r): return {"mode": "free", "remaining_today": 5}
    async def fake_persona(uid): return {"tone": 60, "humor": 40, "formal": 30, "voice": "calm_male"}
    async def fake_charge(u, p, extra=False): return True
    for n, f in [("verify_token", fake_verify), ("load_user", fake_load), ("build_status", fake_status), ("load_persona", fake_persona), ("charge_turn", fake_charge)]:
        monkeypatch.setattr(ws_mod, n, f)

    @app.websocket("/ws")
    async def ep(w: WebSocket):
        await ws_mod.handle_session(w)
    c = TestClient(app)
    c.__enter__()                       # one shared event loop, so two devices can talk through the same Hub
    return c


def collect(wsc, until="done", limit=80):
    msgs = []
    for _ in range(limit):
        m = wsc.receive()
        if m.get("bytes") is not None:
            msgs.append({"type": "BYTES", "n": len(m["bytes"])})
            continue
        d = json.loads(m["text"]); msgs.append(d)
        if d["type"] == until or d["type"] == "error":
            break
    return msgs


def test_typed_turn_streams_tokens_and_agent_status(monkeypatch):
    rot = FakeRot('{"agent":"research","skill":null}', "Paris is the capital of France.")
    with make_client(monkeypatch, rot).websocket_connect("/ws") as w:
        w.send_json({"type": "auth", "token": "t", "device": "desktop"}); assert json.loads(w.receive()["text"])["type"] == "ready"
        w.send_json({"type": "text", "text": "capital of France?"})
        types = [m["type"] for m in collect(w)]
        assert "agent" in types and "token" in types and types[-1] in ("done", "status") and "audio" not in types


def test_spoken_turn_sends_audio_after_each_sentence(monkeypatch):
    rot = FakeRot('{"agent":"chat","skill":null}', "Hello there my friend. How are you doing today, I hope well.")
    with make_client(monkeypatch, rot).websocket_connect("/ws") as w:
        w.send_json({"type": "auth", "token": "t"}); w.receive()
        w.send_json({"type": "text", "text": "hi", "speak": True})
        msgs = collect(w)
        assert [m["type"] for m in msgs].count("audio") >= 1 and any(m["type"] == "BYTES" for m in msgs)
        seqs = [m["seq"] for m in msgs if m["type"] == "audio"]; assert seqs == sorted(seqs)


def test_action_roundtrip_with_desktop_confirmation(monkeypatch):
    rot = FakeRot('{"agent":"chat","skill":{"name":"open_app","args":{"app":"notepad"}}}', "Done, Notepad is open.")
    with make_client(monkeypatch, rot).websocket_connect("/ws") as w:
        w.send_json({"type": "auth", "token": "t", "device": "desktop"}); w.receive()
        w.send_json({"type": "text", "text": "open notepad"})
        req = None
        for _ in range(40):
            m = json.loads(w.receive()["text"])
            if m["type"] == "action_request":
                req = m; break
        assert req and req["skill"] == "open_app" and req["args"] == {"app": "notepad"}
        w.send_json({"type": "action_result", "id": req["id"], "ok": True, "output": "launched"})
        assert "token" in [m["type"] for m in collect(w)]


def test_denied_action_is_reported_not_executed(monkeypatch):
    rot = FakeRot('{"agent":"chat","skill":{"name":"open_app","args":{"app":"notepad"}}}', "Okay, I will not open it.")
    seen = {}
    orig = FakeRot.stream_llm

    async def spy(self, plan, messages, on_provider):
        if not messages[0]["content"].startswith("You are the orchestrator"):
            seen["sys"] = messages[0]["content"]
        async for t in orig(self, plan, messages, on_provider):
            yield t
    monkeypatch.setattr(FakeRot, "stream_llm", spy)
    with make_client(monkeypatch, rot).websocket_connect("/ws") as w:
        w.send_json({"type": "auth", "token": "t", "device": "desktop"}); w.receive()
        w.send_json({"type": "text", "text": "open notepad"})
        for _ in range(40):
            m = json.loads(w.receive()["text"])
            if m["type"] == "action_request":
                w.send_json({"type": "action_result", "id": m["id"], "denied": True}); break
        collect(w)
    assert "declined" in seen["sys"] and "NOT done" in seen["sys"]


def test_no_desktop_means_no_action(monkeypatch):
    rot = FakeRot('{"agent":"chat","skill":{"name":"open_app","args":{"app":"notepad"}}}', "I cannot reach your computer.")
    with make_client(monkeypatch, rot).websocket_connect("/ws") as w:
        w.send_json({"type": "auth", "token": "t", "device": "mobile"}); w.receive()          # phone only, no desktop online
        w.send_json({"type": "text", "text": "open notepad"})
        types = [m["type"] for m in collect(w)]
        assert "action_request" not in types and "token" in types


def _no_provider_error(monkeypatch, info=None, role="free"):
    rot = FakeRot("", "", fail_llm=True)
    if info is not None:
        rot.info = info
    with make_client(monkeypatch, rot, role).websocket_connect("/ws") as w:
        w.send_json({"type": "auth", "token": "t"}); w.receive()
        w.send_json({"type": "text", "text": "hello"})
        return [m for m in collect(w) if m["type"] == "error"][0]


def test_no_key_configured_says_so_instead_of_claiming_a_limit(monkeypatch):
    err = _no_provider_error(monkeypatch, {"configured": [], "cooling": {}, "none_configured": True})
    assert err["code"] == "no_provider" and "backend/.env" in err["message"] and "limit" not in err["message"]


def test_all_cooling_down_reports_a_wait_time(monkeypatch):
    from datetime import datetime, timedelta, timezone
    soon = datetime.now(timezone.utc) + timedelta(minutes=7)
    err = _no_provider_error(monkeypatch, {"configured": ["gemini", "groq"], "cooling": {"gemini": soon, "groq": soon}, "none_configured": False})
    assert "limits" in err["message"] and "min" in err["message"]


def test_provider_errors_are_reported_as_errors_not_limits(monkeypatch):
    err = _no_provider_error(monkeypatch)
    assert "returned errors" in err["message"] and "limit" not in err["message"]


def test_mobile_remote_command_runs_on_desktop_account_and_fans_out(monkeypatch):
    rot = FakeRot('{"agent":"chat","skill":null}', "Hi from the desktop brain.")
    client = make_client(monkeypatch, rot)
    with client.websocket_connect("/ws") as desk, client.websocket_connect("/ws") as phone:
        desk.send_json({"type": "auth", "token": "t", "device": "desktop"}); desk.receive()
        phone.send_json({"type": "auth", "token": "t", "device": "mobile"}); ready = json.loads(phone.receive()["text"])
        assert ready["desktop_online"] is True
        phone.send_json({"type": "remote_command", "text": "hello"})
        got_desktop = [m["type"] for m in collect(desk)]
        assert "turn_start" in got_desktop and "token" in got_desktop           # desktop sees the phone's command and the reply


def test_barge_in_interrupt_cancels_the_running_turn(monkeypatch):
    class Slow(FakeRot):
        async def stream_llm(self, plan, messages, on_provider):
            if messages[0]["content"].startswith("You are the orchestrator"):
                yield '{"agent":"chat","skill":null}'; return
            await on_provider(plan[0])
            for _ in range(200):
                yield "word "; await asyncio.sleep(0.02)
    with make_client(monkeypatch, Slow("", "")).websocket_connect("/ws") as w:
        w.send_json({"type": "auth", "token": "t"}); w.receive()
        w.send_json({"type": "text", "text": "tell me a long story"})
        for _ in range(30):
            if json.loads(w.receive()["text"])["type"] == "token":
                break
        w.send_json({"type": "interrupt"})
        types = [m["type"] for m in collect(w, until="interrupted")]
        assert types[-1] == "interrupted"
