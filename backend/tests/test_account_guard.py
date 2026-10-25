import asyncio
import datetime as dt

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import guard
from app.auth import CurrentUser, current_user
from app.hub import Hub
from app.routes import account

NOW = dt.datetime(2026, 10, 19, 12, 0, tzinfo=dt.timezone.utc)


class Pool:
    def __init__(self, fail=None): self.sql, self.fail = [], fail

    async def fetchrow(self, q, *a): return {"email": "a@b.com", "role": "free", "plan": "free", "created_at": NOW}
    async def fetchval(self, q, *a): return '{"tone": 60}'

    async def fetch(self, q, *a):
        if "memory_facts" in q: return [{"fact": "likes tea", "scope": "global", "created_at": NOW}]
        if "usage_daily" in q: return [{"day": NOW.date(), "turns": 3}]
        if "automation_log" in q: return [{"agent": "chat", "skill": "open_app", "status": "done", "at": NOW}]
        return [{"capability": "llm", "provider": "groq", "last4": "1234", "created_at": NOW}]

    async def execute(self, q, *a):
        self.sql.append((q, a))
        if self.fail: raise self.fail
        return "DELETE 1"


def client(monkeypatch, pool, role="free"):
    app = FastAPI(); app.state.hub = Hub(); app.include_router(account.router)
    app.dependency_overrides[current_user] = lambda: CurrentUser("u1", "a@b.com", role, "free")
    monkeypatch.setattr(account.db, "pool", lambda: pool)
    return TestClient(app)


def test_export_contains_my_data_and_never_a_secret(monkeypatch):
    j = client(monkeypatch, Pool()).get("/account/export").json()
    assert j["account"]["email"] == "a@b.com" and j["settings"] == {"tone": 60} and j["memory"][0]["fact"] == "likes tea"
    assert j["api_keys"] == [{"capability": "llm", "provider": "groq", "last4": "1234", "created_at": NOW.isoformat()}]
    assert "key_cipher" not in str(j) and j["daily_usage"][0]["turns"] == 3


def test_delete_needs_the_word_DELETE_and_removes_the_auth_user(monkeypatch):
    pool = Pool(); c = client(monkeypatch, pool)
    assert c.post("/account/delete", json={"confirm": "yes"}).status_code == 400 and not pool.sql
    r = c.post("/account/delete", json={"confirm": "DELETE"})
    assert r.status_code == 200 and r.json() == {"deleted": True} and "auth.users" in pool.sql[0][0] and pool.sql[0][1] == ("u1",)


def test_owner_cannot_delete_and_admin_history_blocks_with_a_clear_message(monkeypatch):
    assert client(monkeypatch, Pool(), "owner").post("/account/delete", json={"confirm": "DELETE"}).status_code == 403
    r = client(monkeypatch, Pool(fail=asyncpg.ForeignKeyViolationError("fk")), "moderator").post("/account/delete", json={"confirm": "DELETE"})
    assert r.status_code == 409 and "owner" in r.json()["detail"]


def test_turn_flood_protection(monkeypatch):
    guard._last.clear()
    assert guard.allowed("u", 100.0) and not guard.allowed("u", 100.4) and guard.allowed("u", 101.2) and guard.allowed("other", 100.1)
    guard._last.clear()
    for i in range(6000): guard._last[f"x{i}"] = 0.0
    guard.allowed("fresh", 1000.0); assert len(guard._last) < 5000                       # old entries are swept
