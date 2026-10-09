#!/usr/bin/env python3
"""Fetch live Sleeper data, update ONLY the Sleeper entry in data/leagues.json, and regenerate index.html.

Usage: python3 refresh_sleeper.py [--refresh-players]
ESPN / Yahoo entries (imported by import_espn_yahoo.py) are preserved untouched, including their
own last_updated timestamps. If the Sleeper fetch fails the file is left unchanged.
"""
import json, sys, time, urllib.request
from pathlib import Path
from build_html import write_html, norm_injury

BASE = "https://api.sleeper.app/v1"
ROOT = Path(__file__).parent
DATA = ROOT / "data"
LEAGUES = DATA / "leagues.json"
PLAYERS = DATA / "players_nfl_cache.json"
USERNAME = "millertime2750"
USER_ID = "865267854264664064"
SLEEPER_LEAGUE_ID = "1401978044331089922"
PROJ_KEY = {0: "pts_std", 0.5: "pts_half_ppr", 1: "pts_ppr", 1.0: "pts_ppr"}


def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "ffl-dashboard/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def players(force=False):
    if force or not PLAYERS.exists():
        print("Downloading players/nfl (cached locally)...")
        PLAYERS.write_text(json.dumps(get("/players/nfl")))
    return json.loads(PLAYERS.read_text())


def pinfo(pid, P):
    p = P.get(pid) or {}
    name = p.get("full_name") or (f"{p.get('first_name','')} {p.get('last_name','')}".strip()) or pid
    raw = p.get("injury_status")
    return {"id": pid, "name": name, "pos": p.get("position") or ("DEF" if len(pid) <= 3 else "?"),
            "team": p.get("team"), "injury": norm_injury(raw), "injury_status": raw or "Healthy",
            "injury_body_part": p.get("injury_body_part"), "slot": None, "projection": None, "score": None}


