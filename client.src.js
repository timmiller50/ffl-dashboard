/* FFL dashboard client: Refresh button. Inlined into every page by build_html.py (no external assets).
   Renderers below mirror build_html.py; the pre-rendered HTML is the no-JS fallback. */
(function () {
  'use strict';
  var CFG = window.FFL_CFG || {};
  var ATTN = { Q: 1, D: 1, O: 1, IR: 1, DTD: 1 };
  var INJ = { questionable: 'Q', q: 'Q', doubtful: 'D', d: 'D', out: 'O', o: 'O', ir: 'IR', 'injured reserve': 'IR',
    dtd: 'DTD', 'day-to-day': 'DTD', pup: 'PUP', sus: 'SUSP', susp: 'SUSP', suspended: 'SUSP', na: null, healthy: null, active: null, '': null };
  var doc = null;           // last doc loaded from data/leagues.json (+ live Sleeper overlay)
  var liveInfo = null;      // {at: Date} when the Sleeper overlay succeeded
  var busy = false;

  /* ---------- helpers ---------- */
  function esc(x) {
    return (x == null ? '' : String(x)).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
  }
  function num(x, nd) {
    if (x == null || x === '') return '–';
    var f = Number(x);
    if (!isFinite(f)) return esc(x);
    return f.toFixed(nd == null ? 1 : nd);
  }
  function parseTs(s) {
    var m = /^(\d{4})-(\d\d)-(\d\d)[ T](\d\d):(\d\d):(\d\d)Z$/.exec(s || '');
    return m ? new Date(Date.UTC(+m[1], m[2] - 1, +m[3], +m[4], +m[5], +m[6])) : null;
  }
  function isoZ(d) { return d.toISOString().replace(/\.\d+Z$/, 'Z'); }
  function stampZ(d) { return isoZ(d).replace('T', ' '); }
  function fmtLocal(d) {
    try { return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); }
    catch (e) { return d.toISOString(); }
  }
  function ago(d) {
    var s = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000));
    if (s < 60) return 'just now';
    if (s < 3600) return Math.floor(s / 60) + 'm ago';
    if (s < 86400) return Math.floor(s / 3600) + 'h ago';
    return Math.floor(s / 86400) + 'd ago';
  }
  function tsTag(s) {
    var d = parseTs(s);
    return d ? '<time datetime="' + esc(isoZ(d)) + '">' + esc(fmtLocal(d)) + '</time>' : 'unknown';
  }
  function normInjury(raw) {
    if (raw == null) return null;
    var k = String(raw).trim().toLowerCase();
    if (Object.prototype.hasOwnProperty.call(INJ, k)) return INJ[k];
    return String(raw).trim().toUpperCase();
  }
  function injOf(p) { return ('injury' in p) ? p.injury : normInjury(p.injury_status); }
  function badge(c) { return c ? '<span class="b inj-' + esc(c) + '">' + esc(c) + '</span>' : '<span class="b ok">OK</span>'; }
  function splitRoster(l) { var r = l.my_roster || {}; return [r.starters || [], r.bench || [], r.ir || []]; }
  function lid(l) { return String(l.league_id != null ? l.league_id : l.id); }
  function slug(l) {
    if (CFG.slugs && CFG.slugs[lid(l)]) return CFG.slugs[lid(l)];
    return String(l.name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'league-' + lid(l);
  }
  function pageHref(l) { return 'league/' + slug(l) + '.html'; }
  function orderLeagues(ls) {
    var pr = CFG.priority || [];
    function ix(l) { var i = pr.indexOf(lid(l)); return i < 0 ? pr.length : i; }
    return ls.slice().sort(function (a, b) { return ix(a) - ix(b); });
  }

  /* ---------- renderers (mirror build_html.py) ---------- */
  function attentionItems(leagues) {
    var items = [];
    leagues.forEach(function (l) {
      if (l.status !== 'live') return;
      splitRoster(l)[0].forEach(function (p) { var c = injOf(p); if (ATTN[c]) items.push([l, p, c]); });
    });
    var ord = { O: 0, IR: 0, D: 1, Q: 2, DTD: 2 };
    items.sort(function (a, b) {
      var x = ord[a[2]] == null ? 3 : ord[a[2]], y = ord[b[2]] == null ? 3 : ord[b[2]];
      return x - y || (a[0].name < b[0].name ? -1 : a[0].name > b[0].name ? 1 : 0);
    });
    return items;
  }
  function rosterTable(ps, showProj, showPts) {
    if (!ps.length) return '<p class="muted">None</p>';
    var head = '<th>Slot</th><th>Player</th><th>Status</th>' + (showProj ? '<th class="n">Proj</th>' : '') + (showPts ? '<th class="n">Pts</th>' : '');
    var rows = ps.map(function (p) {
      var c = injOf(p), slot = p.slot || p.pos || '', body = p.injury_body_part;
      var extra = body && c ? ' <span class="muted">(' + esc(body) + ')</span>' : '';
      return '<tr class="' + (ATTN[c] ? 'flag' : '') + '"><td class="slot">' + esc(slot) + '</td>' +
        '<td>' + esc(p.name) + ' <small>' + esc(p.pos !== slot ? p.pos : '') + ' ' + esc(p.team) + '</small></td>' +
        '<td>' + badge(c) + extra + '</td>' +
        (showProj ? '<td class="n">' + num(p.projection) + '</td>' : '') +
        (showPts ? '<td class="n">' + num(p.score) + '</td>' : '') + '</tr>';
    });
    return '<div class="tw"><table><thead><tr>' + head + '</tr></thead><tbody>' + rows.join('') + '</tbody></table></div>';
  }
  function standingsTable(l) {
    var cols = l.standings_columns || [['rank', '#'], ['team', 'Team'], ['record', 'W-L'], ['pf', 'PF'], ['pa', 'PA']];
    var plain = { rank: 1, team: 1, record: 1, streak: 1 };
    var head = cols.map(function (c) { return '<th class="' + (plain[c[0]] ? '' : 'n') + '">' + esc(c[1]) + '</th>'; }).join('');
    var rows = (l.standings || []).map(function (s) {
      var tds = cols.map(function (c) {
        var k = c[0], v = s[k];
        if (k === 'record' && v == null && 'wins' in s) v = s.wins + '-' + s.losses + (s.ties ? '-' + s.ties : '');
        if (plain[k]) return '<td>' + esc(v) + '</td>';
        return '<td class="n">' + num(v, (k === 'pf' || k === 'pa' || k === 'season_pts') ? 2 : 1) + '</td>';
      }).join('');
      return '<tr class="' + (s.is_me ? 'me' : '') + '">' + tds + '</tr>';
    }).join('');
    return '<div class="tw"><table><thead><tr>' + head + '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  }
  function matchupBlock(l) {
    var m = l.matchup || {};
    if (!m.opponent) return '<p class="muted">Week ' + esc(m.week) + ': no matchup data ' + esc(m.error || '') + '</p>';
    var mp = m.my_points, op = m.opponent_points, lead = '';
    if (mp != null && op != null && isFinite(Number(mp)) && isFinite(Number(op))) lead = Number(mp) > Number(op) ? 'me' : Number(op) > Number(mp) ? 'opp' : '';
    function side(cls, name, pts, proj, sub, wp) {
      return '<div class="side ' + cls + '"><div class="tn">' + esc(name) + '</div><div class="pts">' + num(pts, 2) + '</div>' +
        '<div class="proj">proj ' + num(proj) + '</div>' + (sub ? '<div class="sub">' + esc(sub) + '</div>' : '') + (wp ? '<div class="sub">' + esc(wp) + '</div>' : '') + '</div>';
    }
    var me = side('me' + (lead === 'me' ? ' lead' : ''), l.team_name, mp, m.my_projection, null, m.my_win_prob);
    var opp = side('opp' + (lead === 'opp' ? ' lead' : ''), m.opponent, op, m.opponent_projection,
      m.opponent_record || (m.opponent_manager ? 'mgr ' + m.opponent_manager : null), m.opponent_win_prob);
    var meta = [m.dates, m.status].filter(Boolean).join(' · ');
    var note = m.note ? '<p class="muted small">' + esc(m.note) + '</p>' : '';
    return '<div class="vs">' + me + '<div class="at">vs</div>' + opp + '</div>' + (meta ? '<p class="muted small">' + esc(meta) + '</p>' : '') + note;
  }
  function survivorBlock(l) {
    var s = l.survivor;
    if (!s) return '';
    var cls = s.alive ? 'alive' : 'dead';
    var txt = (s.alive ? 'ALIVE' : 'ELIMINATED') + (s.status_label ? ' · ' + esc(s.status_label) : '');
    var el = s.eliminated || [];
    var elim = el.map(function (e) { return '<li><b>Week ' + esc(e.week) + '</b>: ' + esc(e.team) + ' <span class="muted">(' + num(e.season_pts, 2) + ' pts)</span></li>'; }).join('');
    return '<div class="surv ' + cls + '"><div class="big">' + txt + '</div>' +
      '<div>' + esc(s.teams_remaining) + ' of ' + esc(s.teams_total) + ' teams remaining · ' + esc(s.teams_eliminated) + ' eliminated</div>' +
      (l.format ? '<div class="muted">' + esc(l.format) + '</div>' : '') + '</div>' +
      '<details data-k="' + esc(lid(l)) + ':elim"><summary>Eliminated teams (' + el.length + ')</summary><ul class="elim">' + elim + '</ul>' +
      (s.source_updated ? '<p class="muted small">Standings as of ' + esc(s.source_updated) + '</p>' : '') + '</details>';
  }
  function rosterParts(l) {
    var r = splitRoster(l), all = r[0].concat(r[1], r[2]);
    function any(k) { return all.some(function (p) { return p[k] != null; }); }
    return { st: r[0], bn: r[1], ir: r[2], proj: any('projection'), pts: any('score'),
      flagged: r[0].filter(function (p) { return ATTN[injOf(p)]; }).length };
  }
  function flagTxt(n) { return n ? ' · <span class="warn">' + n + ' starter' + (n !== 1 ? 's' : '') + ' flagged</span>' : ''; }
  function rosterHtml(r) {
    return '<h4>Starters</h4>' + rosterTable(r.st, r.proj, r.pts) + '<h4>Bench</h4>' + rosterTable(r.bn, r.proj, r.pts) +
      (r.ir.length ? '<h4>Injured reserve</h4>' + rosterTable(r.ir, r.proj, r.pts) : '');
  }
  function card(l) {
    var live = l.status === 'live', plat = esc(l.platform);
    var head = '<div class="chead"><span class="plat p-' + plat.toLowerCase() + '">' + plat + '</span><h2>' +
      (live ? '<a class="tl" href="' + esc(pageHref(l)) + '">' + esc(l.name) + '</a>' : esc(l.name)) + '</h2></div>';
    if (!live) return '<section class="card pending">' + head + '<p class="pend">Pending import</p></section>';
    var r = rosterParts(l), ts = l.last_updated || l.updated, m = l.matchup || {}, k = esc(lid(l));
    var stats = '<div class="stats"><div><span>Team</span><b>' + esc(l.team_name) + '</b></div><div><span>Record</span><b>' + esc(l.record || '–') +
      '</b></div><div><span>Standing</span><b>' + esc(l.standing || '–') + '</b></div></div>';
    return '<section class="card live">' + head + stats + survivorBlock(l) +
      '<details open data-k="' + k + ':matchup"><summary>Week ' + esc(m.week || l.week) + ' matchup</summary>' + matchupBlock(l) + '</details>' +
      '<details data-k="' + k + ':standings"><summary>Standings (' + (l.standings || []).length + ' teams)</summary>' + standingsTable(l) + '</details>' +
      '<details open data-k="' + k + ':roster"><summary>My roster' + flagTxt(r.flagged) + '</summary>' + rosterHtml(r) + '</details>' +
      '<p class="upd">' + esc(l.source || l.platform) + ' · updated ' + tsTag(ts) + '</p>' +
      '<a class="open" href="' + esc(pageHref(l)) + '">Open full view &rarr;</a></section>';
  }
  function detailBody(l) {
    var r = rosterParts(l), ts = l.last_updated || l.updated, m = l.matchup || {}, wk = m.week || l.week;
    var stats = '<div class="stats four"><div><span>Team</span><b>' + esc(l.team_name) + '</b></div><div><span>Record</span><b>' + esc(l.record || '–') +
      '</b></div><div><span>Standing</span><b>' + esc(l.standing || '–') + '</b></div><div><span>Flagged starters</span><b>' + r.flagged + '</b></div></div>';
    return stats + survivorBlock(l) +
      '<section class="panel"><h3>Week ' + esc(wk) + ' matchup</h3>' + matchupBlock(l) + '</section>' +
      '<section class="panel"><h3>Standings (' + (l.standings || []).length + ' teams)</h3>' + standingsTable(l) + '</section>' +
      '<section class="panel"><h3>My roster' + flagTxt(r.flagged) + '</h3>' + rosterHtml(r) + '</section>' +
      '<p class="upd">' + esc(l.source || l.platform) + ' · updated ' + tsTag(ts) + '</p>';
  }
  function attentionHtml(leagues) {
    var items = attentionItems(leagues);
    if (!items.length) return '<div class="attn clear"><h3>Needs attention</h3><p style="margin:0">No injured starters across your leagues.</p></div>';
    var lis = items.map(function (t) {
      var l = t[0], p = t[1];
      return '<li>' + badge(t[2]) + ' <b>' + esc(p.name) + '</b> <small>' + esc(p.slot || p.pos) + ' · ' + esc(l.name) + ' (' + esc(l.platform) + ')</small></li>';
    }).join('');
    return '<div class="attn"><h3>Needs attention · ' + items.length + ' injured starter' + (items.length !== 1 ? 's' : '') + ' (Q / D / O / IR / DTD)</h3><ul>' + lis + '</ul></div>';
  }
  function subtitle(d, leagues) {
    var live = leagues.filter(function (l) { return l.status === 'live'; });
    var seen = {}, weeks = [];
    live.forEach(function (l) { if (l.week && !seen[l.week]) { seen[l.week] = 1; weeks.push(String(l.week)); } });
    weeks.sort();
    return esc((d.user || {}).sleeper_username || '') + ' · ' + live.length + ' of ' + leagues.length + ' leagues live' + (weeks.length ? ' · Week ' + esc(weeks.join(', ')) : '');
  }
  function chipsHtml(d, leagues) {
    var order = [], best = {};
    leagues.forEach(function (l) {
      var t = parseTs(l.last_updated || l.updated);
      if (!t) return;
      if (!best[l.platform]) { best[l.platform] = t; order.push(l.platform); } else if (t > best[l.platform]) best[l.platform] = t;
    });
    var h = '<span class="lbl">Last pulled:</span>';
    order.forEach(function (p) {
      var t = best[p], isLive = p === 'Sleeper' && liveInfo;
      h += '<span data-plat="' + esc(p) + '">' + esc(p) + ': <b>' + tsTag(stampZ(t)) + '</b> <small>' + (isLive ? 'live · ' : '') + esc(ago(t)) + '</small></span>';
    });
    return h + '<span data-built="1">Built: <b>' + tsTag(d.generated) + '</b></span>';
  }

  /* ---------- DOM ---------- */
  function $(id) { return document.getElementById(id); }
  function renderAll() {
    if (!doc || !Array.isArray(doc.leagues)) return;
    var leagues = orderLeagues(doc.leagues);
    var open = {};
    [].forEach.call(document.querySelectorAll('details[data-k]'), function (d) { open[d.getAttribute('data-k')] = d.open; });
    if (CFG.page === 'index') {
      $('sub').innerHTML = subtitle(doc, leagues);
      $('attn-wrap').innerHTML = attentionHtml(leagues);
      $('grid').innerHTML = leagues.map(card).join('');
    } else {
      var l = leagues.filter(function (x) { return lid(x) === CFG.lid && x.status === 'live'; })[0];
      if (l) $('dbody').innerHTML = detailBody(l);
    }
    [].forEach.call(document.querySelectorAll('details[data-k]'), function (d) {
      var k = d.getAttribute('data-k');
      if (Object.prototype.hasOwnProperty.call(open, k)) d.open = open[k];
    });
    renderChips();
  }
  function renderChips() {
    var c = $('chips');
    if (c && doc && Array.isArray(doc.leagues)) c.innerHTML = chipsHtml(doc, orderLeagues(doc.leagues));
  }
  function localizeStatic() {  // pre-rendered times are UTC; show them in local time
    [].forEach.call(document.querySelectorAll('time[datetime]'), function (t) {
      var d = new Date(t.getAttribute('datetime'));
      if (!isNaN(d)) t.textContent = fmtLocal(d);
    });
  }
  function setStatus(msg, cls) { var s = $('rstatus'); if (s) { s.textContent = msg; s.className = 'rstatus' + (cls ? ' s-' + cls : ''); } }

  /* ---------- data ---------- */
  function timed(url, ms, opts) {
    var ctl = typeof AbortController === 'function' ? new AbortController() : null;
    var t = setTimeout(function () { if (ctl) ctl.abort(); }, ms);
    var o = { cache: 'no-store' };
    if (ctl) o.signal = ctl.signal;
    return fetch(url, o).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (j) { clearTimeout(t); return j; }, function (e) { clearTimeout(t); throw e; });
  }
  function loadDoc() {
    return timed(CFG.dataUrl + '?_=' + Date.now(), 15000).then(function (d) {
      if (!d || !Array.isArray(d.leagues)) throw new Error('bad data file');
      return d;
    });
  }

  /* Live Sleeper overlay. Mutates the Sleeper league entry of `d`. Player names/injuries/projections come from
     the saved data (known ids); only cheap endpoints are called. Returns {parts:[ok...], errors:[...]}. */
  function liveSleeper(d) {
    var S = CFG.sleeper, L = null;
    d.leagues.forEach(function (l) { if (lid(l) === S.league && l.status === 'live') L = l; });
    if (!L) return Promise.reject(new Error('Sleeper league is not in the saved data'));
    var base = S.base + '/league/' + S.league;
    function sg(p) { return timed(S.base + p + (p.indexOf('?') < 0 ? '?' : '&') + '_=' + Date.now(), 12000); }
    return Promise.all([sg('/state/nfl'), sg('/league/' + S.league), sg('/league/' + S.league + '/users'), sg('/league/' + S.league + '/rosters')]
      .map(function (p) { return p.then(function (v) { return { v: v }; }, function (e) { return { e: e }; }); })).then(function (r) {
      var st = r[0].v, lg = r[1].v, users = r[2].v, rosters = r[3].v, errs = [], done = [];
      [['state', r[0]], ['league', r[1]], ['users', r[2]], ['rosters', r[3]]].forEach(function (x) { if (x[1].e) errs.push(x[0] + ': ' + (x[1].e.message || x[1].e)); });
      var oldM = L.matchup || {}, oldWeek = oldM.week || L.week;
      var week = st ? (st.display_week || st.week || oldWeek) : oldWeek;
      var sameWeek = Number(week) === Number(oldWeek);
      // known players from saved data
      var known = {};
      var rr = L.my_roster || {};
      (rr.starters || []).concat(rr.bench || [], rr.ir || [], oldM.opponent_starters || []).forEach(function (p) { if (p && p.id != null) known[p.id] = p; });
      var unknown = 0;
      function pinfo(id) {
        var k = known[id], p;
        if (k) { p = JSON.parse(JSON.stringify(k)); }
        else { unknown++; p = { id: id, name: /^\d+$/.test(id) ? 'Player ' + id : id, pos: /^\d+$/.test(id) ? '?' : 'DEF', team: null, injury: null, injury_status: 'Healthy', injury_body_part: null, projection: null }; }
        p.slot = null; if (!sameWeek) { p.projection = null; } p.score = sameWeek && k ? k.score : null;
        return p;
      }
      var uMap = {};
      (users || []).forEach(function (u) { uMap[u.user_id] = u; });
      function teamName(ro) { var u = uMap[ro.owner_id] || {}; return (u.metadata && u.metadata.team_name) || u.display_name || ('Roster ' + ro.roster_id); }
      function rec(s) { return (s.wins || 0) + '-' + (s.losses || 0) + (s.ties ? '-' + s.ties : ''); }
      var mine = null, byRid = {};
      if (rosters && users) {
        rosters.forEach(function (ro) { byRid[ro.roster_id] = ro; if (ro.owner_id === S.user) mine = ro; });
        var table = rosters.map(function (ro) {
          var s = ro.settings || {};
          return { roster_id: ro.roster_id, team: teamName(ro), owner: (uMap[ro.owner_id] || {}).display_name, wins: s.wins || 0, losses: s.losses || 0, ties: s.ties || 0,
            pf: Math.round(((s.fpts || 0) + (s.fpts_decimal || 0) / 100) * 100) / 100, pa: Math.round(((s.fpts_against || 0) + (s.fpts_against_decimal || 0) / 100) * 100) / 100,
            record: rec(s), is_me: ro.owner_id === S.user };
        });
        table.sort(function (a, b) { return (b.wins - a.wins) || (a.losses - b.losses) || (b.pf - a.pf); });
        table.forEach(function (s, i) { s.rank = i + 1; });
        var me = table.filter(function (s) { return s.is_me; })[0];
        if (table.length && me) {
          L.standings = table; L.record = me.record; L.standing = me.rank + ' of ' + table.length; L.team_name = me.team; done.push('standings');
        } else errs.push('standings: my team not found');
      }
      if (mine) {
        var slots = lg && lg.roster_positions ? lg.roster_positions.filter(function (x) { return x !== 'BN'; })
          : (rr.starters || []).map(function (p) { return p.slot; });
        var sIds = mine.starters || [], sSet = {}, reserve = mine.reserve || [], rSet = {};
        sIds.forEach(function (i) { sSet[i] = 1; }); reserve.forEach(function (i) { rSet[i] = 1; });
        var starters = [];
        sIds.forEach(function (id, i) { if (!id || id === '0') return; var p = pinfo(id); p.slot = i < slots.length ? slots[i] : p.pos; starters.push(p); });
        var bench = (mine.players || []).filter(function (id) { return !sSet[id] && !rSet[id]; }).map(function (id) { var p = pinfo(id); p.slot = 'BN'; return p; });
        var ir = reserve.map(function (id) { var p = pinfo(id); p.slot = 'IR'; return p; });
        L.my_roster = { starters: starters, bench: bench, ir: ir }; done.push('roster');
      }
      L.week = week;
      var after = function (ms) {
        if (ms && mine) {
          var mm = null, opp = null;
          ms.forEach(function (m) { if (m.roster_id === mine.roster_id) mm = m; });
          if (mm) ms.forEach(function (m) { if (m.matchup_id != null && m.matchup_id === mm.matchup_id && m.roster_id !== mm.roster_id) opp = m; });
          if (mm) {
            var pp = mm.players_points || {};
            ['starters', 'bench', 'ir'].forEach(function (g) { L.my_roster[g].forEach(function (p) { if (Object.prototype.hasOwnProperty.call(pp, p.id)) p.score = pp[p.id]; }); });
            var oroster = opp ? byRid[opp.roster_id] : null;
            var oname = oroster ? teamName(oroster) : null;
            var mp = null;
            if (sameWeek) {
              var anyP = false, sum = 0;
              L.my_roster.starters.forEach(function (p) { if (p.projection != null) { anyP = true; sum += p.projection; } });
              mp = anyP ? Math.round(sum * 10) / 10 : null;
            }
            var oldOpp = oldM.opponent;
            var nm = {}; Object.keys(oldM).forEach(function (k) { nm[k] = oldM[k]; });
            nm.week = week; nm.my_points = mm.points; nm.opponent = oname; nm.opponent_record = oroster ? rec(oroster.settings || {}) : null;
            nm.opponent_points = opp ? opp.points : null; nm.my_projection = mp;
            nm.opponent_projection = (sameWeek && oname && oname === oldOpp) ? oldM.opponent_projection : null;
            nm.opponent_starters = opp ? (opp.starters || []).filter(function (id) { return id && id !== '0'; }).map(pinfo) : [];
            delete nm.error;
            L.matchup = nm; done.push('matchup');
          } else errs.push('matchup: no matchup for my roster in week ' + week);
        } else if (mine) errs.push('matchup: request failed');
        if (unknown) errs.push(unknown + ' player id' + (unknown > 1 ? 's' : '') + ' not in saved data (shown as ids)');
        if (done.length) {
          var now = new Date();
          L.last_updated = stampZ(now); L.source = 'Sleeper API (live, from your browser)';
        }
        return { done: done, errs: errs };
      };
      if (!mine) return after(null);
      return sg('/league/' + S.league + '/matchups/' + week).then(after, function (e) { var o = after(null); o.errs.push('matchup: ' + (e.message || e)); return o; });
    });
  }

  /* ---------- refresh ---------- */
  function needsLive() { return CFG.page === 'index' || CFG.lid === (CFG.sleeper || {}).league; }
  function refresh() {
    if (busy) return;
    busy = true;
    var btn = $('refresh');
    btn.disabled = true; btn.classList.add('busy'); setStatus('Refreshing…', '');
    var msgs = [], cls = 'ok';
    loadDoc().then(function (d) {
      doc = d; liveInfo = null;
      if (!needsLive()) { msgs.push('Saved data reloaded'); return; }
      return liveSleeper(doc).then(function (res) {
        if (res.done.length) liveInfo = { at: new Date() };
        if (!res.done.length) { cls = 'warn'; msgs.push('Saved data reloaded; Sleeper live update failed (' + res.errs.join('; ') + ')'); }
        else if (res.errs.length) { cls = 'warn'; msgs.push('Sleeper partly updated live (' + res.done.join(', ') + '); ' + res.errs.join('; ')); }
        else msgs.push('Saved data reloaded; Sleeper updated live');
      }, function (e) { cls = 'warn'; msgs.push('Saved data reloaded; Sleeper live update failed (' + (e && e.message || e) + ')'); });
    }, function (e) {
      cls = 'err';
      msgs.push(location.protocol === 'file:' ? 'Refresh needs the hosted site (browsers block data loading from local files).'
        : 'Could not load data/leagues.json (' + (e && e.message || e) + '). Showing what was already on screen.');
    }).then(function () {
      try { renderAll(); } catch (e) { cls = 'err'; msgs.push('Render problem: ' + (e && e.message || e)); if (window.console) console.warn(e); }
    }).then(function () {
      setStatus(fmtLocal(new Date()) + ' · ' + msgs.join(' '), cls);
      busy = false; btn.disabled = false; btn.classList.remove('busy');
    });
  }

  /* ---------- request ESPN/Yahoo update (opens a prefilled GitHub issue in a new tab; user must press Submit) ---------- */
  function reqUrl() {
    var body = 'Please re-pull ESPN and Yahoo data.\n\nRequested from the dashboard at ' + new Date().toISOString() +
      ' (' + fmtLocal(new Date()) + ' local).';
    return 'https://github.com/timmiller50/ffl-dashboard/issues/new?labels=update-request&title=' +
      encodeURIComponent('Update request: ESPN + Yahoo') + '&body=' + encodeURIComponent(body);
  }
  function wireRequest() {
    var a = $('requpd');
    if (!a) return;
    a.href = reqUrl();
    a.addEventListener('click', function () { a.href = reqUrl(); }); // fresh timestamp at click time; default navigation opens new tab
  }

  /* ---------- init ---------- */
  function init() {
    localizeStatic();
    wireRequest();
    var btn = $('refresh');
    if (btn) btn.addEventListener('click', refresh);
    // quietly load the data file at runtime so pages pick up newly pushed data without a rebuild
    if (location.protocol !== 'file:') loadDoc().then(function (d) { doc = d; renderAll(); }, function () { /* keep the pre-rendered page */ });
    setInterval(function () { try { renderChips(); } catch (e) { /* ignore */ } }, 60000);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
