"""Client version gate and maintenance notices (server/client_policy.py): off unless an operator
writes <data>/client_policy.json, changed without a restart, readable for released games."""
import json
import os
import time
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings, server_version
from server import client_policy
from server.client_policy import parse_version, older, FILE_NAME

NOW = 1_800_000_000.0
NEW = {'X-Villagen-Version': '0.11.10'}
OLD = {'X-Villagen-Version': '0.11.9'}


@pytest.fixture
def world(tmp_path):
    now = [NOW]
    app = create_app(Settings(data_dir=tmp_path), clock=lambda: now[0], worker_enabled=False)
    # Tests change the file many times a second; the server checks it every couple of seconds.
    app.state.client_policy.check_seconds = 0
    with TestClient(app) as client:
        yield app, client, now, tmp_path / FILE_NAME


def write(path, **data):
    path.write_text(json.dumps(data), encoding='utf-8')
    # Same size within the same timestamp tick would look unchanged; make every write distinct.
    stamp = time.time_ns() + write.count * 1_000_000
    write.count += 1
    os.utime(path, ns=(stamp, stamp))
write.count = 0


def register(client, name, headers=None):
    reply = client.post('/v1/auth/register', json={'username': name, 'password': 'Testing-only-12345'}, headers=headers or {})
    assert reply.status_code == 200, reply.text
    return {'Authorization': 'Bearer ' + reply.json()['token']}


def test_versions_compare_by_number():
    assert parse_version('0.11.10') > parse_version('0.11.9')
    assert parse_version('v0.11.4-school') == parse_version('0.11.4') == (0, 11, 4, 0)
    assert parse_version('0.12') > parse_version('0.11.99')
    assert parse_version('1.0') == parse_version('1.0.0')
    assert parse_version('') is None and parse_version('latest') is None and parse_version(None) is None
    assert older('0.11.9', '0.11.10') and not older('0.11.10', '0.11.10') and not older('0.11.11', '0.11.10')
    assert older(None, '0.11.3') and older('garbage', '0.11.3')
    assert not older(None, '') and not older('0.1', '')


def test_nothing_changes_without_a_policy_file(world):
    """The judging server has no policy file: released games without the header play as before."""
    app, c, now, path = world
    assert not path.exists()
    a = register(c, 'judge_one')
    assert c.get('/v1/me', headers=a).status_code == 200
    assert c.get('/v1/homestead', headers=a).status_code == 200
    health = c.get('/health').json()
    assert health['protocol'] == 6 and health['service'] == 'tripothon'
    assert health['client'] == {'min': '', 'latest': '', 'download_url': ''} and health['notice'] is None
    assert c.get('/v1/me', headers=a).headers['x-villagen-notice-version'] == '0'


def test_old_and_unversioned_games_get_426_with_a_readable_sentence(world):
    app, c, now, path = world
    a = register(c, 'alice', NEW)
    url = 'https://github.com/NormalMan0228/tripo_s1/releases/tag/v0.11.10-school'
    write(path, min_client_version='0.11.10', latest_client_version='0.11.10', client_download_url=url)
    assert c.get('/v1/me', headers={**a, **NEW}).status_code == 200
    assert c.get('/v1/me', headers={**a, 'X-Villagen-Version': '0.12.0'}).status_code == 200
    for extra in (OLD, {}, {'X-Villagen-Version': 'nonsense'}):
        reply = c.get('/v1/me', headers={**a, **extra})
        assert reply.status_code == 426, extra
        body = reply.json()
        assert body['code'] == 'client_update_required'
        assert body['client'] == {'min': '0.11.10', 'latest': '0.11.10', 'download_url': url}
        # Released games print the detail (the room studio after its own prefix): a sentence, not a code.
        assert body['detail'] == '새 버전(0.11.10)이 나왔어요. 게임을 새로 받아 주세요: ' + url
    # Posts are refused before their body is even read.
    assert c.post('/v1/homestead', headers={**a, **OLD}, json={'request_id': 'x'}).status_code == 426
    # /health and the download information stay open for everyone.
    for extra in (OLD, {}):
        health = c.get('/health', headers=extra)
        assert health.status_code == 200 and health.json()['client']['min'] == '0.11.10'
        info = c.get('/v1/client', headers=extra)
        assert info.status_code == 200 and info.json()['client']['download_url'] == url


