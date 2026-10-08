"""Painted surface textures: owner upload/fetch/replace/clear, guest reads, validation,
listings, account deletion and backups."""
import asyncio
import base64
import io
import sqlite3
import struct
import uuid
import zlib
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server.admin_cli import main as admin_main
from server.backups import create_backup, verify_backup, restore_backup, BackupError
from server.tests.test_studio import FurnitureProvider, paid_world


def mutation(**extra):
    return dict(request_id=str(uuid.uuid4()), **extra)


def png(width=1024, height=1024, color=(200, 80, 40, 255)):
    out = io.BytesIO()
    Image.new('RGBA', (width, height), color).save(out, 'PNG')
    return out.getvalue()


def encoded(blob):
    return base64.b64encode(blob).decode()


@pytest.fixture
def world(tmp_path):
    settings = Settings(data_dir=tmp_path, daily_generation_limit=100)
    app = create_app(settings, worker_enabled=False)
    with TestClient(app) as client:
        headers = []
        for name in ('alice', 'bravo'):
            response = client.post('/v1/auth/register', json={'username': name, 'password': 'Test-password-123'})
            headers.append({'Authorization': 'Bearer ' + response.json()['token']})
        yield app, client, headers, tmp_path


def starter(c, h):
    return c.get('/v1/me', headers=h).json()['objects'][0]


def paint_files(data):
    folder = data / 'assets' / 'paint'
    return sorted(p.name for p in folder.glob('*')) if folder.is_dir() else []


def listed_version(c, h, object_id):
    return next(o for o in c.get('/v1/me', headers=h).json()['objects'] if o['id'] == object_id)['paint_version']


def test_upload_fetch_replace_and_clear(world):
    app, c, hs, data = world
    obj = starter(c, hs[0])
    route = '/v1/objects/' + obj['id'] + '/paint'
    assert obj['paint_version'] is None
    assert c.get(route, headers=hs[0]).status_code == 404
    first = png(color=(10, 20, 30, 255))
    body = mutation(png=encoded(first))
    reply = c.post(route, headers=hs[0], json=body)
    assert reply.status_code == 200, reply.text
    assert reply.json()['paint_version'] == 1
    # A retried request is answered once (same version, nothing bumped).
    assert c.post(route, headers=hs[0], json=body).json() == reply.json()
    fetched = c.get(route, headers=hs[0])
    assert fetched.status_code == 200 and fetched.headers['content-type'] == 'image/png'
    assert fetched.content == first and fetched.headers['cache-control'] == 'no-store'
    assert listed_version(c, hs[0], obj['id']) == 1
    # Replacing keeps one file and a growing version.
    second = png(512, 256, (90, 200, 120, 255))
    assert c.post(route, headers=hs[0], json=mutation(png=encoded(second))).json()['paint_version'] == 2
    assert c.get(route, headers=hs[0]).content == second
    assert len(paint_files(data)) == 1
    # Clearing removes it; the version never goes back (clients cache by object and version).
    cleared = c.post(route, headers=hs[0], json=mutation(clear=True))
    assert cleared.status_code == 200 and cleared.json()['paint_version'] is None
    assert c.get(route, headers=hs[0]).status_code == 404
    assert listed_version(c, hs[0], obj['id']) is None
    assert paint_files(data) == []
    assert c.post(route, headers=hs[0], json=mutation(clear=True)).json()['paint_version'] is None
    assert c.post(route, headers=hs[0], json=mutation(png=encoded(first))).json()['paint_version'] == 4
    assert c.get(route, headers=hs[0]).content == first
    with sqlite3.connect(data / 'world.sqlite3') as conn:
        assert conn.execute('SELECT version FROM object_paint WHERE object_id=?', (obj['id'],)).fetchone()[0] == 4


def test_only_the_owner_paints_or_reads_and_listed_objects_are_locked(world):
    app, c, hs, data = world
    obj = starter(c, hs[0])
    route = '/v1/objects/' + obj['id'] + '/paint'
    assert c.post(route, json=mutation(png=encoded(png()))).status_code == 401
    assert c.post(route, headers=hs[1], json=mutation(png=encoded(png()))).status_code == 404
    assert c.post(route, headers=hs[0], json=mutation(png=encoded(png()))).status_code == 200
    assert c.get(route, headers=hs[1]).status_code == 404
    assert c.get(route).status_code == 401
    assert c.post(route, headers=hs[1], json=mutation(clear=True)).status_code == 404
    assert c.get(route, headers=hs[0]).status_code == 200
    assert c.post('/v1/market', headers=hs[0], json=mutation(object_id=obj['id'], version=1, price=5)).status_code == 200
    refused = c.post(route, headers=hs[0], json=mutation(png=encoded(png(64, 64))))
    assert refused.status_code == 409 and refused.json()['detail'] == 'object_is_listed'


