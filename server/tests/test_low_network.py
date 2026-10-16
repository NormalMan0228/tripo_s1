"""Wire encoding, cache validity and old-client compatibility regressions."""
import asyncio
import gzip
import json
import zlib

import pytest

from server.low_network import LowNetworkMiddleware
from server.tests.social_world import World


def wire(body, request_headers=(), path='/v1/social', method='GET', **options):
    messages = []

    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': options.get('status', 200), 'headers': [
            (b'content-type', options.get('content_type', b'application/json')),
            (b'content-length', str(len(body)).encode())]})
        for pos in range(0, len(body), 71):
            await send({'type': 'http.response.body', 'body': body[pos:pos + 71],
                        'more_body': pos + 71 < len(body)})

    async def send(message):
        messages.append(message)

    async def receive():
        return {'type': 'http.request', 'body': b''}

    asyncio.run(LowNetworkMiddleware(app, maximum_size=options.get('maximum_size', 4 * 1024 * 1024))(
        {'type': 'http', 'method': method, 'path': path, 'headers': request_headers}, receive, send))
    return messages[0]['status'], dict(messages[0]['headers']), b''.join(m.get('body', b'') for m in messages[1:])


@pytest.mark.parametrize('accept,expected', [
    ('gzip', 'gzip'), ('deflate', 'deflate'), ('gzip;q=0, deflate;q=0.8', 'deflate'),
    ('gzip;q=0, *;q=1', 'deflate'), ('gzip;q=0, deflate;q=0', None),
    ('GZip; q=0.7, deflate;q=0.2', 'gzip'), ('br', None), ('gzip;q=oops', None),
])
def test_encoding_negotiation_and_exact_decoded_json(accept, expected):
    payload = json.dumps({'objects': ['sample furniture'] * 200}).encode()
    code, headers, body = wire(payload, [(b'accept-encoding', accept.encode())])
    assert code == 200
    assert headers.get(b'content-encoding') == (expected.encode() if expected else None)
    assert b'Accept-Encoding' in headers[b'vary']
    assert int(headers[b'content-length']) == len(body)
    assert (gzip.decompress(body) if expected == 'gzip' else zlib.decompress(body) if expected else body) == payload


def test_threshold_binary_errors_and_large_responses_are_not_compressed():
    for body, options in [(b'{"ok":true}', {}), (b'x' * 2000, {'content_type': b'model/gltf-binary'}),
                          (b'x' * 2000, {'status': 503}), (b'x' * 2000, {'maximum_size': 1024})]:
        _, headers, result = wire(body, [(b'accept-encoding', b'gzip')], **options)
        assert b'content-encoding' not in headers and result == body


def test_conditional_get_uses_weak_comparison_and_preserves_encoding_independence():
    body = json.dumps({'rows': ['same'] * 400}).encode()
    _, plain, _ = wire(body)
    _, compressed, _ = wire(body, [(b'accept-encoding', b'gzip')])
    assert plain[b'etag'] == compressed[b'etag']
    for match in (plain[b'etag'], plain[b'etag'][2:], b'"unrelated", ' + plain[b'etag'], b'*'):
        code, headers, result = wire(body, [(b'if-none-match', match), (b'accept-encoding', b'gzip')])
        assert code == 304 and result == b''
        assert b'content-length' not in headers and b'content-encoding' not in headers
        assert headers[b'cache-control'] == b'private, no-cache'
    assert wire(body + b' ', [(b'if-none-match', plain[b'etag'])])[0] == 200


def test_post_heartbeat_and_non_poll_routes_never_get_304():
    for path, method in [('/v1/social/presence', 'POST'), ('/v1/social', 'POST'), ('/v1/me', 'GET')]:
        code, headers, result = wire(b'{"same":true}', [(b'if-none-match', b'*')], path=path, method=method)
        assert code == 200 and result and b'etag' not in headers


