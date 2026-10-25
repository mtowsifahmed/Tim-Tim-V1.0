"""Turns a token stream into speakable sentences so TTS can start before the reply is finished."""
from __future__ import annotations

import re

_END = re.compile(r"([.!?…]+[\"')\]]*)(\s+|$)|\n+")
_CLAUSE = re.compile(r"[,;:—–]\s+")


def clean_for_speech(text: str) -> str:
    t = re.sub(r"```.*?```", " (code omitted) ", text, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"[*_#>~|]+", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


class SentenceChunker:
    """First chunk may be short (to start speaking early); later chunks are a bit longer for natural prosody."""

    def __init__(self, first_min: int = 12, min_len: int = 40, first_clause: int = 24):
        self.buf, self.first_min, self.min_len, self.sent_any, self.first_clause = "", first_min, min_len, False, first_clause

    def feed(self, tok: str) -> list[str]:
        self.buf += tok
        out = []
        while True:
            need = self.min_len if self.sent_any else self.first_min
            m = next((x for x in _END.finditer(self.buf) if x.end() >= need and (x.end() < len(self.buf) or x.group(0).endswith("\n") or x.group(2) != "")), None)
            if not m and not self.sent_any:                  # nothing sentence-like yet: speak the first clause once it is long enough
                c = next((x for x in _CLAUSE.finditer(self.buf) if x.end() >= self.first_clause), None)
                if c:
                    piece, self.buf = self.buf[:c.end()], self.buf[c.end():]
                    if clean_for_speech(piece):
                        out.append(clean_for_speech(piece)); self.sent_any = True
                    continue
            if not m:
                break
            piece, self.buf = self.buf[:m.end()], self.buf[m.end():]
            if clean_for_speech(piece):
                out.append(clean_for_speech(piece)); self.sent_any = True
        return out

    def flush(self) -> list[str]:
        piece, self.buf = clean_for_speech(self.buf), ""
        return [piece] if piece else []
