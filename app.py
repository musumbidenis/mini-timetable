"""Mini Timetable — dynamic Streamlit app.
Upload the CDACC master timetable PDF, one or more attendance-register PDFs, and
the room-allocation DOCX; the app parses them, allocates rooms per session, and
exports PDF + Excel. Deployable to Streamlit Cloud (poppler via packages.txt)."""
import copy, hashlib, datetime
from collections import defaultdict
import pandas as pd
import streamlit as st
from parsing import pdf_bytes_to_text, classify_pdf, parse_rooms, build_data
from allocate import group_by_session, allocate_session
from excel_export import build_workbook
from pdf_export import build_pdf
from registers_zip import build_registers_zip, fmt_folder
import ui

# Sidebar starts hidden on the upload screen, appears once documents are parsed.
_ready = bool(st.session_state.get("has_data"))
st.set_page_config(page_title="Mini Timetable", layout="wide",
                   initial_sidebar_state="expanded" if _ready else "collapsed")
st.markdown(ui.GLOBAL_CSS, unsafe_allow_html=True)
st.markdown(ui.page_header(), unsafe_allow_html=True)

def _hash(blobs):
    h = hashlib.md5()
    for b in blobs: h.update(b)
    return h.hexdigest()

@st.cache_data(show_spinner="Parsing documents…")
def parse_uploads(files, _key):
    """files: tuple of (filename, bytes). Auto-classifies the PDFs; the room list
    comes from a .docx or a PDF (table of ROOM | CAPACITY)."""
    reg_texts, reg_blobs, tt_bytes, rooms_blob, rooms_name = [], [], None, None, ''
    for name, blob in files:
        if name.lower().endswith('.docx'):
            rooms_blob, rooms_name = blob, name
            continue
        kind = classify_pdf(pdf_bytes_to_text(blob))
        if kind == 'registers':
            reg_texts.append(pdf_bytes_to_text(blob))
            reg_blobs.append((name, blob))          # keep raw PDF for the day-split ZIP
        elif kind == 'master':
            tt_bytes = blob
        elif rooms_blob is None:                    # 'rooms' or unclassified -> rooms
            rooms_blob, rooms_name = blob, name
    rooms = parse_rooms(rooms_blob, rooms_name) if rooms_blob is not None else []
    status = (bool(reg_texts), tt_bytes is not None, bool(rooms), len(reg_texts))
    if not (reg_texts and tt_bytes is not None and rooms):
        return None, status, ()
    return build_data(reg_texts, tt_bytes, rooms), status, tuple(reg_blobs)

def mkey(k):
    try: return (datetime.datetime.strptime(k[0], '%d %b %Y'), k[1])
    except Exception: return (datetime.datetime.max, k[1])

@st.cache_data(show_spinner="Packaging registers by day…")
def registers_zip_bytes(reg_blobs, mapping):
    """mapping: tuple of (code, folder, name). Cached on the register bytes and
    the code→day mapping, so it rebuilds only when documents or assignments change."""
    code_folder = {c: f for c, f, _ in mapping}
    code_name = {c: n for c, _, n in mapping}
    return build_registers_zip(list(reg_blobs), code_folder, code_name).getvalue()

# ---------------- uploader (main screen until parsed, then sidebar) ----------------
def uploader():
    return st.file_uploader("Upload", type=['pdf', 'docx'], accept_multiple_files=True,
                            label_visibility="collapsed", key="uploader")

if _ready:
    with st.sidebar:
        st.markdown(ui.sidebar_label("Documents"), unsafe_allow_html=True)
        st.markdown(ui.sidebar_caption("Re-upload to change the plan."), unsafe_allow_html=True)
        ups = uploader()
else:
    st.markdown(ui.HIDE_SIDEBAR, unsafe_allow_html=True)
    st.markdown(ui.start_head(), unsafe_allow_html=True)
    with st.columns([1, 2, 1])[1]:
        ups = uploader()

files = tuple((f.name, f.getvalue()) for f in ups) if ups else ()
base, status, reg_blobs = (None, (False, False, False, 0), ())
if files:
    base, status, reg_blobs = parse_uploads(files, _hash([b for _, b in files]))

# Flip between the start screen (sidebar hidden) and the loaded view (sidebar shown).
now_ready = base is not None
if now_ready != _ready:
    st.session_state["has_data"] = now_ready
    st.rerun()

if not now_ready:
    if files:                                       # uploaded but still incomplete
        missing = [m for m, ok in [("attendance register PDF", status[0]),
                                   ("master timetable PDF", status[1]),
                                   ("room allocation document", status[2])] if not ok]
        if missing:
            st.info("Still need the " + " and ".join(missing) + ".")
    st.stop()

n_reg = status[3]

# ---------------- session state (rooms + manual assignments) ----------------
key = _hash([b for _, b in files])
if st.session_state.get('_key') != key:
    st.session_state['_key'] = key
    st.session_state.rooms = copy.deepcopy(base['rooms'])
    st.session_state.manual = {}

# ---------------- sidebar: rooms ----------------
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(ui.sidebar_label("Rooms & capacities"), unsafe_allow_html=True)
    st.markdown(ui.sidebar_caption("Edit capacities, add or remove rooms — "
                                   "the plan recomputes."), unsafe_allow_html=True)
    rooms_df = st.data_editor(pd.DataFrame(st.session_state.rooms),
                              num_rows="dynamic", width='stretch', key="rooms_editor",
                              column_config={'room': 'Room', 'capacity': 'Capacity'})
rooms = [{'room': str(r['room']), 'capacity': int(r['capacity'])}
         for _, r in rooms_df.iterrows()
         if str(r.get('room', '')).strip() and pd.notna(r.get('capacity'))]
