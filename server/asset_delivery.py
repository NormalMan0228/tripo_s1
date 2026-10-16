"""Opt-in private GLB caching, resumable reads, and bounded ready-time variants.

Call ``asset_response`` only after the route's normal ownership/visit checks.
Variants never change the published original or any manifest/mesh contract.
"""
import hashlib
import io
import json
import os
import re
import struct
import tempfile
from pathlib import Path

from fastapi.responses import Response
from PIL import Image

from .backups import BackupError, asset_path
from .provider import ProviderError, validate_glb
from .stored_assets import read_glb

LOW_MAX_BYTES = 4 * 1024 * 1024
LOW_TEXTURE_EDGE = 512
_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_SINGLE_RANGE = re.compile(r'^bytes=(\d*)-(\d*)$')


def _pack(doc, binary):
    doc['buffers'][0]['byteLength'] = len(binary)
    encoded = json.dumps(doc, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    binary = bytes(binary) + b'\0' * (-len(binary) % 4)
    return (struct.pack('<III', 0x46546c67, 2, 28 + len(encoded) + len(binary))
            + struct.pack('<II', len(encoded), 0x4e4f534a) + encoded
            + struct.pack('<II', len(binary), 0x004e4942) + binary)


def low_glb(blob):
    """Preserve every geometry/animation byte; shrink embedded PNG/JPEG images.

    No external resources/codecs, mesh decimation, or material changes. Return
    None when a smaller <=4 MiB representation cannot be made safely.
    """
    try:
        doc = validate_glb(blob, allow_textures=True)
    except ProviderError:
        # The rig validator requires a complete rig; static models use its
        # existing static contract instead of enabling it unconditionally.
        doc = validate_glb(blob, allow_textures=True, allow_rigged=True)
    binary = None
    offset = 12
    while offset < len(blob):
        size, kind = struct.unpack_from('<II', blob, offset)
        if kind == 0x004e4942:
            binary = blob[offset + 8:offset + 8 + size]
        offset += 8 + size
    replacements = {}
    image_views = {image['bufferView'] for image in doc.get('images', [])}
    # A shared accessor/image view cannot be rewritten without changing geometry.
    if image_views & {a['bufferView'] for a in doc.get('accessors', [])}:
        return None
    for entry in doc.get('images', []):
        index = entry['bufferView']
        if index in replacements:
            continue
        view = doc['bufferViews'][index]
        start = view.get('byteOffset', 0)
        source = binary[start:start + view['byteLength']]
        with Image.open(io.BytesIO(source)) as picture:
            if picture.format not in ('PNG', 'JPEG'):
                return None
            if max(picture.size) <= LOW_TEXTURE_EDGE:
                continue
            # The server validator already bounds decoded pixels; keep that gate.
            picture.load()
            picture.thumbnail((LOW_TEXTURE_EDGE, LOW_TEXTURE_EDGE), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            if picture.format == 'JPEG':
                picture.convert('RGB').save(output, 'JPEG', quality=82)
            else:
                picture.save(output, 'PNG', optimize=True)
            replacements[index] = output.getvalue()
    if not replacements:
        return None
    packed = bytearray()
    for index, view in enumerate(doc['bufferViews']):
        start = view.get('byteOffset', 0)
        content = replacements.get(index, binary[start:start + view['byteLength']])
        packed.extend(b'\0' * (-len(packed) % 4))
        view.update(byteOffset=len(packed), byteLength=len(content))
        packed.extend(content)
        if len(packed) > LOW_MAX_BYTES:
            return None
    result = _pack(doc, packed)
    if len(result) >= len(blob) or len(result) > LOW_MAX_BYTES:
        return None
    validate_glb(result, allow_textures=True, allow_rigged=bool(doc.get('skins')))
    return result


def _variant_paths(assets, filename, source_hash):
    if not isinstance(source_hash, str) or not _SHA256.fullmatch(source_hash):
        raise BackupError('invalid_asset_digest')
    original = asset_path(assets.parent, filename)
    variant = asset_path(assets.parent, original.stem + '.low.' + source_hash + '.glb')
    metadata = variant.with_suffix('.json')
    if metadata.is_symlink():
        raise BackupError('invalid_asset_path')
    return variant, metadata


def _atomic_write(target, content):
    handle, name = tempfile.mkstemp(prefix='.low-', suffix='.tmp', dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(handle, 'wb') as output:
            output.write(content)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _read_low(assets, filename, source_hash):
    variant, metadata = _variant_paths(assets, filename, source_hash)
    with metadata.open('rb') as source:
        encoded = source.read(1025)
    if len(encoded) > 1024:
        return None
    info = json.loads(encoded)
    if (info.get('source_sha256') != source_hash or type(info.get('bytes')) is not int
            or not 0 < info['bytes'] <= LOW_MAX_BYTES
            or not isinstance(info.get('sha256'), str) or not _SHA256.fullmatch(info['sha256'])):
        return None
    with variant.open('rb') as source:
        blob = source.read(LOW_MAX_BYTES + 1)
    if len(blob) != info['bytes'] or hashlib.sha256(blob).hexdigest() != info['sha256']:
        return None
    return blob, info['sha256']


def prepare_low_variant(assets, filename, source_hash, blob):
    """Best-effort once at ready time, outside the event loop/DB transaction.

    The source hash in the filename makes replacement assets select a new variant.
    Missing/unsupported/corrupt derivatives always fall back to the original.
    """
    try:
        if hashlib.sha256(blob).hexdigest() != source_hash:
            return False
        variant, metadata = _variant_paths(assets, filename, source_hash)
        if metadata.exists() and _read_low(assets, filename, source_hash):
            return True
        reduced = low_glb(blob)
        if reduced is None:
            return False
        info = {'source_sha256': source_hash, 'sha256': hashlib.sha256(reduced).hexdigest(), 'bytes': len(reduced)}
        _atomic_write(variant, reduced)
        _atomic_write(metadata, json.dumps(info, separators=(',', ':')).encode())
        return True
    except (OSError, ValueError, TypeError, AttributeError, KeyError, BackupError, ProviderError, Image.DecompressionBombError):
        # An optional optimization must never fail a paid craft or publish a bad GLB.
        return False


def asset_response(request, assets, filename, source_hash):
    # Preserve the existing integrity gate even on 304 and derivative responses.
    blob = read_glb(assets, filename, source_hash)
    checksum, lod = source_hash, 'original'
    if request.query_params.get('lod') == 'low':
        try:
            reduced = _read_low(assets, filename, source_hash)
            if reduced:
                blob, checksum = reduced
                lod = 'low'
        except (OSError, ValueError, TypeError, AttributeError, KeyError, BackupError):
            pass
    conditional = request.headers.get('if-none-match')
    caching = (request.query_params.get('cache') == '1' or request.query_params.get('lod') == 'low'
               or conditional is not None or 'range' in request.headers)
    etag = '"' + checksum + '"'
    headers = {'Accept-Ranges': 'bytes', 'ETag': etag, 'Vary': 'Authorization', 'X-Asset-Lod': lod,
               'Cache-Control': 'private, max-age=0, must-revalidate' if caching else 'no-store'}
    if conditional and any(value.strip().removeprefix('W/') in (etag, '*') for value in conditional.split(',')):
        return Response(status_code=304, headers=headers)
    range_header = request.headers.get('range', '')
    # Unknown units and multipart ranges are ignored: this endpoint supports a
    # single contiguous range, enough for resumable downloads without amplification.
    if range_header.startswith('bytes=') and ',' not in range_header:
        if_range = request.headers.get('if-range')
        if if_range is None or if_range == etag:
            match = _SINGLE_RANGE.fullmatch(range_header) if len(range_header) <= 128 else None
            start, end = 0, len(blob) - 1
            valid = bool(match and any(match.groups()))
            if valid:
                first, last = match.groups()
                if first:
                    start = int(first)
                    end = min(int(last), end) if last else end
                else:
                    length = int(last)
                    start = max(0, len(blob) - length)
                    valid = length > 0
                valid = valid and start <= end and start < len(blob)
            if not valid:
                return Response(status_code=416, headers={**headers, 'Cache-Control': 'no-store',
                                                          'Content-Range': f'bytes */{len(blob)}'})
            headers['Content-Range'] = f'bytes {start}-{end}/{len(blob)}'
            return Response(blob[start:end + 1], status_code=206, media_type='model/gltf-binary', headers=headers)
    return Response(blob, media_type='model/gltf-binary', headers=headers)
