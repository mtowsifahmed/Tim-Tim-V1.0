"""Multi-agent orchestration on LangGraph.
   classify (one orchestrator LLM call) -> [act: propose a desktop skill] -> respond (the chosen sub-agent streams the reply).
Each sub-agent has its own system prompt, its own skill (tool) allow-list, and scoped memory."""
from __future__ import annotations

import json
import os
import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from . import skills, websearch

AGENTS: dict[str, dict] = {
    "chat": {"name": "Tim-Tim", "scopes": ["global"], "task": "Chatting…",
             "prompt": "You are Tim-Tim in general conversation mode: helpful, curious and brief."},
    "research": {"name": "Research", "scopes": ["global", "research"], "task": "Analyzing data…",
                 "prompt": "You are Tim-Tim's Research specialist. Give accurate, balanced, concise findings. Say plainly when you are unsure or when something may be out of date. Never invent sources."},
    "coding": {"name": "Coding", "scopes": ["global", "coding"], "task": "Building solution…",
               "prompt": "You are Tim-Tim's Coding specialist. Explain solutions simply out loud; offer to put long code into a file rather than reading it aloud."},
    "creative": {"name": "Creative", "scopes": ["global", "creative"], "task": "Generating ideas…",
                 "prompt": "You are Tim-Tim's Creative specialist: stories, names, ideas, taglines and design thinking. Be vivid but concise, and offer one or two options rather than a long list."},
    "planner": {"name": "Planner", "scopes": ["global", "planner"], "task": "Scheduling tasks…",
                "prompt": "You are Tim-Tim's Planner: schedules, reminders, task breakdowns and email drafts. Ask briefly for missing details (date, time, recipient). You can only draft emails, never send them or claim to have sent them."},
}

VOICE_RULES = ("You are speaking aloud. Use short natural sentences. No markdown, no bullet symbols, no emojis, no URLs read out. "
               "If you need to give a list, say it conversationally. Keep replies brief: usually one to three sentences (under about 60 words), "
               "and go longer only when the user asks for detail or this is a research request. Start with the answer itself, no preamble.")

COMPANY = os.getenv("COMPANY_NAME", "Zaftan Studios").strip() or "Zaftan Studios"


def identity_block() -> str:
    """Who Tim-Tim is. Models otherwise announce the vendor that trained them ("I am Gemini, made by Google")."""
    return (f"IDENTITY: You are Tim-Tim, an AI companion created and developed by {COMPANY}. If anyone asks who made, created, built, developed, trained or owns you, "
            f"answer that you were created by {COMPANY}. Never say you are Gemini, Claude, ChatGPT, GPT, Llama, Mistral, DeepSeek, Qwen or any other named model, and never say "
            "you were made by Google, OpenAI, Anthropic, Meta, Microsoft, NVIDIA, Groq, Mistral or any other company. If asked which AI model or technology powers you, say you are "
            f"Tim-Tim from {COMPANY} and that your replies come from a mix of AI models behind the scenes, so you can't say which one is answering right now. "
            "You are an AI, and if someone sincerely asks whether you are a human you say plainly that you are an AI.")


class State(TypedDict, total=False):
    text: str
    history: list
    persona: dict
    notes: list
    agent: str
    skill: dict | None
    action_result: str | None
    web_context: str
    web_failed: bool
    deep: bool
    sources: list
    reply: str


def persona_style(p: dict) -> str:
    tone, humor, formal = int(p.get("tone", 60)), int(p.get("humor", 40)), int(p.get("formal", 30))
    t = "warm, kind and encouraging" if tone >= 66 else "friendly and even" if tone >= 33 else "direct and businesslike"
    h = "playful, with light humor" if humor >= 66 else "occasionally witty" if humor >= 33 else "serious, no jokes"
    f = "polite and formal" if formal >= 66 else "relaxed but respectful" if formal >= 33 else "casual and conversational"
    return f"Personality: {t}; {h}; {f}. Stay in this character consistently."