total_cap = sum(r['capacity'] for r in rooms)
st.sidebar.markdown(f'<p class="cap-total">Total capacity: {total_cap}</p>',
                    unsafe_allow_html=True)

# ---------------- allocate ----------------
data = copy.deepcopy(base); data['rooms'] = rooms
for u in data['units']:
    if u['code'] in st.session_state.manual:
        u['slot'] = st.session_state.manual[u['code']]
sessions, unassigned = group_by_session(data['units'])
alloc = {k: allocate_session(v, rooms) for k, v in sessions.items()}

# ---------------- header + metrics ----------------
series = base.get('series', '')
st.markdown(f'<p class="centre-name">{base["centre"]}  ·  Centre code {base["centre_code"]}'
            + (f'  ·  {series} Assessment Series' if series else '')
            + f'  ·  {n_reg} register file{"s" if n_reg != 1 else ""}</p>',
            unsafe_allow_html=True)

students = sum(u['count'] for u in data['units'])
matched = len(data['units']) - len(unassigned)
peak_load = max((sum(u['count'] for u in v) for v in sessions.values()), default=0)
util = round(peak_load / total_cap * 100) if total_cap else 0
overflow = sum(sum(n for _, n in a[1]) for a in alloc.values())

st.markdown(ui.metric_cards([
    ("Units", len(data['units']), None, ""),
    ("Students", students, None, ""),
    ("Sessions", len(sessions), None, ""),
    ("Matched", matched,
     "All units assigned" if not unassigned else f"{len(unassigned)} unmapped",
     "ok" if not unassigned else "warn"),
    ("Capacity", f"{util}%", "Peak utilization", "bad" if util > 100 else "ok"),
]), unsafe_allow_html=True)

if overflow:
    st.warning(f"{overflow} candidate(s) can't be seated in the busiest session — "
               f"add room capacity in the sidebar.")

# ---------------- downloads (above the preview) ----------------
b1, b2, b3, _ = st.columns([1.6, 1.6, 2, 1.8])
b1.download_button("Download timetable (PDF)", data=build_pdf(data).getvalue(),
                   file_name="mini_timetable.pdf", mime="application/pdf")
b2.download_button("Download Excel workbook", data=build_workbook(data).getvalue(),
                   file_name="mini_timetable.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
# One button: it shows a spinner while building the ZIP, then becomes the download.
if reg_blobs:
    mapping = tuple(sorted(
        (u['code'], fmt_folder(u['slot']['date']) if u.get('slot') else 'Unassigned', u['name'])
        for u in data['units']))
    slot = b3.empty()
    if st.session_state.get('zip_sig') == mapping:
        slot.download_button("Download Registers by Day",
                             data=registers_zip_bytes(reg_blobs, mapping),
                             file_name="attendance_registers_by_day.zip",
                             mime="application/zip", key="dl_zip")
    elif slot.button("Download Registers by Day", key="prep_zip"):
        with slot, st.spinner("Preparing registers…"):
            registers_zip_bytes(reg_blobs, mapping)     # build + cache
        st.session_state['zip_sig'] = mapping
        st.rerun()
st.markdown("<br>", unsafe_allow_html=True)

# ---------------- unmapped units ----------------
if unassigned:
    n_stud = sum(u['count'] for u in unassigned)
    with st.expander(f"{len(unassigned)} unit(s) not on the master timetable "
                     f"({n_stud} candidates) — assign a session manually"):
        st.caption("These codes aren't on the master timetable (MOSTLY Level 3/4 Cycle-3)."
                   "Each row shows the unit code and its attendance level.")
        labels = {f"{d} · S{s} · {ui.fmt_time_range(t)}": {'date': d, 'session': s, 'time': t}
                  for (d, s, t) in sorted(sessions, key=lambda k: (mkey(k), k[1]))}
        for u in unassigned:
            lvl = f"Level {u['level']}" if u.get('level') else "Level ?"
            pick = st.selectbox(f"{u['code']} · {lvl} — {u['name']} ({u['count']} candidates)",
                                ["— leave unassigned —"] + list(labels), key=f"asg_{u['code']}")
            if pick != "— leave unassigned —":
                st.session_state.manual[u['code']] = labels[pick]
                st.rerun()

# ---------------- tabs ----------------
tab_tt, tab_rooms = st.tabs(["Timetable", "Room allocation"])

with tab_tt:
    flat = []
    for k in sorted(sessions, key=lambda k: (mkey(k), k[1])):
        d, s, t = k
        used, _ = alloc[k]
        where = defaultdict(list)
        for room in used:
            for o in room['occupants']:
                if room['room'] not in where[o['code']]:
                    where[o['code']].append(room['room'])
        for u in sorted(sessions[k], key=lambda x: -x['count']):
            flat.append({'date': d, 'session': s, 'time': t, 'code': u['code'],
                         'name': u['name'], 'level': u['level'],
                         'duration': u.get('duration', ''), 'count': u['count'],
                         'rooms': ', '.join(where[u['code']])})
    st.markdown(ui.timetable_table(flat), unsafe_allow_html=True)

with tab_rooms:
    view = []
    for k in sorted(sessions, key=lambda k: (mkey(k), k[1])):
        d, s, t = k
        used, _ = alloc[k]
        slot = next((u['slot'] for u in sessions[k] if u.get('slot')), {})
        view.append({'date': d, 'day': (slot or {}).get('day', ''), 'session': s, 'time': t,
                     'students': sum(u['count'] for u in sessions[k]), 'rooms': used})
    st.markdown(ui.room_alloc_table(view), unsafe_allow_html=True)
