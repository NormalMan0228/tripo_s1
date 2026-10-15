"""Resident event mail, stored in the existing npc_letters mailbox.

The caller owns the transaction: completing a request or moving a resident and
writing its letter either succeed together or roll back together. These events
never create currency, items, or friendship points.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone


SCHEMA = '''
CREATE TABLE IF NOT EXISTS npc_letter_events (
 letter_id TEXT PRIMARY KEY REFERENCES npc_letters(id) ON DELETE CASCADE,
 host_id TEXT NOT NULL REFERENCES users(id), npc_id TEXT NOT NULL,
 event TEXT NOT NULL CHECK(event IN ('request_done','resident_day','move_in','move_out')),
 event_key TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}',
 UNIQUE(host_id,npc_id,event,event_key));
'''

EVENTS = frozenset(('request_done', 'resident_day', 'move_in', 'move_out'))
# Hearts occupy 1..4, old request letters 100, legacy move letters 200 and up,
# and story runs 0 and below. New move mail uses the same event namespace.
EVENT_LEVEL_START = 1_000_000
SERVER_TIMEZONE = timezone(timedelta(hours=9))
# Village anniversary dates, not character birthdays. The schedule is stable
# across accounts, processes, and years; missed dates are not delivered later.
RESIDENT_DAYS = {
    'naru': '01-09', 'scout': '02-06', 'sora': '03-12',
    'gentleman': '04-08', 'poet': '05-14', 'moru': '06-10',
    'lamplighter': '07-07', 'haeru': '08-11', 'stroller': '09-16',
    'postman': '10-09', 'sweeper': '10-25', 'fisher': '11-13',
    'kid': '12-18',
}


def server_date(now):
    """A fixed KST date, independent of headers and cosmetic time overrides."""
    return datetime.fromtimestamp(now, SERVER_TIMEZONE).date()


def dispatch(conn, user_id, npc, event, event_key, now, payload=None):
    """Return one durable letter ID per (owner, resident, event, event key).

    Initialize SCHEMA at application startup, then call inside the same write
    transaction as the event. Keys identify durable gameplay events, not HTTP
    attempts. Retrying an event retains its first payload, timestamp, and read
    state. Payload stays nested in the API to keep type/key reserved.
    """
    from .npc_homes import NPCS, SENDERS

    if not conn.in_transaction:
        raise ValueError('npc_letter_transaction_required')
    if npc not in NPCS and npc not in SENDERS:
        raise ValueError('npc_not_found')
    if event not in EVENTS or not isinstance(event_key, str) or not event_key:
        raise ValueError('invalid_npc_letter_event')
    if payload is not None and not isinstance(payload, dict):
        raise ValueError('invalid_npc_letter_payload')
    old = conn.execute(
        'SELECT letter_id FROM npc_letter_events WHERE host_id=? AND npc_id=? AND event=? AND event_key=?',
        (user_id, npc, event, event_key)).fetchone()
    if old:
        return old['letter_id']
    level = conn.execute(
        'SELECT max(?,COALESCE(max(level)+1,?)) FROM npc_letters WHERE host_id=? AND npc_id=?',
        (EVENT_LEVEL_START, EVENT_LEVEL_START, user_id, npc)).fetchone()[0]
    letter_id = str(uuid.uuid4())
    conn.execute('INSERT INTO npc_letters(id,host_id,npc_id,level,created) VALUES (?,?,?,?,?)',
                 (letter_id, user_id, npc, level, now))
    conn.execute('INSERT INTO npc_letter_events(letter_id,host_id,npc_id,event,event_key,payload) VALUES (?,?,?,?,?,?)',
                 (letter_id, user_id, npc, event, event_key, json.dumps(payload or {}, ensure_ascii=False)))
    return letter_id


def daily_pending(conn, user_id, now):
    """Whether this account has an undelivered anniversary for today's date."""
    today = server_date(now)
    return any(
        anniversary == today.strftime('%m-%d') and not conn.execute(
            "SELECT 1 FROM npc_letter_events WHERE host_id=? AND npc_id=? AND event='resident_day' AND event_key=?",
            (user_id, npc, today.isoformat())).fetchone()
        for npc, anniversary in RESIDENT_DAYS.items())


def dispatch_daily(conn, user_id, now):
    """Lazily deliver today's anniversary mail in the caller's transaction."""
    today = server_date(now)
    return [dispatch(conn, user_id, npc, 'resident_day', today.isoformat(), now,
                     {'date': today.isoformat(), 'occasion': 'village_anniversary'})
            for npc, anniversary in RESIDENT_DAYS.items() if anniversary == today.strftime('%m-%d')]
