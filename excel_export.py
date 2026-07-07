"""Build the mini-timetable Excel workbook: a Summary sheet + one sheet per day."""
import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from allocate import group_by_session, allocate_session

HDR   = PatternFill('solid', fgColor='1F4E78')
BANNER= PatternFill('solid', fgColor='2E75B6')
SUB   = PatternFill('solid', fgColor='DDEBF7')
WHITE = Font(color='FFFFFF', bold=True)
BOLD  = Font(bold=True)
THIN  = Side(style='thin', color='BFBFBF')
BORDER= Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CTR   = Alignment(horizontal='center', vertical='center')
LEFT  = Alignment(horizontal='left', vertical='center', wrap_text=True)

def _month_order(date_str):
    try: return datetime.strptime(date_str, '%d %b %Y')
    except Exception: return datetime.max

def build_workbook(data):
    units, rooms = data['units'], data['rooms']
    sessions, unassigned = group_by_session(units)
    # allocate every session
    alloc = {k: allocate_session(v, rooms) for k, v in sessions.items()}

    wb = Workbook()
    # ---------------- Summary ----------------
    ws = wb.active; ws.title = 'Summary'
    ws.append([f"MINI TIMETABLE — {data['centre']}  ({data['centre_code']})"])
    ws['A1'].font = Font(bold=True, size=14)
    ws.append([]); ws.append(['Date','Session','Time','Units','Students','Rooms used','Unseated'])
    for c in ws[3]: c.font = WHITE; c.fill = HDR; c.alignment = CTR; c.border = BORDER
    for k in sorted(sessions, key=lambda x: (_month_order(x[0]), x[1])):
        d,s,t = k; used, unseated = alloc[k]
        ws.append([d, f'S{s}', t, len(sessions[k]),
                   sum(u['count'] for u in sessions[k]), len(used),
                   sum(n for _,n in unseated)])
    widths = [14,9,12,8,10,12,10]
    for i,w in enumerate(widths,1): ws.column_dimensions[get_column_letter(i)].width = w

    # ---------------- One sheet per day ----------------
    by_day = {}
    for k in sessions: by_day.setdefault(k[0], []).append(k)
    for day in sorted(by_day, key=_month_order):
        title = day.replace(' ', '')[:31]
        ws = wb.create_sheet(title)
        cols = ['Room','Cap','Seated','Cycle','Course','Unit Code','Unit Name','Lvl','Dur','Seats']
        w = [14,6,8,16,26,24,40,6,8,7]
        for i,cw in enumerate(w,1): ws.column_dimensions[get_column_letter(i)].width = cw
        ws.append([f"{day} — {data['centre']}"]); ws['A1'].font = Font(bold=True, size=13)
        ws.append([])
        for k in sorted(by_day[day], key=lambda x: x[1]):
            d,s,t = k; used, unseated = alloc[k]
            r = ws.max_row + 1
            ws.append([f"SESSION {s}   {t}   —   {sum(u['count'] for u in sessions[k])} students, {len(used)} rooms"])
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(cols))
            cell = ws.cell(r,1); cell.font = WHITE; cell.fill = BANNER; cell.alignment = LEFT
            ws.append(cols)
            for c in ws[ws.max_row]: c.font = BOLD; c.fill = SUB; c.border = BORDER; c.alignment = CTR
            for room in used:
                first = True
                for o in room['occupants']:
                    ws.append([room['room'] if first else '',
                               room['capacity'] if first else '',
                               room['used'] if first else '',
                               _attr(units,o['code'],'cycle'), _attr(units,o['code'],'course'),
                               o['code'], o['name'], _attr(units,o['code'],'level'),
                               _attr(units,o['code'],'duration'), o['seats']])
                    for c in ws[ws.max_row]: c.border = BORDER; c.alignment = LEFT
                    first = False
            if unseated:
                ws.append(['UNSEATED'] + ['']*8 + [sum(n for _,n in unseated)])
            ws.append([])
    # ---------------- Unassigned units ----------------
    if unassigned:
        ws = wb.create_sheet('Unassigned')
        ws.append(['Units with no master-timetable slot — assign manually'])
        ws['A1'].font = BOLD
        ws.append(['Unit Code','Unit Name','Course','Level','Students'])
        for c in ws[2]: c.font = WHITE; c.fill = HDR
        for u in unassigned:
            ws.append([u['code'], u['name'], u['course'], u['level'], u['count']])
        for i,cw in enumerate([26,42,26,8,10],1): ws.column_dimensions[get_column_letter(i)].width = cw

    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf

def _attr(units, code, field):
    for u in units:
        if u['code']==code: return u.get(field,'')
    return ''

if __name__ == '__main__':
    import json
    data = json.load(open('data.json', encoding='utf-8'))
    buf = build_workbook(data)
    open('mini_timetable.xlsx','wb').write(buf.getvalue())
    print('Wrote mini_timetable.xlsx', len(buf.getvalue()), 'bytes')
