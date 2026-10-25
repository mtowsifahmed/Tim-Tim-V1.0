import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.providers import llm, rotation as rot_mod
from app.providers.errors import AuthError, ModelError, NoProviderAvailable, ProviderError, QuotaError, raise_for
from app.providers.rotation import Resolved, Rotation


def test_http_errors_map_to_the_right_exception():
    with pytest.raises(ModelError):
        raise_for(404, {}, '{"error":{"message":"models/gemini-2.0-flash is not found"}}')
    with pytest.raises(ModelError):
        raise_for(400, {}, '{"error":{"message":"The model `x` has been decommissioned"}}')
    with pytest.raises(AuthError):
        raise_for(401, {}, "")
    with pytest.raises(ProviderError) as e:
        raise_for(500, {}, "boom")
    assert not isinstance(e.value, (ModelError, QuotaError))
    with pytest.raises(QuotaError) as q:
        raise_for(429, {"retry-after": "12"}, "")
    assert q.value.retry_after == 12 and not q.value.daily
    with pytest.raises(QuotaError) as q:
        raise_for(429, {}, '{"error":{"message":"Quota exceeded for metric ... PerDay"}}')
    assert q.value.daily
    with pytest.raises(QuotaError) as q:
        raise_for(429, {}, '{"details":[{"retryDelay":"17s"}]}')
    assert q.value.retry_after == 18


def make_rot(monkeypatch, models=("m-old", "m-new")):
    r = Rotation(None)
    spec = r.spec_by_name("llm", "groq")
    spec = type(spec)(**{**spec.__dict__, "models": models, "model": models[0], "api_key": "k"})
    marks = []

    async def noop(*a, **k): return None
    async def mark(self, res, e): marks.append((res.name, e.daily, e.retry_after))
    monkeypatch.setattr(Rotation, "record_success", noop)
    monkeypatch.setattr(Rotation, "mark_exhausted", mark)
    return r, [Resolved(spec, "k", "rotation")], marks


def run_stream(r, plan):
    async def go():
        out = []
        async for t in r.stream_llm(plan, [{"role": "user", "content": "hi"}], lambda v: asyncio.sleep(0)):
            out.append(t)
        return "".join(out)
    return asyncio.run(go())


def test_retired_model_is_skipped_and_the_next_one_is_used(monkeypatch):
    r, plan, _ = make_rot(monkeypatch)
    calls = []

    async def fake_stream(client, *, base_url, api_key, model, messages):
        calls.append(model)
        if model == "m-old":
            raise ModelError("HTTP 404: model not found")
        yield "hello"
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    assert run_stream(r, plan) == "hello" and calls == ["m-old", "m-new"]
    calls.clear(); run_stream(r, plan)
    assert calls == ["m-new"]                                     # the dead model is remembered and not retried


def test_all_models_dead_triggers_discovery_of_a_working_one(monkeypatch):
    r, plan, _ = make_rot(monkeypatch)
    plan[0].spec = type(plan[0].spec)(**{**plan[0].spec.__dict__, "discover": "llama"})

    async def fake_stream(client, *, base_url, api_key, model, messages):
        if model != "llama-found":
            raise ModelError("gone")
        yield "found"

    async def fake_list(client, base, key): return ["whisper-x", "llama-found", "llama-guard"]
    monkeypatch.setattr(llm, "stream_chat", fake_stream); monkeypatch.setattr(llm, "list_models", fake_list)
    assert run_stream(r, plan) == "found"


def test_rate_limit_cools_down_briefly_and_next_provider_answers(monkeypatch):
    r, plan, marks = make_rot(monkeypatch)
    spec2 = type(plan[0].spec)(**{**plan[0].spec.__dict__, "name": "second", "models": ("x",), "model": "x"})
    plan.append(Resolved(spec2, "k2", "rotation"))

    async def fake_stream(client, *, base_url, api_key, model, messages):
        if api_key == "k":
            raise QuotaError("HTTP 429", None, False)
        yield "from second"
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    assert run_stream(r, plan) == "from second" and marks == [("groq", False, None)]


def test_a_limit_on_one_model_tries_the_providers_next_model(monkeypatch):
    """Free quotas are per MODEL: a 429 on the first model must not take the whole provider down for the day."""
    r, plan, marks = make_rot(monkeypatch)
    calls = []

    async def fake_stream(client, *, base_url, api_key, model, messages):
        calls.append(model)
        if model == "m-old":
            raise QuotaError("HTTP 429: exceeded your current quota", None, True)      # even a daily limit
        yield "answered by the next model"
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    assert run_stream(r, plan) == "answered by the next model"
    assert calls == ["m-old", "m-new"] and marks == []


def test_a_limit_on_every_model_still_cools_the_provider_down(monkeypatch):
    r, plan, marks = make_rot(monkeypatch)

    async def fake_stream(client, *, base_url, api_key, model, messages):
        raise QuotaError("HTTP 429")
        yield ""
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    with pytest.raises(NoProviderAvailable):
        run_stream(r, plan)
    assert marks == [("groq", False, None)]


def test_failure_reasons_are_kept_for_diagnosis(monkeypatch):
    r, plan, _ = make_rot(monkeypatch)

    async def fake_stream(client, *, base_url, api_key, model, messages):
        raise AuthError("HTTP 401: invalid key")
        yield ""
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    with pytest.raises(NoProviderAvailable) as e:
        run_stream(r, plan)
    assert any("401" in x for x in e.value.reasons)


def test_a_saved_key_also_walks_the_model_ladder(monkeypatch):
    """A BYOK key used to fail on the first model name even when the provider served the next one
    (Groq retired the llama ids and users saw 'Your provider rejected this model name')."""
    r, plan, marks = make_rot(monkeypatch)
    plan[0].source = "byok"
    calls = []

    async def fake_stream(client, *, base_url, api_key, model, messages):
        calls.append(model)
        if model == "m-old":
            raise ModelError("HTTP 404: model not found")
        yield "answered with the user's own key"
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    assert run_stream(r, plan) == "answered with the user's own key"
    assert calls == ["m-old", "m-new"] and marks == []


def test_a_saved_key_with_no_usable_model_gets_a_clear_message(monkeypatch):
    r, plan, _ = make_rot(monkeypatch)
    plan[0].source = "byok"

    async def fake_stream(client, *, base_url, api_key, model, messages):
        raise ModelError("decommissioned")
        yield ""
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    with pytest.raises(ProviderError) as e:
        run_stream(r, plan)
    assert "does not serve any model" in str(e.value)


def test_byok_failure_never_falls_back_to_shared_keys(monkeypatch):
    r, plan, _ = make_rot(monkeypatch)
    plan[0].source = "byok"

    async def fake_stream(client, *, base_url, api_key, model, messages):
        raise QuotaError("HTTP 429")
        yield ""
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    with pytest.raises(ProviderError) as e:
        run_stream(r, plan)
    assert "Your own API key" in str(e.value) and not isinstance(e.value, NoProviderAvailable)
