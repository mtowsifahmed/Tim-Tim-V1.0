"""Text-to-speech adapters: one sentence in, (audio bytes, mime) out. Sentence-sized calls let playback
start before the full reply exists."""
from __future__ import annotations

import base64
import hashlib
import io
import re
import wave

import httpx

from ..audio import pcm_to_wav
from .errors import ProviderError
from .errors import raise_for
from .registry import ProviderSpec


def _inline_audio(payload) -> tuple[bytes, str]:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError("the provider returned no audio") from e
    for p in parts:
        blob = p.get("inlineData") or p.get("inline_data") or {} if isinstance(p, dict) else {}
        if blob.get("data"):
            try:
                return (base64.b64decode(blob["data"]),
                        str(blob.get("mimeType") or blob.get("mime_type") or ""))
            except (ValueError, TypeError) as e:
                raise ProviderError("the provider returned audio that could not be decoded") from e
    raise ProviderError("the provider returned no audio")


def _playable(audio: bytes, mime: str) -> tuple[bytes, str]:
    """Unary TTS answers with a WAV, but streaming/preview models send headerless PCM, which needs a header."""
    if not audio:
        raise ProviderError("the provider returned no audio")
    if "wav" in mime.lower() or audio[:4] == b"RIFF":
        return audio, "audio/wav"
    if "l16" in mime.lower() or "pcm" in mime.lower() or not mime:
        rate = re.search(r"rate=(\d+)", mime)
        return pcm_to_wav(audio, int(rate.group(1)) if rate else 24000), "audio/wav"
    return audio, mime


