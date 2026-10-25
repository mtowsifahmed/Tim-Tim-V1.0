import array
import io
import wave

MAX_UTTERANCE_BYTES = 16000 * 2 * 60        # 60 s of 16 kHz mono 16-bit PCM
MIN_UTTERANCE_BYTES = 16000 * 2 // 5        # 0.2 s: shorter than this is noise
RATE = 16000
SPEECH_RMS = 0.010                          # ~-40 dBFS: below this the clip is silence, not speech
MIN_SPEECH_SECONDS = 0.30                   # a real word takes longer than this

# Speech models answer *something* when handed silence. These are the usual inventions.
HALLUCINATIONS = {
    "thank you", "thanks", "thank you.", "thanks.", "thank you very much", "thank you so much",
    "thank you for watching", "thanks for watching", "thanks for watching!", "please subscribe",
    "subscribe", "bye", "bye.", "you", ".", "thank you.", "thank you for watching.",
}


def rms(pcm: bytes) -> float:
    """Loudness of PCM16 mono samples, 0..1. Used to tell speech from an empty recording."""
    usable = len(pcm) // 2 * 2
    if usable <= 0:
        return 0.0
    a = array.array("h")
    a.frombytes(pcm[:usable])
    if not a:
        return 0.0
    return (sum(s * s for s in a) / len(a)) ** 0.5 / 32768


def seconds(pcm: bytes, rate: int = RATE) -> float:
    return (len(pcm) // 2) / rate


def is_silent(pcm: bytes) -> bool:
    return seconds(pcm) < MIN_SPEECH_SECONDS or rms(pcm) < SPEECH_RMS


def looks_invented(text: str, pcm: bytes) -> bool:
    """A short clip that yields a stock phrase ("thank you") was not speech: models invent those from silence."""
    if seconds(pcm) >= 1.5:
        return False
    return text.strip().lower().strip(" .!?,") in {h.strip().lower().strip(" .!?,") for h in HALLUCINATIONS}


def trim_silence(pcm: bytes, rate: int = RATE) -> bytes:
    """Drop leading/trailing near-silence. Models invent phrases like "thank you" when a clip opens
    and closes with seconds of nothing, so send them only the part that actually has sound."""
    frame = max(2, rate // 50) * 2                    # 20 ms of PCM16
    usable = len(pcm) // frame * frame
    if usable < frame * 2:
        return pcm
    first = last = None
    for start in range(0, usable, frame):
        if rms(pcm[start:start + frame]) >= SPEECH_RMS / 2:
            first = start if first is None else first
            last = start + frame
    if first is None or last is None:
        return b""
    pad = frame * 5                                   # keep 100 ms of padding so the first word isn't clipped
    return pcm[max(0, first - pad):min(len(pcm), last + pad)]


def pcm_to_wav(pcm: bytes, rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return buf.getvalue()
