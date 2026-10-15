"""Resident moves, durable bonds, notifications, migration and host isolation."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from server import admin_cli, npc_homes, npc_letters, story, village_residents as residency
from server.app import create_app
from server.config import Settings


def mutation(**values):
    return {'request_id': str(uuid.uuid4()), **values}


def account(client, name='resident'):
    result = client.post('/v1/auth/register', json={'username': name, 'password': 'Resident-test-password'})
    assert result.status_code == 200, result.text
    return {'Authorization': 'Bearer ' + result.json()['token']}


@pytest.fixture
def world(tmp_path):
    now = [1_800_000_000.0]
    settings = Settings(data_dir=tmp_path, resident_moves=True)
    app = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as client:
        headers = account(client)
        with app.state.db.read() as conn:
            host = conn.execute("SELECT id FROM users WHERE username='resident'").fetchone()[0]
        yield app, client, now, headers, host
    app.state.db.close()


def roster(client, headers):
    result = client.get('/v1/village/residency', headers=headers)
    assert result.status_code == 200, result.text
    return result.json()


def finish_chapter(client, headers):
    # Preserve new-player residency before preparing the already-tested opening
    # chapter prerequisite, without creating unrelated gifts or story letters.
    host = roster(client, headers)['host_id']
    with client.app.state.db.transaction() as conn:
        conn.execute("UPDATE story_progress SET step='done' WHERE user_id=?", (host,))


def rescue(client, headers):
    finish_chapter(client, headers)
    for event in story.EVENTS:
        result = client.post('/v1/story/step', headers=headers, json=mutation(action='event', event=event))
        assert result.status_code == 200, result.text
    return result.json()


def move(world, entering):
    app, _, now, _, host = world
    with app.state.db.transaction() as conn:
        return residency.move_in(conn, host, 'shopkeeper', now[0], app.state.settings, entering=entering)


def test_new_player_and_feature_off(world):
    app, client, now, headers, host = world
    result = roster(client, headers)
    assert result['plots'] == {'danbi_plot': 'empty'}
    assert result['residents'][0]['state'] == 'away'
    assert result['residents'][0]['home'] == 'danbi_house'
    assert result['news'] == []
    app.state.settings.resident_moves = False
    disabled = roster(client, headers)
    assert disabled['enabled'] is False and disabled['version'] == 0
    assert disabled['residents'][0]['home'] == '13_shop'
    assert disabled['residents'][0]['state'] == 'home'
    assert disabled['news'] == []
    with app.state.db.transaction() as conn:
        with pytest.raises(HTTPException, match='resident_moves_disabled'):
            residency.leave(conn, host, 'shopkeeper', now[0], app.state.settings)


def test_rescue_delay_exact_boundary_letters_and_board_once(world):
    app, client, now, headers, host = world
    assert 'danbi_rescued' in rescue(client, headers)['story']['events']
    arriving = roster(client, headers)
    assert arriving['residents'][0]['state'] == 'arriving'
    assert arriving['plots']['danbi_plot'] == 'building'
    assert [n['kind'] for n in arriving['news']] == ['arriving']
    due = now[0] + 90
    now[0] = due - 1
    assert roster(client, headers)['residents'][0]['state'] == 'arriving'
    assert client.get('/v1/letters', headers=headers).json()['unread'] == 0
    now[0] = due
    me = client.get('/v1/me', headers=headers).json()
    home = me['residents']
    assert me['npc_letters_unread'] == 1
    assert home['residents'][0]['state'] == 'home'
    assert home['residents'][0]['since'] == due
    assert home['plots']['danbi_plot'] == 'built'
    assert home['version'] == arriving['version'] + 1
    assert home['news'][0]['kind'] == 'moved_in' and home['news'][0]['at'] == due
    mail = client.get('/v1/letters', headers=headers).json()['letters']
    assert len(mail) == 1 and mail[0]['move'] == {'kind': 'in', 'npc': 'shopkeeper'}
    assert mail[0]['level'] == 0 and 'quest' not in mail[0] and 'story' not in mail[0]
    assert mail[0]['id'] == home['news'][0]['letter_id']
    assert mail[0]['event'] == {
        'type': 'move_in', 'key': 'residency:0',
        'payload': {'kind': 'in', 'home': 'danbi_house', 'plot': 'danbi_plot', 'moves': 0}}
    assert roster(client, headers) == home
    assert not move(world, True)
    marked = client.post('/v1/letters/read', headers=headers, json=mutation(ids=[mail[0]['id']]))
    assert marked.json()['unread'] == 0


def test_event_validation_and_retries(world):
    app, client, now, headers, host = world
    result = client.post('/v1/story/step', headers=headers, json=mutation(action='event', event='forest_told'))
    assert result.status_code == 409 and result.json()['detail'] == 'story_not_done'
    finish_chapter(client, headers)
    for event in ('forest_gate', 'danbi_rescued'):
        result = client.post('/v1/story/step', headers=headers, json=mutation(action='event', event=event))
        assert result.status_code == 409 and result.json()['detail'] == 'story_event_order'
    assert client.post('/v1/story/step', headers=headers, json=mutation(action='event')).status_code == 422
    assert client.post('/v1/story/step', headers=headers, json=mutation(action='event', event='unknown')).status_code == 422
    rescue(client, headers)
    body = mutation(action='event', event='danbi_rescued')
    original = roster(client, headers)
    now[0] += 1
    first = client.post('/v1/story/step', headers=headers, json=body)
    assert client.post('/v1/story/step', headers=headers, json=body).json() == first.json()
    assert roster(client, headers) == original
    with app.state.db.read() as conn:
        assert conn.execute('SELECT count(*) FROM story_events WHERE user_id=?', (host,)).fetchone()[0] == 3


def test_departure_and_return_keep_bonds_memory_and_gift_storage(world):
    app, client, now, headers, host = world
    rescue(client, headers)
    now[0] += 90
    client.post('/v1/story/step', headers=headers, json=mutation(action='greet', npc='shopkeeper'))
    me = client.get('/v1/me', headers=headers).json()
    item = me['objects'][0]
    with app.state.db.transaction() as conn:
        conn.execute('INSERT INTO npc_friendship VALUES (?,?,?,?,?)', (host, 'shopkeeper', 85, 3, 20))
        conn.execute("UPDATE objects SET state='gifted' WHERE id=?", (item['id'],))
        conn.execute("INSERT INTO npc_items(object_id,host_id,npc_id,home_id,state,slot,fresh,size,tags,gifted) "
                     "VALUES (?,?,'shopkeeper','danbi_house','placed','old_slot',0,'[1,1,1]','[]',?)", (item['id'], host, now[0]))
        conn.execute("INSERT INTO npc_homes(host_id,home_id,seed,next_change_at,updated) VALUES (?,'danbi_house',1,?,?)", (host, now[0] + 300, now[0]))
        before = dict(conn.execute('SELECT * FROM npc_friendship WHERE host_id=?', (host,)).fetchone())
    memory = roster(client, headers)['residents'][0]['memory']
    assert move(world, False)
    assert not move(world, False)
    assert roster(client, headers)['residents'][0]['state'] == 'leaving'
    now[0] += 90
    away = roster(client, headers)
    assert away['residents'][0]['state'] == 'away' and away['residents'][0]['moves'] == 1
    assert away['plots']['danbi_plot'] == 'empty'
    with app.state.db.read() as conn:
        stored = conn.execute('SELECT state,slot FROM npc_items WHERE object_id=?', (item['id'],)).fetchone()
        assert tuple(stored) == ('stored', None)
        assert conn.execute("SELECT next_change_at FROM npc_homes WHERE host_id=? AND home_id='danbi_house'", (host,)).fetchone()[0] is None
    # Retrying the one-time rescue must never bring a departed resident back.
    rescue(client, headers)
    assert roster(client, headers)['residents'][0]['state'] == 'away'
    assert move(world, True)
    now[0] += 90
    back = roster(client, headers)['residents'][0]
    assert back['back'] and back['hearts'] == 2 and back['memory'] == memory
    assert back['friendship']['points'] == 85
    with app.state.db.read() as conn:
        assert dict(conn.execute('SELECT * FROM npc_friendship WHERE host_id=?', (host,)).fetchone()) == before
        item_state = conn.execute('SELECT state,fresh,home_id FROM npc_items WHERE object_id=?', (item['id'],)).fetchone()
        assert tuple(item_state) == ('stored', 1, 'danbi_house')
        levels = [r[0] for r in conn.execute('SELECT level FROM npc_letters WHERE host_id=? ORDER BY level', (host,))]
        assert levels == list(range(npc_letters.EVENT_LEVEL_START, npc_letters.EVENT_LEVEL_START + 3))
    mail = client.get('/v1/letters', headers=headers).json()['letters']
    assert [m['move']['kind'] for m in mail] == ['back', 'out', 'in']
    # A story rehearsal must not turn an old friend into a stranger.
    with app.state.db.transaction() as conn:
        story.reset(conn, host, now[0])
    assert roster(client, headers)['residents'][0]['memory'] == memory


@pytest.mark.parametrize('chapter', ['missing', 'done', 'craft'])
def test_old_saves_migrate_once_without_notification(world, chapter):
    app, client, now, headers, host = world
    with app.state.db.transaction() as conn:
        if chapter == 'missing':
            conn.execute('DELETE FROM story_progress WHERE user_id=?', (host,))
        else:
            conn.execute('UPDATE story_progress SET step=?,greeted=? WHERE user_id=?', (chapter, '["shopkeeper"]', host))
    first = roster(client, headers)
    resident = first['residents'][0]
    assert resident['state'] == ('away' if chapter == 'craft' else 'home')
    assert resident['legacy'] is (chapter != 'craft')
    assert resident['memory']['met'] is (chapter != 'missing')
    assert first['news'] == [] and client.get('/v1/letters', headers=headers).json()['unread'] == 0
    assert roster(client, headers) == first


def test_rescue_while_disabled_applies_after_restart(world):
    app, client, now, headers, host = world
    app.state.settings.resident_moves = False
    rescue(client, headers)
    assert roster(client, headers)['residents'][0]['home'] == '13_shop'
    app.state.settings.resident_moves = True
    restarted = create_app(app.state.settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(restarted) as fresh:
        assert roster(fresh, headers)['residents'][0]['state'] == 'arriving'
        now[0] += 90
        assert roster(fresh, headers)['residents'][0]['state'] == 'home'
    restarted.state.db.close()


def test_plot_furniture_returns_and_both_placement_routes_reserve_plot(world):
    app, client, now, headers, host = world
    item = client.get('/v1/me', headers=headers).json()['objects'][0]
    # Simulate furniture from a save predating the reserved plot.
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE objects SET state='placed',x=9.5,z=-28 WHERE id=?", (item['id'],))
        conn.execute('INSERT INTO furniture_locations VALUES (?,?)', (item['id'], 'village'))
    rescue(client, headers)
    now[0] += 90
    me = client.get('/v1/me', headers=headers).json()
    returned = next(o for o in me['objects'] if o['id'] == item['id'])
    assert returned['state'] == 'inventory' and returned['version'] == item['version'] + 1
    assert me['residents']['news'][0]['returned_to_bag'] == [item['id']]
    for suffix, extra in [('', {}), ('/placement', {'room': 'village'})]:
        result = client.post('/v1/objects/' + item['id'] + suffix, headers=headers,
                             json=mutation(action='place', version=returned['version'], x=9.5, z=-28, **extra))
        assert result.status_code == 409 and result.json()['detail'] == 'plot_reserved', result.text


def test_plot_clearance_returns_stacked_furniture_once(world):
    app, client, now, headers, host = world
    parent = client.get('/v1/me', headers=headers).json()['objects'][0]
    child = str(uuid.uuid4())
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE objects SET state='placed',x=9.5,z=-28 WHERE id=?", (parent['id'],))
        conn.execute('INSERT INTO furniture_locations VALUES (?,?)', (parent['id'], 'village'))
        conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,state,x,z,created) "
                     "SELECT ?,owner_id,creator_id,asset_id,'stacked piece','placed',10,-28,? FROM objects WHERE id=?",
                     (child, now[0], parent['id']))
        conn.execute('INSERT INTO furniture_locations VALUES (?,?)', (child, 'village'))
        conn.execute("INSERT INTO object_mounts(object_id,surface,y,parent_id) VALUES (?,'top',1,?)", (child, parent['id']))
    rescue(client, headers)
    now[0] += 90
    me = client.get('/v1/me', headers=headers).json()
    assert set(me['residents']['news'][0]['returned_to_bag']) == {parent['id'], child}
    objects = {item['id']: item for item in me['objects']}
    assert objects[parent['id']]['version'] == parent['version'] + 1
    assert objects[child]['version'] == 2
    assert all(objects[item]['state'] == 'inventory' for item in (parent['id'], child))
    with app.state.db.read() as conn:
        assert not conn.execute('SELECT 1 FROM object_mounts WHERE object_id=?', (child,)).fetchone()
        assert not conn.execute('SELECT 1 FROM furniture_locations WHERE object_id IN (?,?)', (parent['id'], child)).fetchone()


def test_carried_furniture_cannot_enter_reserved_plot(world):
    app, client, now, headers, host = world
    parent = client.get('/v1/me', headers=headers).json()['objects'][0]
    child = str(uuid.uuid4())
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE objects SET state='placed',x=9.5,z=-20 WHERE id=?", (parent['id'],))
        conn.execute('INSERT INTO furniture_locations VALUES (?,?)', (parent['id'], 'village'))
        conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,state,x,z,created) "
                     "SELECT ?,owner_id,creator_id,asset_id,'stacked piece','placed',9.5,-20.5,? FROM objects WHERE id=?",
                     (child, now[0], parent['id']))
        conn.execute('INSERT INTO furniture_locations VALUES (?,?)', (child, 'village'))
        conn.execute("INSERT INTO object_mounts(object_id,surface,y,parent_id) VALUES (?,'top',1.2,?)", (child, parent['id']))
    response = client.post('/v1/objects/' + parent['id'] + '/placement', headers=headers,
                           json=mutation(action='place', room='village', version=parent['version'], x=9.5, z=-22.8))
    assert response.status_code == 409 and response.json()['detail'] == 'plot_reserved', response.text
    with app.state.db.read() as conn:
        assert tuple(conn.execute('SELECT z,version FROM objects WHERE id=?', (parent['id'],)).fetchone()) == (-20, parent['version'])
        assert tuple(conn.execute('SELECT z,version FROM objects WHERE id=?', (child,)).fetchone()) == (-20.5, 1)
        assert conn.execute('SELECT parent_id FROM object_mounts WHERE object_id=?', (child,)).fetchone()[0] == parent['id']


def test_host_is_selected_by_visit_not_query_parameter(world):
    app, client, now, headers, host = world
    guest = account(client, 'visitor')
    rescue(client, headers)
    now[0] += 90
    own = roster(client, headers)
    guest_own = roster(client, guest)
    assert guest_own['host_id'] != host and guest_own['residents'][0]['state'] == 'away'
    invite = client.post('/v1/social/invites', headers=headers, json=mutation(username='visitor', kind='village')).json()
    assert client.post('/v1/social/invites/' + invite['id'] + '/accept', headers=guest, json=mutation()).status_code == 200
    assert roster(client, guest) == own
    assert client.get('/v1/residents?host_id=ignored', headers=guest).json() == own
    assert client.get('/v1/me', headers=guest).json()['residents']['host_id'] == guest_own['host_id']
    assert client.get('/v1/letters', headers=guest).json()['unread'] == 0
    assert client.get('/v1/village/residency').status_code == 401
    assert client.post('/v1/village/residency', headers=headers, json=mutation()).status_code == 405
    result = client.post('/v1/story/step', headers=guest, json=mutation(action='event', event='forest_told'))
    assert result.status_code == 409


def test_danbi_quest_is_locked_while_absent_and_reopens(world):
    app, client, now, headers, host = world
    roster(client, headers)
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE story_progress SET step='done' WHERE user_id=?", (host,))
    listing = client.get('/v1/quests', headers=headers).json()['quests']['list']
    assert next(q for q in listing if q['id'] == 'danbi_home')['state'] == 'locked'
    for action in ('accept', 'progress', 'complete'):
        result = client.post('/v1/quests/danbi_home/' + action, headers=headers, json=mutation(**({'place': 'village'} if action == 'progress' else {})))
        assert result.status_code == 409 and result.json()['detail'] == 'quests_locked'
    assert move(world, True)
    now[0] += 90
    # No residency poll: the quest route settles the due arrival itself.
    result = client.post('/v1/quests/danbi_home/accept', headers=headers, json=mutation())
    assert result.status_code == 200, result.text
    assert move(world, False)
    now[0] += 90
    listing = client.get('/v1/quests', headers=headers).json()['quests']['list']
    assert next(q for q in listing if q['id'] == 'danbi_home')['state'] == 'locked'
    with app.state.db.read() as conn:
        assert conn.execute("SELECT state FROM quest_progress WHERE user_id=? AND quest_id='danbi_home'", (host,)).fetchone()[0] == 'active'
    assert move(world, True)
    now[0] += 90
    listing = client.get('/v1/quests', headers=headers).json()['quests']['list']
    assert next(q for q in listing if q['id'] == 'danbi_home')['state'] in ('active', 'ready')


def test_concurrent_poll_and_rollback_do_not_duplicate_events(world):
    app, client, now, headers, host = world
    rescue(client, headers)
    now[0] += 90
    with pytest.raises(RuntimeError):
        with app.state.db.transaction() as conn:
            residency.settle(conn, host, now[0], app.state.settings)
            raise RuntimeError('abort')
    with app.state.db.read() as conn:
        assert conn.execute('SELECT count(*) FROM npc_letters WHERE host_id=?', (host,)).fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM npc_letter_events WHERE host_id=?', (host,)).fetchone()[0] == 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: app.state.village_residents.residents_for(host), range(8)))
    assert all(r == results[0] for r in results)
    with app.state.db.read() as conn:
        assert conn.execute('SELECT count(*) FROM village_news WHERE host_id=?', (host,)).fetchone()[0] == 2
        assert conn.execute('SELECT count(*) FROM npc_letters WHERE host_id=?', (host,)).fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM npc_letter_events WHERE host_id=?', (host,)).fetchone()[0] == 1


def test_operator_commands_and_zero_delay(world, monkeypatch, capsys):
    app, client, now, headers, host = world
    monkeypatch.setenv('TRIPOTHON_RESIDENT_MOVES', 'on')
    monkeypatch.setenv('TRIPOTHON_RESIDENT_ARRIVE_SECONDS', '0')
    monkeypatch.setenv('TRIPOTHON_RESIDENT_LEAVE_SECONDS', '0')
    monkeypatch.setattr(admin_cli.time, 'time', lambda: now[0])
    args = ['residents', 'resident']
    for command, expected in [('move-in', 'home'), ('move-out', 'away'), ('move-in', 'home'), ('show', 'home')]:
        assert admin_cli.main(args + [command, '--data-dir', str(app.state.settings.data_dir)]) == 0
        assert json.loads(capsys.readouterr().out)['residents'][0]['state'] == expected
    assert roster(client, headers)['residents'][0]['back']


@pytest.mark.parametrize('delay', [-1, float('nan'), float('inf'), 30 * 86400 + 1])
def test_invalid_move_settings(tmp_path, delay):
    with pytest.raises(ValueError, match='resident move timing'):
        Settings(data_dir=tmp_path, resident_arrive_seconds=delay).validate()


def test_news_window_does_not_delete_history(world):
    app, client, now, headers, host = world
    rescue(client, headers)
    now[0] += 90
    roster(client, headers)
    now[0] += 8 * 86400
    assert app.state.village_residents.residents_for(host)['news'] == []
    with app.state.db.read() as conn:
        assert conn.execute('SELECT count(*) FROM village_news WHERE host_id=?', (host,)).fetchone()[0] == 2


def test_schema_upgrade_preserves_old_save_and_restart_keeps_new_state(world):
    app, client, now, headers, host = world
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE story_progress SET step='done',greeted='[\"shopkeeper\"]' WHERE user_id=?", (host,))
        conn.execute('INSERT INTO npc_friendship VALUES (?,?,?,?,?)', (host, 'shopkeeper', 160, 7, 11))
        for table in ('village_news', 'village_residents', 'village_roster', 'npc_conversation_memory', 'story_events'):
            conn.execute('DROP TABLE ' + table)
    upgraded = create_app(app.state.settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(upgraded) as fresh:
        old = roster(fresh, headers)
        assert old['residents'][0]['legacy'] and old['residents'][0]['hearts'] == 3
        assert old['residents'][0]['memory']['met'] and old['news'] == []
        with upgraded.state.db.transaction() as conn:
            residency.leave(conn, host, 'shopkeeper', now[0], upgraded.state.settings)
        now[0] += 90
        away = roster(fresh, headers)
        assert away['residents'][0]['state'] == 'away'
    upgraded.state.db.close()
    restarted = create_app(app.state.settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(restarted) as fresh:
        assert roster(fresh, headers) == away
        with restarted.state.db.transaction() as conn:
            residency.arrive(conn, host, 'shopkeeper', now[0], restarted.state.settings)
        now[0] += 90
        back = roster(fresh, headers)['residents'][0]
        assert back['back'] and back['hearts'] == 3
        assert back['memory'] == old['residents'][0]['memory']
        assert fresh.get('/v1/letters', headers=headers).json()['letters'][0]['move']['kind'] == 'back'
    restarted.state.db.close()


def test_read_mail_settles_move_and_disabled_mode_creates_no_rows(world):
    app, client, now, headers, host = world
    app.state.settings.resident_moves = False
    roster(client, headers)
    with app.state.db.read() as conn:
        assert conn.execute('SELECT count(*) FROM village_residents').fetchone()[0] == 0
    app.state.settings.resident_moves = True
    rescue(client, headers)
    now[0] += 90
    mail = client.get('/v1/letters', headers=headers).json()
    assert mail['unread'] == 1 and mail['letters'][0]['move']['kind'] == 'in'


def test_plot_configuration_drives_new_saves(world, monkeypatch):
    app, client, now, headers, host = world
    monkeypatch.setitem(residency.MOVERS, 'shopkeeper', {
        'name': 'Danbi', 'plot': 'map_named_plot', 'home': 'map_named_house', 'old_home': '13_shop'})
    monkeypatch.setattr(residency, 'PLOTS', {'map_named_plot': {'x': 22, 'z': -35, 'radius': 3}})
    rescue(client, headers)
    now[0] += 90
    result = roster(client, headers)
    assert result['plots'] == {'map_named_plot': 'built'}
    assert result['residents'][0]['home'] == 'map_named_house'
    assert residency.plot_reserved(22, -35) == 'plot_reserved'
    assert residency.plot_reserved(9.5, -28) is None
