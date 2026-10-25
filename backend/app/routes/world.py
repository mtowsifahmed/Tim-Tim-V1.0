"""World Monitor feeds from free public sources (no API keys):
   - USGS earthquakes M4.5+, last 24 hours
   - BBC World News RSS headlines (titles only, with source and time)
Results are cached for 10 minutes so many users don't hammer the upstream sites."""
from __future__ import annotations

import time
from email.utils import parsedate_to_datetime

import httpx
from defusedxml import ElementTree as ET
from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import CurrentUser, current_user

router = APIRouter(prefix="/world")

USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
RSS_URL = "https://feeds.bbci.co.uk/news/world/rss.xml"
TTL = 600
_cache: dict[str, tuple[float, object]] = {}


def parse_usgs(data: dict) -> list[dict]:
    out = []
    for f in data.get("features", []):
        p, g = f.get("properties") or {}, (f.get("geometry") or {}).get("coordinates") or []
        if p.get("mag") is None or len(g) < 2:
            continue
        out.append({"title": p.get("place") or "Earthquake", "mag": float(p["mag"]),
                    "time": int(p.get("time") or 0), "lon": float(g[0]), "lat": float(g[1])})
    out.sort(key=lambda e: e["time"], reverse=True)
    return out[:40]


def parse_rss(xml_text: str, source: str = "BBC News") -> list[dict]:
    out = []
    for item in ET.fromstring(xml_text).iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        try:
            ms = int(parsedate_to_datetime(item.findtext("pubDate") or "").timestamp() * 1000)
        except (TypeError, ValueError):
            ms = int(time.time() * 1000)
        out.append({"title": title, "source": source, "time": ms})
    return out[:20]


async def _cached(key: str, fetch):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    try:
        val = await fetch()
    except (httpx.HTTPError, ValueError, ET.ParseError) as e:
        if hit:
            return hit[1]                      # serve stale data rather than an error
        raise HTTPException(502, "World feed is temporarily unavailable") from e
    _cache[key] = (time.time(), val)
    return val


@router.get("/events")
async def events(request: Request, user: CurrentUser = Depends(current_user)):
    http = request.app.state.rotation.http

    async def fetch():
        r = await http.get(USGS_URL, timeout=15); r.raise_for_status(); return parse_usgs(r.json())
    return {"events": await _cached("usgs", fetch)}


@router.get("/headlines")
async def headlines(request: Request, user: CurrentUser = Depends(current_user)):
    http = request.app.state.rotation.http

    async def fetch():
        r = await http.get(RSS_URL, timeout=15); r.raise_for_status(); return parse_rss(r.text)
    return {"headlines": await _cached("rss", fetch)}
