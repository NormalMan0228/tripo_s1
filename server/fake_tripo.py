"""A stand-in for the Tripo API on development servers (TRIPOTHON_FAKE_TRIPO=true, ops/staging.sh fake).

Crafting runs its real path (pricing, limits, task ids, polling, download, validation, assembly) but
every Tripo call is answered here, inside the process: no network, no key, no credits. Each task
finishes at once (or after TRIPOTHON_FAKE_TRIPO_SECONDS) with a small sample shape and bills 0
credits, so fake crafts never count toward a real budget. Task ids carry everything a later poll or
download needs, so tasks survive a server restart.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time

import httpx

from .asset_assembly import fixture_glb

FAKE_KEY = 'fake-tripo-development-only'
HOST = 'fake.tripo3d.ai'
IMAGE_ROUTES = ('text-to-image', 'image-to-image')


def _answer(data, status=200):
    return httpx.Response(status, json={'code': 0, 'data': data} if status == 200 else {'code': 1, 'message': data})


def _task_id(kind, payload, now):
    """Task IDs encode model/image/rig/animation, texture, shape and start time."""
    words = str(payload.get('prompt') or payload.get('input') or '')
    shape = 'box' if hashlib.sha256(words.encode()).digest()[0] % 2 == 0 else 'ball'
    return '-'.join(('fake', 'i' if kind in IMAGE_ROUTES else ('r' if kind == 'rig' else ('a' if kind == 'retarget' else 'm')), 't' if payload.get('texture') else 'u',
                     shape, str(int(now)), secrets.token_hex(6)))


def _parse(task):
    parts = task.split('-')
    if len(parts) != 6 or parts[0] != 'fake' or parts[1] not in ('m','i','r','a') or parts[2] not in 'tu' \
            or parts[3] not in ('box', 'ball') or not parts[4].isdigit():
        return None
    return {'animated':parts[1] == 'a', 'image': parts[1] == 'i', 'textured': parts[2] == 't', 'shape': parts[3], 'started': int(parts[4])}


def transport(seconds=0.0, clock=time.time):
    """An httpx transport for TripoProvider that never leaves the process."""
    def handle(request):
        path = request.url.path
        if request.url.host == HOST:
            # Asset downloads (never carry the key, like Tripo's asset hosts).
            name = path.rsplit('/', 1)[-1].split('.', 1)[0]
            task = _parse(name)
            if not task:
                return httpx.Response(404)
            if path.startswith('/images/'):
                from .asset_studio import fixture_concept
                return httpx.Response(200, content=fixture_concept(name), headers={'content-type': 'image/jpeg'})
            if task['animated']:
                from .rigged_glb import fixture_rigged_glb
                return httpx.Response(200, content=fixture_rigged_glb(), headers={'content-type':'model/gltf-binary'})
            return httpx.Response(200, content=fixture_glb('box' if task['shape'] == 'box' else 'sphere', task['textured']),
                                  headers={'content-type': 'model/gltf-binary'})
        if request.headers.get('authorization') != 'Bearer ' + FAKE_KEY:
            return httpx.Response(401, json={'code': 1})
        if path.endswith('/account/balance'):
            return _answer({'balance': 1000000, 'frozen': 0})
        if path.endswith('/files'):
            return _answer({'file_token': 'fake-file-' + secrets.token_hex(8)})
        if ('/generation/' in path or path.endswith(('/animations/rig','/animations/retarget'))) and request.method == 'POST':
            try:
                payload = json.loads(request.content or b'{}')
            except ValueError:
                return _answer('invalid json', 400)
            kind = path.rsplit('/', 1)[-1]
            return _answer({'task_id': _task_id(kind, payload if isinstance(payload, dict) else {}, clock())})
        if '/tasks/' in path:
            name = path.rsplit('/', 1)[-1]
            task = _parse(name)
            if not task:
                return _answer('task not found', 404)
            waited = clock() - task['started']
            if seconds > 0 and waited < seconds:
                return _answer({'task_id': name, 'status': 'running', 'progress': int(100 * max(0, waited) / seconds)})
            output = {'generated_image': 'https://%s/images/%s.jpg' % (HOST, name)} if task['image'] \
                else {'model_url': 'https://%s/models/%s.glb' % (HOST, name)}
            return _answer({'task_id': name, 'status': 'success', 'progress': 100, 'credits_consumed': 0, 'output': output})
        return _answer('unknown route', 404)
    return httpx.MockTransport(handle)
