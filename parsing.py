"""Document parsing for the Mini Timetable app.
Takes uploaded file *bytes* -> structured data. Primary PDF text extraction is
poppler `pdftotext -layout` (fast); falls back to pdfplumber if poppler absent."""
import io, re, os, tempfile, subprocess
from collections import defaultdict
from docx import Document

CAND = re.compile(r'\b\d{6,}[A-Z]?/[A-Z]+/\d+/\d{4}/\d+')
CODE = re.compile(r'\b[A-Z]{2,}(?:/[A-Z0-9]+){4,}\b')

# ---------------- PDF text extraction ----------------
def pdf_bytes_to_text(data: bytes) -> str:
    """Try poppler pdftotext -layout; fall back to pdfplumber."""
    tmp_pdf = tmp_txt = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(data); tmp_pdf = f.name
        tmp_txt = tmp_pdf[:-4] + '.txt'
        subprocess.run(['pdftotext', '-layout', tmp_pdf, tmp_txt],
                       check=True, capture_output=True)
        with open(tmp_txt, encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _pdfplumber_text(data)
    finally:
        for p in (tmp_pdf, tmp_txt):
            if p and os.path.exists(p):
                try: os.remove(p)
                except OSError: pass

def _pdfplumber_text(data: bytes) -> str:
    import pdfplumber
    out = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text(layout=True) or '')
    return '\n'.join(out)

# ---------------- classification ----------------
def classify_pdf(text: str) -> str:
    if 'Assessment Registrations' in text or 'CANDIDATE NAME' in text:
        return 'registers'
    if 'MASTER TIMETABLE' in text or 'GENERAL INSTRUCTIONS' in text or 'WRITTEN ASSESSMENT' in text:
        return 'master'
    return 'unknown'

# ---------------- registers ----------------
def parse_registers(text: str):
    """-> (centre, centre_code, {code: {name,course,level,cands:set}})"""
    # Name & code sit in a two-column header that wraps across lines; grab the
    # whole block up to COURSE NAME, then strip the label and the code out.
    blob = re.search(r'CENTRE NAME\s*:\s*(.*?)COURSE NAME', text, re.S)
    blob = blob.group(1) if blob else ''
    cc = re.search(r':\s*([0-9]{5,}[A-Z]?)', blob)
    ccode = cc.group(1) if cc else ''
    centre = re.sub(r'CENTRE CODE', ' ', blob)
    centre = re.sub(r':\s*[0-9]{5,}[A-Z]?', ' ', centre)
    centre = re.sub(r'\s+', ' ', centre).strip()
    units = {}
    for b in text.split('Report Type: Assessment Registrations'):
        mc = re.search(r'UNIT CODE\s*:?\s*([A-Z0-9/]+)', b)
        if not mc or not CODE.fullmatch(mc.group(1).strip()):
            continue
        code = mc.group(1).strip()
        nm = re.search(r'UNIT NAME\s*:\s*(.+)', b)
        cs = re.search(r'COURSE NAME\s*:\s*(.+)', b)
        # The level digit is right-aligned and often wraps below a continued
        # course name, so it isn't adjacent to "Level". Take the first lone
        # 3-6 in the COURSE LEVEL -> UNIT NAME header region.
        reg = re.search(r'COURSE LEVEL(.*?)UNIT NAME', b, re.S)
        lv = re.search(r'\b([3-6])\b', reg.group(1)) if reg else None
        u = units.setdefault(code, {'code': code, 'name': '', 'course': '', 'level': '', 'cands': set()})
        # In the two-column PDF a short value shares its line with the next
        # label ("... Prepare Pastries   UNIT CODE"); trim the trailing label.
        if nm and not u['name']: u['name'] = _clean(nm.group(1), 'UNIT CODE')
        if cs and not u['course']: u['course'] = _clean(cs.group(1), 'COURSE LEVEL')
        if lv and not u['level']: u['level'] = lv.group(1)
        u['cands'].update(CAND.findall(b))
    return centre, ccode, units

def _clean(value, trailing_label):
    """Drop a trailing column label the layout appended, and tidy whitespace."""
    value = re.split(re.escape(trailing_label), value)[0]
    return re.sub(r'\s+', ' ', value).strip()

