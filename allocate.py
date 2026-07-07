"""Per-session room allocation (bin-packing).
Rule: mix units freely up to room capacity; keep each unit whole if it fits in
the largest room; split a unit across rooms only when it exceeds the largest room."""
from collections import defaultdict

def slot_key(s):
    if not s: return None
    return (s['date'], s['session'], s['time'])

def group_by_session(units):
    sessions = defaultdict(list)
    unassigned = []
    for u in units:
        k = slot_key(u.get('slot'))
        (unassigned if k is None else sessions[k]).append(u)
    return sessions, unassigned

def allocate_session(units, rooms):
    """Return list of room dicts: {room, capacity, used, occupants:[{code,name,seats}]}."""
    R = [{'room': r['room'], 'capacity': r['capacity'], 'remaining': r['capacity'],
          'occupants': []} for r in sorted(rooms, key=lambda x: -x['capacity'])]
    maxcap = max((r['capacity'] for r in R), default=0)

    def put(room, u, seats):
        room['occupants'].append({'code': u['code'], 'name': u['name'], 'seats': seats})
        room['remaining'] -= seats

    oversized = sorted([u for u in units if u['count'] > maxcap], key=lambda x: -x['count'])
    whole     = sorted([u for u in units if u['count'] <= maxcap], key=lambda x: -x['count'])

    def spill(u, left):
        """Split a unit across the roomiest rooms; return seats that didn't fit."""
        while left > 0:
            room = max(R, key=lambda r: r['remaining'])
            if room['remaining'] <= 0:
                return left
            take = min(room['remaining'], left)
            put(room, u, take); left -= take
        return 0

    unseated = []
    # 1) Split oversized units (bigger than any single room) across the roomiest rooms
    for u in oversized:
        rem = spill(u, u['count'])
        if rem: unseated.append((u, rem))
    # 2) Whole units: keep intact in the tightest-fitting room; if none fits, split
    #    across whatever space remains so nobody is left out until seats truly run out.
    for u in whole:
        fits = [r for r in R if r['remaining'] >= u['count']]
        if fits:
            put(min(fits, key=lambda r: r['remaining']), u, u['count'])  # tightest whole fit
        else:
            rem = spill(u, u['count'])
            if rem: unseated.append((u, rem))

    used = [r for r in R if r['occupants']]
    for r in used: r['used'] = r['capacity'] - r['remaining']
    return used, unseated

if __name__ == '__main__':
    import json
    data = json.load(open('data.json', encoding='utf-8'))
    sessions, unassigned = group_by_session(data['units'])
    # demo on the busiest session
    busiest = max(sessions, key=lambda k: sum(u['count'] for u in sessions[k]))
    units = sessions[busiest]
    used, unseated = allocate_session(units, data['rooms'])
    d,s,t = busiest
    print(f"BUSIEST SESSION  {d}  Session {s}  {t}")
    print(f"{len(units)} units, {sum(u['count'] for u in units)} students -> {len(used)} rooms\n")
    for r in used:
        print(f"  {r['room']:12s} cap {r['capacity']:3d} | seated {r['used']:3d} | {len(r['occupants'])} unit(s)")
        for o in r['occupants']:
            print(f"        {o['seats']:3d}  {o['code']:24s} {o['name'][:32]}")
    print(f"\nUnseated: {unseated if unseated else 'none'}")
    print(f"\nTotal sessions to schedule: {len(sessions)} | Unassigned units: {len(unassigned)}")
