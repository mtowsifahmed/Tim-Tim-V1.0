"""Diagnose the AI providers in one command (never prints a key).
   python check_providers.py            test every configured provider
   python check_providers.py --reset    also clear the 'exhausted' flags stored in the database
Voice is tested for real: a short line is spoken with the first working voice provider and then fed back into
speech recognition, so a broken voice path shows up here instead of mid-conversation."""
import asyncio
import sys
from dataclasses import replace

import httpx

from app.audio import pcm_to_wav
from app.config import settings                      # loads backend/.env into the environment
from app.providers import llm, stt as stt_mod, tts as tts_mod
from app.providers.errors import ProviderError
from app.providers.registry import load_registry


def tail(k: str) -> str:
    return f"key …{k[-4:]}" if k else "NO KEY"


def variant(spec, model):
    return replace(spec, model=model)


def models_of(spec) -> tuple:
    return spec.models or ((spec.model,) if spec.model else ("",))


async def probe_tts(http, s):
    """Speak a line. Returns (wav_bytes_or_None, line to print)."""
    line = ""
    for m in models_of(s):
        try:
            data, mime = await tts_mod.synth(http, variant(s, m), s.api_key, "Voice check passed.",
                                             s.voice_for("expressive_female"))
            return (data if mime.startswith("audio/wav") else None,
                    f"  ok {s.name:14} {tail(s.api_key)}  model {m}: spoke {len(data)} bytes of {mime}")
        except (ProviderError, httpx.HTTPError) as e:
            line = f"  !! {s.name:14} {tail(s.api_key)}  model {m}: {e}"
            if type(e).__name__ in ("AuthError", "QuotaError"):
                break
    return None, line


async def probe_stt(http, s, audio: bytes):
    """Recognize audio. Returns (text, line to print)."""
    line = ""
    for m in models_of(s):
        try:
            text = (await stt_mod.transcribe(http, variant(s, m), s.api_key, audio) or "").strip()
            said = f"heard {text[:48]!r}" if text else "accepted the audio (nothing audible in it)"
            return text, f"  ok {s.name:14} {tail(s.api_key)}  model {m}: {said}"
        except (ProviderError, httpx.HTTPError) as e:
            line = f"  !! {s.name:14} {tail(s.api_key)}  model {m}: {e}"
            if type(e).__name__ in ("AuthError", "QuotaError"):
                break
    return None, line


async def main(reset: bool) -> None:
    reg = load_registry()
    print("Reading", ".env found" if __import__("app.config", fromlist=["ENV_FILE"]).ENV_FILE.exists() else ".env NOT FOUND (copy .env.example to .env)")
    spoken, heard = None, ""                        # audio from the TTS check, and what recognition made of it
    async with httpx.AsyncClient(timeout=40) as http:
        for cap, title in (("llm", "LANGUAGE MODELS"), ("tts", "TEXT-TO-SPEECH"), ("stt", "SPEECH-TO-TEXT")):
            print(f"\n== {title} ==")
            for s in reg[cap]:
                if not s.configured:
                    print(f"  -  {s.name:14} not configured (no key in .env)"); continue
                if cap == "llm":
                    ok = False
                    for m in models_of(s):
                        try:
                            text = "".join([t async for t in llm.stream_chat(http, base_url=s.base_url, api_key=s.api_key, model=m, messages=[{"role": "user", "content": "Reply with the single word OK."}])])
                            print(f"  ok {s.name:14} {tail(s.api_key)}  model {m} replied: {text.strip()[:30]!r}"); ok = True; break
                        except ProviderError as e:
                            print(f"  !! {s.name:14} {tail(s.api_key)}  model {m}: {str(e)[:150]}")
                            if type(e).__name__ == "AuthError":
                                break                          # a bad key is not a per-model problem
                            # a quota is per model, so keep walking the ladder and show which models still answer
                        except httpx.HTTPError as e:
                            print(f"  !! {s.name:14} network error {type(e).__name__}"); break
                    if not ok and s.kind == "openai":
                        try:
                            ids = [m for m in await llm.list_models(http, s.base_url, s.api_key) if (s.discover or "").lower() in m.lower()]
                            print(f"       models this key can see: {', '.join(ids[:10]) or '(none)'}")
                        except Exception as e:                     # noqa: BLE001
                            print(f"       could not list models: {e}")
                elif cap == "tts":
                    wav, line = await probe_tts(http, s); print(line)
                    if wav and spoken is None:
                        spoken = wav
                else:
                    # recognize the line we just spoke when we have it, otherwise a second of silence
                    text, line = await probe_stt(http, s, spoken or pcm_to_wav(bytes(32000)))
                    print(line)
                    if text:
                        heard = text
        if heard:
            print(f"\nVoice round trip: the spoken line came back as {heard!r}")
        elif spoken:
            print("\nVoice out works, but no speech-recognition provider is configured to hear it back.")
    if settings.supabase_db_url:
        import asyncpg
        try:
            c = await asyncpg.connect(settings.supabase_db_url, statement_cache_size=0)
            if reset:
                await c.execute("truncate public.provider_state, public.provider_usage_daily"); print("\nCleared the exhausted flags and daily counters.")
            rows = await c.fetch("select capability, provider, exhausted_until from public.provider_state where exhausted_until > now()")
            print("\nProviders on cooldown:", ", ".join(f"{r['capability']}/{r['provider']} until {r['exhausted_until']:%H:%M} UTC" for r in rows) or "none")
            await c.close()
        except Exception as e:                                     # noqa: BLE001
            print("\nCould not read the database:", str(e)[:120])


asyncio.run(main("--reset" in sys.argv))
