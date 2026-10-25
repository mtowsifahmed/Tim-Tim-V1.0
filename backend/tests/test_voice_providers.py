"""Gemini on one key covers chat, hearing (STT) and speaking (TTS): these lock in the wire format of both."""
import asyncio
import base64
import io
import json
import wave

import httpx
import pytest

from app.providers import stt, tts
from app.providers.errors import ModelError
from app.providers.registry import load_registry


def spec(capability: str, name: str):
    return next(s for s in load_registry()[capability] if s.name == name)


def call(specification, fn, http, *args):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(http)) as c:
            return await fn(c, specification, "test-key", *args)
    return asyncio.run(go())


def audio_payload(data: bytes, mime: str = "audio/wav") -> dict:
    return {"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}}]}}]}


def test_gemini_stt_posts_the_utterance_and_returns_the_transcript():
    seen = {}

    def http(request):
        seen["url"] = str(request.url)
        seen["key_header"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "  hello there "}]}}]})

    heard = call(spec("stt", "gemini-stt"), stt.transcribe, http, b"RIFF....wav-bytes")
    assert heard == "hello there"
    assert seen["url"].endswith("/models/gemini-3.5-transcribe:generateContent")
    assert seen["key_header"] == "test-key"
    part = seen["body"]["contents"][0]["parts"][1]["inlineData"]
    assert part["mimeType"] == "audio/wav" and base64.b64decode(part["data"]) == b"RIFF....wav-bytes"
    assert "transcript" in seen["body"]["contents"][0]["parts"][0]["text"].lower()   # asks for words, not a summary


def test_gemini_stt_reads_the_shape_the_dedicated_transcription_model_uses():
    """gemini-3.5-transcribe answers in audioTranscription.text, not in a plain text part."""
    def http(request):
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"audioTranscription": {"text": "voice check passed"}}], "role": "model"}}]})

    assert call(spec("stt", "gemini-stt"), stt.transcribe, http, b"RIFF....") == "voice check passed"


def test_gemini_stt_treats_silence_as_empty_not_as_a_failure():
    def http(request):
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": ""}]}}]})

    assert call(spec("stt", "gemini-stt"), stt.transcribe, http, b"RIFF....") == ""


def test_gemini_tts_asks_for_audio_and_returns_playable_wav():
    wav = b"RIFF" + b"\x00" * 40
    seen = {}

    def http(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=audio_payload(wav))

    out, mime = call(spec("tts", "gemini-tts"), tts.synth, http, "Voice check passed.", "Aoede")
    assert out == wav and mime == "audio/wav"
    cfg = seen["body"]["generationConfig"]
    assert cfg["responseModalities"] == ["AUDIO"] and cfg["speechConfig"]["voiceConfig"]["voice"] == "Aoede"
    assert seen["body"]["contents"][0]["parts"][0]["text"] == "Voice check passed."


def test_gemini_tts_adds_a_wav_header_when_the_model_sends_headerless_pcm():
    pcm = b"\x01\x02" * 4800                                        # 4800 samples of 16-bit mono

    def http(request):
        return httpx.Response(200, json=audio_payload(pcm, "audio/L16;codec=pcm;rate=24000"))

    out, mime = call(spec("tts", "gemini-tts"), tts.synth, http, "hi", "Kore")
    assert mime == "audio/wav" and out[:4] == b"RIFF"
    with wave.open(io.BytesIO(out)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24000, 1, 2)
        assert w.readframes(w.getnframes()) == pcm


def test_gemini_tts_falls_back_to_the_legacy_voice_field_for_older_models():
    bodies = []

    def http(request):
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return httpx.Response(400, json={"error": {"message": "Unknown name 'voice' in speechConfig.voiceConfig"}})
        return httpx.Response(200, json=audio_payload(b"RIFF" + b"\x00" * 8))

    out, _ = call(spec("tts", "gemini-tts"), tts.synth, http, "hi", "Charon")
    assert out.startswith(b"RIFF") and len(bodies) == 2
    assert bodies[1]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Charon"


def test_gemini_tts_reports_a_retired_model_so_rotation_can_try_the_next_one():
    def http(request):
        return httpx.Response(404, json={"error": {"message": "models/gemini-3.8-flash-tts is not found"}})

    with pytest.raises(ModelError):
        call(spec("tts", "gemini-tts"), tts.synth, http, "hi", "Kore")


def test_cloudflare_transcribes_base64_audio_from_the_result_field(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    seen = {}

    def http(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"result": {"text": "hello cloudflare", "word_count": 2}, "success": True})

    heard = call(spec("stt", "cloudflare-whisper"), stt.transcribe, http, b"RIFFwav")
    assert heard == "hello cloudflare"
    assert seen["url"].startswith("https://api.cloudflare.com/client/v4/accounts/acc123/ai/run/@cf/openai/whisper-large-v3-turbo")
    assert base64.b64decode(seen["body"]["audio"]) == b"RIFFwav" and seen["auth"] == "Bearer tok".replace("tok", "test-key")


