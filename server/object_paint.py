"""Painted surface textures of crafted objects (the in-game painter's saved result).

One flattened PNG per object, stored content-addressed under <data>/assets/paint/
as '<object_id>.<sha256>.png' and named by the object_paint row. The row keeps a
version that only grows (a cleared paint keeps its row with sha256 NULL), so clients can
cache a texture by object and version. Owners upload and read; visitors read through
multiplayer's guest routes with the same visibility rule as the models.
"""
import base64
import binascii
import hashlib
import io
import os
import re
import struct
import uuid
from pathlib import Path
from fastapi import HTTPException, Request
from fastapi.responses import Response
from pydantic import Field
from .models import Mutation

MAX_PNG_BYTES = 4 * 1024 * 1024
MAX_SIDE = 1024
# Base64 of the largest PNG plus room for the JSON envelope (request id, field names).
BODY_LIMIT = (MAX_PNG_BYTES + 2) // 3 * 4 + 4096
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
DIRECTORY = 'paint'
# The only route that takes a large body (BodyLimitMiddleware pattern limit).
UPLOAD_PATH = re.compile(r'^/v1/objects/[^/]{1,64}/paint$')

# Paint version an object list shows (NULL when the object is unpainted or cleared).
VERSION_SQL = '(SELECT version FROM object_paint WHERE object_paint.object_id={} AND object_paint.sha256 IS NOT NULL)'


def version_column(object_column):
    return VERSION_SQL.format(object_column)


class PaintUpload(Mutation):
    png: str = Field(default='', max_length=BODY_LIMIT)
    clear: bool = False


def fail(code, status=409):
    raise HTTPException(status, code)


def decode_png(text):
    """Strict base64 -> bounded, fully decodable PNG with sides of at most 1024 px."""
    if not text:
        fail('invalid_png', 422)
    if len(text) > (MAX_PNG_BYTES + 2) // 3 * 4:
        fail('paint_too_large', 413)
    try:
        blob = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        fail('invalid_png', 422)
    if len(blob) > MAX_PNG_BYTES:
        fail('paint_too_large', 413)
    # Signature, then IHDR as the first chunk (length 13).
    if len(blob) < 33 or blob[:8] != PNG_SIGNATURE or blob[12:16] != b'IHDR' or struct.unpack('>I', blob[8:12])[0] != 13:
        fail('invalid_png', 422)
    width, height = struct.unpack('>II', blob[16:24])
    if not (1 <= width <= MAX_SIDE and 1 <= height <= MAX_SIDE):
        fail('invalid_png_size', 422)
    try:
        from PIL import Image
        with Image.open(io.BytesIO(blob)) as image:
            if image.format != 'PNG' or image.size != (width, height):
                raise ValueError('mismatch')
            image.load()
    except HTTPException:
        raise
    except Exception:
        fail('invalid_png', 422)
    return blob


def folder(assets):
    return Path(assets) / DIRECTORY


def file_for(assets, object_id, sha256):
    return folder(assets) / f'{object_id}.{sha256}.png'


def files_of(assets, object_id):
    base = folder(assets)
    if not base.is_dir():
        return []
    return [p for p in base.glob(f'{object_id}.*.png') if p.is_file() and not p.is_symlink()]


def read(assets, object_id, sha256):
    path = file_for(assets, object_id, sha256)
    try:
        if path.is_symlink() or path.resolve().parent != folder(assets).resolve():
            raise OSError('outside')
        with path.open('rb') as source:
            blob = source.read(MAX_PNG_BYTES + 1)
    except OSError:
        fail('paint_not_found', 404)
    if len(blob) > MAX_PNG_BYTES or hashlib.sha256(blob).hexdigest() != sha256:
        fail('paint_integrity_failed', 503)
    return blob


def response(conn, assets, object_id):
    row = conn.execute('SELECT sha256 FROM object_paint WHERE object_id=?', (object_id,)).fetchone()
    if not row or not row['sha256']:
        fail('paint_not_found', 404)
    return Response(read(assets, object_id, row['sha256']), media_type='image/png', headers={'Cache-Control': 'no-store'})


def write(assets, object_id, blob, sha256):
    base = folder(assets)
    base.mkdir(exist_ok=True)
    target = file_for(assets, object_id, sha256)
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == sha256:
        return
    temporary = base / f'.{object_id}.{uuid.uuid4().hex}.tmp'
    try:
        with temporary.open('wb') as out:
            out.write(blob)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def remove_object_files(assets, object_id, keep=None):
    removed = 0
    for path in files_of(assets, object_id):
        if keep and path.name == f'{object_id}.{keep}.png':
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


class ObjectPaint:
    def __init__(self, app, db, clock, auth, mutate, own, assets):
        self.assets = assets

        def tidy(object_id):
            # Under the writer lock, so an upload that has written its file but not yet
            # committed is never mistaken for a leftover.
            with db.transaction() as conn:
                row = conn.execute('SELECT sha256 FROM object_paint WHERE object_id=?', (object_id,)).fetchone()
                remove_object_files(assets, object_id, row['sha256'] if row else None)

        @app.post('/v1/objects/{object_id}/paint')
        def upload(object_id: str, body: PaintUpload, request: Request):
            if body.clear and body.png:
                fail('invalid_request', 422)
            blob = None if body.clear else decode_png(body.png)
            sha256 = hashlib.sha256(blob).hexdigest() if blob is not None else None

            def save(conn, user):
                row = own(conn, user['id'], object_id)
                if row['state'] == 'listed':
                    fail('object_is_listed')
                previous = conn.execute('SELECT version,sha256 FROM object_paint WHERE object_id=?', (object_id,)).fetchone()
                if blob is not None:
                    write(assets, object_id, blob, sha256)
                elif not previous or not previous['sha256']:
                    return {'paint_version': None, 'sha256': None}
                version = (previous['version'] if previous else 0) + 1
                conn.execute('INSERT INTO object_paint(object_id,sha256,version,updated) VALUES (?,?,?,?) '
                             'ON CONFLICT(object_id) DO UPDATE SET sha256=excluded.sha256,version=excluded.version,updated=excluded.updated',
                             (object_id, sha256, version, clock()))
                return {'paint_version': version if sha256 else None, 'sha256': sha256}

            result = mutate(request, body, 'paint:' + object_id, save)
            tidy(object_id)
            return result

        @app.get('/v1/objects/{object_id}/paint')
        def fetch(object_id: str, request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                own(conn, user['id'], object_id)
                return response(conn, assets, object_id)
