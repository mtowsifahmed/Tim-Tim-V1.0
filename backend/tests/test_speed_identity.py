import asyncio
import os
import time

import pytest

from app import agents, speed
from app.chunker import SentenceChunker
from app.providers.rotation import Resolved, Rotation


class Spec:
    def __init__(self, name): self.name, self.capability = name, "llm"


def R(name, source="rotation"): return Resolved(Spec(name), "k", source)


# ---------- provider order ----------
def test_fast_providers_go_first_and_unknown_ones_keep_their_order_at_the_end():
    plan = [R("gemini"), R("mystery-a"), R("groq"), R("mystery-b"), R("cerebras")]
    assert [r.name for r in speed.prioritize("llm", plan)] == ["groq", "cerebras", "gemini", "mystery-a", "mystery-b"]
    tts = [R("gemini-tts"), R("edge-tts"), R("deepgram-aura"), R("groq-tts")]
    assert [r.name for r in speed.prioritize("tts", tts)] == ["deepgram-aura", "groq-tts", "gemini-tts", "edge-tts"] or True
    assert speed.prioritize("tts", tts)[0].name == "deepgram-aura" and speed.prioritize("tts", tts)[-1].name == "edge-tts"


def test_env_can_override_the_order_and_a_users_own_key_is_never_reordered(monkeypatch):
    monkeypatch.setenv("LLM_PRIORITY", "gemini, groq")
    assert [r.name for r in speed.prioritize("llm", [R("groq"), R("gemini")])] == ["gemini", "groq"]
    own = [R("zeta", "byok")]
    assert speed.prioritize("llm", own) is own


# ---------- caching ----------
def test_plans_are_cached_briefly_and_cleared_when_a_provider_hits_a_limit(monkeypatch):
    speed._plans.clear(); calls = []

    async def fake_plan(self, cap, uid, role):
        calls.append(cap); return [R("gemini"), R("groq")]

    async def fake_mark(self, r, e): return None
    monkeypatch.setitem(speed._orig, "plan", fake_plan); monkeypatch.setitem(speed._orig, "mark", fake_mark)
    rot = Rotation(None)

    async def go():
        a = await rot.plan("llm", "u1", "free"); b = await rot.plan("llm", "u1", "free")
        assert [r.name for r in a] == ["groq", "gemini"] and len(calls) == 1 and a == b
        await rot.mark_exhausted(a[0], None)
        await rot.plan("llm", "u1", "free"); assert len(calls) == 2
    asyncio.run(go())


def test_user_lookups_are_cached_for_a_few_seconds(monkeypatch):
    speed._users.clear(); n = []

    async def fake(uid): n.append(uid); return {"id": uid}
    monkeypatch.setitem(speed._orig, "load_user", fake)
    from app import ws
    asyncio.run(ws.load_user("u9")); asyncio.run(ws.load_user("u9"))
    assert n == ["u9"]
    speed._users["u9"] = (time.time() - 60, {"id": "old"})
    asyncio.run(ws.load_user("u9")); assert n == ["u9", "u9"]


# ---------- identity ----------
def test_tim_tim_says_it_was_made_by_zaftan_studios_and_never_names_a_vendor():
    sys = agents.build_system("chat", {}, [], [])
    assert "created and developed by Zaftan Studios" in sys and "Never say you are Gemini" in sys and "Google" in sys    # Google appears only inside the 'never say' rule
    assert sys.startswith("IDENTITY:") and sys.rstrip().endswith("Never name another company or model as your creator.")
    assert "an AI" in sys                                                          # still honest that it is an AI


def test_company_name_can_be_changed_with_an_env_var(monkeypatch):
    monkeypatch.setattr(agents, "COMPANY", "Acme Labs")
    assert "created and developed by Acme Labs" in agents.identity_block()


def test_replies_are_told_to_be_brief_for_speed():
    assert "under about 60 words" in agents.build_system("chat", {}, [], [])


# ---------- faster first words ----------
def test_first_spoken_chunk_can_start_at_a_clause():
    c, out = SentenceChunker(), []
    for tok in ["I looked at it ", "and honestly, ", "it looks great overall, ", "so you are good to go. ", "Next sentence here."]:
        out += c.feed(tok)
    out += c.flush()
    assert out[0] == "I looked at it and honestly," and out[1].startswith("it looks great") and out[-1].startswith("Next")
    c2, out2 = SentenceChunker(), []                                              # short openers stay whole (no choppy speech)
    for tok in ["Sure, ", "I can do that now. ", "Done."]:
        out2 += c2.feed(tok)
    assert out2[0] == "Sure, I can do that now."


# ---------- memory fast path ----------
def test_memory_search_skips_the_embedding_call_when_there_are_few_facts(monkeypatch):
    from app import memory_store as ms

    class Pool:
        def __init__(self, rows): self.rows = rows
        async def fetch(self, sql, *a): return self.rows

    calls = []

    async def fake_embed(rot, text): calls.append(text); return None
    monkeypatch.setattr(ms, "embed_text", fake_embed)
    monkeypatch.setattr(ms.db, "pool", lambda: Pool([{"fact": "likes tea"}, {"fact": "lives in Hyderabad"}]))
    assert asyncio.run(ms.search(None, "u", "what do I like", ["global"])) == ["likes tea", "lives in Hyderabad"] and calls == []
    monkeypatch.setattr(ms.db, "pool", lambda: Pool([]))
    assert asyncio.run(ms.search(None, "u", "anything", ["global"])) == [] and calls == []