def projections(week, season, scoring_key):
    """Best-effort weekly projections from Sleeper's (undocumented) projections endpoint -> {player_id: pts}."""
    out = {}
    try:
        qs = "&".join(f"position[]={x}" for x in ("QB", "RB", "WR", "TE", "K", "DEF"))
        req = urllib.request.Request(f"https://api.sleeper.com/projections/nfl/{season}/{week}?season_type=regular&{qs}",
                                     headers={"User-Agent": "ffl-dashboard/0.1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            for row in json.load(r):
                v = (row.get("stats") or {}).get(scoring_key)
                if row.get("player_id") and v is not None:
                    out[str(row["player_id"])] = v
    except Exception as e:  # projections are optional
        print("projections unavailable:", e)
    return out


def default_leagues():
    esp = lambda n, lid, tid: {"platform": "ESPN", "name": n, "league_id": lid, "team_id": tid,
                               "team_name": "MillerTime", "record": None, "standing": None,
                               "status": "pending import"}
    return [
        {"platform": "Sleeper", "name": "The Megalabowl 2026", "league_id": SLEEPER_LEAGUE_ID,
         "status": "pending import"},
        esp("Buffalo Gridiron Gauntlet League", "1121237090", 9),
        esp("No Strategy", "43670", 12),
        esp("Seattle Pro H2H Points PPR League", "689864242", 1),
        {"platform": "Yahoo", "name": "Derelict Fantasy Football Club", "league_id": "135402",
         "team_name": "Team Miller", "record": "2-2", "standing": "4th",
         "status": "pending import", "note": "record/standing from manual check, not yet imported"},
        {"platform": "Yahoo", "name": "Yahoo Death 1599505", "league_id": "1599505",
         "team_name": "MillerTime", "record": None, "standing": None,
         "status": "pending import", "note": "survivor/pool league; last seen alive/safe"},
    ]


def build_sleeper():
    state = get("/state/nfl")
    week = state.get("display_week") or state.get("week")
    P = players()
    lg = get(f"/league/{SLEEPER_LEAGUE_ID}")
    users = {u["user_id"]: u for u in get(f"/league/{SLEEPER_LEAGUE_ID}/users")}
    rosters = get(f"/league/{SLEEPER_LEAGUE_ID}/rosters")
    by_rid = {r["roster_id"]: r for r in rosters}

    def team(r):
        u = users.get(r.get("owner_id"), {})
        return u.get("metadata", {}).get("team_name") or u.get("display_name") or f"Roster {r['roster_id']}"

    standings = []
    for r in rosters:
        s = r["settings"]
        standings.append({"roster_id": r["roster_id"], "team": team(r),
                          "owner": users.get(r.get("owner_id"), {}).get("display_name"),
                          "wins": s.get("wins", 0), "losses": s.get("losses", 0), "ties": s.get("ties", 0),
                          "pf": round(s.get("fpts", 0) + s.get("fpts_decimal", 0) / 100, 2),
                          "pa": round(s.get("fpts_against", 0) + s.get("fpts_against_decimal", 0) / 100, 2),
                          "record": f"{s.get('wins', 0)}-{s.get('losses', 0)}" + (f"-{s['ties']}" if s.get("ties") else ""),
                          "is_me": r.get("owner_id") == USER_ID})
    standings.sort(key=lambda x: (-x["wins"], x["losses"], -x["pf"]))
    for i, s in enumerate(standings, 1):
        s["rank"] = i
    me = next((s for s in standings if s["is_me"]), None)
    my_roster = next((r for r in rosters if r.get("owner_id") == USER_ID), None)
    if not my_roster:
        raise SystemExit("My roster not found in league")

    week_proj = projections(week, state.get("season"), PROJ_KEY.get(lg.get("scoring_settings", {}).get("rec"), "pts_ppr"))
    slots = [x for x in lg.get("roster_positions", []) if x != "BN"]
    starters = []
    for i, pid in enumerate(my_roster.get("starters", [])):
        if not pid or pid == "0":
            continue
        d = pinfo(pid, P)
        d["slot"] = slots[i] if i < len(slots) else d["pos"]
        starters.append(d)
    sset = set(my_roster.get("starters", []))
    reserve = set(my_roster.get("reserve") or [])
    bench = [pinfo(p, P) for p in my_roster.get("players", []) if p not in sset and p not in reserve]
    ir = [pinfo(p, P) for p in (my_roster.get("reserve") or [])]
    for d in bench:
        d["slot"] = "BN"
    for d in ir:
        d["slot"] = "IR"
    for d in starters + bench + ir:
        d["projection"] = week_proj.get(d["id"])

    matchup = None
    try:
        ms = get(f"/league/{SLEEPER_LEAGUE_ID}/matchups/{week}")
        mine = next((m for m in ms if m["roster_id"] == my_roster["roster_id"]), None)
        if mine:
            opp = next((m for m in ms if m["matchup_id"] == mine["matchup_id"] and m["roster_id"] != mine["roster_id"]), None)
            pp = mine.get("players_points") or {}
            for d in starters + bench:
                if d["id"] in pp:
                    d["score"] = pp[d["id"]]
            proj_total = lambda ids: round(sum(week_proj.get(p, 0) or 0 for p in ids if p and p != "0"), 1) if week_proj else None
            opp_s = (opp or {}).get("starters", [])
            matchup = {"week": week, "my_points": mine.get("points"),
                       "opponent": team(by_rid[opp["roster_id"]]) if opp else None,
                       "opponent_record": (lambda s: f"{s['wins']}-{s['losses']}" + (f"-{s['ties']}" if s.get("ties") else ""))(by_rid[opp["roster_id"]]["settings"]) if opp else None,
                       "opponent_points": opp.get("points") if opp else None,
                       "my_projection": proj_total(mine.get("starters", [])),
                       "opponent_projection": proj_total(opp_s) if opp else None,
                       "opponent_starters": [pinfo(p, P) for p in opp_s if p and p != "0"]}
    except Exception as e:
        matchup = {"week": week, "error": str(e)}

    rec = f"{me['wins']}-{me['losses']}" + (f"-{me['ties']}" if me["ties"] else "")
    return {"platform": "Sleeper", "name": f"{lg['name']} {lg.get('season','')}".strip(), "league_id": SLEEPER_LEAGUE_ID,
            "team_name": me["team"], "record": rec,
            "standing": f"{me['rank']} of {len(standings)}",
            "status": "live", "league_status": lg.get("status"),
            "week": week, "season": state.get("season"),
            "scoring": lg.get("scoring_settings", {}).get("rec"),
            "source": "Sleeper API (live)", "last_updated": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
            "standings_columns": [["rank", "#"], ["team", "Team"], ["record", "W-L"], ["pf", "PF"], ["pa", "PA"]],
            "standings": standings, "my_roster": {"starters": starters, "bench": bench, "ir": ir},
            "matchup": matchup}


def main():
    DATA.mkdir(exist_ok=True)
    if "--refresh-players" in sys.argv:
        players(True)
    doc = json.loads(LEAGUES.read_text()) if LEAGUES.exists() else {"leagues": default_leagues()}
    live = build_sleeper()  # raises before anything is written if Sleeper is unreachable
    out, replaced = [], False
    for l in doc["leagues"]:
        if l["platform"] == "Sleeper" and l["league_id"] == SLEEPER_LEAGUE_ID:
            out.append(live); replaced = True  # only the Sleeper entry is overwritten
        else:
            out.append(l)  # ESPN / Yahoo entries (and their last_updated) are preserved as-is
    if not replaced:
        out.insert(0, live)
    doc.update({"user": {"sleeper_username": USERNAME, "sleeper_user_id": USER_ID},
                "generated": live["last_updated"], "leagues": out})
    doc.setdefault("schema_note", "status: live | pending import. Each league has last_updated.")
    LEAGUES.write_text(json.dumps(doc, indent=2))
    write_html(doc, ROOT / "index.html")
    print(f"Wrote {LEAGUES} and {ROOT/'index.html'} (Sleeper week {live['week']}, {live['record']}, {live['standing']})")


if __name__ == "__main__":
    main()
