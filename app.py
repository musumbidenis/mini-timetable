"""Mini Timetable — dynamic Streamlit app.
Upload the three CDACC documents (master timetable PDF, attendance registers PDF,
room-allocation DOCX); the app parses them, allocates rooms per session, and
exports an Excel workbook. Deployable to Streamlit Cloud (poppler via packages.txt)."""
import copy, hashlib, datetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from parsing import pdf_bytes_to_text, classify_pdf, parse_rooms, build_data
from allocate import group_by_session, allocate_session
from excel_export import build_workbook
from timetable_html import build_timetable_html
from pdf_export import build_pdf

st.set_page_config(page_title="Mini Timetable", page_icon="📅", layout="wide")
st.title("📅 Mini Timetable & Room Allocation")

def _hash(files):
    h = hashlib.md5()
    for f in files: h.update(f)
    return h.hexdigest()

@st.cache_data(show_spinner="Parsing documents…")
def parse_uploads(pdf_blobs, docx_blob, _key):
    reg_texts, tt_bytes = [], None
    for blob in pdf_blobs:
        text = pdf_bytes_to_text(blob)
        kind = classify_pdf(text)
        if kind == 'registers': reg_texts.append(text)
        elif kind == 'master':  tt_bytes = blob      # keep bytes for table parsing
    rooms = parse_rooms(docx_blob)
    if not reg_texts or tt_bytes is None:
        return None, (bool(reg_texts), tt_bytes is not None, bool(rooms), len(reg_texts))
    data = build_data(reg_texts, tt_bytes, rooms)
    return data, (True, True, bool(rooms), len(reg_texts))

# ---------------- upload ----------------
with st.sidebar:
    st.header("📤 Upload documents")
    st.caption("The master timetable PDF, one or more attendance-register PDFs, "
               "and the room-allocation Word file. Order doesn't matter — "
               "they're auto-detected.")
    ups = st.file_uploader("Drop the files here", type=['pdf', 'docx'],
                           accept_multiple_files=True)

pdfs = [f.getvalue() for f in ups if f.name.lower().endswith('.pdf')] if ups else []
docx = next((f.getvalue() for f in ups if f.name.lower().endswith('.docx')), None) if ups else None

if not ups or not pdfs or docx is None:
    st.info("👈 Upload the **PDFs** and the **room-allocation .docx** to begin.")
    st.markdown(
        "- **Master timetable** PDF — CDACC national timetable (has the session dates/times)\n"
        "- **Attendance registers** PDF(s) — your centre's units & candidates "
        "(you can add several)\n"
        "- **Room allocation** .docx — your venues & capacities")
    st.stop()

base, (has_reg, has_tt, has_rooms, n_reg) = parse_uploads(tuple(pdfs), docx, _hash(pdfs + [docx]))
if base is None:
    missing = []
    if not has_reg: missing.append("attendance registers PDF")
    if not has_tt:  missing.append("master timetable PDF")
    st.error("Couldn't identify: " + ", ".join(missing) +
             ". Make sure the PDFs are the correct CDACC documents.")
    st.stop()

st.caption(f"**{base['centre']}**  ·  Centre code {base['centre_code']}  ·  "
           f"{n_reg} register file{'s' if n_reg != 1 else ''}")

# ---------------- session state (rooms + manual assignments) ----------------
if st.session_state.get('_key') != _hash(pdfs + [docx]):
    st.session_state['_key'] = _hash(pdfs + [docx])
    st.session_state.rooms = copy.deepcopy(base['rooms'])
    st.session_state.manual = {}

with st.sidebar:
    st.header("🏫 Rooms & capacities")
    st.caption("Edit capacities, add or remove rooms — the plan recomputes.")
    rooms_df = st.data_editor(pd.DataFrame(st.session_state.rooms),
                              num_rows="dynamic", width='stretch', key="rooms_editor")
rooms = [{'room': str(r['room']), 'capacity': int(r['capacity'])}
         for _, r in rooms_df.iterrows()
         if str(r.get('room', '')).strip() and pd.notna(r.get('capacity'))]
