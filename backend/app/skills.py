"""Desktop automation skills. The backend only PROPOSES an action; the desktop app enforces
per-skill permission and shows a visible confirmation before anything runs."""
from __future__ import annotations

import re

KEYS = {"enter", "tab", "esc", "up", "down", "left", "right", "backspace", "delete", "space", "home", "end", "pageup", "pagedown",
        "ctrl+a", "ctrl+c", "ctrl+v", "ctrl+x", "ctrl+z", "ctrl+s", "ctrl+f", "alt+left", "alt+right", "alt+f4"}
MEDIA = {"volume_up", "volume_down", "mute", "play_pause", "next_track", "prev_track"}

# args: name -> max length (text) or (min, max) for whole numbers; names in "optional" may be left out
SKILLS: dict[str, dict] = {
    "open_app":     {"risk": "low",    "args": {"app": 100},                          "desc": "open an application by name (e.g. notepad, chrome, spotify)"},
    "close_app":    {"risk": "medium", "args": {"app": 100},                          "desc": "close an application by name"},
    "open_url":     {"risk": "low",    "args": {"url": 2000},                          "desc": "open a web page in the browser (http/https only)"},
    "search_web":   {"risk": "low",    "args": {"query": 200},                         "desc": "search the web for something and show the results in the browser"},
    "open_path":    {"risk": "low",    "args": {"path": 500},                          "desc": "open a file or folder with its default app"},
    "read_file":    {"risk": "medium", "args": {"path": 500},                          "desc": "read a text file"},
    "list_dir":     {"risk": "medium", "args": {"path": 500},                          "desc": "list the files and folders inside a folder"},
    "write_file":   {"risk": "high",   "args": {"path": 500, "content": 100_000},      "desc": "create or overwrite a text file"},
    "create_folder": {"risk": "medium", "args": {"path": 500},                         "desc": "create a folder (and any missing parent folders)"},
    "copy_file":    {"risk": "high",   "args": {"from": 500, "to": 500},               "desc": "copy a file to a new path (refuses to overwrite)"},
    "move_file":    {"risk": "high",   "args": {"from": 500, "to": 500},               "desc": "move or rename a file (refuses to overwrite)"},
    "delete_file":  {"risk": "high",   "args": {"path": 500},                          "desc": "send a file or folder to the Recycle Bin (Windows)"},
    "run_shell":    {"risk": "high",   "args": {"command": 1000},                      "desc": "run a shell command and read its output"},
    "type_text":    {"risk": "high",   "args": {"text": 2000},                         "desc": "type text into whatever window currently has focus (Windows)"},
    "press_key":    {"risk": "high",   "args": {"key": 30},                            "desc": "press one key or shortcut in the focused window, one of: " + ", ".join(sorted(KEYS))},
    "click":        {"risk": "high",   "args": {"x": (0, 20000), "y": (0, 20000)},     "desc": "left-click at screen pixel coordinates x,y (advanced; you cannot see the screen, so only use coordinates the user gave)"},
    "clipboard_read":  {"risk": "medium", "args": {},                                  "desc": "read the text currently on the clipboard (Windows)"},
    "clipboard_write": {"risk": "medium", "args": {"text": 5000},                      "desc": "put text on the clipboard so the user can paste it (Windows)"},
    "media_key":    {"risk": "low",    "args": {"key": 20, "times": (1, 25)}, "optional": {"times"},
                     "desc": "press a media key, one of: " + ", ".join(sorted(MEDIA)) + "; volume keys can repeat with times (each press is about 2 percent)"},
    "system_info":  {"risk": "low",    "args": {},                                     "desc": "report the computer's operating system, CPU load, memory and battery (Windows)"},
    "lock_screen":  {"risk": "medium", "args": {},                                     "desc": "lock the computer (Windows)"},
    "whatsapp_open":    {"risk": "low",  "args": {"contact": 80}, "optional": {"contact"},
                         "desc": "open WhatsApp, or the chat with a saved contact by name (the phone numbers live in the user's own contact list on their device)"},
    "whatsapp_message": {"risk": "high", "args": {"contact": 80, "text": 1000},
                         "desc": "send a WhatsApp message to a saved contact by name; the user confirms first. It cannot read chats or post status"},
    "set_reminder": {"risk": "low",    "args": {"minutes": (1, 1440), "message": 200}, "desc": "remind the user in N minutes (1 to 1440) with a short message; works by notification and voice"},
}