def now_line(p: dict) -> str:
    """Tell the model the real date/time in the user's time zone (models don't know it) and the user's name."""
    from datetime import datetime, timezone
    tz = str(p.get("tz") or "UTC")[:60]
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(tz))
    except Exception:
        now, tz = datetime.now(timezone.utc), "UTC"
    name = str(p.get("uname") or "").strip()[:40]
    s = f"Right now it is {now:%A, %d %B %Y, %H:%M} ({tz}). Use this for anything about today, tomorrow, 'in an hour', deadlines or reminders."
    return s + (f" The user's name is {name}; use it occasionally, not in every sentence." if name else "")


def build_system(agent: str, persona: dict, memories: list[str], notes: list[str], web: str = "", deep: bool = False) -> str:
    parts = [identity_block(), f"You are Tim-Tim, the user's AI companion. {AGENTS[agent]['prompt']}", persona_style(persona), VOICE_RULES, now_line(persona)]
    if memories:
        parts.append("Things you know about the user (use only when relevant, never recite them):\n" + "\n".join(f"- {m}" for m in memories))
    if notes:
        parts.append("Context for this reply:\n" + "\n".join(f"- {n}" for n in notes))
    if web:
        parts.append(websearch.WEB_PROMPT + (websearch.DEEP_PROMPT if deep else "") + web)
    parts.append(f"Reminder: you are Tim-Tim, made by {COMPANY}. Never name another company or model as your creator.")
    return "\n\n".join(parts)


CLASSIFIER = f"""You are the orchestrator of an AI assistant. Pick exactly ONE agent for the user's latest message:
chat (general talk), research (facts, explanations, news), coding (programming, scripts, files of code), creative (stories, ideas, names, design), planner (plans, schedules, reminders, tasks, drafting emails).
If the user clearly asks to DO something on their computer, also give a skill. Skills:
{skills.catalog_for_prompt()}
Reply with ONLY compact JSON like {{"agent":"chat","skill":null}} or {{"agent":"chat","skill":{{"name":"open_app","args":{{"app":"notepad"}}}}}}. Never invent skills."""

_HEUR = [("coding", r"\b(code|bug|script|function|python|javascript|error|compile|program)\b"),
         ("planner", r"\b(schedule|meeting|remind|calendar|appointment|tomorrow|deadline|plan|task|todo|email|e-mail|inbox)\b"),
         ("creative", r"\b(story|poem|idea|ideas|name for|slogan|tagline|brainstorm|design|imagine)\b"),
         ("research", r"\b(research|explain|why|how does|what is|who is|news|compare)\b")]


def heuristic_agent(text: str) -> str:
    t = text.lower()
    return next((a for a, rx in _HEUR if re.search(rx, t)), "chat")


def parse_classification(raw: str, text: str) -> tuple[str, dict | None]:
    agent, skill = heuristic_agent(text), None
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except (ValueError, TypeError):
        return agent, None
    if data.get("agent") in AGENTS:
        agent = data["agent"]
    sk = data.get("skill")
    if isinstance(sk, dict) and isinstance(sk.get("name"), str):
        try:
            skill = {"name": sk["name"], "args": skills.validate(sk["name"], sk.get("args") or {}, agent)}
        except ValueError:
            skill = None
    return agent, skill


def _io(config) -> Any:
    return config["configurable"]["io"]


_ACTION = re.compile(r"\b(open|launch|start|run|execute|close|quit|exit|kill|go to|visit|browse|read|write|save|create|delete|play|search for|whatsapp|send|message)\b", re.I)


def wants_llm_router(text: str) -> bool:
    """ORCHESTRATOR_MODE=auto (default): spend the extra LLM call only when the message looks like an action request,
    so free-tier quota isn't halved by routing. 'llm' always routes with the model; 'keyword' never does."""
    mode = os.getenv("ORCHESTRATOR_MODE", "auto")
    return mode == "llm" or (mode == "auto" and bool(_ACTION.search(text)))