def test_visitors_read_paint_only_where_they_may_see_the_model(world):
    app, c, hs, data = world
    obj = starter(c, hs[0])
    own = '/v1/objects/' + obj['id']
    guest = '/v1/social/village/objects/' + obj['id']
    blob = png(256, 256, (1, 2, 3, 255))
    assert c.post(own + '/paint', headers=hs[0], json=mutation(png=encoded(blob))).status_code == 200
    # In the bag: nobody else sees it.
    assert c.get(guest + '/paint', headers=hs[1]).status_code == 404
    assert c.post(own, headers=hs[0], json=mutation(version=1, action='place', x=5, z=4)).status_code == 200
    # Placed, but bravo is not visiting yet.
    assert c.get(guest + '/paint', headers=hs[1]).status_code == 404
    invite = c.post('/v1/social/invites', headers=hs[0], json=mutation(username='bravo', kind='village')).json()
    assert c.post('/v1/social/invites/' + invite['id'] + '/accept', headers=hs[1], json=mutation()).status_code == 200
    assert c.get(guest + '/model', headers=hs[1]).status_code == 200
    seen = c.get(guest + '/paint', headers=hs[1])
    assert seen.status_code == 200 and seen.content == blob
    space = c.post('/v1/social/presence', headers=hs[1], json={'x': 1, 'z': 2}).json()['village']
    assert [o['paint_version'] for o in space['objects']] == [1]
    # The owner route stays the owner's.
    assert c.get(own + '/paint', headers=hs[1]).status_code == 404
    # Moved to the workshop (guests never see it): neither the model nor the paint.
    assert c.post(own + '/placement', headers=hs[0], json=mutation(version=2, action='retrieve')).status_code == 200
    assert c.post(own + '/placement', headers=hs[0], json=mutation(version=3, room='workshop', x=2, z=2)).status_code == 200
    assert c.get(guest + '/model', headers=hs[1]).status_code == 404
    assert c.get(guest + '/paint', headers=hs[1]).status_code == 404
    # The home is visible to guests again.
    assert c.post(own + '/placement', headers=hs[0], json=mutation(version=4, room='home', x=2, z=-2)).status_code == 200
    assert c.get(guest + '/paint', headers=hs[1]).content == blob
    home = c.post('/v1/social/presence', headers=hs[1], json={'scene': 'home', 'x': 1, 'z': 2}).json()['space']
    assert [o['paint_version'] for o in home['objects']] == [1]


