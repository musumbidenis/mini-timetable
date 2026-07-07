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
                                 fontSize=17, textColor=INK, spaceAfter=2, leading=20),
        'sub': ParagraphStyle('sub', fontName='Helvetica', fontSize=9, textColor=MUTED,
                              spaceAfter=1),
        'sess': ParagraphStyle('sess', fontName='Helvetica-Bold', fontSize=10.5,
                               textColor=ACCENT, spaceBefore=12, spaceAfter=4),
        'cell': ParagraphStyle('cell', fontName='Helvetica', fontSize=8.5, textColor=INK,
                               leading=10.5),
        'code': ParagraphStyle('code', fontName='Courier', fontSize=7, textColor=INK,
                               leading=9),
        'room': ParagraphStyle('room', fontName='Courier', fontSize=8, textColor=INK,
                               leading=10.5),
        'roomsplit': ParagraphStyle('roomsplit', fontName='Courier', fontSize=8,
                                    textColor=WARN, leading=10.5),
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

    flow = [Paragraph(data.get('centre', 'Assessment Centre'), S['centre']),
            Paragraph('Written Assessment Timetable &nbsp;·&nbsp; July / August 2026', S['sub']),
            Paragraph(f"Centre code {data.get('centre_code','')} &nbsp;·&nbsp; {n_units} units "
                      f"&nbsp;·&nbsp; {n_stud} candidates &nbsp;·&nbsp; {len(sessions)} sessions",
                      S['sub']),
            Spacer(1, 4)]

    # column widths (landscape A4 usable ~ 273mm)
    W = [22 * mm, 38 * mm, 38 * mm, 64 * mm, 15 * mm, 15 * mm, 14 * mm, 67 * mm]
    header = ['Curriculum Cycle', 'Course', 'Unit Code', 'Unit Name', 'Level',
              'Duration', 'Cand.', 'Room']

    for s in sessions:
        title = (f"{s['day']} {s['date']} &nbsp;·&nbsp; Session {s['session']} "
                 f"&nbsp;·&nbsp; {s['time']} &nbsp;&nbsp;<font color='#5b6b64'>"
                 f"{s['students']} candidates, {s['rooms']} rooms</font>")
        rows = [[Paragraph(c, S['cell']) for c in header]]
        for r in s['rows']:
            split = ',' in r['room']
            rows.append([
                Paragraph(r.get('cycle') or '—', S['cell']),
                Paragraph(r.get('course') or '', S['cell']),
                Paragraph(r['code'], S['code']),
                Paragraph(r['name'] or '', S['cell']),
                Paragraph(f"Level {r['level']}" if r['level'] else '—', S['cell']),
                Paragraph(r.get('duration') or '—', S['cell']),
                Paragraph(str(r['count']), S['cell']),
                Paragraph(r['room'] or '—', S['roomsplit'] if split else S['room']),
            ])
        t = Table(rows, colWidths=W, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), TINT),
            ('LINEBELOW', (0, 0), (-1, 0), 0.7, ACCENT),
            ('LINEBELOW', (0, 1), (-1, -1), 0.35, RULE),
            ('ALIGN', (4, 0), (6, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
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
