"""Game patches: export, inspect and list them (used by tools/publish_school_build.py).

An installed game is Villagen.exe + Villagen.pck. A patch is a Godot 4 delta pack: only the files
that differ from one released pack, plus removal marks for files that are gone
(godot --export-patch <preset> <out.pck> --patches <base.pck>). The game downloads the one patch
for its installed version (patcher.gd) and loads it before anything else at launch
(game/scripts/patch_boot.gd, the first autoload).

Patches are cumulative: for every kept base B (builds/bases/<B>/Villagen.pck, a released full
install) and the new version V there is one pack <B>_to_<V>.pck, built against B alone.

A release needs the installer instead (requires_reinstall) when the patch could not work:
  engine     the pack was made by another Godot version (the exe is part of the install)
  template   the export template (the exe) changed since that base
  boot       game/scripts/patch_boot.gd changed (it always runs from the installed pack)
  settings   project settings other than the version changed (input map, autoloads, window ...:
             Godot reads them from the installed pack before any patch loads)

PCK layout (Godot 4.7, pack format 3/4): "GDPC", u32 format, u32 engine major/minor/patch,
u32 flags, u64 file base, [u64 directory offset (format >= 3)], 16 reserved u32; the directory
holds u32 count, then per file u32 path length, path (zero padded), u64 offset, u64 size,
16-byte MD5, u32 flags (1 encrypted, 2 removal). Flag 2 in the header (relative file base) makes
offsets relative to the file base.
project.binary: "ECFG", u32 count, then per setting a u32-length name and a u32-length encoded
Variant.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

PACK_REL_FILEBASE = 2
FILE_ENCRYPTED = 1
FILE_REMOVAL = 2
VERSION_KEY = 'application/config/version'
BOOT_FILES = ('scripts/patch_boot.gd', 'scripts/patch_boot.gdc', 'scripts/patch_boot.gd.remap')
VERSION = re.compile(r'\d{1,4}(\.\d{1,4}){1,3}')


def version_key(text):
    return tuple(int(part) for part in text.split('.')) + (0,) * (4 - text.count('.') - 1)


def older(a, b):
    return version_key(a) < version_key(b)


def read_pck(path):
    """{'format', 'engine': 'major.minor.patch', 'files': {path: {offset, size, md5, flags}}}"""
    path = Path(path)
    with path.open('rb') as f:
        head = f.read(112)
        if len(head) < 40 or head[:4] != b'GDPC':
            raise ValueError(f'{path.name} is not a Godot pack')
        fmt, major, minor, patch, flags = struct.unpack_from('<5I', head, 4)
        file_base = struct.unpack_from('<Q', head, 24)[0]
        if fmt >= 3:
            directory = struct.unpack_from('<Q', head, 32)[0]
        else:
            directory = 24 + 8 + 16 * 4
        f.seek(directory)
        count = struct.unpack('<I', f.read(4))[0]
        files = {}
        for _ in range(count):
            length = struct.unpack('<I', f.read(4))[0]
            name = f.read(length).rstrip(b'\0').decode('utf-8')
            offset, size = struct.unpack('<QQ', f.read(16))
            md5 = f.read(16).hex()
            entry_flags = struct.unpack('<I', f.read(4))[0]
            if flags & PACK_REL_FILEBASE:
                offset += file_base
            files[name.removeprefix('res://')] = {'offset': offset, 'size': size, 'md5': md5, 'flags': entry_flags}
    return {'format': fmt, 'engine': f'{major}.{minor}.{patch}', 'files': files}


def read_file(path, pack, name):
    entry = pack['files'][name]
    if entry['flags'] & (FILE_ENCRYPTED | FILE_REMOVAL):
        raise ValueError(f'{name} is encrypted or removed')
    with Path(path).open('rb') as f:
        f.seek(entry['offset'])
        return f.read(entry['size'])


def project_settings(raw):
    """project.binary -> {name: encoded value bytes}."""
    if raw[:4] != b'ECFG':
        raise ValueError('not a project.binary')
    count = struct.unpack_from('<I', raw, 4)[0]
    at, out = 8, {}
    for _ in range(count):
        length = struct.unpack_from('<I', raw, at)[0]
        at += 4
        name = raw[at:at + length].decode('utf-8')
        at += length
        size = struct.unpack_from('<I', raw, at)[0]
        at += 4
        out[name] = raw[at:at + size]
        at += size
    return out


def string_value(encoded):
    """A Variant-encoded String (type 4) as text, else None."""
    if len(encoded) < 8 or struct.unpack_from('<I', encoded, 0)[0] & 0xFFFF != 4:
        return None
    length = struct.unpack_from('<I', encoded, 4)[0]
    return encoded[8:8 + length].decode('utf-8')


def pack_version(path, pack=None):
    pack = pack or read_pck(path)
    if 'project.binary' not in pack['files']:
        return ''
    return string_value(project_settings(read_file(path, pack, 'project.binary')).get(VERSION_KEY, b'')) or ''


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def inspect(base_path, patch_path, base_record=None, template_sha=''):
    """What a patch changes against its base, and why it might need the installer instead."""
    base, patch = read_pck(base_path), read_pck(patch_path)
    removed = sorted(n for n, e in patch['files'].items() if e['flags'] & FILE_REMOVAL)
    changed = sorted(n for n, e in patch['files'].items() if not e['flags'] & FILE_REMOVAL)
    reasons = []
    if base['engine'] != patch['engine']:
        reasons.append('engine')
    if base_record and template_sha and base_record.get('template_sha256') not in ('', None, template_sha):
        reasons.append('template')
    if any(n in BOOT_FILES for n in changed + removed):
        reasons.append('boot')
    settings_changed = []
    if 'project.binary' in changed:
        before = project_settings(read_file(base_path, base, 'project.binary'))
        after = project_settings(read_file(patch_path, patch, 'project.binary'))
        settings_changed = sorted(k for k in set(before) | set(after) if k != VERSION_KEY and before.get(k) != after.get(k))
        if settings_changed:
            reasons.append('settings')
    return {'engine': patch['engine'], 'base_files': len(base['files']), 'changed': changed, 'removed': removed,
            'settings_changed': settings_changed, 'reasons': reasons,
            'version': pack_version(patch_path, patch), 'base_version': pack_version(base_path, base)}


def export_patch(godot, project, preset, base_pck, out):
    """godot --export-patch: the files of the project's export that differ from base_pck."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    # The archipelago's generated data must match the map before it goes into a patch.
    import bake_archipelago
    bake_archipelago.ensure()
    # So must the survival maps' baked data (it is used only when it matches them).
    import bake_survival
    bake_survival.ensure()
    command = [str(godot), '--headless', '--path', str(project), '--export-patch', preset, str(out), '--patches', str(base_pck)]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if not out.is_file():
        tail = '\n'.join((result.stdout + result.stderr).splitlines()[-20:])
        raise SystemExit(f'patch export failed ({result.returncode}):\n{tail}')
    read_pck(out)
    return out


def base_record(pck, template):
    """base.json for a released full pack kept as a patch base."""
    pack = read_pck(pck)
    return {'version': pack_version(pck, pack), 'engine': pack['engine'], 'files': len(pack['files']),
            'template_sha256': sha256(template) if Path(template).is_file() else '',
            'registered': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}


def manifest(latest, entries, edition='school'):
    """patches.json: what a game of each kept base downloads to become `latest`."""
    return {'format': 1, 'edition': edition, 'latest': latest,
            'date': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M'),
            'bases': entries}
