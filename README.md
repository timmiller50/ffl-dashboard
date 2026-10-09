# FFL Dashboard

- `python3 import_espn_yahoo.py` merges data/espn_raw.json + data/yahoo_raw.json into data/leagues.json (replaces ESPN/Yahoo entries) and rebuilds index.html + league/<slug>.html pages.
- `python3 refresh_sleeper.py [--refresh-players]` refreshes ONLY the Sleeper entry (ESPN/Yahoo entries and their last_updated are preserved) and rebuilds index.html + league/<slug>.html pages.
- `python3 build_html.py` rebuilds index.html from data/leagues.json only.
- Pages are pre-rendered (work without JS) and also carry `client.src.js` (inlined by build_html.py, no external assets). The **Refresh** button re-fetches data/leagues.json (cache-busted), does a live Sleeper pull in the browser (state, league, users, rosters, matchups for the Megalabowl; names/injuries/projections come from the saved data) and re-renders in place. ESPN/Yahoo only change when re-pulled + pushed.
- Each league has `last_updated`; the toolbar shows per-platform "Last pulled" times in the viewer's local time.
- If you change the JS renderers, keep them in sync with build_html.py (the pre-rendered HTML and JS output should be identical).
