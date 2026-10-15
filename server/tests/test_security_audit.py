"""Offline regressions for the 0.11.8 security audit; no paid/network calls."""
import base64
import io
import json
import struct
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from server import economy
from server.admin_cli import main
from server.app import create_app
from server.asset_assembly import fixture_glb
from server.asset_studio import MAX_CONCEPT_DRAWS, StudioRequest
from server.config import Settings
from server.provider import ProviderError, jpeg_preview, validate_glb
from server.tests.test_concept import Provider, craft, run, world
from server.tests.test_studio import account, mutation


def picture(fmt='PNG', size=(32, 32)):
    out = io.BytesIO()
    Image.new('RGB', size, 'orange').save(out, fmt)
    return out.getvalue()


def reference(blob, mime):
    return 'data:' + mime + ';base64,' + base64.b64encode(blob).decode()


def textured_glb(blob, mime):
    base = fixture_glb('box')
    length = struct.unpack_from('<I', base, 12)[0]
    doc = json.loads(base[20:20+length])
    binary = base[28+length:]
    doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(blob)})
    doc['images'] = [{'bufferView': len(doc['bufferViews'])-1, 'mimeType': mime}]
    doc['textures'] = [{'source': 0}]
    binary += blob
    doc['buffers'][0]['byteLength'] = len(binary)
    binary += b'\0' * (-len(binary) % 4)
    data = json.dumps(doc).encode()
    data += b' ' * (-len(data) % 4)
    return (struct.pack('<III', 0x46546c67, 2, 28+len(data)+len(binary))
            + struct.pack('<II', len(data), 0x4e4f534a) + data
            + struct.pack('<II', len(binary), 0x004e4942) + binary)


@pytest.mark.parametrize('fmt,mime', [('PNG', 'image/png'), ('JPEG', 'image/jpeg')])
def test_valid_reference_and_embedded_texture(fmt, mime):
    blob = picture(fmt)
    value = reference(blob, mime)
    assert StudioRequest(**mutation(prompt='wooden chair', image=value)).image == value
    validate_glb(textured_glb(blob, mime), allow_textures=True)


@pytest.mark.parametrize('fmt,mime', [('PNG', 'image/jpeg'), ('JPEG', 'image/png')])
def test_reference_and_glb_reject_mime_spoofing(fmt, mime):
    blob = picture(fmt)
    with pytest.raises(ValidationError):
        StudioRequest(**mutation(prompt='wooden chair', image=reference(blob, mime)))
    with pytest.raises(ProviderError, match='invalid_model'):
        validate_glb(textured_glb(blob, mime), allow_textures=True)


def test_truncated_jpeg_passes_header_verification_but_is_rejected():
    blob = picture('JPEG')[:-10]
    with Image.open(io.BytesIO(blob)) as im:
        im.verify()  # Previously accepted without decoding the pixels.
    with pytest.raises(ValidationError):
        StudioRequest(**mutation(prompt='wooden chair', image=reference(blob, 'image/jpeg')))
    with pytest.raises(ProviderError, match='invalid_model'):
        validate_glb(textured_glb(blob, 'image/jpeg'), allow_textures=True)


@pytest.mark.parametrize('size', [(4097, 1), (1, 4097), (65536, 1), (1, 65536)])
def test_preview_rejects_extreme_sides_even_with_small_pixel_count(size):
    with pytest.raises(ProviderError, match='invalid_image'):
        jpeg_preview(picture(size=size))


def test_preview_accepts_side_limit_and_downsizes():
    with Image.open(io.BytesIO(jpeg_preview(picture(size=(4096, 16))))) as im:
        assert max(im.size) <= 1024


@pytest.mark.parametrize('size', [(2049, 16), (16, 2049), (15, 32), (32, 15)])
def test_reference_dimension_limits(size):
    with pytest.raises(ValidationError):
        StudioRequest(**mutation(prompt='wooden chair', image=reference(picture(size=size), 'image/png')))


@pytest.mark.parametrize('quota,detail', [
    ({'signups_per_ip_day': 1}, 'too_many_registrations'),
    ({'signups_per_day': 1}, 'registration_closed_today'),
])
def test_exhausted_signup_quota_does_not_hash_password(tmp_path, monkeypatch, quota, detail):
    app = create_app(Settings(data_dir=tmp_path, mode='live', open_registration=True,
                              registration_code='audit-test-invitation-only', **quota), worker_enabled=False)
    with TestClient(app, base_url='https://testserver') as c:
        assert c.post('/v1/auth/register', json={'username': 'alice', 'password': 'Audit-test-password'}).status_code == 200
        def forbidden_hash(*args, **kwargs):
            pytest.fail('Exhausted registration quota reached Argon2')
        monkeypatch.setattr(PasswordHasher, 'hash', forbidden_hash)
        response = c.post('/v1/auth/register', json={'username': 'bravo', 'password': 'Audit-test-password'})
        assert response.status_code == 429
        assert response.json()['detail'] == detail


