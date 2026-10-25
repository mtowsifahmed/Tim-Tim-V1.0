"""Provider error types and the one place that turns an HTTP failure into the right exception."""
from __future__ import annotations

import json
import re


class ProviderError(Exception):
    """Generic provider failure."""


class QuotaError(ProviderError):
    """Rate/quota exhausted (HTTP 429/402). `daily` means the DAILY allowance is gone (cool down until tomorrow);
    otherwise it is a per-minute limit and a short cooldown is enough."""

    def __init__(self, msg: str = "quota exhausted", retry_after: int | None = None, daily: bool = False):
        super().__init__(msg)
        self.retry_after, self.daily = retry_after, daily


class AuthError(ProviderError):
    """Bad or missing key (HTTP 401/403)."""


class ModelError(ProviderError):
    """The model name is unknown, retired or not allowed for this key (HTTP 404, or 400 about the model)."""


class NoProviderAvailable(ProviderError):
    """Every provider for this capability is exhausted, unconfigured or failing. `reasons` explain why (for logs/staff)."""

    def __init__(self, msg: str = "no provider available", reasons: list[str] | None = None):
        super().__init__(msg)
        self.reasons = reasons or []


_DAILY = re.compile(r"per\s*day|perday|daily|requests per day|\brpd\b|tokens per day|\btpd\b", re.I)
_MODEL = re.compile(r"model|decommission|deprecat|not found|does not exist|not supported|no longer", re.I)


def _message(text: str) -> str:
    """Best-effort human message out of a provider's JSON error body (never contains our key)."""
    try:
        j = json.loads(text)
        j = j[0] if isinstance(j, list) and j else j
        e = j.get("error", j) if isinstance(j, dict) else {}
        return str(e.get("message") if isinstance(e, dict) else e or text)[:200]
    except (ValueError, AttributeError, TypeError):
        return (text or "")[:200]


def _retry_after(headers, text: str) -> int | None:
    ra = headers.get("retry-after") if headers else None
    if ra and ra.strip().isdigit():
        return int(ra)
    m = re.search(r'retryDelay"?\s*[:=]\s*"?(\d+(?:\.\d+)?)s', text or "")      # Gemini puts it in the body
    return int(float(m.group(1))) + 1 if m else None


def raise_for(status: int, headers=None, text: str = "") -> None:
    if status < 400:
        return
    msg = _message(text)
    if status in (429, 402):
        raise QuotaError(f"HTTP {status}: {msg}", _retry_after(headers, text), bool(_DAILY.search(text or "")))
    if status in (401, 403):
        raise AuthError(f"HTTP {status}: {msg}")
    if status == 404 or (status in (400, 422) and _MODEL.search(msg)):
        raise ModelError(f"HTTP {status}: {msg}")
    raise ProviderError(f"HTTP {status}: {msg}")
