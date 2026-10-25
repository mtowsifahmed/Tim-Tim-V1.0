# PC patch 4: deep research

Needs patch 3 (live web search) applied first. This patch only REPLACES two files that patch 3 added, and adds a test file.

## Apply
1. Extract into your project folder, say yes to overwrite (`backend\app\websearch.py`, `backend\app\agents.py`).
2. In `backend` run the tests:  `.venv\Scripts\python -m pytest -q`
3. Restart the backend.

## What it does
Normal questions still do one quick live search. Say something like **"research the best electric cars in India"**, **"deep dive on solar power"**,
**"give me an in-depth look at…"**, **"investigate…"** or **"write a full report on…"** and Tim-Tim:
1. asks the AI to plan 3 to 4 different searches (so one narrow query can't miss the picture),
2. runs them at the same time, merges the results and removes duplicate pages,
3. READS the best pages (not just the search snippets),
4. answers with the main point first, key findings with outlet names and dates, notes where sources disagree, and offers to go deeper.
The agent card shows "Researching…", then "Searching 3 angles…", then "Reading the best sources…", and source chips appear under the answer.
If the AI planner is down, it still searches from several angles on its own.

Costs: a deep research request uses 2 AI calls (plan + answer) instead of 1, so use it when you want it. It never runs when Settings → Live web is Off.
