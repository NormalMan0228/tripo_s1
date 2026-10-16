import asyncio
import hashlib
import io
import random

import pytest
from PIL import Image
from starlette.requests import Request

from server import asset_delivery
from server.asset_assembly import fixture_glb
from server.asset_delivery import asset_response, low_glb, prepare_low_variant
from server.provider import ProviderError, validate_glb
from server.rigged_glb import fixture_rigged_glb, pack, unpack
from server.tests.test_multiplayer import world, invite, post


def textured_glb(*, mode='RGB', format='PNG', rigged=False):
    doc, raw = unpack(fixture_rigged_glb() if rigged else fixture_glb('box'))
    pixels = random.Random(14).randbytes(1024 * 512 * len(mode))
    with Image.frombytes(mode, (1024, 512), pixels) as picture:
        image = io.BytesIO()
        picture.save(image, format)
    raw += b'\0' * (-len(raw) % 4)
    doc['images'] = [{'bufferView': len(doc['bufferViews']), 'mimeType': 'image/' + format.lower()}]
    doc['textures'] = [{'source': 0}]
    doc['materials'][0]['pbrMetallicRoughness']['baseColorTexture'] = {'index': 0}
    doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(raw), 'byteLength': len(image.getvalue())})
    return pack(doc, raw + image.getvalue())


@pytest.mark.parametrize('mode,format,rigged', [('RGB', 'PNG', False), ('RGBA', 'PNG', False),
                                              ('RGB', 'JPEG', False), ('RGB', 'PNG', True)])
def test_low_variant_caps_textures_and_preserves_geometry_animation(mode, format, rigged):
    original = textured_glb(mode=mode, format=format, rigged=rigged)
    reduced = low_glb(original)
    assert reduced and len(reduced) < len(original) and len(reduced) <= asset_delivery.LOW_MAX_BYTES
    validate_glb(reduced, allow_textures=True, allow_rigged=rigged)
    before, raw = unpack(original)
    after, compact = unpack(reduced)
    for field in ('meshes', 'nodes', 'accessors', 'skins', 'animations', 'materials', 'textures'):
        assert before.get(field) == after.get(field)
    for index, view in enumerate(before['bufferViews'][:-1]):
        other = after['bufferViews'][index]
        assert raw[view['byteOffset']:view['byteOffset'] + view['byteLength']] == compact[other['byteOffset']:other['byteOffset'] + other['byteLength']]
    view = after['bufferViews'][-1]
    with Image.open(io.BytesIO(compact[view['byteOffset']:view['byteOffset'] + view['byteLength']])) as picture:
        assert picture.size == (512, 256)
        if mode == 'RGBA':
            assert picture.mode == 'RGBA'


def test_variant_publication_is_reusable_immutable_and_source_bound(tmp_path, monkeypatch):
    assets = tmp_path / 'assets'
    assets.mkdir()
    source = textured_glb()
    checksum = hashlib.sha256(source).hexdigest()
    (assets / 'source.glb').write_bytes(source)
    assert prepare_low_variant(assets, 'source.glb', checksum, source)
    stored = list(assets.glob('*.low.*.glb'))
    assert len(stored) == 1 and len(stored[0].read_bytes()) <= asset_delivery.LOW_MAX_BYTES
    before = stored[0].stat().st_mtime_ns
    monkeypatch.setattr(asset_delivery, 'low_glb', lambda _: pytest.fail('generated twice'))
    assert prepare_low_variant(assets, 'source.glb', checksum, source)
    assert stored[0].stat().st_mtime_ns == before
    assert (assets / 'source.glb').read_bytes() == source
    request = Request({'type': 'http', 'method': 'GET', 'path': '/model', 'query_string': b'lod=low', 'headers': []})
    reduced = asset_response(request, assets, 'source.glb', checksum)
    assert reduced.headers['x-asset-lod'] == 'low'
    # A replacement source must not select an earlier source's derivative.
    replacement = fixture_glb('box')
    (assets / 'source.glb').write_bytes(replacement)
    updated = asset_response(request, assets, 'source.glb', hashlib.sha256(replacement).hexdigest())
    assert updated.body == replacement and updated.headers['x-asset-lod'] == 'original'
    with pytest.raises(ProviderError, match='asset_integrity_failed'):
        asset_response(request, assets, 'source.glb', checksum)


@pytest.mark.parametrize('damage', ['missing', 'changed', 'metadata', 'metadata_shape'])
def test_corrupt_derivative_falls_back_to_verified_original(tmp_path, damage):
    assets = tmp_path / 'assets'
    assets.mkdir()
    source = textured_glb()
    checksum = hashlib.sha256(source).hexdigest()
    (assets / 'source.glb').write_bytes(source)
    assert prepare_low_variant(assets, 'source.glb', checksum, source)
    variant = next(assets.glob('*.low.*.glb'))
    if damage == 'missing':
        variant.unlink()
    elif damage == 'changed':
        variant.write_bytes(b'corrupt')
    elif damage == 'metadata':
        variant.with_suffix('.json').write_bytes(b'invalid json')
    else:
        variant.with_suffix('.json').write_bytes(b'[]')
    request = Request({'type': 'http', 'method': 'GET', 'path': '/model', 'query_string': b'lod=low', 'headers': []})
    response = asset_response(request, assets, 'source.glb', checksum)
    assert response.body == source and response.headers['x-asset-lod'] == 'original'


