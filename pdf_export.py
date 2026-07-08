"""Print-clean PDF of the centre mini-timetable, in the master-timetable layout:
Curriculum Cycle, Course, Unit Code, Unit Name, Level, Duration + Candidates, Room.
Landscape A4. Pure-Python (reportlab) so it runs on Streamlit Cloud."""
import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                Spacer, KeepTogether)
from timetable_html import enrich_sessions
from ui import fmt_time_range, fmt_duration

INK = colors.HexColor('#16211d')
ACCENT = colors.HexColor('#0d5b48')
MUTED = colors.HexColor('#5b6b64')
RULE = colors.HexColor('#c9d3cd')
TINT = colors.HexColor('#eef4f1')
WARN = colors.HexColor('#9a5a08')


def _styles():
    ss = getSampleStyleSheet()
    return {
        'centre': ParagraphStyle('centre', parent=ss['Title'], fontName='Times-Bold',
                                 fontSize=22, textColor=INK, spaceAfter=3, leading=25),
        'sub': ParagraphStyle('sub', fontName='Helvetica', fontSize=11, textColor=MUTED,
                              spaceAfter=1, leading=14),
        'sess': ParagraphStyle('sess', fontName='Helvetica-Bold', fontSize=13,
                               textColor=ACCENT, spaceBefore=15, spaceAfter=5, leading=15),
        'cell': ParagraphStyle('cell', fontName='Helvetica', fontSize=10, textColor=INK,
                               leading=12.5),
        'code': ParagraphStyle('code', fontName='Courier', fontSize=8, textColor=INK,
                               leading=10.5),
        'room': ParagraphStyle('room', fontName='Courier', fontSize=9.3, textColor=INK,
                               leading=12),
        'roomsplit': ParagraphStyle('roomsplit', fontName='Courier', fontSize=9.3,
                                    textColor=WARN, leading=12),
        'th': ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=9.5, textColor=INK,
                             leading=12),
    }


def build_pdf(data):
    S = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=14 * mm,
                            bottomMargin=12 * mm, leftMargin=12 * mm, rightMargin=12 * mm,
                            title=f"{data.get('centre','')} — Mini Timetable")
    sessions = enrich_sessions(data)
    n_units = sum(len(s['rows']) for s in sessions)
    n_stud = sum(s['students'] for s in sessions)

    series = data.get('series') or ''
    subtitle = ('Written Assessment Timetable'
                + (f' &nbsp;·&nbsp; {series} Assessment Series' if series else ''))
    flow = [Paragraph(data.get('centre', 'Assessment Centre'), S['centre']),
            Paragraph(subtitle, S['sub']),
            Paragraph(f"Centre code {data.get('centre_code','')} &nbsp;·&nbsp; {n_units} units "
                      f"&nbsp;·&nbsp; {n_stud} candidates &nbsp;·&nbsp; {len(sessions)} sessions",
                      S['sub']),
            Spacer(1, 6)]

    # column widths (landscape A4 usable ~ 273mm); fills the full width
    W = [24 * mm, 39 * mm, 42 * mm, 64 * mm, 16 * mm, 21 * mm, 16 * mm, 51 * mm]
    header = ['Curriculum Cycle', 'Course', 'Unit Code', 'Unit Name', 'Level',
              'Duration', 'Cand.', 'Room']

    for s in sessions:
        title = (f"{s['day']} {s['date']} &nbsp;·&nbsp; Session {s['session']} "
                 f"&nbsp;·&nbsp; {fmt_time_range(s['time'])} &nbsp;&nbsp;<font color='#5b6b64'>"
                 f"{s['students']} candidates, {s['rooms']} rooms</font>")
        rows = [[Paragraph(c, S['th']) for c in header]]
        for r in s['rows']:
            split = ',' in r['room']
            rows.append([
                Paragraph(r.get('cycle') or '—', S['cell']),
                Paragraph(r.get('course') or '', S['cell']),
                Paragraph(r['code'], S['code']),
                Paragraph(r['name'] or '', S['cell']),
                Paragraph(f"Level {r['level']}" if r['level'] else '—', S['cell']),
                Paragraph(fmt_duration(r.get('duration')), S['cell']),
                Paragraph(str(r['count']), S['cell']),
                Paragraph(r['room'] or '—', S['roomsplit'] if split else S['room']),
            ])
        t = Table(rows, colWidths=W, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), TINT),
            ('LINEBELOW', (0, 0), (-1, 0), 0.8, ACCENT),
            ('LINEBELOW', (0, 1), (-1, -1), 0.4, RULE),
            ('ALIGN', (4, 0), (6, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        flow.append(KeepTogether([Paragraph(title, S['sess']), t]))

    doc.build(flow)
    buf.seek(0)
    return buf


if __name__ == '__main__':
    import parsing
    reg = parsing.pdf_bytes_to_text(open('JULY 2026 CYCLE 2.pdf', 'rb').read())
    tt = open('JULY 2026 TT.pdf', 'rb').read()
    rooms = parsing.parse_rooms(open('ROOM ALLOCATION CDACC ASSESSMENT.docx', 'rb').read())
    data = parsing.build_data([reg], tt, rooms)
    open('mini_timetable.pdf', 'wb').write(build_pdf(data).getvalue())
    print('wrote mini_timetable.pdf')
