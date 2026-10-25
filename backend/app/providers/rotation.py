"""Provider rotation: BYOK key first (Pro), else ranked free-tier providers.
Self-healing: a retired model is skipped (and a working one discovered), a per-minute limit only cools a provider
down briefly, and every failure is logged with its real reason (never the key)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Awaitable, Callable

import httpx

from .. import crypto, db, policy
from . import llm
from .errors import AuthError, ModelError, NoProviderAvailable, ProviderError, QuotaError
from .registry import ProviderSpec, load_registry

log = logging.getLogger("timtim.rotation")
MODEL_BAD_SECONDS = 6 * 3600
_SKIP = ("embed", "whisper", "tts", "guard", "vision", "image", "audio", "rerank", "moderation", "safety")


@dataclass
class Resolved:
    spec: ProviderSpec
    api_key: str
    source: str            # 'byok' | 'rotation'

    @property
    def name(self) -> str:
        return self.spec.name


def _tomorrow_utc() -> datetime:
    n = datetime.now(timezone.utc)
    return (n + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)


class Rotation:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.registry = load_registry()
        self.bad_models: dict[tuple[str, str], float] = {}     # (provider, model) -> retry-after timestamp
        self.good_model: dict[tuple[str, str], str] = {}        # (capability, provider) -> last model that worked
        self.discovered: dict[tuple[str, str], float] = {}

    def spec_by_name(self, capability: str, name: str) -> ProviderSpec | None:
        return next((s for s in self.registry[capability] if s.name == name), None)

    # ───────── planning ─────────
    async def plan(self, capability: str, user_id: str, role: str) -> list[Resolved]:
        """Ordered attempts. A valid BYOK key goes straight to the user's provider (no fallback to ours)."""
        if capability != "embed" and policy.can_use_byok(role):
            row = await db.pool().fetchrow(
                "select provider, key_cipher from public.api_keys where user_id=$1 and capability=$2", user_id, capability)
            if row:
                spec = self.spec_by_name(capability, row["provider"])
                if spec:
                    try:
                        return [Resolved(spec, crypto.decrypt(row["key_cipher"]), "byok")]
                    except Exception as e:                        # noqa: BLE001 - a stored key we can't read must not break the turn
                        log.warning("could not read the stored %s key for %s (%s); using the shared providers",
                                    capability, user_id, type(e).__name__)
        state = {r["provider"]: r["exhausted_until"] for r in await db.pool().fetch(
            "select provider, exhausted_until from public.provider_state where capability=$1", capability)}
        used = {r["provider"]: r["calls"] for r in await db.pool().fetch(
            "select provider, calls from public.provider_usage_daily where capability=$1 and day=(now() at time zone 'utc')::date", capability)}
        now, out = datetime.now(timezone.utc), []
        for s in self.registry[capability]:
            if not s.configured:
                continue
            if state.get(s.name) and state[s.name] > now:
                log.info("skip %s/%s: cooling down until %s", capability, s.name, state[s.name].isoformat(timespec="seconds"))
                continue
            if s.soft_daily_limit and used.get(s.name, 0) >= s.soft_daily_limit:
                continue
            out.append(Resolved(s, s.api_key, "rotation"))
        return out

    async def explain(self, capability: str) -> dict:
        """Why would a rotation plan be empty? (used for honest user-facing messages and the diagnostic page)"""
        configured = [s.name for s in self.registry[capability] if s.configured and not s.no_key]
        rows = await db.pool().fetch("select provider, exhausted_until from public.provider_state where capability=$1 and exhausted_until > now()", capability)
        cooling = {r["provider"]: r["exhausted_until"] for r in rows if r["provider"] in configured}
        return {"configured": configured, "cooling": cooling, "none_configured": not configured}

    async def mark_exhausted(self, r: Resolved, e: QuotaError) -> None:
        if e.retry_after:
            secs = min(e.retry_after, 86400)
            until = datetime.now(timezone.utc) + timedelta(seconds=secs)
        elif e.daily:
            until = _tomorrow_utc()
        else:
            until = datetime.now(timezone.utc) + timedelta(seconds=60)          # per-minute limit: brief cooldown only
        log.warning("%s/%s limit reached (%s); cooling until %s", r.spec.capability, r.name, "daily" if e.daily else "rate", until.isoformat(timespec="seconds"))
        await db.pool().execute(
            "insert into public.provider_state(provider,capability,exhausted_until) values($1,$2,$3) "
            "on conflict (provider,capability) do update set exhausted_until=excluded.exhausted_until", r.name, r.spec.capability, until)

    async def record_success(self, r: Resolved) -> None:
        if r.source != "rotation":
            return
        self.good_model[(r.spec.capability, r.name)] = r.spec.model
        await db.pool().execute(
            "insert into public.provider_usage_daily(provider,capability,day,calls) values($1,$2,(now() at time zone 'utc')::date,1) "
            "on conflict (provider,capability,day) do update set calls=provider_usage_daily.calls+1", r.name, r.spec.capability)

    # ───────── model self-healing ─────────
    def _models(self, r: Resolved) -> list[str]:
        now, cap = time.time(), r.spec.capability
        order = ([self.good_model[(cap, r.name)]] if (cap, r.name) in self.good_model else []) + list(r.spec.models or ((r.spec.model,) if r.spec.model else ()))
        seen, out = set(), []
        for m in order:
            if m and m not in seen and self.bad_models.get((r.name, m), 0) < now:
                seen.add(m); out.append(m)
        return out

    def _variant(self, r: Resolved, model: str) -> Resolved:
        return Resolved(replace(r.spec, model=model), r.api_key, r.source)

    async def _discover(self, r: Resolved) -> list[str]:
        """Ask the provider which models this key can use; return a few that look like chat models."""
        key = (r.spec.capability, r.name)
        if r.spec.capability != "llm" or r.spec.kind != "openai" or self.discovered.get(key, 0) > time.time():
            return []
        self.discovered[key] = time.time() + 1800
        try:
            ids = await llm.list_models(self.http, r.spec.base_url, r.api_key)
        except Exception as e:                                                  # noqa: BLE001 - diagnostics only
            log.warning("model discovery for %s failed: %s", r.name, e); return []
        want = (r.spec.discover or "").lower()
        ok = [m for m in ids if m and (want in m.lower()) and not any(x in m.lower() for x in _SKIP) and self.bad_models.get((r.name, m), 0) < time.time()]
        log.info("discovered %d usable models for %s", len(ok), r.name)
        return sorted(ok, key=lambda m: (("lite" in m.lower() or "8b" in m.lower() or "preview" in m.lower()), m))[:3]

    # ───────── non-streaming calls (STT, TTS, embeddings) ─────────
    async def run(self, plan: list[Resolved], fn: Callable[[Resolved], Awaitable]):
        """Returns (resolved, result). A failing BYOK key never falls back to the app's keys (that would silently spend our quota)."""
        if not plan:
            raise NoProviderAvailable("no provider is configured for this capability")
        reasons: list[str] = []
        capability = plan[0].spec.capability
        for r in list(plan):
            models = self._models(r)
            if not models and (r.spec.models or r.spec.model):
                reasons.append(f"{r.name}: every known model is retired or cooling down")
                continue                                                     # never retry a dead model on every sentence
            models = models or [r.spec.model]
            quota: QuotaError | None = None
            for idx, m in enumerate(models):
                v = self._variant(r, m)
                try:
                    out = await fn(v)
                    await self.record_success(v)
                    return v, out
                except ModelError as e:
                    reasons.append(f"{r.name}/{m}: {e}"); self.bad_models[(r.name, m)] = time.time() + MODEL_BAD_SECONDS
                    if r.source == "byok":
                        raise ProviderError("Your provider rejected the request for this model.") from e
                except QuotaError as e:
                    reasons.append(f"{r.name}/{m}: {e}")
                    if r.source == "byok":
                        raise ProviderError("Your own API key hit its limit (rate or plan quota).") from e
                    if idx < len(models) - 1:          # free quotas are per model: another model here may still have quota
                        quota = e
                        continue
                    await self.mark_exhausted(v, quota or e)
                    plan[:] = [p for p in plan if p.name != r.name]       # later sentences skip it instead of re-hitting a 429
                    break
                except AuthError as e:
                    reasons.append(f"{r.name}: {e}")
                    if r.source == "byok":
                        raise ProviderError("Your API key was rejected. Re-validate it in Settings → API Keys.") from e
                    plan[:] = [p for p in plan if p.name != r.name]
                    break
                except (ProviderError, httpx.HTTPError) as e:
                    reasons.append(f"{r.name}: {e or type(e).__name__}")
                    if r.source == "byok":
                        raise ProviderError("Your provider could not complete the request.") from e
                    break
        log.warning("all %s providers failed: %s", capability, " | ".join(reasons))
        raise NoProviderAvailable("every provider failed or is exhausted", reasons)

    # ───────── streaming chat ─────────
    async def stream_llm(self, plan: list[Resolved], messages: list[dict],
                         on_provider: Callable[[Resolved], Awaitable[None]]) -> AsyncIterator[str]:
        """Fails over to the next model/provider only if the failure happens BEFORE the first token."""
        if not plan:
            raise NoProviderAvailable("no AI provider is configured or available", ["no provider in plan"])
        reasons: list[str] = []
        for r in plan:
            tried_discovery, quota = False, None
            models = self._models(r) or [r.spec.model]
            i = 0
            while i < len(models):
                m = models[i]; i += 1
                v, started = self._variant(r, m), False
                try:
                    async for tok in llm.stream_chat(self.http, base_url=v.spec.base_url, api_key=v.api_key, model=m, messages=messages):
                        if not started:
                            started = True
                            await on_provider(v)
                        yield tok
                    await self.record_success(v)
                    return
                except httpx.HTTPError as e:                                    # network trouble, timeouts
                    if started:
                        raise ProviderError("The connection to the AI service dropped mid-reply.") from e
                    reasons.append(f"{r.name}: network error {type(e).__name__}")
                    if r.source == "byok":
                        raise ProviderError("Could not reach your AI provider.") from e
                    break
                except ModelError as e:
                    reasons.append(f"{r.name}/{m}: {e}"); self.bad_models[(r.name, m)] = time.time() + MODEL_BAD_SECONDS
                    if started:
                        raise
                    if i >= len(models) and not tried_discovery:                 # list exhausted: ask the provider what exists
                        tried_discovery = True; models += await self._discover(r)
                    if i >= len(models):                                        # nothing left on this provider
                        if r.source == "byok":                                  # a saved key walks the same ladder first
                            raise ProviderError("Your key works, but this provider does not serve any model Tim-Tim "
                                                "knows. Re-save the key or pick another provider.") from e
                        break
                except QuotaError as e:
                    reasons.append(f"{r.name}/{m}: {e}")
                    if r.source == "byok":
                        raise ProviderError("Your own API key hit its limit (rate or plan quota).") from e
                    if started:
                        raise
                    if i < len(models):                # free quotas are per model: another model here may still have quota
                        quota = e
                        continue
                    await self.mark_exhausted(v, quota or e)
                    break
                except AuthError as e:
                    reasons.append(f"{r.name}: {e}")
                    if r.source == "byok":
                        raise ProviderError("Your API key was rejected. Re-validate it in Settings → API Keys.") from e
                    if started:
                        raise
                    break
                except ProviderError as e:
                    reasons.append(f"{r.name}: {e}")
                    if r.source == "byok" or started:
                        raise
                    break
        log.warning("all llm providers failed: %s", " | ".join(reasons))
        raise NoProviderAvailable("every AI provider failed or is exhausted", reasons)
