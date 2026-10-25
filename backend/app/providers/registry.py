from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

CAPS = ("llm", "stt", "tts", "embed")


def _expand(url: str) -> str:
    """Let base_url contain ${ENV_VAR} (Cloudflare puts the account id in the path).
    A missing variable leaves a '$' behind, which means 'not configured' rather than a broken URL."""
    out = os.path.expandvars(url)
    return "" if "$" in out else out


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    capability: str
    kind: str
    base_url: str
    model: str
    api_key: str            # the app's own key ('' if not configured)
    voice: str = ""
    soft_daily_limit: int | None = None
    voices: dict | None = None
    no_key: bool = False
    dimensions: int | None = None
    models: tuple = ()
    discover: str | None = None          # substring a discovered model id must contain (e.g. ':free')
    audio_format: str = ""               # TTS output format to request (empty = the adapter's default)
    max_chars: int | None = None         # TTS per-request input cap (Groq Orpheus: 200)

    @property
    def configured(self) -> bool:
        if self.no_key:
            return True
        return bool(self.api_key and self.base_url)

    def voice_for(self, persona: str) -> str:
        if self.voices and persona in self.voices:
            return self.voices[persona]
        return self.voice


def _custom_voices(prefix: str, default: dict | None) -> dict | None:
    male, female = os.getenv(f"{prefix}_VOICE_MALE", ""), os.getenv(f"{prefix}_VOICE_FEMALE", "")
    if male or female:
        return {"calm_male": male or female, "expressive_female": female or male}
    return default


def load_registry(path: Path | None = None) -> dict[str, list[ProviderSpec]]:
    path = path or Path(__file__).resolve().parents[2] / "providers.yaml"
    raw = yaml.safe_load(path.read_text())
    out: dict[str, list[ProviderSpec]] = {}
    for cap in CAPS:
        specs = []
        for e in raw.get(cap, []):
            if "custom" in e:                       # custom gateway: all fields from env
                p = e["custom"]
                specs.append(ProviderSpec(
                    name="custom", capability=cap, kind=e["kind"],
                    base_url=_expand(os.getenv(f"{p}_BASE_URL", "")).rstrip("/"),
                    model=os.getenv(f"{p}_MODEL", ""), api_key=os.getenv(f"{p}_API_KEY", ""),
                    voice=os.getenv(f"{p}_VOICE", ""), voices=_custom_voices(p, e.get("voices")),
                    dimensions=e.get("dimensions"), models=(os.getenv(f"{p}_MODEL", ""),) if os.getenv(f"{p}_MODEL") else ()))
            else:
                override_var = e.get("model_env") or (f"{e['env'].removesuffix('_API_KEY')}_MODEL" if e.get("env") else "")
                override = os.getenv(override_var, "").strip() if override_var else ""
                models = tuple(dict.fromkeys(([override] if override else []) + list(e.get("models") or ([e["model"]] if e.get("model") else []))))
                specs.append(ProviderSpec(
                    name=e["name"], capability=cap, kind=e["kind"], base_url=_expand(e.get("base_url", "")).rstrip("/"),
                    model=models[0] if models else "", models=models, discover=e.get("discover"),
                    api_key=os.getenv(e["env"], "") if e.get("env") else "",
                    soft_daily_limit=e.get("soft_daily_limit"), voices=e.get("voices"),
                    no_key=bool(e.get("no_key")), dimensions=e.get("dimensions"),
                    audio_format=e.get("audio_format", ""), max_chars=e.get("max_chars")))
        out[cap] = specs
    return out
