# HANDOFF — read this first (updated Oct 2026)

Audience: **Claude** (the project's author agent) or any agent picking this repo up. Written so you're current in 5 minutes.

## What this is
Tim-Tim: $0-stack agentic voice companion — FastAPI backend (`backend/`), Tauri-2 desktop UI shipped as static
`desktop/src` (open `index.html` in a browser; Tauri shell not compiled here), Supabase schema (`supabase/migrations/`),
Flutter phone app not written yet. Owner account: `m.towsifoffical2013@gmail.com`. Read `START-HERE.md` for setup,
`README-PROVIDERS.md` for the free-tier provider tables.

## What the assistant session changed (all verified except where noted)

### 1. Retired-model crisis → model ladders + self-healing  (`backend/providers.yaml`, `rotation.py`)
Google retired the 2.5 line (HTTP 404) and Groq retired the `llama-3.x` ids, so every chat/voice call was dying.
- Every provider now has an ordered `models:` ladder; a 404/400-model marks that model bad for 6 h and the next model is tried.
- If the ladder is exhausted, `discover` fetches `/models` from the provider and picks up to 3 usable ids (substring filter, e.g. `:free`, `gpt-oss`).
- `model_env` lets one key (Gemini) serve chat/STT/TTS without one env var overriding all three:
  `GEMINI_MODEL`, `GEMINI_STT_MODEL`, `GEMINI_TTS_MODEL`, `CLOUDFLARE_STT_MODEL`, `CLOUDFLARE_TTS_MODEL`.

### 2. BYOK (Pro users' own keys) hardening  (`rotation.py`, tests)
- A BYOK key walks **its own provider's model ladder** (this fixed the user's "Your provider rejected this model name." loop),
  then raises a clear, key-free message — it **never** falls back to the shared keys (that would silently spend owner quota).
- Quota/auth/model failures on BYOK map to user-facing sentences, never leak the key.

### 3. New free-tier voice providers  (`providers.yaml`, `stt.py`, `tts.py`, `validate.py`, `registry.py`)
- STT registry order: `gemini-stt → cloudflare-whisper → groq-whisper → elevenlabs-scribe → deepgram → custom`.
- TTS registry order: `gemini-tts → groq-tts → cloudflare-voice → deepgram-aura → elevenlabs → custom → edge-tts` (keyless fallback).
- New `kind: cloudflare` adapter (Workers AI; base_url expands `${CLOUDFLARE_ACCOUNT_ID}`, needs `CLOUDFLARE_API_TOKEN` too).
- Groq Orpheus TTS on the existing Groq key: `audio_format: wav`, `max_chars: 190` — adapter splits long text on word
  boundaries and re-joins WAV frames (`_split`/`_join` in `tts.py`).
- ElevenLabs Scribe STT on the existing ElevenLabs key. `registry.py` gained `audio_format` / `max_chars` spec fields.

### 4. ElevenLabs female voice fix  (`providers.yaml`, `tts.py`)
Root cause: the shipped female id (Rachel) is a **library** voice → ElevenLabs free plan returns `402 paid_plan_required`;
the male (Adam) is **premade** and worked. Now ships premade **Jessica** (expressive female, `cgSgspJ2msm6clMCkdW9`) and
**Daniel** (calm male, `onwK4e9ZLuTAKqWW03F9`). Adapter is self-healing: on 400/402/404 mentioning the voice it fetches
`/v1/voices`, picks a **premade same-gender** voice for that account, caches it per key, retries.

### 5. Gemini STT quality  (`stt.py`)
Dedicated transcription models return `audioTranscription.text` (not `text`) — parser now reads both; a verbatim-transcript
prompt stops the general audio models from summarizing/translate instead of transcribing; thought-parts are skipped.

### 6. Diagnostics  (`backend/check_providers.py`)
`python check_providers.py` probes every configured key per capability with real (tiny) calls and prints OK/exact problem;
`--reset` clears `provider_state` cooldowns and daily counters.

### 7. Docs
`START-HERE.md` (Python 3.11 venv, key setup, troubleshooting table), `README-PROVIDERS.md` (all tables current Oct 2026),
`backend/.env.example` (all key slots incl. Cloudflare + model overrides).

## File map (where things live)
| Area | Files |
|---|---|
| Provider registry & specs | `backend/providers.yaml`, `app/providers/registry.py` |
| Rotation/self-healing/BYOK | `app/providers/rotation.py`, `app/providers/errors.py` |
| Adapters | `app/providers/llm.py` (OpenAI-compatible stream), `stt.py`, `tts.py`, `validate.py` |
| Voice turn pipeline | `app/ws.py` (STT→LLM→TTS, interrupt), `app/turn.py`, `app/audio.py` (PCM→WAV) |
| BYOK routes | `app/routes/keys.py` (validate-before-save, Fernet-encrypted, masked last4) |
| Desktop UI | `desktop/src/app.js` (Settings keys screen is registry-driven via `GET /providers`), `index.html` |
| Tests | `backend/tests/` — `test_rotation.py` (incl. BYOK-ladder cases), `test_voice_providers.py`, others |

## Verified vs not
**Verified:** 57 backend tests pass (`cd backend && .venv/Scripts/python -m pytest -q`). Live on the owner's real keys:
Groq chat streaming, Groq Orpheus TTS (184 KB WAV + auto-split long sentence), Deepgram STT/TTS round trip
("Voice check passed." → exact transcript), ElevenLabs Jessica/Daniel audio + Scribe transcribing that audio back verbatim,
Gemini STT/TTS, model-ladder failover after a 429. Backend runs on `127.0.0.1:8000` (`uvicorn app.main:app --reload`), `/health` → 200.
**Not verified:** Cloudflare Workers AI against the real API (no Cloudflare account — mocked tests only);
Tauri desktop build (no Rust/MSVC on this machine); Flutter app (doesn't exist).

## Gotchas for the next agent
- **Free quotas are per MODEL, not per provider** — that's why ladders exist; a 429 on one model must not cool the whole provider (only `daily` does, until 00:01 UTC).
- Groq Orpheus is **billed per character** (not documented as free) and caps requests at 200 chars — keep `max_chars`.
- ElevenLabs free plan: non-commercial + attribution; only **premade** voices work.
- `edge-tts` is unofficial and keyless — the always-available last resort.
- Keys are Fernet-encrypted with `KEY_ENCRYPTION_SECRET`; changing it invalidates saved BYOK keys.
- `.env` and `desktop/src/config.js` are gitignored/user-local — never assume they're in a fresh checkout.

## Sensible next steps
1. Flutter phone app (backend pairing/relay ready) · 2. Compile the Tauri shell on a Rust-capable machine ·
3. Local whisper STT for genuinely unlimited recognition · 4. Streaming partial transcripts during speech ·
5. Typing/clicking computer-use skills.
