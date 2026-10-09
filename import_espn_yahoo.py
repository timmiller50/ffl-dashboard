#!/usr/bin/env python3
"""Merge data/espn_raw.json + data/yahoo_raw.json into data/leagues.json.

Replaces the ESPN/Yahoo entries (matched by platform + league_id) with normalized live data.
The Sleeper entry and entry order are preserved. Regenerates index.html.
Usage: python3 import_espn_yahoo.py
"""
import json, time
from datetime import datetime, timezone
from pathlib import Path
from build_html import write_html, norm_injury

ROOT = Path(__file__).parent
DATA = ROOT / "data"
LEAGUES = DATA / "leagues.json"
BENCH_SLOTS = {"bench", "bn"}
IR_SLOTS = {"ir", "ir+", "na"}


def mtime_iso(p):
    return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def f(x):
    try:
        return None if x in (None, "") else float(x)
    except (TypeError, ValueError):
        return None


def roster(rows):
    out = {"starters": [], "bench": [], "ir": []}
    for r in rows:
        slot = r.get("lineup_slot") or ""
        raw = r.get("injury_status")
        p = {"name": r["player_name"], "pos": r.get("position"), "team": (r.get("nfl_team") or "").upper() or None,
             "slot": slot, "injury": norm_injury(raw), "injury_raw": raw,
             "projection": f(r.get("projection", r.get("proj_pts"))), "score": f(r.get("score", r.get("fan_pts")))}
        s = slot.lower()
        out["ir" if s in IR_SLOTS else "bench" if s in BENCH_SLOTS else "starters"].append(p)
    return out


def wlt(w, l, t):
    return f"{w}-{l}" + (f"-{t}" if t else "")


def trim(rec):
    """'4-0-0' -> '4-0' (drop zero ties); leaves '2-1-1' alone."""
    return rec[:-2] if rec and rec.count("-") == 2 and rec.endswith("-0") else rec


def espn_entry(lid, d, ts, cfg):
    me = d["my_team"]
    standings = []
    for s in d["standings"]:
        standings.append({"rank": s["rank"], "team": s["team_name"], "record": wlt(s["wins"], s["losses"], s["ties"]),
                          "pf": s["points_for"], "is_me": s["team_name"] == me["team_name"]})
    m = d["current_matchup"]
    return {"platform": "ESPN", "name": d["league_name"], "league_id": lid, "team_id": me["team_id"],
            "team_name": me["team_name"], "record": trim(me["record"]),
            "standing": me["rank"], "status": "live", "season": str(d["season_id"]), "week": m["week"],
            "source": "ESPN (browser session import)", "last_updated": ts,
            "standings_columns": [["rank", "#"], ["team", "Team"], ["record", "W-L"], ["pf", "PF"]],
            "standings": standings, "my_roster": roster(d["roster"]),
            "matchup": {"week": m["week"], "opponent": m["opponent_team_name"], "opponent_record": ", ".join([trim(x) if i == 0 else x for i, x in enumerate((m.get("opponent_record") or "").split(", "))]) or None,
                        "my_points": m["my_score"], "opponent_points": m["opponent_score"],
                        "my_projection": m["my_projection_total"], "opponent_projection": m["opponent_projection_total"]}}


def yahoo_derelict(lid, d, ts):
    m = d["current_matchup"]
    standings = []
    for s in d["standings"]:
        standings.append({"rank": int(s["rank"]), "team": s["team_name"], "record": trim(s["w_l_t"]),
                          "pf": f(s["points_for"]), "pa": f(s["points_against"]), "streak": s["streak"],
                          "is_me": s["team_name"] == d["my_team_name"]})
    rec = trim(d["my_team_record"])
    return {"platform": "Yahoo", "name": d["league_name"], "league_id": lid, "team_name": d["my_team_name"],
            "record": rec, "standing": d["my_team_rank"] + f" of {len(standings)}", "status": "live", "season": d["season"],
            "week": m["week"], "source": "Yahoo (browser session import)", "last_updated": ts, "url": d.get("url"),
            "standings_columns": [["rank", "#"], ["team", "Team"], ["record", "W-L"], ["pf", "PF"], ["pa", "PA"], ["streak", "Strk"]],
            "standings": standings, "my_roster": roster(d["roster"]),
            "matchup": {"week": m["week"], "dates": m.get("week_dates"), "opponent": m["opponent_team_name"],
                        "opponent_manager": m.get("opponent_manager_name"),
                        "opponent_record": f"{trim(m['opponent_record'])}, {m['opponent_rank']}" if m.get("opponent_rank") else trim(m.get("opponent_record")),
                        "my_points": f(m["my_score"]), "opponent_points": f(m["opponent_score"]),
                        "my_projection": f(m["my_live_proj"]), "opponent_projection": f(m["opponent_live_proj"]),
                        "my_win_prob": m.get("my_win_probability_label"), "opponent_win_prob": m.get("opponent_win_probability_label"),
                        "players_remaining": m.get("my_players_remaining"), "opponent_players_remaining": m.get("opponent_players_remaining"),
                        "note": m.get("note")}}