def raw_png(width, height, rows=None):
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
    rows = rows if rows is not None else b''.join(b'\0' + b'\x80' * (width * 3) for _ in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def test_invalid_and_oversized_paint_is_refused(world):
    app, c, hs, data = world
    route = '/v1/objects/' + starter(c, hs[0])['id'] + '/paint'

    def refused(payload, status, detail=None):
        response = c.post(route, headers=hs[0], json=mutation(**payload))
        assert response.status_code == status, response.text
        if detail:
            assert response.json()['detail'] == detail
    refused({'png': 'not base64 at all!'}, 422, 'invalid_png')
    refused({'png': ''}, 422, 'invalid_png')
    refused({}, 422, 'invalid_png')
    jpeg = io.BytesIO()
    Image.new('RGB', (64, 64)).save(jpeg, 'JPEG')
    refused({'png': encoded(jpeg.getvalue())}, 422, 'invalid_png')
    refused({'png': encoded(raw_png(2048, 2048))}, 422, 'invalid_png_size')
    refused({'png': encoded(raw_png(1025, 16))}, 422, 'invalid_png_size')
    # A real header whose image data is cut short.
    refused({'png': encoded(raw_png(64, 64, rows=b'\0\1\2'))}, 422, 'invalid_png')
    refused({'png': encoded(png()[:200])}, 422, 'invalid_png')
    refused({'png': encoded(png(64, 64)), 'clear': True}, 422)
    # Decoded over 4 MB (a valid start, then padding) and a body far over the route limit.
    refused({'png': encoded(raw_png(16, 16) + b'\0' * (4 * 1024 * 1024))}, 413, 'paint_too_large')
    huge = c.post(route, headers=hs[0], json=mutation(png='A' * (7 * 1024 * 1024)))
    assert huge.status_code == 413
    # Other routes keep their small body limit.
    assert c.post('/v1/prefs', headers=hs[0], json=mutation(prefs={'a': {'b': 'x' * 9000}})).status_code == 413
    # Sizes up to 1024 per side are fine, square or not.
    assert c.post(route, headers=hs[0], json=mutation(png=encoded(raw_png(1000, 600)))).status_code == 200
    assert paint_files(data) and all(name.endswith('.png') for name in paint_files(data))


def test_listings_show_paint_version_for_studio_objects(world):
    app, c, hs, data = world
    job = c.post('/v1/studio/jobs', headers=hs[0], json=mutation(prompt='wooden chest', motion='static')).json()['id']
    asyncio.run(app.state.studio.process(job))
    oid = c.get('/v1/studio/jobs/' + job, headers=hs[0]).json()['object_id']
    studio = {o['id']: o for o in c.get('/v1/studio', headers=hs[0]).json()['objects']}
    assert studio[oid]['paint_version'] is None
    assert c.post('/v1/objects/' + oid + '/paint', headers=hs[0], json=mutation(png=encoded(png(512, 512)))).status_code == 200
    studio = {o['id']: o for o in c.get('/v1/studio', headers=hs[0]).json()['objects']}
    assert studio[oid]['paint_version'] == 1 and studio[oid]['studio']
    assert listed_version(c, hs[0], oid) == 1
    # The other object stays unpainted.
    assert sum(1 for o in c.get('/v1/me', headers=hs[0]).json()['objects'] if o['paint_version']) == 1


def test_fixture_box_faces_do_not_share_uv_space():
    from server.asset_assembly import fixture_glb
    import json
    blob = fixture_glb('box')
    length = struct.unpack_from('<I', blob, 12)[0]
    doc = json.loads(blob[20:20 + length])
    binary = blob[20 + length + 8:]
    accessor = doc['accessors'][doc['meshes'][0]['primitives'][0]['attributes']['TEXCOORD_0']]
    view = doc['bufferViews'][accessor['bufferView']]
    uvs = [struct.unpack_from('<ff', binary, view['byteOffset'] + 8 * i) for i in range(accessor['count'])]
    cells = [{(int(u * 3), int(v * 2)) for u, v in uvs[face * 4:face * 4 + 4]} for face in range(6)]
    assert all(len(cell) == 1 for cell in cells) and len(set.union(*cells)) == 6


def test_crafts_always_request_uvs(tmp_path):
    provider = FurnitureProvider()
    app, client = paid_world(tmp_path, provider)
    with client as c:
        h = {'Authorization': 'Bearer ' + c.post('/v1/auth/register', json={'username': 'alice', 'password': 'Test-password-123'}).json()['token']}
        job = c.post('/v1/studio/jobs', headers=h, json=mutation(prompt='wooden stool', geometry='tripo', motion='static', material='mesh')).json()['id']
        asyncio.run(app.state.studio.process(job))
        assert c.post('/v1/studio/jobs/' + job + '/confirm', headers=h, json=mutation()).status_code == 200
        asyncio.run(app.state.studio.process(job))
    assert provider.calls and all(call['export_uv'] is True and call['texture'] is False for call in provider.calls)


def test_account_deletion_removes_paint_files(world, tmp_path_factory):
    app, c, hs, data = world
    keep = starter(c, hs[1])
    gone = starter(c, hs[0])
    for h, obj in ((hs[0], gone), (hs[1], keep)):
        assert c.post('/v1/objects/' + obj['id'] + '/paint', headers=h, json=mutation(png=encoded(png(128, 128)))).status_code == 200
    assert len(paint_files(data)) == 2
    backups = tmp_path_factory.mktemp('admin_backups')
    assert admin_main(['delete-accounts', 'alice', '--yes', '--data-dir', str(data), '--backups', str(backups)]) == 0
    remaining = paint_files(data)
    assert len(remaining) == 1 and remaining[0].startswith(keep['id'] + '.')
    with sqlite3.connect(data / 'world.sqlite3') as conn:
        assert conn.execute('SELECT object_id FROM object_paint').fetchall() == [(keep['id'],)]


def test_backups_carry_paint_and_detect_tampering(world, tmp_path_factory):
    app, c, hs, data = world
    obj = starter(c, hs[0])
    blob = png(256, 256, (5, 6, 7, 255))
    assert c.post('/v1/objects/' + obj['id'] + '/paint', headers=hs[0], json=mutation(png=encoded(blob))).status_code == 200
    root = tmp_path_factory.mktemp('snapshots')
    manifest = create_backup(data, root / 'snapshot')
    assert len(manifest['paint']) == 1 and verify_backup(root / 'snapshot') == manifest
    restore_backup(root / 'snapshot', root / 'restored', 'demo')
    assert [p.read_bytes() for p in (root / 'restored' / 'assets' / 'paint').glob('*.png')] == [blob]
    (root / 'snapshot' / 'assets' / 'paint' / manifest['paint'][0]['name']).write_bytes(png(8, 8))
    with pytest.raises(BackupError, match='paint_digest_mismatch'):
        verify_backup(root / 'snapshot')
