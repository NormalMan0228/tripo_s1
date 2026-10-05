"""Place the reviewed buildings on the approved terrain; keep source assets intact."""
import ast
import io
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.interpolate import LinearNDInterpolator

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/maps/archipelago_placement_v1'
LAB = ROOT / 'labs/terrain_lab'
OUT.mkdir(parents=True, exist_ok=True)
(LAB / 'assets/buildings').mkdir(parents=True, exist_ok=True)

# Coordinates use Godot metres: north = -Z. Entries follow the reference's
# island membership and relative ordering, with room for later bridges/props.
SITES = [
    ('01_cafe', 1, -62, -38, 0),
    ('02_timber_house', 1, -42, -50, -20),
    ('03_teal_cottage', 1, -34, -28, 20),
    ('04_windmill', 1, -18, -44, 0),
    ('05_observatory', 2, 30, -48, 0),
    ('06_orange_cottage', 2, 24, -28, 40),
    ('07_greenhouse', 2, 49, -20, 38),
    ('08_gazebo', 2, 71, -36, 0),
    ('09_town_hall', 3, -33, 22, -19),
    ('10_red_house', 3, -55, 17, -25),
    ('11_purple_house', 3, -68, 32, 0),
    ('12_blue_house', 3, -67, 46, 0),
    ('13_shop', 3, -17, 28, 0),
    ('14_stage', 4, 37, 26, 0),
    ('15_picnic_shelter', 4, 65, 29, 0),
    ('16_blue_cottage', 4, 70, 52, 45),
    ('17_lighthouse', 5, 7, 78, 0),
]

def compact_views(doc):
    # Unreferenced source image views were emptied during bitmap repacking.
    # glTF requires positive view lengths, so remove and remap these entries.
    remap = {}
    views = []
    for i, view in enumerate(doc['bufferViews']):
        if view['byteLength'] > 0:
            remap[i] = len(views)
            views.append(view)
    for accessor in doc.get('accessors', []):
        if 'bufferView' in accessor:
            accessor['bufferView'] = remap[accessor['bufferView']]
    for entry in doc.get('images', []):
        if 'bufferView' in entry:
            entry['bufferView'] = remap[entry['bufferView']]
    doc['bufferViews'] = views

def map_copy(source, target):
    """Only resize embedded bitmap copies; preserve all mesh/material records."""
    raw = source.read_bytes()
    magic, version, length = struct.unpack_from('<III', raw)
    assert magic == 0x46546C67 and version == 2 and length == len(raw)
    jl, jt = struct.unpack_from('<II', raw, 12)
    doc = json.loads(raw[20:20 + jl])
    at = 20 + jl
    bl, bt = struct.unpack_from('<II', raw, at)
    binary = bytearray(raw[at + 8:at + 8 + bl])
    resized = []
    image_limits = {}
    for tex in doc.get('textures', []):
        image_limits[tex['source']] = 2048
    for mat in doc.get('materials', []):
        tex = mat.get('pbrMetallicRoughness', {}).get('baseColorTexture')
        if tex:
            image_limits[doc['textures'][tex['index']]['source']] = 4096
    for index, entry in enumerate(doc.get('images', [])):
        if 'bufferView' not in entry:
            continue
        view = doc['bufferViews'][entry['bufferView']]
        offset = view.get('byteOffset', 0)
        im = Image.open(io.BytesIO(binary[offset:offset + view['byteLength']]))
        old = list(im.size)
        limit = image_limits.get(index, 2048)
        if max(im.size) <= limit:
            continue
        im.thumbnail((limit, limit), Image.Resampling.LANCZOS)
        stream = io.BytesIO()
        # Preserve alpha and linear normal/ORM channels; never JPEG normals.
        im.save(stream, format='PNG', compress_level=3)
        encoded = stream.getvalue()
        binary.extend(b'\0' * ((-len(binary)) % 4))
        entry['bufferView'] = len(doc['bufferViews'])
        entry['mimeType'] = 'image/png'
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(encoded)})
        binary.extend(encoded)
        resized.append({'name': entry.get('name'), 'source': old, 'map': list(im.size)})
    # Remove obsolete image bytes by repacking buffer views without changing
    # accessor references. Shared views remain shared; originals are untouched.
    used_images = {im.get('bufferView') for im in doc.get('images', [])}
    used_accessors = {a['bufferView'] for a in doc.get('accessors', []) if 'bufferView' in a}
    packed = bytearray()
    for i, view in enumerate(doc['bufferViews']):
        if i not in used_images and i not in used_accessors:
            view['byteOffset'] = 0
            view['byteLength'] = 0
            continue
        offset = view.get('byteOffset', 0)
        chunk = binary[offset:offset + view['byteLength']]
        packed.extend(b'\0' * ((-len(packed)) % 4))
        view['byteOffset'] = len(packed)
        packed.extend(chunk)
    doc['buffers'][0]['byteLength'] = len(packed)
    compact_views(doc)
    j = json.dumps(doc, separators=(',', ':')).encode()
    j += b' ' * ((-len(j)) % 4)
    packed.extend(b'\0' * ((-len(packed)) % 4))
    result = struct.pack('<III', magic, version, 12 + 8 + len(j) + 8 + len(packed))
    result += struct.pack('<II', len(j), jt) + j + struct.pack('<II', len(packed), bt) + packed
    target.write_bytes(result)
    return resized

