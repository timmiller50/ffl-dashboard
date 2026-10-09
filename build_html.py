#!/usr/bin/env python3
"""Render data/leagues.json -> index.html (static, no JS, no external assets)."""
import html, json, re
from datetime import datetime, timezone
from pathlib import Path

ATTENTION = {"Q", "D", "O", "IR", "DTD"}  # Questionable, Doubtful, Out, Injured Reserve, Day-to-day
_INJ = {"questionable": "Q", "q": "Q", "doubtful": "D", "d": "D", "out": "O", "o": "O", "ir": "IR",
        "injured reserve": "IR", "dtd": "DTD", "day-to-day": "DTD", "pup": "PUP", "sus": "SUSP", "susp": "SUSP",
        "suspended": "SUSP", "na": None, "healthy": None, "active": None, "": None}


def norm_injury(raw):
    if raw is None:
        return None
    k = str(raw).strip().lower()
    if k in _INJ:
        return _INJ[k]
    return str(raw).strip().upper()


def esc(x):
    return html.escape("" if x is None else str(x))


def num(x, nd=1):
    if x is None or x == "":
        return "–"
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return esc(x)


def parse_ts(s):
    for fmt in ("%Y-%m-%d %H:%M:%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return None


def fmt_ts(s):
    d = parse_ts(s)
    return d.strftime("%b %-d, %H:%M UTC") if d else "unknown"


def ts_tag(s):
    d = parse_ts(s)
    return f'<time datetime="{esc(d.strftime("%Y-%m-%dT%H:%M:%SZ"))}">{esc(fmt_ts(s))}</time>' if d else "unknown"


def inj_of(p):
    if "injury" in p:
        return p["injury"]
    return norm_injury(p.get("injury_status"))


def badge(code):
    if not code:
        return '<span class="b ok">OK</span>'
    return f'<span class="b inj-{esc(code)}">{esc(code)}</span>'


def split_roster(l):
    r = l.get("my_roster") or {}
    return r.get("starters", []), r.get("bench", []), r.get("ir", [])


def attention_items(leagues):
    items = []
    for l in leagues:
        if l.get("status") != "live":
            continue
        for p in split_roster(l)[0]:
            c = inj_of(p)
            if c in ATTENTION:
                items.append((l, p, c))
    order = {"O": 0, "IR": 0, "D": 1, "Q": 2, "DTD": 2}
    items.sort(key=lambda t: (order.get(t[2], 3), t[0]["name"]))
    return items


def roster_table(ps, show_proj, show_pts):
    if not ps:
        return '<p class="muted">None</p>'
    head = '<th>Slot</th><th>Player</th><th>Status</th>' + ('<th class="n">Proj</th>' if show_proj else '') + ('<th class="n">Pts</th>' if show_pts else '')
    rows = []
    for p in ps:
        c = inj_of(p)
        slot = p.get("slot") or p.get("pos") or ""
        body = p.get("injury_body_part")
        extra = f' <span class="muted">({esc(body)})</span>' if body and c else ""
        rows.append(f'<tr class="{"flag" if c in ATTENTION else ""}"><td class="slot">{esc(slot)}</td>'
                    f'<td>{esc(p["name"])} <small>{esc(p.get("pos") if p.get("pos") != slot else "")} {esc(p.get("team"))}</small></td>'
                    f'<td>{badge(c)}{extra}</td>'
                    + (f'<td class="n">{num(p.get("projection"))}</td>' if show_proj else '')
                    + (f'<td class="n">{num(p.get("score"))}</td>' if show_pts else '') + '</tr>')
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def standings_table(l):
    cols = l.get("standings_columns") or [["rank", "#"], ["team", "Team"], ["record", "W-L"], ["pf", "PF"], ["pa", "PA"]]
    head = "".join(f'<th class="{"n" if k not in ("rank", "team", "record", "streak") else ""}">{esc(lbl)}</th>' for k, lbl in cols)
    rows = []
    for s in l.get("standings", []):
        tds = []
        for k, _ in cols:
            v = s.get(k)
            if k == "record" and v is None and "wins" in s:
                v = f'{s["wins"]}-{s["losses"]}' + (f'-{s["ties"]}' if s.get("ties") else "")
            if k == "team":
                tds.append(f'<td>{esc(v)}</td>')
            elif k in ("rank", "record", "streak"):
                tds.append(f'<td>{esc(v)}</td>')
            else:
                tds.append(f'<td class="n">{num(v, 2 if k in ("pf", "pa", "season_pts") else 1)}</td>')
        rows.append(f'<tr class="{"me" if s.get("is_me") else ""}">{"".join(tds)}</tr>')
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def matchup_block(l):
    m = l.get("matchup") or {}
    if not m.get("opponent"):
        return f'<p class="muted">Week {esc(m.get("week"))}: no matchup data {esc(m.get("error", ""))}</p>'
    mp, op = m.get("my_points"), m.get("opponent_points")
    jp, jo = m.get("my_projection"), m.get("opponent_projection")
    try:
        lead = "me" if float(mp) > float(op) else "opp" if float(op) > float(mp) else ""
    except (TypeError, ValueError):
        lead = ""
    def side(cls, name, pts, proj, sub=None, wp=None):
        return (f'<div class="side {cls}"><div class="tn">{esc(name)}</div>'
                f'<div class="pts">{num(pts, 2)}</div>'
                f'<div class="proj">proj {num(proj)}</div>'
                + (f'<div class="sub">{esc(sub)}</div>' if sub else '') + (f'<div class="sub">{esc(wp)}</div>' if wp else '') + '</div>')
    me = side("me" + (" lead" if lead == "me" else ""), l.get("team_name"), mp, jp, None, m.get("my_win_prob"))
    opp = side("opp" + (" lead" if lead == "opp" else ""), m.get("opponent"), op, jo,
               m.get("opponent_record") or (f'mgr {m["opponent_manager"]}' if m.get("opponent_manager") else None), m.get("opponent_win_prob"))
    meta = " · ".join(x for x in [m.get("dates"), m.get("status")] if x)
    note = f'<p class="muted small">{esc(m.get("note"))}</p>' if m.get("note") else ""
    return f'<div class="vs">{me}<div class="at">vs</div>{opp}</div>' + (f'<p class="muted small">{esc(meta)}</p>' if meta else "") + note


def survivor_block(l):
    s = l.get("survivor")
    if not s:
        return ""
    alive = s.get("alive")
    cls = "alive" if alive else "dead"
    txt = ("ALIVE" if alive else "ELIMINATED") + (f' · {esc(s.get("status_label"))}' if s.get("status_label") else "")
    elim = "".join(f'<li><b>Week {e["week"]}</b>: {esc(e["team"])} <span class="muted">({num(e.get("season_pts"), 2)} pts)</span></li>' for e in s.get("eliminated", []))
    return (f'<div class="surv {cls}"><div class="big">{txt}</div>'
            f'<div>{esc(s.get("teams_remaining"))} of {esc(s.get("teams_total"))} teams remaining · {esc(s.get("teams_eliminated"))} eliminated</div>'
            f'{"<div class=muted>" + esc(l.get("format")) + "</div>" if l.get("format") else ""}</div>'
            f'<details><summary>Eliminated teams ({len(s.get("eliminated", []))})</summary><ul class="elim">{elim}</ul>'
            + (f'<p class="muted small">Standings as of {esc(s.get("source_updated"))}</p>' if s.get("source_updated") else "") + '</details>')


PRIORITY = ["43670", "135402", "1401978044331089922"]  # No Strategy, Derelict, Megalabowl first
SLUGS = {"43670": "no-strategy", "135402": "derelict", "1401978044331089922": "megalabowl",
         "1121237090": "buffalo-gridiron", "689864242": "seattle-pro-h2h", "1599505": "yahoo-death"}


def lid(l):
    return str(l.get("league_id") or l.get("id"))


def slug(l):
    if lid(l) in SLUGS:
        return SLUGS[lid(l)]
    return re.sub(r"[^a-z0-9]+", "-", str(l.get("name", "")).lower()).strip("-") or f"league-{lid(l)}"


def page_href(l, prefix="league/"):
    return f"{prefix}{slug(l)}.html"


def order_leagues(leagues):
    return sorted(leagues, key=lambda l: PRIORITY.index(lid(l)) if lid(l) in PRIORITY else len(PRIORITY))


def card(l):
    live = l.get("status") == "live"
    plat = esc(l["platform"])
    head = (f'<div class="chead"><span class="plat p-{plat.lower()}">{plat}</span>'
            f'<h2>{"<a class=tl href=" + chr(34) + esc(page_href(l)) + chr(34) + ">" + esc(l["name"]) + "</a>" if live else esc(l["name"])}</h2></div>')
    if not live:
        return f'<section class="card pending">{head}<p class="pend">Pending import</p></section>'
    st, bn, ir = split_roster(l)
    has_proj = any(p.get("projection") is not None for p in st + bn + ir)
    has_pts = any(p.get("score") is not None for p in st + bn + ir)
    flagged = sum(1 for p in st if inj_of(p) in ATTENTION)
    ts = l.get("last_updated") or l.get("updated")
    flag_txt = f' · <span class="warn">{flagged} starter{"s" if flagged != 1 else ""} flagged</span>' if flagged else ""
    stats = (f'<div class="stats"><div><span>Team</span><b>{esc(l.get("team_name"))}</b></div>'
             f'<div><span>Record</span><b>{esc(l.get("record") or "–")}</b></div>'
             f'<div><span>Standing</span><b>{esc(l.get("standing") or "–")}</b></div></div>')
    return (f'<section class="card live">{head}{stats}{survivor_block(l)}'
            f'<details open><summary>Week {esc((l.get("matchup") or {}).get("week") or l.get("week"))} matchup</summary>{matchup_block(l)}</details>'
            f'<details><summary>Standings ({len(l.get("standings", []))} teams)</summary>{standings_table(l)}</details>'
            f'<details open><summary>My roster{flag_txt}</summary>'
            f'<h4>Starters</h4>{roster_table(st, has_proj, has_pts)}'
            f'<h4>Bench</h4>{roster_table(bn, has_proj, has_pts)}'
            + (f'<h4>Injured reserve</h4>{roster_table(ir, has_proj, has_pts)}' if ir else '') + '</details>'
            f'<p class="upd">{esc(l.get("source") or l["platform"])} · updated {ts_tag(ts)}</p>'
            f'<a class="open" href="{esc(page_href(l))}">Open full view &rarr;</a></section>')


def detail_page(l, doc):
    plat = esc(l["platform"])
    st, bn, ir = split_roster(l)
    has_proj = any(p.get("projection") is not None for p in st + bn + ir)
    has_pts = any(p.get("score") is not None for p in st + bn + ir)
    flagged = sum(1 for p in st if inj_of(p) in ATTENTION)
    ts = l.get("last_updated") or l.get("updated")
    m = l.get("matchup") or {}
    wk = m.get("week") or l.get("week")
    stats = (f'<div class="stats four"><div><span>Team</span><b>{esc(l.get("team_name"))}</b></div>'
             f'<div><span>Record</span><b>{esc(l.get("record") or "–")}</b></div>'
             f'<div><span>Standing</span><b>{esc(l.get("standing") or "–")}</b></div>'
             f'<div><span>Flagged starters</span><b>{flagged}</b></div></div>')
    flag_txt = f' · <span class="warn">{flagged} starter{"s" if flagged != 1 else ""} flagged</span>' if flagged else ""
    body = (f'<a class="back" href="../index.html">&lt; Back to dashboard</a>'
            f'<header class="dh"><div class="chead"><span class="plat p-{plat.lower()}">{plat}</span><h1>{esc(l["name"])}</h1></div>'
            f'<div class="updated"><span>Last updated: <b>{ts_tag(ts)}</b></span><span>Built: <b>{ts_tag(doc.get("generated"))}</b></span></div></header>'
            f'{stats}{survivor_block(l)}'
            f'<section class="panel"><h3>Week {esc(wk)} matchup</h3>{matchup_block(l)}</section>'
            f'<section class="panel"><h3>Standings ({len(l.get("standings", []))} teams)</h3>{standings_table(l)}</section>'
            f'<section class="panel"><h3>My roster{flag_txt}</h3>'
            f'<h4>Starters</h4>{roster_table(st, has_proj, has_pts)}'
            f'<h4>Bench</h4>{roster_table(bn, has_proj, has_pts)}'
            + (f'<h4>Injured reserve</h4>{roster_table(ir, has_proj, has_pts)}' if ir else '') + '</section>'
            f'<p class="upd">{esc(l.get("source") or l["platform"])} · updated {ts_tag(ts)} · times are UTC</p>'
            f'<a class="back" href="../index.html">&lt; Back to dashboard</a>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(l["name"])} · FFL Dashboard</title><style>{CSS}</style></head><body class="detail"><div class="wrap">'
            f'{body}</div></body></html>')


CSS = """
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:#0f1419;color:#e6e6e6;margin:0;padding:16px;line-height:1.35}
.wrap{max-width:1400px;margin:0 auto}
header{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:baseline;justify-content:space-between;margin-bottom:12px}
h1{margin:0;font-size:24px}h2{margin:0;font-size:18px}h4{margin:12px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#9ab}
.updated{display:flex;flex-wrap:wrap;gap:6px;font-size:12px}
.updated span{background:#1a2230;border:1px solid #2a3547;border-radius:999px;padding:3px 10px;color:#b8c4d4}
.updated b{color:#e6e6e6}
.attn{background:#2b2113;border:1px solid #8a4b12;border-left:5px solid #e0a030;border-radius:10px;padding:10px 14px;margin-bottom:16px}
.attn.clear{background:#13261d;border-color:#1f5f3f;border-left-color:#3ecf8e}
.attn h3{margin:0 0 6px;font-size:14px;text-transform:uppercase;letter-spacing:.05em;color:#f0c070}
.attn.clear h3{color:#7fe0b0}
.attn ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px}
.attn li{background:#1a2230;border-radius:8px;padding:5px 9px;font-size:13px}
.attn li small{color:#9ab}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,420px),1fr));gap:16px;align-items:start}
.card{background:#1a2230;border-radius:12px;padding:14px;border-top:4px solid #555;min-width:0}
.card.live{border-top-color:#3ecf8e}.card.pending{border-top-color:#e0a030;opacity:.85}
.chead{display:flex;gap:10px;align-items:center;margin-bottom:8px;flex-wrap:wrap}
.plat{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;border-radius:6px;padding:2px 7px;background:#334}
.p-sleeper{background:#1f4f8a}.p-espn{background:#8a1f2b}.p-yahoo{background:#5b2a8a}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:8px}
.stats div{background:#141b27;border-radius:8px;padding:6px 8px;min-width:0}
.stats span{display:block;font-size:11px;color:#9ab;text-transform:uppercase}
.stats b{font-size:14px;overflow-wrap:anywhere}
.surv{border-radius:8px;padding:8px 10px;margin:6px 0;font-size:13px}
.surv.alive{background:#13261d;border:1px solid #1f5f3f}.surv.dead{background:#2b1315;border:1px solid #8a1f2b}
.surv .big{font-size:18px;font-weight:800}
.elim{margin:6px 0 0;padding-left:18px;font-size:13px}
details{border-top:1px solid #2a3547;padding:4px 0}
summary{cursor:pointer;font-weight:600;padding:8px 0;font-size:14px}
.warn{color:#f0b060}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:13px}
th{font-size:11px;text-transform:uppercase;color:#9ab;font-weight:600}
td,th{padding:5px 6px;text-align:left;border-bottom:1px solid #2a3547;white-space:nowrap}
td:nth-child(2){white-space:normal}
.n{text-align:right;font-variant-numeric:tabular-nums}
td.slot{color:#9ab;font-size:12px;width:1%}
tr.me{background:#27406b}tr.flag{background:#2b2113}
small,.muted{color:#9ab}.small{font-size:12px;margin:4px 0}
.b{display:inline-block;padding:1px 7px;border-radius:8px;font-size:11px;font-weight:700;min-width:30px;text-align:center}
.ok{background:#1f5f3f;color:#bfeed5}
.inj-Q,.inj-DTD{background:#8a6a12;color:#fff1c0}.inj-D{background:#a8501a;color:#fff}
.inj-O,.inj-IR{background:#a62b2b;color:#fff}.inj-PUP,.inj-SUSP{background:#6a2a8a;color:#fff}
.vs{display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:stretch;margin:4px 0}
.side{background:#141b27;border-radius:8px;padding:8px;text-align:center;min-width:0;border:2px solid transparent}
.side.lead{border-color:#3ecf8e}
.side .tn{font-size:13px;font-weight:600;overflow-wrap:anywhere}
.side .pts{font-size:26px;font-weight:800;font-variant-numeric:tabular-nums}
.side .proj{font-size:12px;color:#9ab}.side .sub{font-size:11px;color:#9ab;margin-top:2px}
.at{align-self:center;color:#678;font-size:12px}
.pend{color:#e0a030;font-weight:700}.upd{color:#9ab;font-size:12px;margin:8px 0 0}
.tl{color:inherit;text-decoration:none;border-bottom:1px dashed #678}.tl:hover{color:#7fb8ff}
.open{display:block;margin-top:10px;text-align:center;background:#2b6cb0;color:#fff;font-weight:700;text-decoration:none;border-radius:8px;padding:10px;font-size:14px}
.open:hover{background:#3b82d0}
.back{display:inline-block;margin:0 0 12px;background:#2b6cb0;color:#fff;font-weight:700;text-decoration:none;border-radius:8px;padding:10px 16px;font-size:16px}
.back:hover{background:#3b82d0}
.dh{margin-bottom:12px}.dh h1{font-size:28px}
.stats.four{grid-template-columns:repeat(4,1fr)}
.panel{background:#1a2230;border-radius:12px;padding:14px;margin:0 0 14px}
.panel h3{margin:0 0 8px;font-size:16px}
body.detail table{font-size:14px}
footer{margin-top:20px;color:#678;font-size:12px}
@media(max-width:520px){.stats.four{grid-template-columns:repeat(2,1fr)}.dh h1{font-size:22px}body{padding:10px}h1{font-size:20px}.card{padding:12px}.side .pts{font-size:22px}.stats b{font-size:13px}td,th{padding:5px 4px}}
"""


def render(doc):
    leagues = doc["leagues"]
    leagues = order_leagues(leagues)
    live = [l for l in leagues if l.get("status") == "live"]
    # last-updated per platform (latest of its leagues)
    plat_ts = {}
    for l in leagues:
        t = parse_ts(l.get("last_updated") or l.get("updated"))
        if t and (l["platform"] not in plat_ts or t > plat_ts[l["platform"]]):
            plat_ts[l["platform"]] = t
    chips = "".join(f'<span>{esc(p)}: <b>{ts_tag(t.strftime("%Y-%m-%d %H:%M:%SZ"))}</b></span>' for p, t in plat_ts.items())
    chips += f'<span>Built: <b>{ts_tag(doc.get("generated"))}</b></span>'
    weeks = sorted({str(l.get("week")) for l in live if l.get("week")})
    items = attention_items(leagues)
    if items:
        lis = "".join(f'<li>{badge(c)} <b>{esc(p["name"])}</b> <small>{esc(p.get("slot") or p.get("pos"))} · {esc(l["name"])} ({esc(l["platform"])})</small></li>' for l, p, c in items)
        attn = f'<div class="attn"><h3>Needs attention · {len(items)} injured starter{"s" if len(items) != 1 else ""} (Q / D / O / IR / DTD)</h3><ul>{lis}</ul></div>'
    else:
        attn = '<div class="attn clear"><h3>Needs attention</h3><p style="margin:0">No injured starters across your leagues.</p></div>'
    user = doc.get("user", {}).get("sleeper_username", "")
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>FFL Dashboard</title><style>{CSS}</style></head><body><div class="wrap">'
            f'<header><div><h1>FFL Dashboard</h1><div class="muted small">{esc(user)} · {len(live)} of {len(leagues)} leagues live'
            f'{" · Week " + esc(", ".join(weeks)) if weeks else ""}</div></div><div class="updated">{chips}</div></header>'
            f'{attn}<div class="grid">{"".join(card(l) for l in leagues)}</div>'
            '<footer>Static page generated from data/leagues.json. Times are UTC.</footer></div></body></html>')


def write_html(doc, path):
    """Write index.html at `path` plus league/<slug>.html next to it (all leagues)."""
    path = Path(path)
    path.write_text(render(doc))
    out = path.parent / "league"
    out.mkdir(exist_ok=True)
    keep = set()
    for l in doc["leagues"]:
        if l.get("status") == "live":
            f = out / f"{slug(l)}.html"
            f.write_text(detail_page(l, doc))
            keep.add(f.name)
    for old in out.glob("*.html"):  # drop pages of leagues that no longer exist
        if old.name not in keep:
            old.unlink()


if __name__ == "__main__":
    root = Path(__file__).parent
    write_html(json.loads((root / "data" / "leagues.json").read_text()), root / "index.html")
