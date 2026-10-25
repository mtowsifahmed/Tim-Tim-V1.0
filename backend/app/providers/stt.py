"""Speech-to-text adapters (one utterance in, text out)."""
from __future__ import annotations

import base64

import httpx

from .errors import ProviderError
from .errors import raise_for
from .registry import ProviderSpec

# The general audio models answer a prompt, so ask for a plain transcript or they summarize/translate instead.
TRANSCRIBE_PROMPT = ("Generate a verbatim transcript of all audible speech. Return only the transcript text. "
                     "Do not summarize, translate, or add commentary.")


def _transcript(payload) -> str:
    """Text of the first candidate's parts (Gemini's native generateContent shape). Empty audio -> empty string.
    The dedicated transcription models answer in `audioTranscription.text`; the audio-understanding ones answer in `text`."""
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError("the provider returned no transcript") from e
    out = []
    for p in parts:
        if not isinstance(p, dict) or p.get("thought"):
            continue
        heard = p.get("audioTranscription") or p.get("audio_transcription")
        if isinstance(heard, dict) and heard.get("text"):
            out.append(str(heard["text"]))
        elif p.get("text"):
            out.append(str(p["text"]))
    return "\n".join(x.strip() for x in out if x.strip()).strip()


async def transcribe(client: httpx.AsyncClient, spec: ProviderSpec, key: str, wav: bytes) -> str:
    if spec.kind == "gemini":                     # native generateContent: Gemini hears the audio itself
        r = await client.post(
            f"{spec.base_url}/models/{spec.model}:generateContent",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [
                {"text": TRANSCRIBE_PROMPT},
                {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(wav).decode()}}]}]},
            timeout=60)
        raise_for(r.status_code, r.headers, r.text if r.status_code >= 400 else '')
        return _transcript(r.json())
    if spec.kind == "cloudflare":                 # Workers AI: the account id is in base_url and the audio goes base64 in JSON
        r = await client.post(f"{spec.base_url}/{spec.model}", headers={"Authorization": f"Bearer {key}"},
                              json={"audio": base64.b64encode(wav).decode()}, timeout=60)
        raise_for(r.status_code, r.headers, r.text if r.status_code >= 400 else '')
        res = r.json().get("result")
        if isinstance(res, dict):
            return str(res.get("text") or "").strip()
        if isinstance(res, str):
            return res.strip()
        raise ProviderError("the provider returned no transcript")
    if spec.kind == "elevenlabs":                 # Scribe, on the same key that can speak
        r = await client.post(f"{spec.base_url}/v1/speech-to-text", headers={"xi-api-key": key},
                              files={"file": ("speech.wav", wav, "audio/wav")},
                              data={"model_id": spec.model}, timeout=60)
        raise_for(r.status_code, r.headers, r.text if r.status_code >= 400 else '')
        return str(r.json().get("text") or "").strip()
    if spec.kind == "openai":                     # Groq Whisper, OpenAI-compatible custom gateways
        r = await client.post(f"{spec.base_url}/audio/transcriptions", headers={"Authorization": f"Bearer {key}"},
                              files={"file": ("speech.wav", wav, "audio/wav")},
                              data={"model": spec.model, "response_format": "json"}, timeout=40)
        raise_for(r.status_code, r.headers, r.text if r.status_code >= 400 else '')
        return (r.json().get("text") or "").strip()
    if spec.kind == "deepgram":
        r = await client.post(f"{spec.base_url}/v1/listen", params={"model": spec.model, "smart_format": "true"},
                              headers={"Authorization": f"Token {key}", "Content-Type": "audio/wav"}, content=wav, timeout=40)
        raise_for(r.status_code, r.headers, r.text if r.status_code >= 400 else '')
        try:
            return (r.json()["results"]["channels"][0]["alternatives"][0]["transcript"] or "").strip()
        except (KeyError, IndexError, ValueError) as e:
            raise ProviderError("unexpected Deepgram response") from e
    raise ProviderError(f"STT kind {spec.kind} not supported")
