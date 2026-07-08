"""Presentation layer for the Mini Timetable app: global CSS and HTML builders.
Keeps app.py focused on data flow. All markup is rendered via st.markdown(...,
unsafe_allow_html=True); the styling matches the approved redesign."""
import html
import re

ACCENT = "#0d5b48"

# ---------------------------------------------------------------- global CSS
GLOBAL_CSS = """
<style>
:root{ --accent:#0d5b48; --accent-soft:#0a8f6f; --ink:#1a2420; --muted:#68766f;
  --rule:#e6e9e7; --card:#ffffff; --grey:#f4f5f4; --warn:#9a5a08; --danger:#b3261e;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif; }

/* trim Streamlit chrome */
header[data-testid="stHeader"]{ background:transparent; height:0; }
[data-testid="stToolbar"]{ display:none; }
.block-container{ padding-top:2.2rem; padding-bottom:3rem; max-width:1400px; }
#MainMenu, footer{ visibility:hidden; }

/* page header */
.app-head{ margin-bottom:.2rem; }
.app-title{ font-family:var(--serif); font-weight:700; font-size:2rem; color:var(--ink);
  letter-spacing:-.01em; line-height:1.1; margin:0; }
.app-sub{ color:var(--muted); font-size:.95rem; margin:.25rem 0 0; }
.app-rule{ border:none; border-top:1px solid var(--rule); margin:1.1rem 0 1.4rem; }
.centre-name{ font-weight:700; font-size:.95rem; color:var(--ink); margin:0 0 1rem; }

/* metric cards */
.metric-row{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-bottom:1.6rem; }
.metric-card{ background:var(--card); border:1px solid var(--rule); border-radius:12px;
  padding:16px 18px; }
.metric-card .label{ font-size:.7rem; letter-spacing:.09em; text-transform:uppercase;
  color:var(--muted); font-weight:600; }
.metric-card .value{ font-size:2rem; font-weight:700; color:var(--ink); line-height:1.15;
  margin-top:.35rem; font-variant-numeric:tabular-nums; }
.metric-card .note{ font-size:.78rem; margin-top:.2rem; }
.metric-card .note.ok{ color:var(--accent-soft); }
.metric-card .note.warn{ color:var(--warn); }
.metric-card .note.bad{ color:var(--danger); }
@media (max-width:1100px){ .metric-row{ grid-template-columns:repeat(2,1fr);} }

/* data tables */
.tt-scroll{ overflow-x:auto; border:1px solid var(--rule); border-radius:12px; }
table.tt{ border-collapse:collapse; width:100%; font-size:.86rem; }
table.tt thead th{ background:var(--grey); text-align:left; font-size:.68rem; font-weight:600;
  letter-spacing:.06em; text-transform:uppercase; color:var(--muted); padding:11px 16px;
  white-space:nowrap; border-bottom:1px solid var(--rule); }
table.tt tbody td{ padding:11px 16px; border-bottom:1px solid var(--rule); color:var(--ink);
  vertical-align:top; }
table.tt tbody tr:last-child td{ border-bottom:none; }
table.tt tbody tr:hover td{ background:#fafbfa; }
.tt .code{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.8rem; color:var(--accent); white-space:nowrap; }
.tt .num{ text-align:center; font-variant-numeric:tabular-nums; white-space:nowrap; }
.tt .room{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.8rem; white-space:nowrap; }
.tt .room.split{ color:var(--warn); }
.tt .rowspan{ font-weight:600; }
.sess-band td{ background:#f0f4f2 !important; font-weight:600; color:var(--ink) !important;
  font-size:.8rem; letter-spacing:.01em; }

/* empty state */
.empty{ text-align:center; padding:3.5rem 1rem; color:var(--muted); }
.empty .ico{ font-size:2.4rem; }
.empty h3{ color:var(--ink); font-size:1.1rem; margin:.6rem 0 .3rem; }
.empty p{ font-size:.9rem; margin:0; }

/* sidebar section labels */
[data-testid="stSidebar"] .side-label{ font-size:.72rem; letter-spacing:.09em;
  text-transform:uppercase; color:var(--muted); font-weight:700; margin:.3rem 0 .1rem; }
[data-testid="stSidebar"] .side-cap{ font-size:.8rem; color:var(--muted); margin:0 0 .5rem; }
[data-testid="stSidebar"] .cap-total{ font-weight:700; font-size:.9rem; color:var(--ink);
  margin-top:.4rem; }

/* file uploader dropzone */
[data-testid="stFileUploaderDropzone"]{ background:var(--card); border:1.5px dashed #c7d0cb;
  border-radius:12px; }

/* download buttons: solid green, width fits the label */
.stDownloadButton button{ background:var(--accent); color:#fff; border:none; border-radius:9px;
  font-weight:600; padding:.55rem 1.2rem; white-space:nowrap; width:auto; }
.stDownloadButton button:hover{ background:#0a4a3b; color:#fff; }
.stDownloadButton button p{ white-space:nowrap; }

/* main-area upload start screen */
.start-head{ text-align:center; margin:2.4rem 0 .4rem; }
.start-head .ico{ font-size:2.4rem; }
.start-head h3{ color:var(--ink); font-size:1.15rem; margin:.5rem 0 .3rem; }
.start-head p{ color:var(--muted); font-size:.9rem; margin:0; }

/* tabs */
[data-baseweb="tab-list"]{ gap:1.4rem; border-bottom:1px solid var(--rule); }
button[data-baseweb="tab"]{ font-weight:600; }
</style>
"""


