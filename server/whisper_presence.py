"""Read-only adapter for chat; do not change the multiplayer presence contract."""
import math


def nearby(conn, a, b, now):
    # Use only spaces with an unambiguous shared instance in the current contract.
    from .multiplayer import VISIBLE_SECONDS
    rows = {r['user_id']: r for r in conn.execute(
        'SELECT user_id,host_id,scene,place,floor,x,y,z,seen FROM mp_presence WHERE user_id IN (?,?)', (a,b))}
    if len(rows) != 2:
        return False
    left, right = rows[a], rows[b]
    for row in (left, right):
        if not 0 <= now-row['seen'] < VISIBLE_SECONDS or row['scene'] not in ('village', 'home'):
            return False
        if (row['place'] or row['scene']) not in ('village', 'home'):
            return False
        if row['user_id'] != row['host_id'] and not conn.execute(
                'SELECT 1 FROM mp_visits WHERE user_id=? AND host_id=? AND expires>?',
                (row['user_id'], row['host_id'], now)).fetchone():
            return False
    if any(left[key] != right[key] for key in ('host_id','scene')):
        return False
    if (left['place'] or left['scene']) != (right['place'] or right['scene']):
        return False
    if left['floor'] != right['floor']:
        return False
    distance = sum((left[key]-right[key])**2 for key in ('x','y','z'))
    return math.isfinite(distance) and distance <= 8**2