st.sidebar.metric("Total capacity", sum(r['capacity'] for r in rooms))

# ---------------- allocate ----------------
data = copy.deepcopy(base); data['rooms'] = rooms
for u in data['units']:
    if u['code'] in st.session_state.manual:
        u['slot'] = st.session_state.manual[u['code']]
sessions, unassigned = group_by_session(data['units'])
alloc = {k: allocate_session(v, rooms) for k, v in sessions.items()}

n_inferred = sum(1 for u in data['units'] if u.get('matched') == 'inferred')
n_codeonly = sum(1 for u in data['units'] if u.get('matched') == 'code')
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Units", len(data['units']))
c2.metric("Students", sum(u['count'] for u in data['units']))
c3.metric("Sessions", len(sessions))
c4.metric("Matched", f"{len(data['units']) - len(unassigned)}",
          help=f"Match on unit code + level. {n_codeonly} matched on code where the "
               f"register level differed from the master (same session). "
               f"{n_inferred} matched by shared-tool / name.")
overflow = sum(sum(n for _, n in a[1]) for a in alloc.values())
c5.metric("Unseated", overflow, delta=None if overflow == 0 else "overflow!",
          delta_color="inverse")

if unassigned:
    n_stud = sum(u['count'] for u in unassigned)
    with st.expander(f"⚠️ {len(unassigned)} unit(s) not on the master timetable "
                     f"({n_stud} candidates) — assign a session manually", expanded=False):
        st.caption("These codes aren't on the master timetable (mostly Level 3/4 Cycle-3 "
                   "craft units with no scheduled written session). Assign a session if one applies.")
        labels = {f"{d} · S{s} · {t}": {'date': d, 'session': s, 'time': t}
                  for (d, s, t) in sorted(sessions)}
        for u in unassigned:
            lvl = f"Level {u['level']}" if u.get('level') else "Level ?"
            pick = st.selectbox(f"{u['code']} · {lvl} — {u['name']} ({u['count']} candidates)",
                                ["— leave unassigned —"] + list(labels), key=f"asg_{u['code']}")
            if pick != "— leave unassigned —":
                st.session_state.manual[u['code']] = labels[pick]
                st.rerun()

# ---------------- downloads ----------------
st.divider()
dl1, dl2 = st.columns(2)
dl1.download_button("📄 Download timetable (PDF)",
                    data=build_pdf(data).getvalue(),
                    file_name="mini_timetable.pdf", mime="application/pdf",
                    type="primary", width='stretch')
dl2.download_button("📊 Download Excel workbook",
                    data=build_workbook(data).getvalue(),
                    file_name="mini_timetable.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch')
st.caption("PDF is the print-ready timetable. The Excel workbook has a Summary "
           "sheet plus one sheet per exam day.")

# ---------------- views ----------------
def mkey(k):
    try: return (datetime.datetime.strptime(k[0], '%d %b %Y'), k[1])
    except Exception: return (datetime.datetime.max, k[1])

tab_tt, tab_rooms = st.tabs(["📋 Timetable", "🪑 Room allocation (detail)"])

with tab_tt:
    components.html(build_timetable_html(data), height=760, scrolling=True)

with tab_rooms:
    days = sorted({k[0] for k in sessions}, key=lambda d: mkey((d, '')))
    day = st.selectbox("Exam day", days)
    for k in sorted([s for s in sessions if s[0] == day], key=lambda x: x[1]):
        d, s, t = k; used, unseated = alloc[k]
        st.markdown(f"**Session {s} · {t}** — {sum(u['count'] for u in sessions[k])} students · {len(used)} rooms")
        rows = []
        for room in used:
            for i, o in enumerate(room['occupants']):
                rows.append({'Room': room['room'] if i == 0 else '',
                             'Cap': str(room['capacity']) if i == 0 else '',
                             'Seated': str(room['used']) if i == 0 else '',
                             'Unit Code': o['code'], 'Unit Name': o['name'],
                             'Seats': str(o['seats'])})
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
        if unseated:
            st.error(f"Unseated: {sum(n for _, n in unseated)} — increase room capacity.")
