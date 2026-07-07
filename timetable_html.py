"""Minimal centre mini-timetable, master-timetable style, for the live preview.
Columns: Unit Code · Unit Name · Level · Candidates · Room. Self-contained HTML."""
import json
from allocate import group_by_session, allocate_session


def enrich_sessions(data):
    """-> list of session dicts with rows ready for the table."""
    sessions, _ = group_by_session(data['units'])
    out = []
    for k in sorted(sessions):
        d, s, t = k
        units = sessions[k]
        used, _ = allocate_session(units, data['rooms'])
        where = {}
        for room in used:
            for o in room['occupants']:
                where.setdefault(o['code'], []).append((room['room'], o['seats']))
        day = ''
        rows = []
        for u in sorted(units, key=lambda x: -x['count']):
            w = where.get(u['code'], [])
            room = ', '.join(f"{r}({n})" if len(w) > 1 else r for r, n in w)
            sl = u.get('slot') or {}
            day = day or sl.get('day', '')
            rows.append({'cycle': u.get('cycle', ''), 'course': u['course'],
                         'code': u['code'], 'name': u['name'], 'level': u['level'],
                         'duration': u.get('duration', ''), 'count': u['count'],
                         'room': room})
        out.append({'date': d, 'day': day, 'session': s, 'time': t,
                    'students': sum(u['count'] for u in units),
                    'rooms': len(used), 'rows': rows})
    return out


def build_timetable_html(data, standalone=True):
    payload = {'centre': data.get('centre', 'Assessment Centre'),
               'code': data.get('centre_code', ''),
               'sessions': enrich_sessions(data)}
    doc = _CSS + _BODY.replace('__DATA__', json.dumps(payload, separators=(',', ':'),
                                                       ensure_ascii=False))
    if standalone:
        return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{payload["centre"]} — Mini Timetable</title></head><body>'
                + doc + '</body></html>')
    return doc


_CSS = r'''<style>
:root{--paper:#fff;--ink:#1a2420;--muted:#68766f;--accent:#0d5b48;--rule:#e2e8e4;
--tint:#f2f7f4;--warn:#9a5a08;
--serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
--sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
@media (prefers-color-scheme:dark){:root{--paper:#0f1613;--ink:#e7ede9;--muted:#93a49b;
--accent:#4fd0a8;--rule:#232e28;--tint:#16241d;--warn:#e0a95c;}}
:root[data-theme="light"]{--paper:#fff;--ink:#1a2420;--muted:#68766f;--accent:#0d5b48;--rule:#e2e8e4;--tint:#f2f7f4;--warn:#9a5a08;}
:root[data-theme="dark"]{--paper:#0f1613;--ink:#e7ede9;--muted:#93a49b;--accent:#4fd0a8;--rule:#232e28;--tint:#16241d;--warn:#e0a95c;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:14px;line-height:1.45}
.wrap{max-width:1180px;margin:0 auto;padding:22px 20px 60px}
h1{font-family:var(--serif);font-weight:700;font-size:20px;margin:0 0 2px;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:12.5px;margin-bottom:18px}
.sub b{color:var(--ink);font-variant-numeric:tabular-nums}
.session{margin-bottom:22px}
.shead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;
padding-bottom:5px;border-bottom:1.5px solid var(--accent);margin-bottom:2px}
.shead .when{font-weight:600;font-size:13.5px;font-variant-numeric:tabular-nums}
.shead .tally{color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th{text-align:left;font-size:10.5px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);
font-weight:600;padding:6px 8px;border-bottom:1px solid var(--rule);white-space:nowrap}
td{padding:6px 8px;border-bottom:1px solid var(--rule);vertical-align:top}
tr:last-child td{border-bottom:none}
.code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;white-space:nowrap}
.cyc,.c-dur{color:var(--muted);white-space:nowrap}
.c-lvl,.c-cand,.c-dur{text-align:center;font-variant-numeric:tabular-nums;white-space:nowrap}
.room{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px}
.room.split{color:var(--warn)}
th.c-lvl,th.c-cand,th.c-dur,th.c-room{text-align:center}
@media print{body{background:#fff}.session{break-inside:avoid}}
</style>'''

_BODY = r'''<div class="wrap">
<h1 id="centre">Centre Mini Timetable</h1>
<div class="sub" id="sub"></div>
<main id="sessions"></main>
</div>
<script type="application/json" id="data">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
document.getElementById('centre').textContent=D.centre;
const tot=D.sessions.reduce((a,s)=>a+s.students,0);
const units=D.sessions.reduce((a,s)=>a+s.rows.length,0);
document.getElementById('sub').innerHTML=`Written Assessment · July/August 2026 &nbsp;·&nbsp; Centre code <b>${D.code}</b> &nbsp;·&nbsp; <b>${units}</b> units &nbsp;·&nbsp; <b>${tot}</b> candidates &nbsp;·&nbsp; <b>${D.sessions.length}</b> sessions`;
const main=document.getElementById('sessions');
const roomCell=(room)=>{if(!room)return '—';const sp=room.includes(',');return `<span class="room${sp?' split':''}">${room}</span>`;};
D.sessions.forEach(s=>{
const rows=s.rows.map(r=>`<tr><td class="cyc">${r.cycle||'—'}</td><td>${r.course||''}</td><td class="code">${r.code}</td><td>${r.name||''}</td><td class="c-lvl">${r.level?('Level '+r.level):'—'}</td><td class="c-dur">${r.duration||'—'}</td><td class="c-cand">${r.count}</td><td class="c-room">${roomCell(r.room)}</td></tr>`).join('');
main.insertAdjacentHTML('beforeend',`<section class="session"><div class="shead"><div class="when">${s.day} ${s.date} · Session ${s.session} · ${s.time}</div><div class="tally">${s.students} candidates · ${s.rooms} room${s.rooms!==1?'s':''}</div></div><table><thead><tr><th>Curriculum Cycle</th><th>Course</th><th>Unit Code</th><th>Unit Name</th><th class="c-lvl">Level</th><th class="c-dur">Duration</th><th class="c-cand">Cand.</th><th class="c-room">Room</th></tr></thead><tbody>${rows}</tbody></table></section>`);});
</script>'''