def test_cloudflare_speaks_with_the_right_body_per_model(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    bodies = []

    def http(request):
        bodies.append((str(request.url).split("/ai/run/", 1)[-1].split("?")[0], json.loads(request.content)))
        return httpx.Response(200, content=b"mp3-bytes", headers={"content-type": "audio/mpeg"})

    cloudflare = spec("tts", "cloudflare-voice")
    aura_model, melo_model = cloudflare.models[0], cloudflare.models[1]
    out, mime = call(cloudflare, tts.synth, http, "hi", "asteria")
    assert (out, mime) == (b"mp3-bytes", "audio/mpeg") and bodies[0] == (aura_model, {"prompt": "hi", "lang": "en"})
    bodies.clear()
    aura = type(cloudflare)(**{**cloudflare.__dict__, "model": "@cf/deepgram/aura-1"})
    call(aura, tts.synth, http, "hi", "orion")
    assert bodies[0] == ("@cf/deepgram/aura-1", {"text": "hi", "speaker": "orion"})


def test_elevenlabs_scribe_posts_multipart_and_reads_text():
    seen = {}

    def http(request):
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        return httpx.Response(200, json={"text": "scribe heard this"})

    assert call(spec("stt", "elevenlabs-scribe"), stt.transcribe, http, b"RIFFwav") == "scribe heard this"
    assert seen["url"].endswith("/v1/speech-to-text")
    assert b"scribe_v1" in seen["body"] and b"RIFFwav" in seen["body"]


def test_a_library_voice_on_a_free_elevenlabs_plan_falls_back_to_a_premade_one():
    """ElevenLabs answers 402 paid_plan_required for library voices; the account's premade voices still work."""
    calls = []

    def http(request):
        calls.append((request.method, str(request.url)))
        if request.method == "GET" and str(request.url).endswith("/v1/voices"):
            return httpx.Response(200, json={"voices": [
                {"voice_id": "lib-voice", "category": "library", "labels": {"gender": "female"}},
                {"voice_id": "pre-made-f", "category": "premade", "labels": {"gender": "female"}},
                {"voice_id": "pre-made-m", "category": "premade", "labels": {"gender": "male"}}]})
        if "/text-to-speech/lib-voice/" in str(request.url):        # the request carries a ?output_format=… query
            return httpx.Response(402, json={"detail": {"message": "Free users cannot use library voices via the API"}})
        return httpx.Response(200, content=b"mp3-ok", headers={"content-type": "audio/mpeg"})

    out, mime = call(spec("tts", "elevenlabs"), tts.synth, http, "hi", "lib-voice")
    assert (out, mime) == (b"mp3-ok", "audio/mpeg")
    assert any(m == "GET" for m, _ in calls)                       # it asked which voices the account may use
    assert "/text-to-speech/pre-made-f/" in calls[-1][1]              # and kept the female gender


def test_groq_tts_requests_wav_and_splits_at_its_character_cap():
    """Groq's Orpheus voices only return WAV and refuse more than 200 characters per request."""
    body_texts, formats = [], []

    def http(request):
        body = json.loads(request.content)
        body_texts.append(body["input"]); formats.append(body["response_format"])
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes(b"\x01\x00" * 100)
        return httpx.Response(200, content=buf.getvalue(), headers={"content-type": "audio/wav"})

    long_text = "This sentence is deliberately long so that it must be cut into more than one request. " * 4
    out, mime = call(spec("tts", "groq-tts"), tts.synth, http, long_text, "hannah")
    assert mime == "audio/wav" and len(body_texts) > 1 and set(formats) == {"wav"}
    assert all(len(t) <= 190 for t in body_texts)
    with wave.open(io.BytesIO(out)) as w:
        assert w.getnframes() == 100 * len(body_texts)               # stitched into one valid wav


def test_one_gemini_key_registers_chat_and_voice_separately(monkeypatch):
    """GEMINI_MODEL pins the chat model; the voice models must not be dragged along by it."""
    monkeypatch.setenv("GEMINI_API_KEY", "g" * 20)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-chat-pinned")
    monkeypatch.setenv("GEMINI_TTS_MODEL", "gemini-voice-pinned")
    reg = load_registry()
    assert next(s for s in reg["llm"] if s.name == "gemini").model == "gemini-chat-pinned"
    tts_spec = next(s for s in reg["tts"] if s.name == "gemini-tts")
    assert tts_spec.model == "gemini-voice-pinned" and tts_spec.voice_for("calm_male") == "Charon"
    stt_spec = next(s for s in reg["stt"] if s.name == "gemini-stt")
    assert stt_spec.model == "gemini-3.5-transcribe" and stt_spec.configured
