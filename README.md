# Mini Timetable & Room Allocation

A **dynamic** Streamlit app: upload the three CDACC documents and it parses them,
allocates rooms for every assessment session, and exports an Excel workbook.

## What you upload
1. **Master timetable** PDF — CDACC national timetable (the fixed session dates/times).
2. **Attendance registers** PDF — your centre's units and candidates.
3. **Room allocation** `.docx` — your venues and their capacities.

Order doesn't matter — the two PDFs are auto-detected by their content.

## What it does
- Reads each unit's fixed date/session/time from the master timetable.
- Reads your centre's units and candidate counts from the registers.
- For every session, packs units into rooms:
  - units are **mixed freely** into a room up to its capacity,
  - each unit is kept **whole** when it fits in the largest room,
  - a unit is **split across rooms** only when it is larger than the biggest room.
- Lets you **edit rooms/capacities** live and **manually assign** any unit whose
  code isn't on the master timetable.
- Exports an Excel workbook: a **Summary** sheet + **one sheet per exam day**.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
Local PDF text extraction uses poppler `pdftotext` if present, otherwise falls
back to the bundled `pdfplumber` (slower). On Windows, `pdftotext` ships with
Git-for-Windows / MSYS2, or install poppler separately.

## Deploy to Streamlit Cloud
1. Push this folder to a GitHub repo (the source PDFs/DOCX are git-ignored — see below).
2. https://share.streamlit.io → **New app** → point it at `app.py`.
3. Cloud installs `poppler-utils` from `packages.txt` (fast PDF extraction) and the
   Python deps from `requirements.txt`.

## Files
| File | Role |
|------|------|
| `app.py` | Streamlit UI: upload, view allocation, edit rooms, download Excel |
| `parsing.py` | PDF/DOCX text extraction + parsing (uploads → structured data) |
| `allocate.py` | Per-session bin-packing engine |
| `excel_export.py` | Builds the Excel workbook |
| `requirements.txt` | Python dependencies |
| `packages.txt` | System package for Streamlit Cloud (`poppler-utils`) |

## Privacy
Attendance registers contain candidate names and registration numbers.
`.gitignore` excludes all `*.pdf` / `*.docx` so personal data is **never committed**.
Uploaded files are parsed in memory at runtime and not persisted.

## Notes
- Units in the registers whose code is **not** on the master timetable are flagged
  in the app for manual session assignment.
- For the July 2026 sample data, peak load is 256 students (27 Jul, S1) against
  465 seats, so every session fits.
