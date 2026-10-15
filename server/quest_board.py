"""Daily requests using existing residents, conditions and reward scale.

Five offers rotate at server KST midnight. Three can be accepted/completed per
account/day; unfinished offers expire. Display time never changes the board date.
All writes use the application's idempotent transaction.
"""
import json
from datetime import datetime, timedelta, timezone

from fastapi import Request

from . import homestead, npc_homes, npc_letters, quest_content, quests, village_residents
from .models import Mutation

BOARD_SIZE = 5
DAILY_LIMIT = 3
ZONE = timezone(timedelta(hours=9))
SCHEMA = '''
CREATE TABLE IF NOT EXISTS quest_board_progress (
 user_id TEXT NOT NULL REFERENCES users(id), day TEXT NOT NULL, quest_id TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('active','done')), accepted REAL NOT NULL,
 baseline TEXT NOT NULL DEFAULT '{}', progress TEXT NOT NULL DEFAULT '{}',
 completed REAL, stars INTEGER, letter_id TEXT REFERENCES npc_letters(id),
 PRIMARY KEY(user_id,day,quest_id));
'''


def board_day(now):
    return datetime.fromtimestamp(now, ZONE).date().isoformat()


def offers(now):
    # Stable across restarts/accounts; a full rotation includes every resident.
    day_index = int((now + 9 * 3600) // 86400)
    catalog = tuple(quests.QUESTS)
    start = day_index * BOARD_SIZE % len(catalog)
    return tuple(catalog[(start + n) % len(catalog)] for n in range(BOARD_SIZE))


def public(conn, user_id, settings, now):
    day = board_day(now)
    rows = {r['quest_id']: r for r in conn.execute(
        'SELECT * FROM quest_board_progress WHERE user_id=? AND day=?', (user_id, day))}
    opened = quests.unlocked(conn, user_id)
    waiting = quests.held(conn, user_id, settings)
    missing = village_residents.absent(conn, user_id, settings)
    listing = []
    for quest_id in offers(now):
        item = quests.entry(conn, user_id, quest_id, rows.get(quest_id), settings.quest_stars_scale,
                            opened and quest_id not in waiting)
        if item['npc'] in missing and item['state'] != 'done':
            item['state'] = 'locked'
        item.update(day=day, letter=True)
        content = quest_content.quest_template(quest_id, now)
        if content is not None:
            item['content'] = content
        listing.append(item)
    completed = sum(r['state'] == 'done' for r in rows.values())
    return {'day': day, 'timezone': 'Asia/Seoul',
            'resets_at': (int((now + 9 * 3600) // 86400) + 1) * 86400 - 9 * 3600,
            'unlocked': opened, 'scale': settings.quest_stars_scale,
            'limits': {'accept': DAILY_LIMIT, 'complete': DAILY_LIMIT},
            'accepted': len(rows), 'completed': completed,
            'remaining_accepts': max(0, DAILY_LIMIT - len(rows)),
            'remaining_completions': max(0, DAILY_LIMIT - completed), 'list': listing}


class QuestBoard:
    def __init__(self, app, db, settings, clock, auth, mutate, money, host_for):
        with db.read() as conn:
            conn.executescript(SCHEMA)

        def check(conn, user, day, quest_id, now):
            if quest_id not in quests.QUESTS:
                quests.fail('quest_not_found', 404)
            if day != board_day(now):
                quests.fail('quest_board_expired')
            if quest_id not in offers(now):
                quests.fail('quest_board_not_offered', 404)
            if host_for(conn, user['id']) != user['id']:
                quests.fail('quest_own_village_only')
            app.state.village_residents.sync_in(conn, user['id'], now)
            if not quests.unlocked(conn, user['id'], quest_id) or quest_id in quests.held(conn, user['id'], settings):
                quests.fail('quests_locked')
            return quests.QUESTS[quest_id]

        def get_row(conn, user_id, day, quest_id):
            return conn.execute('SELECT * FROM quest_board_progress WHERE user_id=? AND day=? AND quest_id=?',
                                (user_id, day, quest_id)).fetchone()

        def active(conn, user_id, day, quest_id):
            row = get_row(conn, user_id, day, quest_id)
            if row is None:
                quests.fail('quest_not_active')
            if row['state'] == 'done':
                quests.fail('quest_already_done')
            return row

        def reply(conn, user_id, quest_id, now, **extra):
            board = public(conn, user_id, settings, now)
            return {'quest': next(q for q in board['list'] if q['id'] == quest_id), 'board': board, **extra}

        @app.get('/v1/quest_board')
        def read(request: Request):
            with db.read() as conn:
                user = auth(conn, request)
            app.state.village_residents.residents_for(user['id'])
            with db.read() as conn:
                return {'board': public(conn, user['id'], settings, clock())}

        @app.post('/v1/quest_board/{day}/{quest_id}/accept')
        def accept(day: str, quest_id: str, body: quests.QuestAccept, request: Request):
            def apply(conn, user):
                now = clock()
                quest = check(conn, user, day, quest_id, now)
                row = get_row(conn, user['id'], day, quest_id)
                if row and row['state'] == 'done':
                    quests.fail('quest_already_done')
                if row is None:
                    accepted = conn.execute('SELECT COUNT(*) FROM quest_board_progress WHERE user_id=? AND day=?',
                                            (user['id'], day)).fetchone()[0]
                    if accepted >= DAILY_LIMIT:
                        quests.fail('quest_board_daily_limit', 429)
                    baseline = quests.baseline_for(conn, user['id'], quest)
                    progress = {}
                    if quest['kind'] == 'visit' and body.place in quest['places'] and (not quest.get('night') or homestead.night(now)):
                        progress = {'places': [body.place], 'last': now}
                    conn.execute('INSERT INTO quest_board_progress(user_id,day,quest_id,state,accepted,baseline,progress) '
                                 "VALUES (?,?,?,'active',?,?,?)",
                                 (user['id'], day, quest_id, now, json.dumps(baseline), json.dumps(progress)))
                return reply(conn, user['id'], quest_id, now)
            return mutate(request, body, f'quest_board_accept:{day}:{quest_id}', apply)

        @app.post('/v1/quest_board/{day}/{quest_id}/progress')
        def progress(day: str, quest_id: str, body: quests.QuestReport, request: Request):
            def apply(conn, user):
                now = clock()
                quest = check(conn, user, day, quest_id, now)
                row = active(conn, user['id'], day, quest_id)
                if quest['kind'] not in ('visit', 'talk'):
                    quests.fail('quest_wrong_kind')
                if body.place not in quest['places']:
                    quests.fail('quest_bad_place', 422)
                state = json.loads(row['progress'])
                places = state.get('places', [])
                if quest.get('night') and body.place not in places and not homestead.night(now):
                    quests.fail('quest_not_night')
                if body.place not in places and len(places) < quest['count']:
                    if now - float(state.get('last', 0)) < quests.VISIT_GAP:
                        quests.fail('quest_too_fast', 429)
                    places.append(body.place)
                    conn.execute('UPDATE quest_board_progress SET progress=? WHERE user_id=? AND day=? AND quest_id=?',
                                 (json.dumps({'places': places, 'last': now}), user['id'], day, quest_id))
                return reply(conn, user['id'], quest_id, now)
            return mutate(request, body, f'quest_board_progress:{day}:{quest_id}', apply)

        @app.post('/v1/quest_board/{day}/{quest_id}/complete')
        def complete(day: str, quest_id: str, body: Mutation, request: Request):
            def apply(conn, user):
                now = clock()
                quest = check(conn, user, day, quest_id, now)
                row = active(conn, user['id'], day, quest_id)
                completed = conn.execute("SELECT COUNT(*) FROM quest_board_progress WHERE user_id=? AND day=? AND state='done'",
                                         (user['id'], day)).fetchone()[0]
                if completed >= DAILY_LIMIT:
                    quests.fail('quest_board_daily_limit', 429)
                extra = quests.fulfill(conn, user['id'], quest_id, row, now)
                reference = f'{day}:{quest_id}'
                stars = quests.reward(quest_id, settings.quest_stars_scale)
                if stars:
                    money(conn, user['id'], stars, 'quest_board_reward', reference)
                letter_id = npc_letters.dispatch(conn, user['id'], quest['npc'], 'request_done', reference, now,
                                                 {'quest_id': quest_id, 'day': day})
                conn.execute("UPDATE quest_board_progress SET state='done',completed=?,stars=?,letter_id=? "
                             'WHERE user_id=? AND day=? AND quest_id=?',
                             (now, stars, letter_id, user['id'], day, quest_id))
                shards = conn.execute('SELECT shards FROM users WHERE id=?', (user['id'],)).fetchone()[0]
                letters = [letter for letter in npc_homes.letters(conn, user['id']) if letter['id'] == letter_id]
                return reply(conn, user['id'], quest_id, now, stars=stars, shards=shards, letters=letters, **extra)
            return mutate(request, body, f'quest_board_complete:{day}:{quest_id}', apply)
