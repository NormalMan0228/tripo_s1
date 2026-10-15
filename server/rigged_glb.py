"""Bounded skin/animation validation and deterministic merging for approved crafts."""
import copy
import json
import math
import struct

from .provider import ProviderError, validate_glb

MAX_BONES = 128
MAX_CLIPS = 8
MAX_CHANNELS = 512
MAX_SECONDS = 60


def reject(code='invalid_model'):
    raise ProviderError(code)


def reference(items, index):
    if type(index) is not int or not 0 <= index < len(items):
        reject()
    return items[index]


def unpack(blob):
    # Callers validate the GLB envelope before using this helper on external bytes.
    chunks, offset = {}, 12
    while offset < len(blob):
        size, kind = struct.unpack_from('<II', blob, offset)
        offset += 8
        chunks[kind] = blob[offset:offset + size]
        offset += size
    doc = json.loads(chunks[0x4E4F534A])
    return doc, chunks[0x004E4942][:doc['buffers'][0]['byteLength']]


def pack(doc, binary):
    doc = copy.deepcopy(doc)
    doc['buffers'][0]['byteLength'] = len(binary)
    data = json.dumps(doc, separators=(',', ':'), ensure_ascii=True).encode()
    data += b' ' * (-len(data) % 4)
    binary += b'\0' * (-len(binary) % 4)
    return (struct.pack('<III', 0x46546C67, 2, 28 + len(data) + len(binary))
            + struct.pack('<II', len(data), 0x4E4F534A) + data
            + struct.pack('<II', len(binary), 0x004E4942) + binary)


def values(doc, binary, index):
    a = reference(doc['accessors'], index)
    view = reference(doc['bufferViews'], a['bufferView'])
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
    fmt = '<' + {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}[a['componentType']] * width
    stride = view.get('byteStride', struct.calcsize(fmt))
    start = view.get('byteOffset', 0) + a.get('byteOffset', 0)
    return [struct.unpack_from(fmt, binary, start + i * stride) for i in range(a['count'])]


