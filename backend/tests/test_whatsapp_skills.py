import asyncio

import pytest

from app import agents, skills
from tests.test_release import ask, make_io


def test_whatsapp_skills_validate_names_and_text():
    assert skills.validate("whatsapp_message", {"contact": "  Mom ", "text": "I'll be late\nsee you soon"}, "chat") == {"contact": "Mom", "text": "I'll be late\nsee you soon"}
    assert skills.validate("whatsapp_open", {}, "chat") == {} and skills.validate("whatsapp_open", {"contact": "Rahul"}, "planner") == {"contact": "Rahul"}
    for bad in ({"contact": "", "text": "hi"}, {"contact": "Mom", "text": ""}, {"contact": "Mom"}, {"contact": "M" * 81, "text": "hi"}, {"contact": "Mom", "text": "x" * 1001}, {"contact": "Mo\x00m", "text": "hi"}):
        with pytest.raises(ValueError):
            skills.validate("whatsapp_message", bad, "chat")


def test_only_chat_and_planner_may_send_whatsapp_messages():
    for agent in ("research", "coding", "creative"):
        with pytest.raises(ValueError):
            skills.validate("whatsapp_message", {"contact": "Mom", "text": "hi"}, agent)
    assert skills.SKILLS["whatsapp_message"]["risk"] == "high"                 # sending on your behalf always asks first, never "Always allow"


def test_router_notices_whatsapp_requests_and_the_catalog_says_what_it_cannot_do(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_MODE", "auto")
    for t in ("message mom on WhatsApp that I'm late", "send a message to Rahul", "open whatsapp"):
        assert agents.wants_llm_router(t), t
    assert "cannot read chats or post status" in skills.catalog_for_prompt()


def test_a_phone_alone_can_send_through_whatsapp_but_not_run_commands():
    io, hub, conns = make_io(["mobile"])
    res = asyncio.run(ask(io, hub, "whatsapp_message", {"contact": "Mom", "text": "hi"}, {"ok": True, "output": "opened"}))
    assert res["ok"] and [m["skill"] for m in conns["mobile"].ws.sent] == ["whatsapp_message"]
    io, hub, conns = make_io(["mobile"])
    assert not asyncio.run(ask(io, hub, "run_shell", {"command": "dir"}))["ok"]