# which skills each sub-agent may request ("tool access" per agent)
_CORE = {"open_app", "open_url", "search_web", "open_path", "clipboard_write", "set_reminder", "whatsapp_open", "whatsapp_message"}
AGENT_SKILLS: dict[str, set[str]] = {
    "chat": _CORE | {"close_app", "press_key", "type_text", "click", "media_key", "system_info", "lock_screen", "clipboard_read"},
    "research": {"open_url", "search_web", "clipboard_write", "open_path"},
    "coding": {"open_app", "open_path", "run_shell", "read_file", "write_file", "list_dir", "create_folder", "copy_file", "move_file",
               "delete_file", "type_text", "press_key", "clipboard_read", "clipboard_write"},
    "creative": {"open_app", "open_url", "search_web", "write_file", "create_folder", "open_path", "clipboard_write"},
    "planner": {"open_app", "open_url", "search_web", "set_reminder", "whatsapp_open", "whatsapp_message", "type_text", "press_key", "clipboard_write", "system_info"},
}

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# ───────── reminders, understood directly (so they never depend on the model or on a slow router call) ─────────
_REMIND = re.compile(r"\b(remind(?:er)?|yaad dila(?:o|de|na)?|alert me|notify me|wake me|timer)\b", re.I)
_MIN = re.compile(r"\b(\d{1,4})\s*(?:min(?:ute)?s?|m|mins?)\b", re.I)
_HR = re.compile(r"\b(\d{1,2})\s*(?:hours?|hrs?|ghant(?:a|e|ay?))\.?\b", re.I)
_NOISE = re.compile(r"\b(?:please|pls|plz|karo|kardo|kar do|kar de|set|a|an|the|me|mujhe|for|in|after|baad|baar|baad me|reminder|remind|yaad|dila(?:o|de|na)?|to|that|ki|ka|ke)\b", re.I)


def guess_reminder(text: str) -> dict | None:
    """"remind me in 10 minutes to stretch" / "1 min baar paani peene ka reminder set kardo" -> set_reminder args.
    Returns None unless a reminder is clearly meant AND a time is stated; the confirmation screen still applies."""
    t = (text or "").strip()
    if not t or not _REMIND.search(t):
        return None
    minutes = None
    m = _MIN.search(t)
    if m:
        minutes = int(m.group(1))
    else:
        h = _HR.search(t)
        if h:
            minutes = int(h.group(1)) * 60
    if not minutes:
        return None
    message = _NOISE.sub(" ", _MIN.sub(" ", _HR.sub(" ", t)))
    message = re.sub(r"\s+", " ", message).strip(" .,!?-:;")
    return {"minutes": max(1, min(minutes, 1440)), "message": (message or t)[:200]}


def validate(name: str, args: dict, agent: str = "chat") -> dict:
    """Returns cleaned args or raises ValueError (the action is then dropped, never executed)."""
    spec = SKILLS.get(name)
    if not spec:
        raise ValueError(f"unknown skill {name!r}")
    if name not in AGENT_SKILLS.get(agent, set()):
        raise ValueError(f"agent {agent!r} may not use {name!r}")
    if not isinstance(args, dict):
        raise ValueError("args must be an object")
    optional = spec.get("optional", set())
    clean: dict = {}
    for key, limit in spec["args"].items():
        v = args.get(key)
        if v is None and key in optional:
            continue
        if isinstance(limit, tuple):
            lo, hi = limit
            if isinstance(v, str) and v.strip().lstrip("-").isdigit():
                v = int(v)
            if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
                raise ValueError(f"bad number {key!r}")
            clean[key] = v
            continue
        if not isinstance(v, str) or (not v.strip() and key != "content"):
            raise ValueError(f"missing argument {key!r}")
        if len(v) > limit or _CTRL.search(v) and key not in ("text", "content"):
            raise ValueError(f"bad argument {key!r}")
        if key in ("text", "content") and re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", v):
            raise ValueError(f"bad argument {key!r}")
        clean[key] = v if key in ("content", "text") else v.strip()
    if name == "open_url" and not re.match(r"^https?://[^\s]+$", clean["url"]):
        raise ValueError("only http(s) URLs are allowed")
    if name == "press_key":
        clean["key"] = clean["key"].lower()
        if clean["key"] not in KEYS:
            raise ValueError("key not allowed")
    if name == "media_key":
        clean["key"] = clean["key"].lower()
        if clean["key"] not in MEDIA:
            raise ValueError("media key not allowed")
    if name in ("open_app", "close_app") and re.search(r"[&|<>^%\"`$;]", clean["app"]):
        raise ValueError("app name contains forbidden characters")
    for pkey in ("path", "from", "to"):
        if pkey in clean and (re.search(r"[<>\"|?*]", clean[pkey].replace(":", "", 1)) or ".." in re.split(r"[\\/]", clean[pkey])):
            raise ValueError(f"unsafe {pkey}")
    return clean


def catalog_for_prompt() -> str:
    def sig(s):
        return ", ".join(f"{a}?" if a in s.get("optional", set()) else a for a in s["args"]) or "no args"
    return "\n".join(f"- {n}: {s['desc']}; args: {sig(s)}" for n, s in SKILLS.items())