def test_signup_limit_rechecked_after_parallel_hashes(tmp_path, monkeypatch):
    app = create_app(Settings(data_dir=tmp_path, mode='live', open_registration=True, signups_per_ip_day=1,
                              registration_code='audit-test-invitation-only'), worker_enabled=False)
    barrier = threading.Barrier(2)
    original = PasswordHasher.hash
    def hash_together(self, *args, **kwargs):
        barrier.wait(timeout=10)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(PasswordHasher, 'hash', hash_together)
    with TestClient(app, base_url='https://testserver') as c:
        def signup(name):
            return c.post('/v1/auth/register', json={'username': name, 'password': 'Audit-test-password'}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(signup, ('alice', 'bravo'))) == [200, 429]
    with app.state.db.read() as conn:
        assert conn.execute('SELECT count(*) FROM users').fetchone()[0] == 1
        assert economy.ledger_check(conn) == []


@pytest.mark.parametrize('failure', ['failed', 'uncertain'])
def test_failed_redraws_are_bounded_across_replay_and_restart(tmp_path, failure):
    class FailingProvider(Provider):
        broken = False
        async def request(self, method, path, payload):
            result = await super().request(method, path, payload)
            if self.broken and failure == 'uncertain':
                raise ProviderError('upstream_unreachable', uncertain=True)
            return result
        async def task(self, task):
            if self.broken:
                return {'status': 'failed', 'credits_consumed': 5}
            return await super().task(task)
    provider = FailingProvider()
    app, client = world(tmp_path, provider)
    with client as c:
        headers = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=headers, json=craft()).json()['id']
        run(app, job)
        provider.broken = True
        redraw = '/v1/studio/jobs/' + job + '/redraw'
        for _ in range(MAX_CONCEPT_DRAWS-1):
            body = mutation()
            accepted = c.post(redraw, headers=headers, json=body)
            assert accepted.status_code == 200
            run(app, job)
            assert c.post(redraw, headers=headers, json=body).json() == accepted.json()
        refused = c.post(redraw, headers=headers, json=mutation())
        assert refused.status_code == 429 and refused.json()['detail'] == 'concept_redraw_limit'
        assert len(provider.calls) == MAX_CONCEPT_DRAWS
    app, client = world(tmp_path, provider)
    with client as c:
        assert c.post(redraw, headers=headers, json=mutation()).status_code == 429
    assert len(provider.calls) == MAX_CONCEPT_DRAWS


def test_parallel_redraws_reserve_one_attempt(tmp_path):
    app, client = world(tmp_path, Provider())
    with client as c:
        headers = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=headers, json=craft()).json()['id']
        run(app, job)
        def redraw(_):
            return c.post('/v1/studio/jobs/' + job + '/redraw', headers=headers, json=mutation()).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(redraw, range(2))) == [200, 409]
        with app.state.db.read() as conn:
            quote = json.loads(conn.execute('SELECT provenance FROM studio_jobs WHERE id=?', (job,)).fetchone()[0])
            assert quote['concept_redraw_attempts'] == 1


def test_tester_creation_uses_atomic_ledger_helper(tmp_path, monkeypatch):
    app = create_app(Settings(data_dir=tmp_path), worker_enabled=False)
    monkeypatch.setenv('TRIPOTHON_TESTER_PASSWORD', 'Audit-test-password')
    original = economy.change_shards
    calls = []
    def checked(conn, user_id, amount, reason, reference_id, now):
        assert conn.in_transaction
        assert conn.execute('SELECT shards FROM users WHERE id=?', (user_id,)).fetchone()[0] == 0
        original(conn, user_id, amount, reason, reference_id, now)
        calls.append(amount)
    monkeypatch.setattr(economy, 'change_shards', checked)
    assert main(['tester', 'create', 'tripo1', '--data-dir', str(tmp_path)]) == 0
    assert calls == [1500]
    with app.state.db.read() as conn:
        assert economy.ledger_check(conn) == []
    def reject(*args):
        checked(*args)
        raise RuntimeError('audit rollback probe')
    monkeypatch.setattr(economy, 'change_shards', reject)
    with pytest.raises(RuntimeError, match='audit rollback probe'):
        main(['tester', 'create', 'tripo2', '--data-dir', str(tmp_path)])
    with app.state.db.read() as conn:
        assert conn.execute("SELECT count(*) FROM users WHERE username='tripo2'").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM ledger WHERE reason='tester_welcome'").fetchone()[0] == 1
        assert economy.ledger_check(conn) == []


@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer invalid-audit-session'}])
@pytest.mark.parametrize('kind', ['studio', 'paint'])
def test_upload_auth_precedes_image_decoding(tmp_path, monkeypatch, headers, kind):
    app = create_app(Settings(data_dir=tmp_path), worker_enabled=False)
    encoded = base64.b64encode(picture()).decode()
    calls = []
    original = Image.open
    def observed(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(Image, 'open', observed)
    with TestClient(app) as c:
        route = '/v1/studio/jobs' if kind == 'studio' else '/v1/objects/unknown/paint'
        body = mutation(prompt='wooden chair', image='data:image/png;base64,'+encoded) if kind == 'studio' else mutation(png=encoded)
        response = c.post(route, headers=headers, json=body)
        assert response.status_code == 401
        assert response.headers['cache-control'] == 'no-store'
        assert calls == []