async def _gemini(client: httpx.AsyncClient, spec: ProviderSpec, key: str, text: str, voice: str) -> tuple[bytes, str]:
    """Native Gemini TTS (free tier): ask for AUDIO output and read the audio out of the first candidate.
    Gemini 3.8 names a voice with voiceConfig.voice; the older preview models want the nested prebuiltVoiceConfig."""
    url = f"{spec.base_url}/models/{spec.model}:generateContent"
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    base = {"contents": [{"parts": [{"text": text}]}]}
    generation = {"responseModalities": ["AUDIO"]}
    r = await client.post(url, headers=headers, json={
        **base, "generationConfig": {**generation, "speechConfig": {"voiceConfig": {"voice": voice or "Kore"}}}}, timeout=60)
    if r.status_code == 400 and "voice" in r.text.lower():          # older model: retry with the legacy voice field
        r = await client.post(url, headers=headers, json={
            **base, "generationConfig": {**generation,
                                         "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice or "Kore"}}}}}, timeout=60)
    raise_for(r.status_code, r.headers, r.text if r.status_code >= 400 else '')
    return _playable(*_inline_audio(r.json()))


_voice_cache: dict[str, str] = {}          # sha of the key -> a premade voice that account may actually use


async def _premade_voice(client: httpx.AsyncClient, spec: ProviderSpec, key: str, wanted: str) -> str:
    """Library voices are refused on ElevenLabs' free plan (402 paid_plan_required); pick a premade one instead."""
    ck = hashlib.sha256(key.encode()).hexdigest()[:16]
    if ck in _voice_cache:
        return _voice_cache[ck]
    try:
        r = await client.get(f"{spec.base_url}/v1/voices", headers={"xi-api-key": key}, timeout=30)
        voices = r.json().get("voices", []) if r.status_code == 200 else []
    except (httpx.HTTPError, ValueError):
        return ""
    usable = [v for v in voices if v.get("category") == "premade" and v.get("voice_id")]
    if not usable:
        return ""
    gender = next(((v.get("labels") or {}).get("gender") for v in voices if v.get("voice_id") == wanted), None)
    pick = next((v["voice_id"] for v in usable if gender and (v.get("labels") or {}).get("gender") == gender),
                usable[0]["voice_id"])
    _voice_cache[ck] = pick
    return pick


def _split(text: str, limit: int | None) -> list[str]:
    """Some providers cap the input per request (Groq Orpheus: 200 characters), so cut on word boundaries."""
    if not limit or len(text) <= limit:
        return [text]
    pieces, cur = [], ""
    for word in text.split():
        if cur and len(cur) + len(word) + 1 > limit:
            pieces.append(cur); cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        pieces.append(cur)
    return pieces


def _join(parts: list[bytes], mime: str) -> bytes:
    """Stitch per-piece audio back into one clip: real WAV frames for wav, concatenated frames for mp3."""
    if len(parts) == 1:
        return parts[0]
    if mime == "audio/wav" and all(p[:4] == b"RIFF" for p in parts):
        params, frames = None, bytearray()
        try:
            for p in parts:
                with wave.open(io.BytesIO(p)) as w:
                    params = params or (w.getnchannels(), w.getsampwidth(), w.getframerate())
                    frames += w.readframes(w.getnframes())
        except wave.Error:
            return b"".join(parts)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(params[0]); w.setsampwidth(params[1]); w.setframerate(params[2]); w.writeframes(bytes(frames))
        return buf.getvalue()
    return b"".join(parts)


async def synth(client: httpx.AsyncClient, spec: ProviderSpec, key: str, text: str, voice: str) -> tuple[bytes, str]:
    if spec.kind == "gemini":
        return await _gemini(client, spec, key, text, voice)
    if spec.kind == "cloudflare":                 # Workers AI: one JSON endpoint per model, audio comes back as bytes or base64
        body = {"text": text, "speaker": voice or "asteria"} if "aura" in spec.model else {"prompt": text, "lang": "en"}
        r = await client.post(f"{spec.base_url}/{spec.model}", headers={"Authorization": f"Bearer {key}"},
                              json=body, timeout=60)
        raise_for(r.status_code, r.headers, r.text if r.status_code >= 400 else '')
        kind = r.headers.get("content-type", "")
        if kind.startswith("audio"):
            return r.content, "audio/wav" if "wav" in kind else "audio/mpeg"
        try:
            blob = r.json().get("result")
        except ValueError as e:
            raise ProviderError("the provider returned no audio") from e
        blob = blob.get("audio") if isinstance(blob, dict) else blob
        if isinstance(blob, str) and blob:
            return _playable(base64.b64decode(blob), "")
        raise ProviderError("the provider returned no audio")
    if spec.kind == "openai":
        fmt = spec.audio_format or "mp3"
        mime = "audio/wav" if fmt == "wav" else "audio/mpeg"
        out = []
        for piece in _split(text, spec.max_chars):
            r = await client.post(f"{spec.base_url}/audio/speech", headers={"Authorization": f"Bearer {key}"},
                                  json={"model": spec.model, "input": piece, "voice": voice or "nova",
                                        "response_format": fmt}, timeout=60)
            raise_for(r.status_code, r.headers, r.text if r.status_code >= 400 else '')
            out.append(r.content)
        return _join(out, mime), mime
    if spec.kind == "elevenlabs":
        params = {"output_format": "mp3_44100_64"}
        body = {"text": text, "model_id": spec.model}
        r = await client.post(f"{spec.base_url}/v1/text-to-speech/{voice}/stream", params=params,
                              headers={"xi-api-key": key}, json=body, timeout=60)
        if r.status_code in (400, 402, 404) and "voice" in r.text.lower():     # retired or library-only voice
            alt = await _premade_voice(client, spec, key, voice)
            if alt and alt != voice:
                r = await client.post(f"{spec.base_url}/v1/text-to-speech/{alt}/stream", params=params,
                                      headers={"xi-api-key": key}, json=body, timeout=60)
        raise_for(r.status_code, r.headers, r.text if r.status_code >= 400 else '')
        return r.content, "audio/mpeg"
    if spec.kind == "deepgram":
        r = await client.post(f"{spec.base_url}/v1/speak", params={"model": voice or spec.model, "encoding": "mp3"},
                              headers={"Authorization": f"Token {key}"}, json={"text": text}, timeout=40)
        raise_for(r.status_code, r.headers, r.text if r.status_code >= 400 else '')
        return r.content, "audio/mpeg"
    if spec.kind == "edge":                       # unofficial, keyless fallback
        try:
            import edge_tts
            buf = bytearray()
            async for chunk in edge_tts.Communicate(text, voice or "en-US-AriaNeural").stream():
                if chunk["type"] == "audio":
                    buf += chunk["data"]
        except Exception as e:                     # network blocks, protocol changes, package missing
            raise ProviderError("edge-tts unavailable") from e
        if not buf:
            raise ProviderError("edge-tts returned no audio")
        return bytes(buf), "audio/mpeg"
    raise ProviderError(f"TTS kind {spec.kind} not supported")
