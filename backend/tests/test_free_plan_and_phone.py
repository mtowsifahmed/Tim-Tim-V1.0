"""Rules added in v1: the phone can only do phone things, and every account brings its own key."""
import asyncio

from app import policy
from app.turn import RUNS_ON_CALLING_DEVICE, TurnIO, _mobile_site


class _Hub:
    async def broadcast(self, user_id, msg): pass

    def desktop(self, user_id): return None


class _Origin:
    device = "mobile"

    def __init__(self): self.sent = []

    async def send(self, msg): self.sent.append(msg)


class _User:
    id, role, email, plan = "u1", "free", "new@example.com", "free"


def _io(device="mobile"):
    origin = _Origin(); origin.device = device
    return TurnIO(_Hub(), origin, _User(), None, {}, {}, False)


def test_open_app_on_a_phone_becomes_the_website():
    assert _mobile_site("YouTube") == "https://www.youtube.com"
    assert _mobile_site("whatsapp.exe") == "https://web.whatsapp.com"
    assert _mobile_site("open Instagram app") == "https://www.instagram.com"
    assert _mobile_site("chrome") is None          # a program, not a website: the phone cannot do this


def test_phone_gets_a_useful_answer_instead_of_no_desktop_app_connected():
    """The old text told phone users their desktop app was missing even for a program the phone never had."""
    io = _io("mobile")
    res = asyncio.run(io.request_action("open_app", {"app": "notepad"}))
    assert res["ok"] is False
    assert "desktop app" in res["error"] and "open youtube.com" in res["error"]


def test_the_device_itself_may_run_these_without_a_desktop():
    assert {"open_url", "search_web", "set_reminder"} <= RUNS_ON_CALLING_DEVICE


def test_free_accounts_never_use_the_apps_shared_keys():
    assert policy.requires_own_key("free")
    assert not policy.requires_own_key("pro") and not policy.requires_own_key("owner")
    assert policy.can_use_byok("free")             # so the free plan can run on its own key


def test_a_free_account_without_a_key_gets_no_shared_provider(monkeypatch):
    """The whole point of the change: a free turn must never be served by the owner's keys."""
    from app.providers import rotation as rot_mod

    class Pool:
        async def fetchrow(self, *a, **k): return None

        async def fetch(self, *a, **k): raise AssertionError("shared providers must not be consulted for a free account")

    monkeypatch.setattr(rot_mod.db, "pool", lambda: Pool())
    rot = rot_mod.Rotation(None)
    for cap in ("llm", "stt", "tts", "embed"):
        assert asyncio.run(rot.plan(cap, "u1", "free")) == []


def test_one_key_setup_route_exists():
    from app.main import app
    paths = app.openapi()["paths"]
    assert "post" in paths["/keys/one-key"]          # one Google key for chat, speech and voice
    assert "put" in paths["/keys/{capability}"]
    assert "post" in paths["/keys/{capability}/validate"]
