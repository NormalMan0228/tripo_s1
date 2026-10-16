"""The tick that ends a run keeps its ending line: an action held in the same request (a repeating
attack/gather key) is not tried on the finished run, so the reply does not say '탐험이 이미 종료되었습니다.'
over the win or loss message."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from server import coop, simulation
from server.app import create_app
from server.config import Settings
from server.models import Input

ENDED = '탐험이 이미 종료되었습니다.'
LOST = '탐험이 끝났습니다. 마을에서 다시 준비해 보세요.'


def mutation(**kw):
    return dict(request_id=str(uuid.uuid4()), **kw)


@pytest.fixture
def world(tmp_path):
    now = [1000000.]
    app = create_app(Settings(data_dir=tmp_path), clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as client:
        r = client.post('/v1/auth/register', json={'username': 'ending_alice', 'password': 'Testing-only-12345'})
        assert r.status_code == 200, r.text
        yield app, client, now, {'Authorization': 'Bearer ' + r.json()['token']}


def edit_run(app, run_id, edit):
    with app.state.db.transaction() as conn:
        state = json.loads(conn.execute('SELECT state FROM runs WHERE id=?', (run_id,)).fetchone()[0])
        edit(state)
        conn.execute('UPDATE runs SET state=? WHERE id=?', (json.dumps(state), run_id))


def test_tutorial_clear_line_survives_a_held_attack(world):
    app, c, now, h = world
    rid = c.post('/v1/runs', headers=h, json=mutation(map_id='tutorial')).json()['id']
    edit_run(app, rid, lambda s: s.update(harvested=6, crafted={'axe': 1}, fires=1, kills=2))
    now[0] += .1
    state = c.post('/v1/runs/' + rid + '/input', headers=h, json={'sequence': 1, 'action': 'attack'}).json()
    assert state['status'] == 'won' and state['reward'] == simulation.TUTORIAL_REWARD
    assert state['message'] == '첫 탐험을 마쳤어요! 마을로 돌아가 별씨를 받으세요.'
    assert c.get('/v1/me', headers=h).json()['tutorial_done'] is True


def test_loss_line_survives_a_held_gather(world):
    app, c, now, h = world
    rid = c.post('/v1/runs', headers=h, json=mutation(map_id='forest')).json()['id']
    edit_run(app, rid, lambda s: s.update(hp=.05, hunger=0.))
    now[0] += .1
    state = c.post('/v1/runs/' + rid + '/input', headers=h, json={'sequence': 1, 'action': 'harvest', 'target': 'n0'}).json()
    assert state['status'] == 'lost' and state['message'] == LOST
    # A later request on the ended run keeps the line too.
    now[0] += .1
    state = c.post('/v1/runs/' + rid + '/input', headers=h, json={'sequence': 2, 'action': 'attack'}).json()
    assert state['status'] == 'lost' and state['message'] == LOST


def test_party_member_acting_on_the_clearing_tick_is_not_told_it_ended():
    members = [dict(id=k, username=k, avatar={}) for k in 'ab']
    state = coop.new_world(2, 0, 90, members, 'tutorial', 'standard')
    for actor in state['players'].values():
        actor['last_seen'] = 0.
    state['players']['a'].update(harvested=6, crafted={'axe': 1}, fires=1, kills=2, last_action=-10., last_attack=-10.)
    coop.apply_input(state, 'a', Input(sequence=1, action='attack'), .2)
    assert state['world']['status'] == 'won' and state['world']['reward'] == simulation.TUTORIAL_REWARD
    assert state['players']['a']['message'] != ENDED
    assert coop.public(state, 'a', .2)['status'] == 'won'
