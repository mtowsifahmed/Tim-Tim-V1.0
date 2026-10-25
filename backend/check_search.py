"""Try the live web search from your own PC and see exactly which source answers.
   python check_search.py "today's latest news"        python check_search.py "who won the match yesterday"
(never prints a key)"""
import asyncio
import os
import sys

import httpx

try:                                    # Windows consoles default to cp1252, which mangles the headlines
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                       # noqa: BLE001 - older/odd consoles just keep their own encoding
    pass

from app.config import settings  # noqa: F401  loads backend/.env into the environment
from app import websearch as w


async def main(q: str) -> None:
    print(f"Tavily key: {'yes' if os.getenv('TAVILY_API_KEY') else 'no (optional, free at tavily.com)'}   Brave key: {'yes' if os.getenv('BRAVE_API_KEY') else 'no (optional)'}")
    try:
        import ddgs  # noqa: F401
        print("DuckDuckGo search library: installed")
    except ImportError:
        print("DuckDuckGo search library: MISSING (pip install -r requirements.txt)")
    async with httpx.AsyncClient(timeout=30) as http:
        res = await w.research(http, q, {"lang": os.getenv("LANG_TAG", "en-IN")}, deep=True)
    if not res:
        print("\nNo results from any source. Check your internet connection; if only some sites are blocked, add a free Tavily key."); return
    print(f"\nAnswered by: {', '.join(res.providers)}  ({len(res.results)} results)\n")
    for i, r in enumerate(res.results, 1):
        print(f"[{i}] {r.title}\n    {r.source}  {w._age(r.published)}\n    {r.url}")


asyncio.run(main(" ".join(sys.argv[1:]) or "today's latest news"))