def test_released_games_still_sign_in_so_their_room_shows_the_sentence(world):
    """0.11.2 sends no version: login opens the player's room, which prints the 426 detail."""
    app, c, now, path = world
    write(path, min_client_version='0.11.4')
    legacy = register(c, 'legacy_player')
    reply = c.post('/v1/auth/login', json={'username': 'legacy_player', 'password': 'Testing-only-12345'})
    assert reply.status_code == 200
    studio = c.get('/v1/studio', headers=legacy)
    assert studio.status_code == 426 and studio.json()['detail'] == '새 버전(0.11.4)이 나왔어요. 게임을 새로 받아 주세요.'
    assert c.post('/v1/auth/logout', headers=legacy).status_code == 200
    # A game that does send its version is told at login already.
    refused = c.post('/v1/auth/login', headers={'X-Villagen-Version': '0.11.3'}, json={'username': 'legacy_player', 'password': 'Testing-only-12345'})
    assert refused.status_code == 426 and refused.json()['code'] == 'client_update_required'


def test_policy_changes_apply_without_a_restart(world):
    app, c, now, path = world
    a = register(c, 'bob', OLD)
    assert c.get('/v1/me', headers={**a, **OLD}).status_code == 200
    write(path, min_client_version='0.11.10')
    assert c.get('/v1/me', headers={**a, **OLD}).status_code == 426
    write(path, min_client_version='0.11.9')
    assert c.get('/v1/me', headers={**a, **OLD}).status_code == 200
    # A broken file keeps the last good settings; removing the file turns everything off.
    write(path, min_client_version='0.11.10')
    assert c.get('/v1/me', headers={**a, **OLD}).status_code == 426
    path.write_text('{"min_client_version": "0.11', encoding='utf-8')
    os.utime(path, ns=(time.time_ns() + 5_000_000_000,) * 2)
    assert c.get('/v1/me', headers={**a, **OLD}).status_code == 426
    path.unlink()
    assert c.get('/v1/me', headers={**a, **OLD}).status_code == 200


def test_the_file_is_read_again_only_every_few_seconds(tmp_path):
    policy = client_policy.ClientPolicy(tmp_path / FILE_NAME, clock=lambda: NOW, check_seconds=60)
    assert policy.state()['min_client_version'] == ''
    write(tmp_path / FILE_NAME, min_client_version='0.11.4')
    assert policy.state()['min_client_version'] == ''      # cached
    policy._checked -= 61
    assert policy.state()['min_client_version'] == '0.11.4'


def test_scheduled_maintenance_counts_down_then_closes_every_route_but_health(world):
    app, c, now, path = world
    a = register(c, 'carol', NEW)
    plain = c.get('/v1/me', headers={**a, **NEW})
    write(path, notice={'id': 'n1', 'starts_at': NOW + 1800, 'minutes': 10, 'message': '새 버전 업데이트를 해요.'})
    announced = c.get('/v1/me', headers={**a, **NEW})
    assert announced.status_code == 200
    assert announced.headers['x-villagen-notice-version'] != plain.headers['x-villagen-notice-version']
    notice = c.get('/health').json()['notice']
    assert notice['starts_in'] == 1800 and notice['ends_in'] == 2400 and notice['active'] is False
    assert notice['message'] == '새 버전 업데이트를 해요.' and notice['minutes'] == 10
    before = announced.headers['x-villagen-notice-version']
    now[0] = NOW + 1800
    for extra in (NEW, OLD, {}):
        reply = c.get('/v1/me', headers={**a, **extra})
        assert reply.status_code == 503
        body = reply.json()
        assert body['code'] == 'server_maintenance' and body['notice']['active'] is True
        assert body['detail'] == '서버 점검 중이에요. 약 10분 뒤에 다시 들어와 주세요.'
        assert reply.headers['retry-after'] == '600'
        # The notice version changes when maintenance starts, so a game polling cheaply sees it.
        assert reply.headers['x-villagen-notice-version'] != before
    assert c.post('/v1/auth/login', json={'username': 'carol', 'password': 'Testing-only-12345'}).status_code == 503
    assert c.get('/health').status_code == 200 and c.get('/health').json()['notice']['active'] is True
    assert c.get('/v1/client').status_code == 200
    # Without hold the window ends by itself.
    now[0] = NOW + 2400
    assert c.get('/v1/me', headers={**a, **NEW}).status_code == 200
    assert c.get('/health').json()['notice'] is None