def test_stream_without_length_flushes_once_at_memory_bound():
    messages = []

    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200,
                    'headers': [(b'content-type', b'application/json')]})
        for index in range(4):
            await send({'type': 'http.response.body', 'body': bytes([65 + index]) * 800,
                        'more_body': index < 3})

    async def send(message):
        messages.append(message)

    asyncio.run(LowNetworkMiddleware(app, maximum_size=1024)(
        {'type': 'http', 'method': 'GET', 'path': '/v1/social', 'headers': [(b'accept-encoding', b'gzip')]},
        None, send))
    assert sum(message['type'] == 'http.response.start' for message in messages) == 1
    assert b'content-encoding' not in dict(messages[0]['headers'])
    assert b''.join(message.get('body', b'') for message in messages) == b'A' * 800 + b'B' * 800 + b'C' * 800 + b'D' * 800
    assert not messages[-1]['more_body']


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.close()
    w.app.state.db.close()


def test_real_poll_auth_mutations_and_logout_are_checked_before_304(world):
    w = world
    a, b = w.players('cache_a', 'cache_b')
    first = w.client.get('/v1/social', headers=a.headers)
    assert first.status_code == 200 and first.headers['cache-control'] == 'no-store'
    headers = {**a.headers, 'If-None-Match': first.headers['etag']}
    unchanged = w.client.get('/v1/social', headers=headers)
    assert unchanged.status_code == 304 and unchanged.content == b''
    assert unchanged.headers['x-content-type-options'] == 'nosniff'
    assert 'x-villagen-notice-version' in unchanged.headers
    # A new invitation is visible immediately, regardless of the caller's validator.
    w.call(b, '/v1/social/invites', username=a.name, kind='village')
    changed = w.client.get('/v1/social', headers=headers)
    assert changed.status_code == 200 and changed.headers['etag'] != first.headers['etag']
    assert w.client.get('/v1/social', headers={'If-None-Match': '*'}).status_code == 401
    w.client.post('/v1/auth/logout', headers=a.headers)
    assert w.client.get('/v1/social', headers=headers).status_code == 401


def test_job_read_keeps_owner_boundary_and_detects_progress(world):
    w = world
    a, b = w.players('job_cache_a', 'job_cache_b')
    from server import economy
    with w.app.state.db.transaction() as conn:
        economy.change_shards(conn, a.id, 100, 'demo_welcome', a.id, w.now[0])
    job = w.call(a, '/v1/studio/jobs', prompt='wooden chair')
    path = '/v1/studio/jobs/' + job['id']
    first = w.client.get(path, headers={**a.headers, 'X-Villagen-Cache': '1'})
    assert first.status_code == 200 and first.headers['cache-control'] == 'private, no-cache'
    conditional = {**a.headers, 'If-None-Match': first.headers['etag']}
    assert w.client.get(path, headers=conditional).status_code == 304
    assert w.client.get(path, headers={**b.headers, 'If-None-Match': '*'}).status_code == 404
    with w.app.state.db.transaction() as conn:
        conn.execute("UPDATE studio_jobs SET state='failed' WHERE id=?", (job['id'],))
    assert w.client.get(path, headers=conditional).json()['state'] == 'failed'


def test_presence_compression_does_not_skip_writes_or_change_json(world):
    w = world
    a = w.player('compression_presence')
    first = w.client.post('/v1/social/presence', headers={**a.headers, 'Accept-Encoding': 'identity'}, json={})
    compressed = w.client.post('/v1/social/presence', headers={**a.headers, 'Accept-Encoding': 'gzip', 'If-None-Match': '*'}, json={})
    assert compressed.status_code == 200
    assert compressed.headers['content-encoding'] == 'gzip'
    assert compressed.json() == first.json()
    w.tick(2)
    w.client.post('/v1/social/presence', headers=a.headers, json={'x': 3})
    with w.app.state.db.read() as conn:
        row = conn.execute('SELECT x,seen FROM mp_presence WHERE user_id=?', (a.id,)).fetchone()
        assert row['x'] == 3 and row['seen'] == w.now[0]
