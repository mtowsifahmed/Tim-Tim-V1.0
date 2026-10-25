"""Regressions: a spoken reminder must actually be scheduled, a stalled turn must end, and a 429'd
voice provider must not be re-hit for every sentence of the same reply."""
import asyncio

import pytest

from app import agents, skills
from app.providers.errors import NoProviderAvailable, QuotaError
from app.providers.rotation import Resolved, Rotation
from app.turn import TURN_TIMEOUT, TurnTimeout, execute_turn_timed


def run(coro):
    return asyncio.run(coro)


# ---------- understanding a reminder ----------
@pytest.mark.parametrize("text,minutes,word", [
    ("1 min baar paani peene ka reminder set kardo", 1, "paani"),
    ("remind me in 10 minutes to stretch", 10, "stretch"),
    ("2 ghante baad call karna hai reminder", 120, "call"),
    ("set a reminder for 45 mins to check the oven", 45, "oven"),
    ("Remind me in 1 hour", 60, ""),
])
def test_reminder_time_and_message_are_understood(text, minutes, word):
    got = skills.guess_reminder(text)
    assert got and got["minutes"] == minutes, text
    if word:
        assert word in got["message"].lower(), got["message"]


def test_no_reminder_without_a_time_or_without_the_intent():
    assert skills.guess_reminder("remind me later about the meeting") is None
    assert skills.guess_reminder("1 min baar paani peena") is None
    assert skills.guess_reminder("what is a reminder in Outlook") is None       # no time stated


def test_absurd_times_are_clamped_to_the_skill_limit():
    assert skills.guess_reminder("remind me in 9999 mins to sleep")["minutes"] == 1440


def test_the_reminder_is_validated_for_the_planner_agent():
    args = skills.validate("set_reminder", skills.guess_reminder("remind me in 5 minutes to stretch"), "planner")
    assert args == {"minutes": 5, "message": "stretch"}


# ---------- the graph proposes it without asking the model ----------
class IO:
    class rot:
        http = None

    def __init__(self):
        self.actions, self.events, self.system = [], [], None

    async def emit(self, m): self.events.append(m)
    async def llm_collect(self, msgs): raise AssertionError("no router call should be needed for a reminder")
    async def memory_search(self, q, s): return []
    async def on_token(self, t): pass

    async def request_action(self, skill, args, agent):
        self.actions.append((skill, args, agent))
        return {"ok": True, "output": "Reminder pending"}

    def llm_stream(self, msgs):
        self.system = msgs[0]["content"]

        async def gen():
            yield "ok"
        return gen()


def test_a_reminder_request_becomes_a_real_action(monkeypatch):
    io = IO()
    asyncio.run(agents.build_graph().ainvoke(
        {"text": "1 min baar paani peene ka reminder set kardo", "history": [], "persona": {}, "notes": []},
        config={"configurable": {"io": io}}))
    assert io.actions == [("set_reminder", {"minutes": 1, "message": "paani peene"}, "planner")]
    assert "succeeded" in io.system


def test_a_plain_question_is_not_turned_into_a_reminder(monkeypatch):
    io = IO()
    monkeypatch.setattr(agents, "wants_llm_router", lambda t: False)
    asyncio.run(agents.build_graph().ainvoke({"text": "what is a good reminder app", "history": [], "persona": {}, "notes": []},
                                             config={"configurable": {"io": io}}))
    assert io.actions == []


# ---------- a stalled turn ends instead of spinning ----------
class StubIO:
    def __init__(self):
        self.aborted, self.finished = False, False
        self.hub = type("H", (), {"history": lambda self, uid: []})()
        self.user = type("U", (), {"id": "u", "role": "free"})()
        self.persona, self.reply_so_far = {}, []

    async def abort(self): self.aborted = True
    async def finish(self): self.finished = True


def test_a_hung_provider_raises_turn_timeout_and_aborts(monkeypatch):
    monkeypatch.setattr("app.turn.TURN_TIMEOUT", 0.05)
    class Hanging:
        async def ainvoke(self, state, config): await asyncio.sleep(5)
    io = StubIO()
    with pytest.raises(TurnTimeout):
        run(execute_turn_timed(io, Hanging(), "hello"))
    assert io.aborted


def test_a_stalled_voice_provider_never_holds_the_reply_open(monkeypatch):
    monkeypatch.setattr("app.turn.TTS_GRACE", 0.05)

    class Fast:
        async def ainvoke(self, state, config): pass

    class SlowFinish(StubIO):
        async def finish(self): await asyncio.sleep(5)
    io = SlowFinish()
    run(execute_turn_timed(io, Fast(), "hello"))            # returns instead of waiting for audio
    assert io.aborted


def test_a_normal_turn_is_untouched():
    class Fast:
        async def ainvoke(self, state, config):
            config["configurable"]["io"].reply_so_far.append("hi")
    io = StubIO()
    run(execute_turn_timed(io, Fast(), "hello"))
    assert io.finished and not io.aborted and TURN_TIMEOUT >= 30


# ---------- an exhausted voice provider is dropped for the rest of the reply ----------
def _tts_plan():
    rot = Rotation(None)
    gem = rot.spec_by_name("tts", "gemini-tts")
    edge = rot.spec_by_name("tts", "edge-tts")
    return rot, [Resolved(gem, "k", "rotation"), Resolved(edge, "", "rotation")]


def test_quota_exhausted_provider_is_removed_from_the_plan(monkeypatch):
    rot, plan = _tts_plan()
    calls = []

    async def noop(*a, **k): return None
    monkeypatch.setattr(Rotation, "mark_exhausted", noop)
    monkeypatch.setattr(Rotation, "record_success", noop)

    async def synth(r):
        calls.append(r.name)
        if r.name == "gemini-tts":
            raise QuotaError("429", retry_after=30)
        return b"audio"
    _r, audio = run(rot.run(plan, synth))
    assert audio == b"audio" and [p.name for p in plan] == ["edge-tts"]
    n = len(calls)
    run(rot.run(plan, synth))                                   # the next sentence of the same reply
    assert len(calls) == n + 1 and "gemini-tts" not in calls[n:]


def test_a_provider_with_only_dead_models_is_skipped_without_a_call(monkeypatch):
    rot, plan = _tts_plan()

    async def noop(*a, **k): return None
    monkeypatch.setattr(Rotation, "record_success", noop)
    for m in plan[0].spec.models:
        rot.bad_models[("gemini-tts", m)] = 9e9
    calls = []

    async def synth(r):
        calls.append(r.name); return b"audio"
    run(rot.run(plan, synth))
    assert calls == ["edge-tts"]


def test_every_provider_failing_still_reports_cleanly(monkeypatch):
    rot, plan = _tts_plan()

    async def noop(*a, **k): return None
    for name in ("mark_exhausted", "record_success"):
        monkeypatch.setattr(Rotation, name, noop)                # monkeypatch restores them (a bare setattr leaked into every later test)

    async def dead(r): raise QuotaError("429")
    with pytest.raises(NoProviderAvailable):
        run(rot.run(plan, dead))
    assert plan == []                                           # nothing left to retry for the next sentence
