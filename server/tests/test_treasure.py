"""Treasure chests (server/treasure.py): each pays its starseeds once per account through the ledger,
retries are idempotent, visitors cannot open a friend's, the operator's scale/off switch, the
reward table, the operator's view and the story reset leaving chests alone."""
import json
import re
import sqlite3
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server import admin_cli, treasure

ROOT = Path(__file__).resolve().parents[2]


def mutation(**kw):
    return {'request_id': str(uuid.uuid4()), **kw}


def account(c, name, password='Chest-test-password'):
    r = c.post('/v1/auth/register', json={'username': name, 'password': password})
    assert r.status_code == 200, r.text
    return {'Authorization': 'Bearer ' + r.json()['token']}


def make(tmp_path, now, **kw):
    settings = Settings(data_dir=tmp_path, daily_generation_limit=100, user_daily_generation_limit=50, **kw)
    return create_app(settings, clock=lambda: now[0], worker_enabled=False)


@pytest.fixture
def world(tmp_path):
    now = [1_800_000_000.0]
    app = make(tmp_path, now)
    with TestClient(app) as c:
        yield app, c, now


def db(app):
    conn = sqlite3.connect(app.state.settings.data_dir / 'world.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn


def open_chest(c, h, chest_id, body=None):
    return c.post('/v1/chests/%s/open' % chest_id, headers=h, json=body or mutation())


def me(c, h):
    return c.get('/v1/me', headers=h).json()


def paid(app, chest_id=None):
    with db(app) as conn:
        rows = conn.execute("SELECT reference,amount FROM ledger WHERE reason='chest_reward'").fetchall()
    return [(r['reference'], r['amount']) for r in rows if chest_id in (None, r['reference'])]


def test_a_chest_opens_once_and_pays_through_the_ledger(world):
    app, c, now = world
    h = account(c, 'finder')
    before = me(c, h)
    assert before['chests'] == {'opened': [], 'total': 11}
    reply = open_chest(c, h, 'home')
    assert reply.status_code == 200, reply.text
    data = reply.json()
    assert data['stars'] == 10 and data['shards'] == before['shards'] + 10
    assert data['chest'] == {'id': 'home', 'place': 'home', 'open': True, 'stars': 10, 'opened': now[0]}
    assert data['chests'] == {'opened': ['home'], 'total': 11}
    after = me(c, h)
    assert after['shards'] == before['shards'] + 10 and after['chests']['opened'] == ['home']
    assert paid(app) == [('home', 10)]
    # The full list says which are open and what each pays.
    listing = c.get('/v1/chests', headers=h).json()['chests']
    assert listing['found'] == 1 and listing['total'] == 11 and listing['opened'] == ['home']
    assert {e['id']: e['open'] for e in listing['list']}['home'] is True
    assert next(e for e in listing['list'] if e['id'] == 'fields_cafe') == {'id': 'fields_cafe', 'place': 'fields', 'open': False, 'stars': 4}
    # A field chest pays its own amount.
    now[0] += 30
    assert open_chest(c, h, 'fields_cafe').json()['stars'] == 4
    assert me(c, h)['shards'] == before['shards'] + 14
    assert me(c, h)['chests']['opened'] == ['home', 'fields_cafe']


def test_a_retry_is_idempotent_and_a_second_open_is_refused(world):
    app, c, now = world
    h = account(c, 'retrier')
    start = me(c, h)['shards']
    body = mutation()
    first = open_chest(c, h, 'lighthouse_rocks', body)
    # The same request again (a lost reply): the same answer, nothing paid twice.
    again = open_chest(c, h, 'lighthouse_rocks', body)
    assert first.status_code == again.status_code == 200 and first.json() == again.json()
    assert me(c, h)['shards'] == start + 5 and paid(app) == [('lighthouse_rocks', 5)]
    # A new request for the same chest: already open.
    now[0] += 60
    second = open_chest(c, h, 'lighthouse_rocks')
    assert second.status_code == 409 and second.json()['detail'] == 'chest_already_open'
    assert me(c, h)['shards'] == start + 5 and paid(app) == [('lighthouse_rocks', 5)]
    # The request id reused for another chest is refused.
    assert open_chest(c, h, 'camp_tents', body).json()['detail'] == 'request_id_reused'
    # A reward already in the ledger (a restored table) still blocks a second payment.
    with db(app) as conn:
        conn.execute("DELETE FROM chest_opened WHERE chest_id='lighthouse_rocks'")
    assert open_chest(c, h, 'lighthouse_rocks').json()['detail'] == 'chest_already_open'
    assert paid(app) == [('lighthouse_rocks', 5)]


def test_refusals(world):
    app, c, now = world
    h = account(c, 'hostess')
    guest = account(c, 'guesting')
    assert open_chest(c, h, 'nowhere').status_code == 404 and open_chest(c, h, 'nowhere').json()['detail'] == 'chest_not_found'
    assert c.get('/v1/chests').status_code == 401
    assert c.post('/v1/chests/home/open', json=mutation()).status_code == 401
    assert c.post('/v1/chests/home/open', headers=h, json={'request_id': 'x'}).status_code == 422
    # Two chests in a breath: the second waits for the gap.
    assert open_chest(c, h, 'square_cape').status_code == 200
    now[0] += 0.5
    fast = open_chest(c, h, 'square_backyard')
    assert fast.status_code == 429 and fast.json()['detail'] == 'chest_too_fast'
    now[0] += treasure.CHEST_GAP
    assert open_chest(c, h, 'square_backyard').status_code == 200
    # While visiting a friend's village the friend's chests stay shut (the server refuses too).
    invite = c.post('/v1/social/invites', headers=h, json=mutation(username='guesting', kind='village')).json()
    assert c.post('/v1/social/invites/' + invite['id'] + '/accept', headers=guest, json=mutation()).json()['visiting']
    for chest_id in ('home', 'fields_cafe'):
        refused = open_chest(c, guest, chest_id)
        assert refused.status_code == 409 and refused.json()['detail'] == 'chest_own_village_only'
    assert me(c, guest)['chests']['opened'] == [] and paid(app, 'home') == []


def test_the_operator_scale_and_off_switch(tmp_path, monkeypatch):
    now = [1_800_000_000.0]
    off = make(tmp_path / 'off', now, chest_stars_scale=0)
    with TestClient(off) as c:
        h = account(c, 'unpaid')
        before = me(c, h)['shards']
        assert c.get('/v1/chests', headers=h).json()['chests']['scale'] == 0
        reply = open_chest(c, h, 'home').json()
        # Still opens (and stays open), pays nothing.
        assert reply['stars'] == 0 and reply['chest']['open'] and me(c, h)['shards'] == before
        assert me(c, h)['chests']['opened'] == ['home'] and paid(off) == []
        now[0] += 10
        assert open_chest(c, h, 'home').json()['detail'] == 'chest_already_open'
    double = make(tmp_path / 'double', now, chest_stars_scale=2.0)
    with TestClient(double) as c:
        h = account(c, 'doubled')
        before = me(c, h)['shards']
        assert open_chest(c, h, 'fields_cafe').json()['stars'] == 8 and me(c, h)['shards'] == before + 8
    assert treasure.reward('home', 0.5) == 5 and treasure.reward('square_cape', 0.5) == 2 and treasure.reward('home', 0) == 0
    for bad in (-1, 6, float('nan')):
        with pytest.raises(ValueError):
            Settings(data_dir=tmp_path / 'bad', chest_stars_scale=bad).validate()
    # From the environment: the default, a number, and a word the server refuses to start with.
    monkeypatch.delenv('TRIPOTHON_CHEST_STARS_SCALE', raising=False)
    assert Settings(data_dir=tmp_path / 'env').chest_stars_scale == 1.0
    monkeypatch.setenv('TRIPOTHON_CHEST_STARS_SCALE', '0')
    assert Settings(data_dir=tmp_path / 'env').chest_stars_scale == 0
    monkeypatch.setenv('TRIPOTHON_CHEST_STARS_SCALE', 'lots')
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path / 'env')


