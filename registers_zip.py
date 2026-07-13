"""Repackage the uploaded attendance-register PDFs into a ZIP, with each unit's
register saved as its own PDF inside a folder named for its assessment day
(e.g. 20_07_2026/). Units with no scheduled day go under 'Unassigned'.

Pages are grouped by unit using the fast pdftotext extraction (form-feed page
breaks, full unit codes); pypdf is used only to copy pages into per-unit PDFs."""
import io
import re
import zipfile
from datetime import datetime
import pypdf
from parsing import pdf_bytes_to_text

CODELINE = re.compile(r'UNIT CODE\s*:?\s*([A-Z]{2,}(?:/[A-Z0-9]+){4,})')
SESSION_LABEL = {'1': 'Morning', '2': 'Mid-morning'}


def fmt_folder(date_str):
    """'20 Jul 2026' -> '20_07_2026'."""
    try:
        return datetime.strptime(date_str, '%d %b %Y').strftime('%d_%m_%Y')
    except Exception:
        return (date_str or 'Unassigned').replace(' ', '_')


def _safe(s, n=70):
    return re.sub(r'[^\w .\-]+', '', s or '').strip()[:n].strip()


def _file_groups(blob, valid):
    """Return (reader, {code: [page indices]}) for one register PDF. A new unit
    starts only on a page whose UNIT CODE is a known unit (`valid`); pages with no
    code, or a mis-extracted code, are continuations of the unit above them."""
    reader = pypdf.PdfReader(io.BytesIO(blob))
    n = len(reader.pages)
    pages = pdf_bytes_to_text(blob).split('\f')
    while len(pages) > n and not pages[-1].strip():   # trim trailing blank page(s)
        pages.pop()
    if len(pages) != n:                               # last-resort clamp to page count
        pages = (pages + [''] * n)[:n]
    groups, cur = {}, None
    for i in range(n):
        m = CODELINE.search(pages[i])
        code = m.group(1) if m else None
        if code in valid and code != cur:             # genuine new unit
            cur = code
            groups.setdefault(code, []).append(i)
        elif cur is not None:                         # continuation / overflow / same
            groups[cur].append(i)
        elif code:                                    # leading page, unknown unit
            cur = code
            groups.setdefault(code, []).append(i)
    return reader, groups


def build_registers_zip(reg_files, code_folder, code_name, code_session=None):
    """reg_files: list of (filename, pdf_bytes). code_folder/code_name/code_session:
    code -> str. A unit's pages are merged across all register files into one PDF,
    filed under its assessment-day folder and tagged with its session (S1/S2).
    Returns a BytesIO ZIP."""
    code_session = code_session or {}
    valid = set(code_folder)                          # known unit codes from the timetable
    parts = {}                                        # code -> [(reader, [idx]), ...]
    for _, blob in reg_files:
        reader, groups = _file_groups(blob, valid)
        for code, idxs in groups.items():
            parts.setdefault(code, []).append((reader, idxs))

    zbuf, used = io.BytesIO(), set()
    with zipfile.ZipFile(zbuf, 'w', zipfile.ZIP_DEFLATED) as z:
        for code, plist in parts.items():
            folder = code_folder.get(code, 'Unsorted')
            base = _safe(code.replace('/', '_'))
            if code_name.get(code):
                base += f" - {_safe(code_name[code])}"
            label = SESSION_LABEL.get(code_session.get(code, ''), '')
            if label:                                 # tag with session for easy ID
                base = f"{label} - {base}"
            path, k = f"{folder}/{base}.pdf", 1
            while path in used:
                k += 1
                path = f"{folder}/{base} ({k}).pdf"
            used.add(path)
            writer = pypdf.PdfWriter()
            for reader, idxs in plist:
                for i in idxs:
                    writer.add_page(reader.pages[i])
            b = io.BytesIO()
            writer.write(b)
            z.writestr(path, b.getvalue())
    zbuf.seek(0)
    return zbuf


if __name__ == '__main__':
    import parsing, time, zipfile as zf
    regs = [(f'CYCLE{i}.pdf', open(f'JULY 2026 CYCLE {i}.pdf', 'rb').read()) for i in (1, 2, 3)]
    tt = open('JULY 2026 TT.pdf', 'rb').read()
    rooms = parsing.parse_rooms(open('ROOM ALLOCATION CDACC ASSESSMENT.docx', 'rb').read())
    data = parsing.build_data([parsing.pdf_bytes_to_text(b) for _, b in regs], tt, rooms)
    cf = {u['code']: (fmt_folder(u['slot']['date']) if u.get('slot') else 'Unassigned')
          for u in data['units']}
    cn = {u['code']: u['name'] for u in data['units']}
    cs = {u['code']: (u['slot'] or {}).get('session', '') for u in data['units']}
    t0 = time.time()
    zbytes = build_registers_zip(regs, cf, cn, cs).getvalue()
    print(f"built {len(zbytes)//1024} KB in {time.time()-t0:.1f}s")
    z = zf.ZipFile(io.BytesIO(zbytes))
    folders = sorted({n.split('/')[0] for n in z.namelist()})
    print('folders:', folders)
    print('files:', len(z.namelist()), '| Unsorted:',
          sum(1 for n in z.namelist() if n.startswith('Unsorted/')))
    print('sample:', z.namelist()[:3])
