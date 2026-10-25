import asyncio

import pytest

from app import agents, websearch as w


@pytest.fixture(autouse=True)
def clean():
    w._cache.clear(); w._down.clear()


def R(title, url, text="", provider="duckduckgo"):
    return w.Result(title, url, "short", "site.com", None, provider, text)


def test_explicit_research_requests_are_detected():
    for t in ("research the best electric cars", "deep dive on quantum computing", "give me an in-depth look at the chip shortage", "investigate this claim",
              "Please research mortgage rates", "write a full report on solar power"):
        assert w.wants_deep(t) and w.needs_web(t, "chat"), t
    for t in ("what is a deep learning model", "tell me a joke", "I did some research yesterday and it was fun"):
        assert not w.wants_deep(t), t


def test_planned_queries_are_cleaned_deduplicated_and_capped():
    raw = 'Sure!\n```json\n["EV range 2026", "ev range 2026", "best electric cars India", "EV battery life", "x", "charging network comparison", "extra one here"]\n```'
    qs = w.parse_queries(raw, "research electric cars")
    assert qs == ["EV range 2026", "best electric cars India", "EV battery life", "charging network comparison"]


def test_unusable_plan_falls_back_to_several_angles():
    for raw in ("", "not json", '{"agent":"chat"}', '["only one"]'):
        qs = w.parse_queries(raw, "research electric cars")
        assert len(qs) == 3 and qs[0] == "electric cars" and "latest" in qs[1]


def test_merge_is_round_robin_and_drops_duplicate_pages():
    a = [R("a1", "https://x.com/1"), R("a2", "https://x.com/2/")]
    b = [R("b1", "https://x.com/1?utm=1"), R("b2", "https://y.com/9"), R("b3", "https://y.com/10")]
    out = w._merge([a, b])
    assert [r.title for r in out] == ["a1", "a2", "b2", "b3"]
    assert len(w._merge([[R(f"t{i}", f"https://z.com/{i}") for i in range(30)]])) == 10


def test_deep_research_runs_all_searches_reads_pages_and_reports_progress(monkeypatch):
    seen_q, progress = [], []

    async def chain(http, q, news, hl, cc, base, **kw):
        seen_q.append(q); i = len(seen_q)
        return [R(f"Result {i}a", f"https://s{i}.com/a"), R(f"Result {i}b", f"https://s{i}.com/b")], ["duckduckgo"]

    async def fetch(http, url): return "Full page text about the topic. " * 5
    monkeypatch.setattr(w, "_chain", chain); monkeypatch.setattr(w, "fetch_page", fetch)

    async def llm(msgs): return '["q one", "q two", "q three"]'

    async def on_progress(m): progress.append(m)
    res = asyncio.run(w.deep_research(None, "research something big", {"lang": "en-IN"}, llm, on_progress))
    assert sorted(seen_q) == ["q one", "q three", "q two"] and progress == ["Searching 3 angles…", "Reading the best sources…"]
    assert "Full page text" in res.context and res.providers[-1] == "deep" and 1 <= len(res.sources) <= 8 and len(res.results) == 6


def test_planner_failure_still_produces_research(monkeypatch):
    calls = []

    async def chain(http, q, news, hl, cc, base, **kw):
        calls.append(q); return [R("T", f"https://s.com/{len(calls)}")], ["duckduckgo"]

    async def fetch(http, url): return ""
    monkeypatch.setattr(w, "_chain", chain); monkeypatch.setattr(w, "fetch_page", fetch)

    async def broken(msgs): raise RuntimeError("llm down")
    res = asyncio.run(w.deep_research(None, "research solar panels", {}, broken))
    assert res and len(calls) == 3


def test_nothing_found_means_none(monkeypatch):
    async def chain(*a, **k): return [], []
    monkeypatch.setattr(w, "_chain", chain)

    async def llm(msgs): return "[]"
    assert asyncio.run(w.deep_research(None, "research nothing", {}, llm)) is None


def test_context_respects_the_larger_deep_limit():
    rs = [w.Result(f"T{i}", f"https://a.com/{i}", "", "a.com", None, "x", "word " * 300) for i in range(12)]
    assert len(w.format_context(rs, limit=9000)) <= 9000 + 1000 and len(w.format_context(rs)) < len(w.format_context(rs, limit=9000))


# ---------- through the agent graph ----------
class IO:
    class rot:
        http = None

    def __init__(self):
        self.events, self.system, self.collected = [], None, 0

    async def emit(self, m): self.events.append(m)
    async def memory_search(self, q, s): return []
    async def request_action(self, *a, **k): return {"ok": False}
    async def on_token(self, t): pass

    async def llm_collect(self, msgs):
        self.collected += 1
        return '["angle one", "angle two"]' if msgs[0]["content"].startswith("You plan web searches") else '{"agent":"research","skill":null}'

    def llm_stream(self, msgs):
        self.system = msgs[0]["content"]

        async def g():
            yield "ok"
        return g()


def test_graph_uses_deep_research_and_the_research_prompt(monkeypatch):
    async def fake_chain(http, q, news, hl, cc, base, **kw): return [R("Found " + q, "https://e.com/" + q.replace(" ", ""))], ["duckduckgo"]

    async def fetch(http, url): return "Detailed page content for the report. " * 4
    monkeypatch.setattr(w, "_chain", fake_chain); monkeypatch.setattr(w, "fetch_page", fetch)
    io = IO()
    asyncio.run(agents.build_graph().ainvoke({"text": "research the future of solar power", "history": [], "persona": {}, "notes": []}, config={"configurable": {"io": io}}))
    assert "RESEARCH request" in io.system and "Found angle one" in io.system and "Detailed page content" in io.system
    tasks = [e.get("task") for e in io.events if e["type"] == "agent"]
    assert "Researching…" in tasks and "Searching 2 angles…" in tasks and "Reading the best sources…" in tasks
    assert any(e["type"] == "sources" and len(e["items"]) == 2 for e in io.events)


def test_deep_research_respects_the_off_switch(monkeypatch):
    async def boom(*a, **k): raise AssertionError("must not search")
    monkeypatch.setattr(w, "deep_research", boom); monkeypatch.setattr(w, "research", boom)
    io = IO()
    asyncio.run(agents.build_graph().ainvoke({"text": "research the future of solar power", "history": [], "persona": {"web": "off"}, "notes": []}, config={"configurable": {"io": io}}))
    assert io.system