def test_the_reward_table_and_the_game_agree():
    total = sum(treasure.reward(c, 1.0) for c in treasure.STARS)
    assert total == 45 and 40 <= total <= 50
    assert treasure.STARS['home'] == 10
    field = [c for c in treasure.STARS if c != 'home']
    assert len(field) == 10 and all(3 <= treasure.STARS[c] <= 5 for c in field)
    for island in treasure.ISLANDS:
        assert sum(1 for c in field if treasure.place_of(c) == island) == 2
    # The game places the same chests (game/scripts/treasure.gd: HOME and FIELD ids).
    source = (ROOT / 'game' / 'scripts' / 'treasure.gd').read_text(encoding='utf-8')
    ids = re.findall(r'\{"id":"([a-z_]+)"', source)
    assert sorted(ids) == sorted(treasure.STARS)


def test_the_operator_example_states_the_real_totals():
    text = (ROOT / 'ops' / 'production.env.example').read_text(encoding='utf-8')
    total = lambda scale: sum(treasure.reward(c, scale) for c in treasure.STARS)
    assert ('%d in all at 1.0' % total(1.0)) in text and ('%d at 2.0' % total(2.0)) in text and ('%d at 5' % total(5.0)) in text
    for compose, source in (('ops/compose.yaml', 'TRIPOTHON_CHEST_STARS_SCALE'), ('ops/compose.staging.yaml', 'STAGING_CHEST_STARS_SCALE')):
        assert re.search(r'^\s+TRIPOTHON_CHEST_STARS_SCALE: \$\{%s:-1\.0\}' % source, (ROOT / compose).read_text(encoding='utf-8'), re.M)
    assert 'STAGING_CHEST_STARS_SCALE=1.0' in (ROOT / 'ops' / 'staging.env.example').read_text(encoding='utf-8')


def test_the_operator_can_see_a_players_chests(world, capsys):
    app, c, now = world
    h = account(c, 'shown')
    open_chest(c, h, 'garden_pond')
    data_dir = str(app.state.settings.data_dir)
    assert admin_cli.main(['chests', 'show', 'shown', '--data-dir', data_dir]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert [r['chest_id'] for r in shown['opened']] == ['garden_pond'] and shown['opened'][0]['stars'] == 4
    assert shown['paid'] == [{'chest': 'garden_pond', 'amount': 4, 'created': now[0]}]
    assert 'home' in shown['left'] and 'garden_pond' not in shown['left'] and len(shown['left']) == 10
    assert admin_cli.main(['chests', 'show', 'nobody', '--data-dir', data_dir]) == 1
    capsys.readouterr()
    assert admin_cli.main(['chests', 'show', 'shown', '--data-dir', str(Path(data_dir) / 'missing')]) == 1


def test_a_story_reset_leaves_the_chests_alone(world, capsys):
    app, c, now = world
    h = account(c, 'rehearsed')
    open_chest(c, h, 'home')
    shards = me(c, h)['shards']
    assert admin_cli.main(['story', 'reset', 'rehearsed', '--data-dir', str(app.state.settings.data_dir)]) == 0
    capsys.readouterr()
    assert me(c, h)['chests']['opened'] == ['home'] and me(c, h)['shards'] == shards
    now[0] += 10
    assert open_chest(c, h, 'home').json()['detail'] == 'chest_already_open'
    assert paid(app) == [('home', 10)]