def validate_rig(doc, binary, stats=None):
    """Called only after common GLB bounds, finite data, geometry and graph checks."""
    skins, animations, nodes = doc.get('skins'), doc.get('animations'), doc['nodes']
    if not isinstance(skins, list) or len(skins) != 1:
        reject()
    if not isinstance(animations, list) or not 1 <= len(animations) <= MAX_CLIPS:
        reject()
    skin = skins[0]
    joints = skin['joints']
    if not isinstance(joints, list) or not 1 <= len(joints) <= MAX_BONES:
        reject()
    for joint in joints:
        reference(nodes, joint)
    if len(set(joints)) != len(joints):
        reject()
    if 'skeleton' in skin:
        reference(nodes, skin['skeleton'])
    ibm = reference(doc['accessors'], skin['inverseBindMatrices'])
    if (ibm['type'], ibm['componentType'], ibm['count']) != ('MAT4', 5126, len(joints)) or ibm.get('normalized'):
        reject()
    weighted = set()
    skinned = False
    for node in nodes:
        if 'skin' not in node:
            if 'mesh' in node and any('JOINTS_0' in p['attributes'] or 'WEIGHTS_0' in p['attributes'] for p in doc['meshes'][node['mesh']]['primitives']):
                reject()
            continue
        reference(skins, node['skin'])
        mesh = reference(doc['meshes'], node['mesh'])
        skinned = True
        for primitive in mesh['primitives']:
            attrs = primitive['attributes']
            ja, wa = (reference(doc['accessors'], attrs[key]) for key in ('JOINTS_0', 'WEIGHTS_0'))
            if ja['componentType'] not in (5121, 5123) or ja.get('normalized'):
                reject()
            if wa['componentType'] not in (5121, 5123, 5126):
                reject()
            if wa['componentType'] != 5126 and wa.get('normalized') is not True:
                reject()
            divisor = {5121: 255, 5123: 65535, 5126: 1}[wa['componentType']]
            for js, ws in zip(values(doc, binary, attrs['JOINTS_0']), values(doc, binary, attrs['WEIGHTS_0'])):
                if any(j >= len(joints) for j in js) or any(w < 0 or w > divisor for w in ws) or abs(sum(ws) / divisor - 1) > .02:
                    reject()
                weighted.update(joints[j] for j, w in zip(js, ws) if w > 0)
    if not skinned or not weighted:
        reject()
    # Only animation of a weighted joint or its ancestor is evidence of mesh movement.
    parents = {child: i for i, n in enumerate(nodes) for child in n.get('children', [])}
    affected = set(weighted)
    for joint in weighted:
        while joint in parents:
            joint = parents[joint]
            affected.add(joint)
    reachable = set()
    def visit(index):
        reachable.add(index)
        for child in nodes[index].get('children', []):
            visit(child)
    scene = reference(doc['scenes'], doc.get('scene', 0))
    for root in scene['nodes']:
        visit(root)
    if not weighted <= reachable or not any('skin' in nodes[i] for i in reachable):
        reject()
    names, durations, moving_channels = [], {}, {}
    channels_total = 0
    for animation in animations:
        name = animation.get('name')
        if not isinstance(name, str) or not name.strip() or len(name) > 64 or name in names:
            reject()
        names.append(name)
        channels, samplers = animation['channels'], animation['samplers']
        if not isinstance(channels, list) or not isinstance(samplers, list) or not channels or not 1 <= len(samplers) <= MAX_CHANNELS:
            reject()
        channels_total += len(channels)
        if channels_total > MAX_CHANNELS:
            reject()
        moving, duration, targets = 0, 0, set()
        for channel in channels:
            sampler = reference(samplers, channel['sampler'])
            if sampler.get('interpolation', 'LINEAR') not in ('LINEAR', 'STEP'):
                reject()
            target = channel['target']; node = reference(nodes, target['node'])
            path = target['path']
            if path not in ('translation', 'rotation', 'scale') or 'matrix' in node:
                reject()
            pair = (target['node'], path)
            if pair in targets:
                reject()
            targets.add(pair)
            inp, out = (reference(doc['accessors'], sampler[key]) for key in ('input', 'output'))
            if (inp['type'], inp['componentType']) != ('SCALAR', 5126) or inp.get('normalized') or out.get('normalized'):
                reject()
            if out['type'] != ('VEC4' if path == 'rotation' else 'VEC3') or out['componentType'] != 5126 or out['count'] != inp['count']:
                reject()
            times = [v[0] for v in values(doc, binary, sampler['input'])]
            if not 2 <= len(times) <= 18000 or times[0] < 0 or times[-1] > MAX_SECONDS or any(a >= b for a, b in zip(times, times[1:])):
                reject()
            output = values(doc, binary, sampler['output'])
            if path == 'rotation':
                norms = [math.sqrt(sum(v * v for v in row)) for row in output]
                if any(n < .5 or n > 1.5 for n in norms):
                    reject()
                base = [v / norms[0] for v in output[0]]
                changed = any(2 * math.acos(min(1, abs(sum(a * b / norm for a, b in zip(base, row))))) > .02 for row, norm in zip(output[1:], norms[1:]))
            else:
                if path == 'scale' and any(v < .01 or v > 100 for row in output for v in row):
                    reject()
                changed = any(max(abs(a - b) for a, b in zip(output[0], row)) > .001 for row in output[1:])
            if changed and target['node'] in affected:
                moving += 1
            duration = max(duration, times[-1])
        if not moving:
            reject('animation_static')
        durations[name], moving_channels[name] = duration, moving
    if stats is not None:
        stats.update(bones=len(joints), clips=names, seconds=durations, moving_channels=moving_channels)


def validate_rigged_glb(blob, allow_textures=False, stats=None):
    return validate_glb(blob, allow_textures=allow_textures, stats=stats, allow_rigged=True)