# ---------------- master timetable (coordinate-based table reader) ----------------
# The master timetable is a borderless print table. We reconstruct each row from
# word x/y positions: columns by x-range, wrapped cells merged per unit (anchored
# on the unit-code line), and each unit tied to the Date/Session banner above it.
_CODE_ROW = re.compile(r'^[A-Z]{2,}(?:/[A-Z0-9]+){4,}$')
_COLS = [(40, 110, 'cycle'), (110, 235, 'course'), (235, 360, 'code'),
         (360, 450, 'name'), (450, 502, 'level'), (502, 700, 'duration')]
_HDR_WORDS = {'Curriculum', 'Cycle', 'Course', 'Unit', 'Code', 'Name', 'Level', 'Duration'}
_BANNER = re.compile(r'Date:\s*(\d+\s+\w+\s+\d+)\s+Day:\s*(\w+).*?Session:\s*(\d)'
                     r'.*?Time:\s*([\d ]+[AP]M)')

def _col_of(x0):
    for a, b, name in _COLS:
        if a <= x0 < b:
            return name
    return None

def _page_lines(words):
    """Group words into visual lines by their 'top', return [(top, 'line text', [words])]."""
    lines = {}
    for w in words:
        key = round(w['top'] / 3.0)          # ~3px tolerance
        lines.setdefault(key, []).append(w)
    out = []
    for ws in lines.values():
        ws.sort(key=lambda w: w['x0'])
        out.append((min(w['top'] for w in ws), ' '.join(w['text'] for w in ws), ws))
    out.sort()
    return out

def parse_master_table(pdf_bytes: bytes):
    """-> list of row dicts {code, cycle, course, name, level, duration,
    date, day, session, time}. A code may recur at several levels/sessions, so
    every row is kept (deduped on code+level+session)."""
    import pdfplumber
    entries, seen = [], set()
    current = {'date': '', 'day': '', 'session': '', 'time': ''}
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue
            lines = _page_lines(words)
            # banners on this page, with their y position
            banners = []
            for top, text, _ in lines:
                m = _BANNER.search(text)
                if m:
                    banners.append((top, {'date': m.group(1).strip(), 'day': m.group(2),
                                          'session': m.group(3),
                                          'time': re.sub(r'\s+', ' ', m.group(4)).strip()}))
            # unit-code anchors
            anchors = [(w['top'], w['text']) for w in words
                       if _col_of(w['x0']) == 'code' and _CODE_ROW.match(w['text'])]
            if not anchors:
                # page may still carry a banner (session start with table overleaf)
                if banners:
                    current = banners[-1][1]
                continue
            tops = [t for t, _ in anchors]
            cells = {t: {'cycle': [], 'course': [], 'name': [], 'level': [], 'duration': []}
                     for t in tops}
            for w in words:
                c = _col_of(w['x0'])
                if not c or c == 'code':
                    continue
                nt = min(tops, key=lambda t: abs(t - w['top']))
                if abs(nt - w['top']) > 16:
                    continue
                if w['text'] in _HDR_WORDS and w['top'] < min(tops) - 14:
                    continue
                cells[nt][c].append((w['top'], w['x0'], w['text']))
            # assign each unit to the banner most recently above it (carry across pages)
            bsorted = sorted(banners)
            for top, code in sorted(anchors):
                sess = current
                for btop, bdict in bsorted:
                    if btop <= top:
                        sess = bdict
                cell = cells[top]
                join = lambda k: ' '.join(t for _, _, t in sorted(cell[k]))
                rec = {'code': code,
                       'cycle': re.sub(r',\s*', ', ', join('cycle')),  # 'Cycle 01, Cycle 02'
                       'course': join('course'), 'name': join('name'),
                       'level': re.sub(r'\D', '', join('level')),      # 'Level 6' -> '6'
                       'duration': join('duration'), **sess}
                key = (code, rec['level'], rec['date'], rec['session'], rec['time'])
                if key not in seen:
                    seen.add(key)
                    entries.append(rec)
            if banners:
                current = bsorted[-1][1]
    return entries

