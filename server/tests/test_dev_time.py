"""Time override permissions, durable account scope and presentation-only behavior."""
import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Settings
from server.dev_time import PRESET_HOURS
from server.tests.test_api import account, world


ROUTE = '/v1/dev/time_override'
EMPTY = {'time_override': None, 'hour': None, 'updated': None}


def permit(app, name, *, tester=False, role='player'):
    with app.state.db.transaction() as conn:
        conn.execute('UPDATE users SET is_tester=?,role=? WHERE username=?', (int(tester), role, name))


def test_only_server_granted_testers_and_operators_have_access(world):
    app, client, _ = world
    normal = account(client, 'regular_time')
    named_tester = account(client, 'tripo1')
    tester = account(client, 'tester_time')
    operator = account(client, 'staff_time')
    permit(app, 'tester_time', tester=True)
    permit(app, 'staff_time', role='admin')
    assert client.get(ROUTE).status_code == 401
    assert client.post(ROUTE, json={'time_override': 'night'}).status_code == 401
    for headers in (normal, named_tester):
        assert client.get(ROUTE, headers=headers).status_code == 403
        denied = client.post(ROUTE, headers=headers, json={'time_override': 'night'})
        assert denied.status_code == 403
        assert denied.json()['detail'] == 'time_override_forbidden'
        assert client.post(ROUTE, headers=headers, json={'time_override': None}).status_code == 403
    for headers in (tester, operator):
        assert client.get(ROUTE, headers=headers).json() == EMPTY
        assert client.post(ROUTE, headers=headers, json={'time_override': 'night'}).status_code == 200


@pytest.mark.parametrize('value,hour', [*PRESET_HOURS.items(), (0, 0), (15, 15), (23, 23)])
def test_presets_and_hours_are_read_without_presence(world, value, hour):
    app, client, now = world
    headers = account(client, 'display_time')
    permit(app, 'display_time', tester=True)
    reply = client.post(ROUTE, headers=headers, json={'time_override': value})
    assert reply.status_code == 200, reply.text
    assert reply.json() == {'time_override': value, 'hour': hour, 'updated': now[0]}
    assert client.get(ROUTE, headers=headers).json() == reply.json()
    # No join or presence request is needed. The setting follows the reader's
    # account and survives absence from the multiplayer world's presence table.
    with app.state.db.read() as conn:
        assert conn.execute('SELECT count(*) FROM mp_presence').fetchone()[0] == 0


@pytest.mark.parametrize('value', [-1, 24, 1.5, True, False, '12', 'dawn', '', [], {}])
def test_invalid_override_values_leave_saved_state_unchanged(world, value):
    app, client, _ = world
    headers = account(client, 'validated_time')
    permit(app, 'validated_time', tester=True)
    saved = client.post(ROUTE, headers=headers, json={'time_override': 'morning'}).json()
    assert client.post(ROUTE, headers=headers, json={'time_override': value}).status_code == 422
    assert client.get(ROUTE, headers=headers).json() == saved


def test_empty_and_extra_fields_cannot_clear_or_target_another_account(world):
    app, client, _ = world
    headers = account(client, 'target_time')
    permit(app, 'target_time', tester=True)
    saved = client.post(ROUTE, headers=headers, json={'time_override': 17}).json()
    for body in ({}, {'time_override': None, 'user_id': 'someone_else'},
                 {'time_override': 'night', 'is_tester': True}):
        assert client.post(ROUTE, headers=headers, json=body).status_code == 422
    assert client.get(ROUTE, headers=headers).json() == saved


def test_overrides_and_clearing_persist_per_account_across_restarts(tmp_path):
    settings = Settings(data_dir=tmp_path)
    now = [1000000.]

    def start():
        return create_app(settings, clock=lambda: now[0], worker_enabled=False)

    app = start()
    with TestClient(app) as client:
        first = account(client, 'first_time')
        second = account(client, 'second_time')
        permit(app, 'first_time', tester=True)
        permit(app, 'second_time', tester=True)
        saved = client.post(ROUTE, headers=first, json={'time_override': 'evening'}).json()
        assert client.get(ROUTE, headers=second).json() == EMPTY
    app.state.db.close()

    app = start()
    with TestClient(app) as client:
        assert client.get(ROUTE, headers=first).json() == saved
        assert client.get(ROUTE, headers=second).json() == EMPTY
        now[0] += 60
        # Repeating a setting must not create duplicate rows or audit entries.
        assert client.post(ROUTE, headers=first, json={'time_override': 'evening'}).json() == saved
        for _ in range(2):
            reply = client.post(ROUTE, headers=first, json={'time_override': None})
            assert reply.status_code == 200
            assert reply.json() == EMPTY
        with app.state.db.read() as conn:
            assert conn.execute('SELECT count(*) FROM account_time_overrides').fetchone()[0] == 0
            assert conn.execute("SELECT count(*) FROM audit WHERE action='dev_time_override'").fetchone()[0] == 2
    app.state.db.close()

    app = start()
    with TestClient(app) as client:
        assert client.get(ROUTE, headers=first).json() == EMPTY
    app.state.db.close()


def test_permission_is_checked_again_after_tester_role_is_revoked(world):
    app, client, _ = world
    headers = account(client, 'revoked_time')
    permit(app, 'revoked_time', tester=True)
    assert client.post(ROUTE, headers=headers, json={'time_override': 'night'}).status_code == 200
    permit(app, 'revoked_time')
    assert client.get(ROUTE, headers=headers).status_code == 403
    assert client.post(ROUTE, headers=headers, json={'time_override': 'noon'}).status_code == 403


def test_override_does_not_change_authoritative_game_time_or_rewards(world):
    app, client, _ = world
    headers = account(client, 'visual_time')
    permit(app, 'visual_time', tester=True)
    before = client.get('/v1/homestead', headers=headers).json()
    with app.state.db.read() as conn:
        user_before = dict(conn.execute("SELECT * FROM users WHERE username='visual_time'").fetchone())
        ledger_before = [tuple(row) for row in conn.execute('SELECT * FROM ledger')]
    assert client.post(ROUTE, headers=headers, json={'time_override': 'night'}).status_code == 200
    assert client.get('/v1/homestead', headers=headers).json() == before
    with app.state.db.read() as conn:
        assert dict(conn.execute("SELECT * FROM users WHERE username='visual_time'").fetchone()) == user_before
        assert [tuple(row) for row in conn.execute('SELECT * FROM ledger')] == ledger_before