def test_cap_unsupported_and_disk_errors_do_not_break_original(tmp_path, monkeypatch):
    assets = tmp_path / 'assets'
    assets.mkdir()
    source = textured_glb()
    checksum = hashlib.sha256(source).hexdigest()
    assert low_glb(fixture_glb('box')) is None
    assert low_glb(fixture_glb('box', True)) is None
    monkeypatch.setattr(asset_delivery, 'LOW_MAX_BYTES', 1024)
    assert not prepare_low_variant(assets, 'source.glb', checksum, source)
    monkeypatch.setattr(asset_delivery, 'LOW_MAX_BYTES', 4 * 1024 * 1024)
    def no_disk(*args):
        raise OSError('disk unavailable')
    monkeypatch.setattr(asset_delivery, '_atomic_write', no_disk)
    assert not prepare_low_variant(assets, 'source.glb', checksum, source)
    assert not prepare_low_variant(assets, '../source.glb', checksum, source)
    assert not prepare_low_variant(assets, 'source.glb', 'bad', source)
    assert list(assets.iterdir()) == []


def test_legacy_model_range_cache_and_authorization(world):
    app, client, now, headers, settings = world
    item = client.get('/v1/me', headers=headers[0]).json()['objects'][0]
    route = '/v1/objects/' + item['id'] + '/model'
    original = client.get(route, headers=headers[0])
    assert original.headers['cache-control'] == 'no-store'
    assert original.headers['accept-ranges'] == 'bytes'
    etag = '"' + hashlib.sha256(original.content).hexdigest() + '"'
    assert original.headers['etag'] == etag
    for suffix, content in [('0-15', original.content[:16]), ('16-', original.content[16:]), ('-16', original.content[-16:])]:
        response = client.get(route, headers={**headers[0], 'Range': 'bytes=' + suffix, 'If-Range': etag})
        assert response.status_code == 206 and response.content == content
        assert response.headers['content-range'].endswith('/' + str(len(original.content)))
        assert response.headers['content-length'] == str(len(content))
    for invalid in ['99999999-', '12-2', '-0', '-', '1-x']:
        response = client.get(route, headers={**headers[0], 'Range': 'bytes=' + invalid})
        assert response.status_code == 416 and response.headers['content-range'] == 'bytes */' + str(len(original.content))
    for if_range in ['"stale"', 'W/' + etag, 'Fri, 16 Oct 2026 00:00:00 GMT']:
        response = client.get(route, headers={**headers[0], 'Range': 'bytes=16-', 'If-Range': if_range})
        assert response.status_code == 200 and response.content == original.content
    assert client.get(route, headers={**headers[0], 'Range': 'bytes=0-1,3-4'}).status_code == 200
    cached = client.get(route + '?cache=1', headers=headers[0])
    assert cached.headers['cache-control'] == 'private, max-age=0, must-revalidate'
    for matcher in [etag, 'W/' + etag, '"other", ' + etag, '*']:
        response = client.get(route, headers={**headers[0], 'If-None-Match': matcher, 'Range': 'bytes=4-'})
        assert response.status_code == 304 and response.content == b''
    for status, auth in [(401, {}), (404, headers[1])]:
        response = client.get(route + '?lod=low', headers={**auth, 'If-None-Match': etag, 'Range': 'bytes=0-10'})
        assert response.status_code == status and 'etag' not in response.headers


def test_ready_build_serves_low_and_resumes_for_owner_and_visitor(world, monkeypatch):
    app, client, now, headers, settings = world
    source = textured_glb()
    monkeypatch.setattr('server.asset_studio.fixture_glb', lambda *args, **kwargs: source)
    job = post(client, headers[0], '/v1/studio/jobs', prompt='chest', material='textured', motion='static')
    asyncio.run(app.state.studio.process(job['id']))
    status = client.get('/v1/studio/jobs/' + job['id'], headers=headers[0]).json()
    assert status['state'] == 'ready', status
    own = '/v1/objects/' + status['object_id']
    guest = '/v1/social/village/objects/' + status['object_id']
    plan = client.get(own + '/assembly', headers=headers[0]).json()['plan']
    assert len(list((settings.data_dir / 'assets').glob('*.low.*.glb'))) == len(plan['parts'])
    post(client, headers[0], own + '/placement', version=1, room='village', x=5, z=4)
    invite(client, headers[0], headers[1], 'bravo', 'village')
    seen = []
    for prefix, auth in [(own, headers[0]), (guest, headers[1])]:
        for suffix in ['/model'] + ['/parts/' + part['id'] for part in plan['parts']]:
            route = prefix + suffix
            original = client.get(route, headers=auth)
            assert original.content == source and original.headers['cache-control'] == 'no-store'
            low = client.get(route + '?lod=low', headers=auth)
            assert low.status_code == 200 and low.headers['x-asset-lod'] == 'low'
            assert len(low.content) < len(source)
            assert low.headers['etag'] != original.headers['etag']
            first = client.get(route + '?lod=low', headers={**auth, 'Range': 'bytes=0-1023'})
            rest = client.get(route + '?lod=low', headers={**auth, 'Range': 'bytes=1024-', 'If-Range': low.headers['etag']})
            assert first.status_code == rest.status_code == 206
            assert first.content + rest.content == low.content
            if prefix == guest:
                seen.append((route, low.headers['etag']))
    post(client, headers[1], '/v1/social/home')
    for route, etag in seen:
        response = client.get(route + '?lod=low', headers={**headers[1], 'Range': 'bytes=0-15', 'If-None-Match': etag})
        assert response.status_code == 404 and 'etag' not in response.headers