# ---------------- rooms ----------------
def parse_rooms(docx_bytes: bytes):
    doc = Document(io.BytesIO(docx_bytes))
    rooms = []
    for t in doc.tables:
        for row in t.rows:
            cells = [c.text.strip() for c in row.cells]
            # find a name + integer capacity pair anywhere in the row
            name = next((c for c in cells if c and not c.isdigit() and c.upper() not in ('ROOM',)), '')
            cap = next((c for c in cells if c.isdigit()), '')
            if name and cap and name.upper() != 'CAPACITY':
                rooms.append({'room': name, 'capacity': int(cap)})
    return rooms

# ---------------- assemble ----------------
def merge_registers(reg_texts):
    """Combine one or more register PDFs, unioning candidates per unit code."""
    centre = ccode = ''
    merged = {}
    for text in reg_texts:
        c, cc, units = parse_registers(text)
        centre = centre or c
        ccode = ccode or cc
        for code, u in units.items():
            m = merged.setdefault(code, {'code': code, 'name': '', 'course': '',
                                         'level': '', 'cands': set()})
            for f in ('name', 'course', 'level'):
                if u[f] and not m[f]: m[f] = u[f]
            m['cands'].update(u['cands'])
    return centre, ccode, merged

def _norm_name(s):
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()

def _level_sig(code):
    """Code with the level segment (2nd-to-last) blanked, e.g.
    ENG/OS/AUT/CR/01/4/MA -> ENG/OS/AUT/CR/01/L/MA. Lets a unit the register
    codes at one level match the same shared tool the master lists at another."""
    p = code.split('/')
    if len(p) >= 2:
        p[-2] = 'L'
    return '/'.join(p)

def build_data(reg_texts, tt_bytes: bytes, rooms):
    """reg_texts: extracted register text(s). tt_bytes: master-timetable PDF bytes
    (read as a table for clean cycle/course/name/level/duration + session)."""
    if isinstance(reg_texts, str):          # accept a single text too
        reg_texts = [reg_texts]
    centre, ccode, units = merge_registers(reg_texts)
    master = parse_master_table(tt_bytes)

    # Indexes over every master row. Primary match is (code, level): a code can be
    # scheduled at more than one level, so the register's level must agree with the
    # master's. Fallbacks (name / level-agnostic code) are used only when the
    # candidates all point to a single session, else it stays unmapped.
    by_codelevel, by_code = {}, defaultdict(list)
    name_idx, sig_idx = defaultdict(list), defaultdict(list)
    for m in master:
        by_codelevel.setdefault((m['code'], m['level']), m)
        by_code[m['code']].append(m)
        name_idx[_norm_name(m['name'])].append(m)
        sig_idx[_level_sig(m['code'])].append(m)

    def _slotkey(m):
        return (m['date'], m['session'], m['time'])

    def _infer(code, name):
        recs = []
        for group in (name_idx.get(_norm_name(name)), sig_idx.get(_level_sig(code))):
            if group and len({_slotkey(x) for x in group}) == 1:
                recs += group
        if recs and len({_slotkey(x) for x in recs}) == 1:
            return recs[0]
        return None

    out = []
    for code, u in units.items():
        n = len(u['cands'])
        if n == 0: continue
        # 1) code AND level agree between master and register
        m = by_codelevel.get((code, u['level']))
        matched = 'exact' if m else ''
        # 2) code is on the master at other level(s) — all share one session,
        #    so the session is safe even though the level differs
        if not m and by_code.get(code):
            m = by_code[code][0]
            matched = 'code'
        # 3) code written differently by the register — infer via name / shared tool
        if not m:
            m = _infer(code, u['name'])
            matched = 'inferred' if m else ''
        m = m or {}
        # Level always from the documents: the register's COURSE LEVEL is the
        # candidate's actual level (equals the master row's level on an exact match).
        level = u['level'] or m.get('level', '')
        out.append({
            'code': code,
            'name': m.get('name') if matched in ('exact', 'code') else (u['name'] or m.get('name', '')),
            'course': m.get('course') or u['course'],
            'level': level,
            'cycle': m.get('cycle', ''),
            'duration': m.get('duration', ''),
            'count': n,
            'matched': matched,
            'slot': ({'date': m['date'], 'day': m['day'], 'session': m['session'],
                      'time': m['time'], 'cycle': m.get('cycle', '')}
                     if m.get('date') else None),
        })
    return {'centre': centre or 'Assessment Centre', 'centre_code': ccode,
            'units': out, 'rooms': rooms}
