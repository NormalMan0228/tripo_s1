"""tools/game_patch.py: reading Godot packs and deciding when a patch may replace the installer.

The packs here are written by a small writer in the same layout Godot 4.7 uses (pack format 3+,
relative file base, removal flag), so the checks run without exporting the game."""
import importlib.util
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('game_patch', ROOT / 'tools' / 'game_patch.py')
game_patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(game_patch)


def variant_string(text):
    data = text.encode('utf-8')
    return struct.pack('<II', 4, len(data)) + data + b'\0' * (-len(data) % 4)


def project_binary(settings):
    out = b'ECFG' + struct.pack('<I', len(settings))
    for name, value in settings.items():
        key = name.encode('utf-8')
        encoded = variant_string(value) if isinstance(value, str) else value
        out += struct.pack('<I', len(key)) + key + struct.pack('<I', len(encoded)) + encoded
    return out


def write_pck(path, files, engine=(4, 7, 2), removed=()):
    """files: {name: bytes}; removed: names marked as removed (a patch)."""
    header_size = 4 + 4 * 5 + 8 + 8 + 16 * 4
    blobs, offset = [], 0
    for name, data in files.items():
        blobs.append((name, offset, data, 0))
        offset += len(data)
    blobs += [(name, 0, b'', game_patch.FILE_REMOVAL) for name in removed]
    body = b''.join(data for _, _, data, _ in blobs)
    directory = struct.pack('<I', len(blobs))
    for name, at, data, flags in blobs:
        raw = name.encode('utf-8')
        raw += b'\0' * (-len(raw) % 4)
        directory += struct.pack('<I', len(raw)) + raw + struct.pack('<QQ', at, len(data)) + b'\0' * 16 + struct.pack('<I', flags)
    head = b'GDPC' + struct.pack('<5I', 3, *engine, game_patch.PACK_REL_FILEBASE)
    head += struct.pack('<QQ', header_size, header_size + len(body)) + b'\0' * 64
    Path(path).write_bytes(head + body + directory)
    return Path(path)


SETTINGS = {'application/config/name': 'Villagen', 'application/config/version': '0.11.5',
            'autoload/PatchBoot': '*res://scripts/patch_boot.gd'}


@pytest.fixture
def base(tmp_path):
    return write_pck(tmp_path / 'base.pck', {
        'project.binary': project_binary(SETTINGS), 'scripts/main.gdc': b'main v1',
        'scripts/patch_boot.gdc': b'boot', 'maps/old.json': b'{}'})


def test_a_content_patch_needs_no_installer(tmp_path, base):
    patch = write_pck(tmp_path / 'p.pck', {'project.binary': project_binary({**SETTINGS, 'application/config/version': '0.11.6'}),
                                           'scripts/main.gdc': b'main v2'}, removed=['maps/old.json'])
    info = game_patch.inspect(base, patch)
    assert info['base_version'] == '0.11.5' and info['version'] == '0.11.6'
    assert info['changed'] == ['project.binary', 'scripts/main.gdc'] and info['removed'] == ['maps/old.json']
    assert info['reasons'] == [] and info['settings_changed'] == [] and info['base_files'] == 4
    assert game_patch.read_file(patch, game_patch.read_pck(patch), 'scripts/main.gdc') == b'main v2'


def test_what_only_the_installer_can_change(tmp_path, base):
    other_engine = write_pck(tmp_path / 'e.pck', {'scripts/main.gdc': b'x'}, engine=(4, 8, 0))
    assert game_patch.inspect(base, other_engine)['reasons'] == ['engine']
    boot = write_pck(tmp_path / 'b.pck', {'scripts/patch_boot.gdc': b'boot v2'})
    assert game_patch.inspect(base, boot)['reasons'] == ['boot']
    settings = write_pck(tmp_path / 's.pck', {'project.binary': project_binary({**SETTINGS, 'application/config/version': '0.11.6',
                                                                                'autoload/Extra': '*res://scripts/extra.gd'})})
    info = game_patch.inspect(base, settings)
    assert info['reasons'] == ['settings'] and info['settings_changed'] == ['autoload/Extra']
    template = tmp_path / 'template.exe'
    template.write_bytes(b'MZ new template')
    record = {'template_sha256': 'old'}
    assert game_patch.inspect(base, write_pck(tmp_path / 't.pck', {'a.txt': b'a'}), record, game_patch.sha256(template))['reasons'] == ['template']


def test_base_record_and_list(tmp_path, base):
    template = tmp_path / 'template.exe'
    template.write_bytes(b'MZ')
    record = game_patch.base_record(base, template)
    assert record['version'] == '0.11.5' and record['engine'] == '4.7.2' and record['files'] == 4
    assert record['template_sha256'] == game_patch.sha256(template)
    listing = game_patch.manifest('0.11.6', {'0.11.5': {'file': 'patches/0.11.5_to_0.11.6.pck', 'size': 1, 'sha256': 'a' * 64}})
    assert listing['format'] == 1 and listing['latest'] == '0.11.6' and '0.11.5' in listing['bases']
    assert game_patch.older('0.11.9', '0.11.10') and not game_patch.older('0.11.10', '0.11.10')


def test_not_a_pack(tmp_path):
    junk = tmp_path / 'junk.pck'
    junk.write_bytes(b'PK\x03\x04 not a pack' * 4)
    with pytest.raises(ValueError):
        game_patch.read_pck(junk)
