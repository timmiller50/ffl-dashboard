# FFL Dashboard

- `python3 import_espn_yahoo.py` merges data/espn_raw.json + data/yahoo_raw.json into data/leagues.json (replaces ESPN/Yahoo entries) and rebuilds index.html.
- `python3 refresh_sleeper.py [--refresh-players]` refreshes ONLY the Sleeper entry (ESPN/Yahoo entries and their last_updated are preserved) and rebuilds index.html.
- `python3 build_html.py` rebuilds index.html from data/leagues.json only.
- Open index.html (static, no JS). Each league has `last_updated`; the header shows per-platform times.