def main():
    terrain = json.loads((ROOT / 'art/maps/archipelago_terrain_v6/manifest.json').read_text())
    queue = json.loads((ROOT / 'art/maps/archipelago_objects_v1/queue.json').read_text(encoding='utf-8'))
    namespace = {'np': np, 'math': math}
    source = (ROOT / 'tools/prepare_archipelago_v5.py').read_text()
    exec('\n\n'.join(ast.get_source_segment(source, n) for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)), namespace)
    samplers = {}
    for island in terrain['islands']:
        v = np.load(ROOT / f"art/maps/archipelago_terrain_v5/{island['id']}.npz")['vertices']
        samplers[island['id']] = LinearNDInterpolator(v[:, :2], v[:, 2])
    placements = []
    errors = []
    for ident, island_no, x, z, yaw in SITES:
        island = terrain['islands'][island_no - 1]
        folder = ROOT / 'art/maps/archipelago_objects_v1' / ident
        stem = ident.split('_', 1)[1]
        spec = next(i for i in queue['items'] if i['id'] == ident)
        verification = json.loads((folder / 'mesh_verification.json').read_text())
        width, depth, height = verification['dimensions_m']
        theta = math.radians(yaw)
        # A conservative rotated whole-model AABB includes eaves and steps.
        xx, zz = np.meshgrid(np.linspace(-width / 2, width / 2, 17), np.linspace(-depth / 2, depth / 2, 17))
        wx = x + xx.ravel() * math.cos(theta) + zz.ravel() * math.sin(theta)
        wz = z - xx.ravel() * math.sin(theta) + zz.ravel() * math.cos(theta)
        h = samplers[island['id']](wx, -wz)
        if not (np.all(np.isfinite(h)) and h.min() > 1.5):
            errors.append((ident, 'ground height', float(h.min())))
        coast = namespace['distance'](wx, -wz, namespace['catmull'](island['outline']))
        if coast.min() <= 4.7:
            errors.append((ident, 'shore clearance', float(coast.min())))
        if 'pond' in island:
            q = namespace['pondq'](wx, -wz, island['pond']).min()
            if q <= 1.25:
                errors.append((ident, 'lake clearance', float(q)))
        level = float(np.median(h))
        placement = {'id': ident, 'name': spec['name'], 'island': island['id'], 'island_index': island_no,
                     'model': f'res://assets/buildings/{stem}.glb', 'position': [x, level, z],
                     'yaw_degrees': yaw, 'scale': 1.0, 'dimensions_m': [width, height, depth],
                     'pad_half_extents': [width / 2 + .12, depth / 2 + .12], 'pad_blend_m': 1.1,
                     'source_ground_range_m': [float(h.min()), float(h.max())],
                     'coast_clearance_m': float(coast.min())}
        placements.append(placement)
        print('PLACEMENT_SITE', ident, 'floor', round(level, 3), 'relief', round(float(h.max()-h.min()), 3), flush=True)
    assert not errors, errors
    previous_path = OUT / 'placements.json'
    previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {'buildings': []}
    old_specs = {p['id']: p for p in previous['buildings']}
    for p in placements:
        stem = p['id'].split('_', 1)[1]
        folder = ROOT / 'art/maps/archipelago_objects_v1' / p['id']
        if '--layout-only' in sys.argv:
            assert (LAB / 'assets/buildings' / (stem + '.glb')).exists()
            p['map_texture_copies'] = old_specs[p['id']]['map_texture_copies']
        else:
            p['map_texture_copies'] = map_copy(folder / (stem + '.glb'), LAB / 'assets/buildings' / (stem + '.glb'))
        print('PLACEMENT_ASSET_READY', p['id'], flush=True)
    manifest = {'version': 1, 'units': 'metres', 'character_height_m': 1.7, 'reference': 'art/maps/archipelago_terrain_v1/map_reference.png',
                'buildings': placements, 'reserved_sites': {'town_green': [-33, 2.7, 37], 'camp_tents_firepit': [50, 1.8, 46]},
                'placement_authorization': 'User: 이제 맵의 각 위치의 알맞는 곳에 배치해주세요',
                'ground_preparation': 'Small level pads under buildings only; original terrain and coastline retained.',
                'source_assets_preserved': True, 'map_texture_max_sizes': {'base_color': 4096, 'normal_orm': 2048}}
    encoded = json.dumps(manifest, ensure_ascii=False, indent=2)
    (LAB / 'building_placements.json').write_text(encoded, encoding='utf-8')
    (OUT / 'placements.json').write_text(encoded, encoding='utf-8')
    print('PLACEMENT_MANIFEST_READY count=', len(placements), flush=True)

if __name__ == '__main__':
    main()