# ---------------------------------------------------------------- helpers
def _esc(s):
    return html.escape(str(s if s is not None else ""))


def fmt_time_range(t, hours=2):
    """'08 00 AM' -> '08:00–10:00'. Falls back to the raw string if unparseable."""
    m = re.match(r'(\d{1,2})\s*(\d{2})\s*([AP]M)', str(t).strip(), re.I)
    if not m:
        return _esc(t)
    hh, mm, ap = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if ap == 'PM' and hh != 12: hh += 12
    if ap == 'AM' and hh == 12: hh = 0
    start = hh * 60 + mm
    end = start + hours * 60
    f = lambda x: f"{(x // 60) % 24:02d}:{x % 60:02d}"
    return f"{f(start)}–{f(end)}"


def fmt_duration(d):
    n = re.sub(r'\D', '', str(d or ''))
    return f"{n}h" if n else "2h"


# ---------------------------------------------------------------- builders
def page_header():
    return ('<div class="app-head">'
            '<p class="app-title">Mini Timetable</p>'
            '<p class="app-sub">Room allocation scheduling</p></div>'
            '<hr class="app-rule">')


def metric_cards(cards):
    """cards: list of (label, value, note_text_or_None, note_class)."""
    out = ['<div class="metric-row">']
    for label, value, note, cls in cards:
        n = f'<div class="note {cls}">{_esc(note)}</div>' if note else ''
        out.append(f'<div class="metric-card"><div class="label">{_esc(label)}</div>'
                   f'<div class="value">{_esc(value)}</div>{n}</div>')
    out.append('</div>')
    return ''.join(out)


def timetable_table(rows):
    """Flat timetable. rows: dicts with date/session/time/code/name/level/duration/count/rooms."""
    head = ('<div class="tt-scroll"><table class="tt"><thead><tr>'
            '<th>Date</th><th>Session</th><th>Time</th><th>Unit Code</th><th>Unit Name</th>'
            '<th>Level</th><th>Duration</th><th>Students</th><th>Room(s)</th>'
            '</tr></thead><tbody>')
    body = []
    for r in rows:
        split = ',' in (r['rooms'] or '')
        body.append(
            f'<tr><td>{_esc(r["date"])}</td>'
            f'<td class="num">{_esc(r["session"])}</td>'
            f'<td>{fmt_time_range(r["time"])}</td>'
            f'<td class="code">{_esc(r["code"])}</td>'
            f'<td>{_esc(r["name"])}</td>'
            f'<td class="num">{_esc(r["level"]) or "—"}</td>'
            f'<td class="num">{fmt_duration(r["duration"])}</td>'
            f'<td class="num">{_esc(r["count"])}</td>'
            f'<td class="room{" split" if split else ""}">{_esc(r["rooms"]) or "—"}</td></tr>')
    return head + ''.join(body) + '</tbody></table></div>'


def room_alloc_table(sessions_view):
    """Room-centric view. sessions_view: list of dicts with
    date/day/session/time/students and rooms:[{room,capacity,used,occupants:[{code,name,seats}]}]."""
    out = ['<div class="tt-scroll"><table class="tt"><thead><tr>'
           '<th>Room</th><th>Cap.</th><th>Seated</th><th>Unit Code</th><th>Unit Name</th>'
           '<th>Seats</th></tr></thead><tbody>']
    for s in sessions_view:
        out.append(f'<tr class="sess-band"><td colspan="6">{_esc(s["day"])} {_esc(s["date"])} '
                   f'· Session {_esc(s["session"])} · {fmt_time_range(s["time"])} · '
                   f'{s["students"]} candidates · {len(s["rooms"])} rooms</td></tr>')
        for room in s['rooms']:
            span = len(room['occupants'])
            for i, o in enumerate(room['occupants']):
                lead = (f'<td class="rowspan" rowspan="{span}">{_esc(room["room"])}</td>'
                        f'<td class="num rowspan" rowspan="{span}">{room["capacity"]}</td>'
                        f'<td class="num rowspan" rowspan="{span}">{room["used"]}</td>'
                        if i == 0 else '')
                out.append(f'<tr>{lead}<td class="code">{_esc(o["code"])}</td>'
                           f'<td>{_esc(o["name"])}</td><td class="num">{o["seats"]}</td></tr>')
    out.append('</tbody></table></div>')
    return ''.join(out)


def start_head():
    return ('<div class="start-head"><div class="ico">📤</div>'
            '<h3>Upload documents to begin</h3>'
            '<p>Add the master timetable PDF, attendance register PDF(s),<br>'
            'and the room allocation document (Word or PDF) to get started.</p></div>')

HIDE_SIDEBAR = ('<style>[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],'
                '[data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"]'
                '{display:none !important;}</style>')


def sidebar_label(text):
    return f'<p class="side-label">{_esc(text)}</p>'


def sidebar_caption(text):
    return f'<p class="side-cap">{_esc(text)}</p>'