def yahoo_death(lid, d, ts):
    sv, m = d["survivor_status"], d["current_matchup"]
    standings = []
    for s in sorted(d["standings"], key=lambda x: int(x["rank"])):
        standings.append({"rank": int(s["rank"]), "team": s["team_name"], "season_pts": f(s["season_points"]),
                          "week_pts": f(s["points_this_week"]), "proj": f(s["projected_points"]),
                          "ppw": f(s["pts_per_week"]), "is_me": s["team_name"] == d["my_team_name"]})
    elim = [{"week": int(e["week"]), "team": e["team_name"], "season_pts": f(e["season_points"])}
            for e in sorted(d["eliminated_teams"], key=lambda e: int(e["week"]))]
    total = sv["remaining_teams_count"] + sv["eliminated_teams_count"]
    label = sv["status_label"]
    return {"platform": "Yahoo", "name": d["league_name"], "league_id": lid, "team_name": d["my_team_name"],
            "record": ("Alive" if sv["alive"] else "Eliminated") + (f" ({label})" if label else ""),
            "standing": f"{d['my_team_rank']} of {sv['remaining_teams_count']} alive", "status": "live", "season": d["season"],
            "week": m["week"], "source": "Yahoo (browser session import)", "last_updated": ts, "url": d.get("url"),
            "format": "Guillotine / elimination: lowest-scoring team is removed each week",
            "standings_columns": [["rank", "#"], ["team", "Team"], ["season_pts", "Season"], ["week_pts", "Wk pts"], ["proj", "Proj"]],
            "standings": standings, "my_roster": roster(d["roster"]),
            "survivor": {"alive": sv["alive"], "status_label": label, "teams_remaining": sv["remaining_teams_count"],
                         "teams_eliminated": sv["eliminated_teams_count"], "teams_total": total, "eliminated": elim,
                         "source_updated": sv.get("last_standings_update")},
            "matchup": {"week": m["week"], "dates": m.get("week_dates"), "status": m.get("status"), "opponent": m["opponent_team_name"],
                        "opponent_manager": m.get("opponent_manager_name"), "opponent_record": None,
                        "my_points": f(m["my_score"]), "opponent_points": f(m["opponent_score"]),
                        "my_projection": f(m["my_proj_matchup_page"]), "opponent_projection": f(m["opponent_proj_matchup_page"]),
                        "note": m.get("note")}}


def main():
    espn_p, yahoo_p = DATA / "espn_raw.json", DATA / "yahoo_raw.json"
    espn, yahoo = json.loads(espn_p.read_text()), json.loads(yahoo_p.read_text())
    ets, yts = mtime_iso(espn_p), mtime_iso(yahoo_p)
    new = {("ESPN", k): espn_entry(k, v, ets, None) for k, v in espn.items()}
    new[("Yahoo", "135402")] = yahoo_derelict("135402", yahoo["135402"], yts)
    new[("Yahoo", "1599505")] = yahoo_death("1599505", yahoo["1599505"], yts)
    doc = json.loads(LEAGUES.read_text())
    out = []
    for l in doc["leagues"]:
        key = (l["platform"], l["league_id"])
        out.append(new.pop(key, l))
    out.extend(new.values())  # any league not previously listed
    doc["leagues"] = out
    doc["generated"] = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    doc["schema_note"] = ("status: live | pending import. Each league has last_updated. Sleeper is refreshed by refresh_sleeper.py "
                          "(only the Sleeper entry is overwritten); ESPN/Yahoo are imported from data/*_raw.json by import_espn_yahoo.py.")
    LEAGUES.write_text(json.dumps(doc, indent=2))
    write_html(doc, ROOT / "index.html")
    print("Merged", len(out), "leagues ->", LEAGUES)


if __name__ == "__main__":
    main()