async def classify(state: State, config) -> dict:
    io = _io(config)
    # A stated reminder is understood here: no router call, no chance the model just *claims* to have set one.
    guess = skills.guess_reminder(state["text"])
    if guess:
        try:
            return {"agent": "planner", "skill": {"name": "set_reminder", "args": skills.validate("set_reminder", guess, "planner")}}
        except ValueError:
            pass
    if not wants_llm_router(state["text"]):
        return {"agent": heuristic_agent(state["text"]), "skill": None}
    ctx = state.get("history", [])[-2:]
    msgs = [{"role": "system", "content": CLASSIFIER}, *ctx, {"role": "user", "content": state["text"]}]
    try:
        raw = await io.llm_collect(msgs)
    except Exception:
        return {"agent": heuristic_agent(state["text"]), "skill": None}
    agent, skill = parse_classification(raw, state["text"])
    return {"agent": agent, "skill": skill}


async def act(state: State, config) -> dict:
    io, sk = _io(config), state["skill"]
    await io.emit({"type": "agent", "id": state["agent"], "status": "working", "task": f"Requesting {sk['name']}…"})
    res = await io.request_action(sk["name"], sk["args"], state["agent"])
    if res.get("ok"):
        out = f"The action {sk['name']} succeeded. {str(res.get('output', ''))[:1500]}"
    elif res.get("denied"):
        out = f"The user declined (or has not allowed) the action {sk['name']}, so it was NOT done."
    else:
        out = f"The action {sk['name']} failed: {str(res.get('error', 'unknown error'))[:300]}"
    return {"action_result": out}


async def web(state: State, config) -> dict:
    """Look things up on the live web when the question needs current information (news, prices, 'latest', explicit searches)."""
    io, persona = _io(config), state.get("persona") or {}
    if not websearch.needs_web(state["text"], state["agent"], str(persona.get("web", "auto"))):
        return {}
    deep = websearch.wants_deep(state["text"])
    await io.emit({"type": "agent", "id": state["agent"], "status": "working", "task": "Researching…" if deep else "Searching the web…"})

    async def progress(msg: str) -> None:
        await io.emit({"type": "agent", "id": state["agent"], "status": "working", "task": msg})
    key = await io.search_key() if hasattr(io, "search_key") else None   # this account's own key, never somebody else's
    try:
        if deep:
            res = await websearch.deep_research(io.rot.http, state["text"], persona, io.llm_collect, progress, key=key)
        else:
            res = await websearch.research(io.rot.http, state["text"], persona, deep=state["agent"] == "research", key=key)
    except Exception as e:                                                  # noqa: BLE001 - a failed search must never break the answer
        import logging
        logging.getLogger("timtim.web").warning("research failed: %s", type(e).__name__)
        res = None
    if not res or not res.results:
        return {"web_context": "", "web_failed": True}
    return {"web_context": res.context, "sources": res.sources, "deep": deep}


async def respond(state: State, config) -> dict:
    io, agent = _io(config), state["agent"]
    await io.emit({"type": "agent", "id": agent, "status": "working", "task": AGENTS[agent]["task"]})
    notes = list(state.get("notes", []))
    if state.get("action_result"):
        notes.append(state["action_result"] + " Tell the user briefly what happened.")
    if state.get("web_failed"):
        notes.append("You tried to check the live web for this but could not get results. Say plainly that you couldn't check live sources right now, "
                     "and give only what you know with a warning that it may be out of date. Never pretend to have current information.")
    memories = await io.memory_search(state["text"], AGENTS[agent]["scopes"])
    msgs = [{"role": "system", "content": build_system(agent, state.get("persona", {}), memories, notes, state.get("web_context", ""), bool(state.get("deep")))},
            *state.get("history", [])[-12:], {"role": "user", "content": state["text"]}]
    reply = []
    async for tok in io.llm_stream(msgs):
        reply.append(tok)
        await io.on_token(tok)
    if state.get("sources"):
        await io.emit({"type": "sources", "items": state["sources"]})
    await io.emit({"type": "agent", "id": agent, "status": "done"})
    return {"reply": "".join(reply)}


def after_classify(state: State) -> str:
    return "act" if state.get("skill") else "respond"


def build_graph():
    g = StateGraph(State)
    g.add_node("classify", classify); g.add_node("act", act); g.add_node("web", web); g.add_node("respond", respond)
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", after_classify, {"act": "act", "respond": "web"})
    g.add_edge("act", "web"); g.add_edge("web", "respond"); g.add_edge("respond", END)
    return g.compile()