def merge_clips(clips, allow_textures=False):
    """Merge one verified GLB per named clip; require identical named rest skeletons."""
    base, binary = None, b''
    for name, blob in clips.items():
        validate_rigged_glb(blob, allow_textures=allow_textures)
        doc, data = unpack(blob)
        if len(doc['animations']) != 1:
            reject('animation_clip_mismatch')
        node_names = [n.get('name') for n in doc['nodes']]
        if any(not isinstance(n, str) or not n for n in node_names) or len(set(node_names)) != len(node_names):
            reject('animation_skeleton_mismatch')
        def skeleton(d, raw):
            ns = d['nodes']; names = [n['name'] for n in ns]
            rest = {n['name']: {k: v for k, v in n.items() if k not in ('mesh', 'skin', 'children')} for n in ns}
            hierarchy = {n['name']: sorted(names[c] for c in n.get('children', [])) for n in ns}
            skin = d['skins'][0]
            binds = dict(zip((names[j] for j in skin['joints']), values(d, raw, skin['inverseBindMatrices'])))
            return rest, hierarchy, binds
        if base is None:
            base, binary = copy.deepcopy(doc), data
            base['animations'][0]['name'] = name
            continue
        if skeleton(base, binary) != skeleton(doc, data):
            reject('animation_skeleton_mismatch')
        mapping = {i: next(j for j, n in enumerate(base['nodes']) if n['name'] == v) for i, v in enumerate(node_names)}
        binary += b'\0' * (-len(binary) % 4)
        offset, views, accessors = len(binary), len(base['bufferViews']), len(base['accessors'])
        binary += data
        for view in doc['bufferViews']:
            view['byteOffset'] = view.get('byteOffset', 0) + offset
        for accessor in doc['accessors']:
            accessor['bufferView'] += views
        animation = doc['animations'][0]; animation['name'] = name
        for sampler in animation['samplers']:
            sampler['input'] += accessors; sampler['output'] += accessors
        for channel in animation['channels']:
            channel['target']['node'] = mapping[channel['target']['node']]
        base['bufferViews'].extend(doc['bufferViews']); base['accessors'].extend(doc['accessors'])
        base['animations'].append(animation)
    if base is None:
        reject('animation_clip_mismatch')
    blob = pack(base, binary)
    validate_rigged_glb(blob, allow_textures=allow_textures)
    return blob


def fixture_rigged_glb(clips=('idle',)):
    """Small skinned fixture with real rotating, weighted bones (no external tools)."""
    from .asset_assembly import fixture_glb
    doc, raw = unpack(fixture_glb('box'))
    data = bytearray(raw)
    def add(rows, kind, component=5126):
        data.extend(b'\0' * (-len(data) % 4))
        offset = len(data)
        fmt = '<' + ('f' if component == 5126 else 'B') * len(rows[0])
        for row in rows:
            data.extend(struct.pack(fmt, *row))
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(data) - offset})
        doc['accessors'].append({'bufferView': len(doc['bufferViews']) - 1, 'componentType': component, 'count': len(rows), 'type': kind})
        return len(doc['accessors']) - 1
    doc['nodes'] = [{'name': 'Body', 'mesh': 0, 'skin': 0}, {'name': 'tripo::Hips', 'children': [2]}, {'name': 'tripo::Spine'}]
    doc['scenes'] = [{'nodes': [0, 1]}]; doc['scene'] = 0
    identity = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    doc['skins'] = [{'joints': [1, 2], 'skeleton': 1, 'inverseBindMatrices': add([identity, identity], 'MAT4')}]
    for p in doc['meshes'][0]['primitives']:
        count = doc['accessors'][p['attributes']['POSITION']]['count']
        p['attributes']['JOINTS_0'] = add([(0, 1, 0, 0)] * count, 'VEC4', 5121)
        p['attributes']['WEIGHTS_0'] = add([(.5, .5, 0, 0)] * count, 'VEC4')
    doc['animations'] = []
    for name in clips:
        inp = add([(0,), (.5,), (1,)], 'SCALAR')
        out = add([(0, 0, 0, 1), (0, 0, math.sin(.2), math.cos(.2)), (0, 0, 0, 1)], 'VEC4')
        doc['animations'].append({'name': name, 'samplers': [{'input': inp, 'output': out}],
                                  'channels': [{'sampler': 0, 'target': {'node': 2, 'path': 'rotation'}}]})
    return pack(doc, bytes(data))