def test_held_maintenance_lasts_until_the_operator_cancels(world):
    app, c, now, path = world
    a = register(c, 'dave', NEW)
    write(path, notice={'id': 'n2', 'starts_at': NOW, 'minutes': 5, 'message': '', 'hold': True})
    now[0] = NOW + 3600
    reply = c.get('/v1/me', headers={**a, **NEW})
    assert reply.status_code == 503
    assert reply.json()['detail'] == '서버 점검 중이에요. 곧 끝나요. 잠시 뒤 다시 들어와 주세요.'
    assert reply.json()['notice']['message'] == client_policy.DEFAULT_MESSAGE
    client_policy.main(['--data-dir', str(path.parent), 'cancel'])
    os.utime(path, ns=(time.time_ns() + 9_000_000_000,) * 2)
    assert c.get('/v1/me', headers={**a, **NEW}).status_code == 200


def test_maintenance_comes_before_the_version_check(world):
    app, c, now, path = world
    write(path, min_client_version='0.11.10', notice={'id': 'n3', 'starts_at': NOW - 60, 'minutes': 30, 'message': 'x'})
    assert c.get('/v1/me', headers=OLD).json()['code'] == 'server_maintenance'


def test_operator_commands_write_a_policy_the_server_reads(tmp_path, capsys):
    run = lambda *args: client_policy.main(['--data-dir', str(tmp_path), *args])
    run('release', '0.11.4', 'https://github.com/NormalMan0228/tripo_s1/releases/tag/v0.11.4-school')
    run('min', '0.11.4')
    run('maintenance', '--in', '30', '--minutes', '10', '--message', '서버 업데이트가 있어요.', '--hold')
    saved = json.loads((tmp_path / FILE_NAME).read_text(encoding='utf-8'))
    assert saved['min_client_version'] == saved['latest_client_version'] == '0.11.4'
    assert saved['notice']['hold'] is True and saved['notice']['minutes'] == 10
    assert abs(saved['notice']['starts_at'] - (time.time() + 1800)) < 5
    shown = capsys.readouterr().out
    assert '최소 버전: 0.11.4' in shown and '서버 업데이트가 있어요.' in shown and '뒤 시작' in shown
    run('cancel')
    run('min', 'off')
    saved = json.loads((tmp_path / FILE_NAME).read_text(encoding='utf-8'))
    assert 'notice' not in saved and 'min_client_version' not in saved and saved['latest_client_version'] == '0.11.4'
    with pytest.raises(SystemExit):
        run('url', 'http://plain.example/download')
    with pytest.raises(SystemExit):
        run('min', 'soon')
    # A minimum above the latest version also raises the latest, so the banner never points backwards.
    run('min', '0.11.6')
    saved = json.loads((tmp_path / FILE_NAME).read_text(encoding='utf-8'))
    assert saved['latest_client_version'] == '0.11.6'


def test_unsafe_download_links_and_messages_are_dropped(world):
    app, c, now, path = world
    write(path, latest_client_version='0.11.4', client_download_url='file:///C:/Windows/System32/calc.exe',
          notice={'id': 'n4', 'starts_at': NOW + 60, 'minutes': 5, 'message': '점검\u202e 해요\n'})
    health = c.get('/health').json()
    assert health['client'] == {'min': '', 'latest': '0.11.4', 'download_url': ''}
    assert health['notice']['message'] == '점검 해요'


def test_health_reports_the_real_build(world, monkeypatch):
    app, c, now, path = world
    text = (server_version.__globals__['ROOT'] / 'game' / 'project.godot').read_text(encoding='utf-8')
    expected = text.split('config/version="', 1)[1].split('"', 1)[0]
    assert c.get('/health').json()['version'] == expected != '0.10.0'
    monkeypatch.setenv('VILLAGEN_SERVER_COMMIT', '5498320')
    assert server_version() == (expected, '5498320')
    monkeypatch.setenv('VILLAGEN_SERVER_COMMIT', 'not a commit')
    assert server_version() == (expected, '')
