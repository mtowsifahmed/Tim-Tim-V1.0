"""The owner's Tavily key stays with the owner: every other account uses its own key or the keyless sources."""
import asyncio

import httpx
import pytest
from cryptography.fernet import Fernet

from app import websearch as w
from app.auth import CurrentUser
from app.routes import search as routes


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    w._cache.clear(); w._down.clear()
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", Fernet.generate_key().decode())
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-owner")
    yield
    w._cache.clear(); w._down.clear()


def run(coro):
    return asyncio.run(coro)


class FakePool:
    def __init__(self, row=None):
        self.row, self.executed = row, []

    async def fetchrow(self, sql, *args):
        return self.row

    async def execute(self, sql, *args):
        self.executed.append((sql, args))


def use_pool(monkeypatch, pool):
    monkeypatch.setattr(routes.db, "pool", lambda: pool)
    monkeypatch.setattr(w.db, "pool", lambda: pool, raising=False)


# ---------- who may use which key ----------
def test_the_owner_falls_back_to_the_app_key(monkeypatch):
    monkeypatch.setattr(w.db, "pool", lambda: FakePool(), raising=False)
    assert run(w.user_key("owner-id", "owner")) == "tvly-owner"


def test_another_account_never_gets_the_app_key(monkeypatch):
    monkeypatch.setattr(w.db, "pool", lambda: FakePool(), raising=False)
    assert run(w.user_key("free-id", "free")) == ""
    assert run(w.user_key("pro-id", "pro")) == ""


def test_a_saved_personal_key_is_used_and_decrypted(monkeypatch):
    from app import crypto
    pool = FakePool({"key_cipher": crypto.encrypt("tvly-personal")})
    monkeypatch.setattr(w.db, "pool", lambda: pool, raising=False)
    assert run(w.user_key("free-id", "free")) == "tvly-personal"          # own key wins for anyone
    assert run(w.user_key("owner-id", "owner")) == "tvly-personal"        # and for the owner too


def test_a_broken_key_store_does_not_break_search(monkeypatch):
    class Boom:
        async def fetchrow(self, *a):
            raise RuntimeError("db down")
    monkeypatch.setattr(w.db, "pool", lambda: Boom(), raising=False)
    assert run(w.user_key("free-id", "free")) == ""                       # no borrowing, no crash
    assert run(w.user_key("owner-id", "owner")) == "tvly-owner"           # owner keeps the app key


# ---------- the key that actually reaches Tavily ----------
def test_tavily_sends_the_key_it_was_given_and_an_empty_key_disables_it(monkeypatch):
    seen = []

    def handler(req):
        seen.append(req.headers["authorization"])
        return httpx.Response(200, json={"results": []})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert run(w.tavily(client, "q", False, api_key="tvly-personal")) == []
    assert seen == ["Bearer tvly-personal"]                               # not the owner's key from .env
    assert run(w.tavily(client, "q", False, api_key="")) is None
    assert seen == ["Bearer tvly-personal"]                               # no request at all without a key


def test_research_uses_the_account_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    seen = {}

    def handler(req):
        seen["auth"] = req.headers["authorization"]
        return httpx.Response(200, json={"results": [{"title": "Story", "url": "https://bbc.com/x", "content": "x"}]})
    res = run(w.research(httpx.AsyncClient(transport=httpx.MockTransport(handler)), "latest news about chips",
                         {"lang": "en-IN"}, key="tvly-personal"))
    assert seen["auth"] == "Bearer tvly-personal" and res.providers == ["tavily"]


# ---------- the endpoints ----------
def owner(role="owner"):
    return CurrentUser(id="u-" + role, email=role + "@example.com", role=role, plan="free")


def test_owner_with_no_personal_key_is_told_the_app_key_is_in_use(monkeypatch):
    use_pool(monkeypatch, FakePool(None))
    out = run(routes.get_key(owner()))
    assert out == {"configured": False, "masked": None, "shared": True, "placeholder": "tvly-…"}


def test_other_accounts_get_a_placeholder_not_the_app_key(monkeypatch):
    use_pool(monkeypatch, FakePool(None))
    out = run(routes.get_key(owner("free")))
    assert out["shared"] is False and out["configured"] is False and out["placeholder"]


def test_saving_a_key_validates_encrypts_and_returns_only_the_mask(monkeypatch):
    pool = FakePool(None); use_pool(monkeypatch, pool)
    checked = []

    async def ok(key):
        checked.append(key); return True
    monkeypatch.setattr(routes, "_check", ok)
    out = run(routes.save_key(routes.KeyIn(key=" tvly-personal-key "), owner("free")))
    assert checked == ["tvly-personal-key"] and out["saved"] is True and out["checked"] is True
    assert out["masked"].endswith("-key") and "tvly-personal-key" not in str(out)
    sql, args = pool.executed[0]
    assert "'search'" in sql and args[2] == "-key" and "tvly-personal-key" not in args      # only the mask is stored plainly


def test_a_rejected_key_is_never_saved(monkeypatch):
    pool = FakePool(None); use_pool(monkeypatch, pool)

    async def rejected(key):
        raise routes.HTTPException(400, "Tavily rejected that key")
    monkeypatch.setattr(routes, "_check", rejected)
    with pytest.raises(routes.HTTPException) as e:
        run(routes.save_key(routes.KeyIn(key="tvly-bad-key"), owner("free")))
    assert e.value.status_code == 400 and pool.executed == []


def test_removing_a_key_deletes_only_that_accounts_search_key(monkeypatch):
    pool = FakePool(None); use_pool(monkeypatch, pool)
    assert run(routes.remove_key(owner("free"))) == {"removed": True}
    sql, args = pool.executed[0]
    assert "capability='search'" in sql and args == ("u-free",)
