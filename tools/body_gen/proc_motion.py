"""Procedural creature motions (Blender Python only, no paid tools) for a Tripo "Other" auto-rig.

  blender -b --factory-startup -P tools/body_gen/proc_motion.py -- <in.fbx> <out.fbx> <hints.json> <id> [report.json]

Tripo's "Other" rig has generic bone names (tripo::Spine_0, bone_17, ...) and patchy skin weights, so
nothing here relies on names except the per-monster hints (art/characters/body_p2_v1/mon_v3/anim/
proc_motion_hints.json). Species with a motion program: centipede, mimic, basilisk, naga, chimera,
dragon.

1. mesh: optional debris/shell cleanup (hint "cleanup", same options as mesh_cleanup.py / mon_v3/clean);
   new vertices take the nearest old vertex's weights (or "new_vertex_bone");
2. stray weights: a weight is dropped when the vertex lies farther than 0.12 from everything that bone
   (or its parent / children) moves - Tripo leaves e.g. 20-47 % of a chimera goat-head vertex on the
   tail tip, which spikes as soon as the tail swings;
3. rig survey: bone tree + chains found automatically (legs = chains that leave the midline and whose
   skin reaches the floor, head = bone owning the most forward skin, spine = root -> head, tail =
   bone path owning the rearmost skin); written to the report;
4. rig repairs from the hints - the mesh itself never moves (house rule: keep the original mesh):
   add_chain (new bones through points for parts Tripo left on one bone: basilisk / dragon tail, naga
   snake body, dragon wings; vertices re-weighted by projection onto the chain, blended into the
   parent at its base, inner joints optionally re-centred in the skin), mirror_chain (the mimic's
   unrigged middle-right leg gets a mirrored copy of the middle-left chain and weights), split (a new
   bone takes the skin above / below a line: mimic lid, dragon jaw), delete (bones left without skin);
5. six actions proc_idle / proc_walk / proc_run / proc_attack / proc_hurt / proc_death at 30 fps from
   the species' motion program. Poses are armature-space turns per bone (about its head, carried by
   its parents), a whole-body transform, bones held at a world orientation (the naga tail stays flat
   on the floor) and foot targets. Legs are planted by a curl-and-swing solver that keeps each leg's
   own shape (no knee flips; zig-zag hock legs fold the right way) with a soft reach limit; in walk
   and run the planted foot slides back on the floor = the in-place ground speed. Loops use whole
   numbers of cycles, so the last frame equals the first;
6. the deformed mesh is measured every frame: anything under the rest floor lifts the body (smooth
   envelope, the bone that sank is logged), and the death pose is lowered / raised onto the floor
   once it lies down;
7. every bone's channels are keyed and the FBX is saved with all six actions (the .fbm texture folder
   is copied next to it), ready for build_game_monster.py (config: game_build.json "bones" aliases).
"""
import json
import math
import os
import shutil
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
SRC, OUT, HINTS_PATH, MID = argv[:4]
REPORT_PATH = argv[4] if len(argv) > 4 else OUT.rsplit('.', 1)[0] + '_proc.json'
HINTS = json.load(open(HINTS_PATH, encoding='utf-8')).get(MID, {})
FPS = 30
TAU = 2 * math.pi
XA, YA, ZA = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
REPORT = {'id': MID, 'source': SRC, 'fixes': [], 'clips': {}, 'warnings': []}


def log(*a):
    print('[proc]', *a)


# ------------------------------------------------------------------ time helpers
def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def ramp(t, a, b):
    """0 before a, 1 after b, smoothstep in between."""
    if b <= a:
        return 1.0 if t >= a else 0.0
    return smooth((t - a) / (b - a))


def bump(t, a, b, c):
    """0 -> 1 between a and b, back to 0 between b and c."""
    return ramp(t, a, b) - ramp(t, b, c)


def wave(t, period, cycles=1, phase=0.0):
    return math.sin(TAU * cycles * t / period + phase)


def shake(t, a, freq, rate):
    """Decaying oscillation starting at a (0 before)."""
    if t < a:
        return 0.0
    return math.sin(TAU * freq * (t - a)) * math.exp(-rate * (t - a))


# ------------------------------------------------------------------ scene
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC, automatic_bone_orientation=False)
scene = bpy.context.scene
ARM = next(o for o in scene.objects if o.type == 'ARMATURE')
MESHES = [o for o in scene.objects if o.type == 'MESH']
MESH = max(MESHES, key=lambda m: len(m.data.vertices))
for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)
if ARM.animation_data:
    ARM.animation_data.action = None


def mesh_rest_points():
    m = MESH
    co = np.empty(len(m.data.vertices) * 3)
    m.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    mw = np.array(m.matrix_world)
    aw = np.array(ARM.matrix_world.inverted())
    w = co @ mw[:3, :3].T + mw[:3, 3]
    return w @ aw[:3, :3].T + aw[:3, 3]  # armature space


def read_weights():
    names = [g.name for g in MESH.vertex_groups]
    W = np.zeros((len(MESH.data.vertices), len(names)), np.float32)
    for v in MESH.data.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    return names, W


if HINTS.get('cleanup'):
    # same debris / shell cleanup as mon_v3/clean (tools/body_gen/mesh_cleanup.py), before rigging;
    # vertices it adds (a replacement box) take the weights of the nearest old vertex, or one bone
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import mesh_cleanup
    n_before = len(MESH.data.vertices)
    REPORT['cleanup'] = mesh_cleanup.clean_object(MESH, mesh_cleanup.parse(HINTS['cleanup']))
    REPORT['cleanup']['options'] = HINTS['cleanup']
    bare = [v.index for v in MESH.data.vertices if not v.groups]
    if bare:
        to = HINTS.get('new_vertex_bone')
        if to:
            g = MESH.vertex_groups.get(to) or MESH.vertex_groups.new(name=to)
            g.add(bare, 1.0, 'REPLACE')
        else:
            from mathutils.kdtree import KDTree
            done = [v for v in MESH.data.vertices if v.groups]
            kd = KDTree(len(done))
            for k, v in enumerate(done):
                kd.insert(v.co, k)
            kd.balance()
            for i in bare:
                src = done[kd.find(MESH.data.vertices[i].co)[1]]
                for gg in src.groups:
                    MESH.vertex_groups[gg.group].add([i], gg.weight, 'REPLACE')
    REPORT['cleanup']['new_vertices_weighted'] = len(bare)
    print('[proc] cleanup', n_before, '->', len(MESH.data.vertices), 'vertices;', len(bare), 'new ones weighted')

PTS = mesh_rest_points()
FLOOR = float(PTS[:, 2].min())
H = float(PTS[:, 2].max()) - FLOOR
LEN_Y = float(PTS[:, 1].max() - PTS[:, 1].min())
REPORT['rest'] = {'height': round(H, 4), 'floor': round(FLOOR, 4), 'length_y': round(LEN_Y, 4),
                  'bones_in': len(ARM.data.bones), 'vertices': len(PTS)}


def bone_tree():
    out = []

    def walk(b, d):
        h, t = b.head_local, b.tail_local
        out.append('%s%s (%.2f,%.2f,%.2f)->(%.2f,%.2f,%.2f)' % ('  ' * d, b.name, h.x, h.y, h.z, t.x, t.y, t.z))
        for c in b.children:
            walk(c, d + 1)
    for b in ARM.data.bones:
        if b.parent is None:
            walk(b, 0)
    return out


# ------------------------------------------------------------------ rig repairs
def edit_bones():
    bpy.context.view_layer.objects.active = ARM
    ARM.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    return ARM.data.edit_bones


def object_mode():
    bpy.ops.object.mode_set(mode='OBJECT')


def group(name):
    return MESH.vertex_groups.get(name) or MESH.vertex_groups.new(name=name)


def set_weights(idx, wmap_rows):
    """Replace all weights of vertices idx with the given {group name: weight} dicts."""
    gl = list(MESH.vertex_groups)
    for i, row in zip(idx, wmap_rows):
        v = MESH.data.vertices[int(i)]
        for g in list(v.groups):
            gl[g.group].remove([int(i)])
        s = sum(row.values())
        for n, w in row.items():
            if w > 1e-4:
                group(n).add([int(i)], float(w / s), 'REPLACE')
        gl = list(MESH.vertex_groups)


def dominant_mask(spec):
    names, W = read_weights()
    dom = np.array([names[i] if W[j, i] > 0 else '' for j, i in enumerate(W.argmax(1))])
    m = np.ones(len(PTS), bool)
    if spec.get('only_dominant'):
        m &= np.isin(dom, spec['only_dominant'])
    if spec.get('only_dominant_match'):
        m &= np.array([any(k in d for k in spec['only_dominant_match']) for d in dom])
    boxes = ([spec['box']] if spec.get('box') else []) + spec.get('more_boxes', [])
    if boxes:  # inside any of the boxes
        p = PTS
        inside = np.zeros(len(p), bool)
        for (x0, x1), (y0, y1), (z0, z1) in boxes:
            inside |= (p[:, 0] >= x0) & (p[:, 0] <= x1) & (p[:, 1] >= y0) & (p[:, 1] <= y1) & (p[:, 2] >= z0) & (p[:, 2] <= z1)
        m &= inside
    return m


def project_polyline(p, pts):
    """For points p (N,3): nearest segment index and t in [0,1] on the polyline pts (K,3)."""
    best_d = np.full(len(p), 1e9)
    seg = np.zeros(len(p), int)
    tt = np.zeros(len(p))
    for k in range(len(pts) - 1):
        a, b = pts[k], pts[k + 1]
        ab = b - a
        t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
        d = np.linalg.norm(p - (a + t[:, None] * ab), axis=1)
        m = d < best_d
        best_d[m], seg[m], tt[m] = d[m], k, t[m]
    return seg, tt


def fix_add_chain(f):
    pts = np.array(f['points'], float)
    mask = dominant_mask(f)
    idx = np.nonzero(mask)[0]
    if f.get('refine'):  # move inner joints to the centre of the skin around them
        for _ in range(2):
            seg, t = project_polyline(PTS[idx], pts)
            u = seg + t
            new = pts.copy()
            for k in range(1, len(pts) - 1):
                near = np.abs(u - k) < 0.35
                if near.sum() > 12:
                    c = PTS[idx][near].mean(axis=0)
                    new[k] = 0.5 * pts[k] + 0.5 * c
            pts = new
    n = len(pts) - 1
    names = ['%s%d' % (f['prefix'], k) for k in range(n)]
    eb = edit_bones()
    parent = eb[f['parent']]
    prev = parent
    for k, nm in enumerate(names):
        b = eb.new(nm)
        b.head, b.tail = Vector(pts[k]), Vector(pts[k + 1])
        b.roll = 0.0
        b.parent = prev
        b.use_connect = k > 0
        b.use_deform = True
        prev = b
    object_mode()
    seg, t = project_polyline(PTS[idx], pts)
    u = seg + t  # 0..n along the chain
    rows = []
    bp = f.get('blend_parent')
    for uu in u:
        # hat functions centred on segment middles; below the first middle the parent keeps a share
        row = {}
        c = uu - 0.5
        k0 = int(math.floor(c))
        w1 = smooth(c - k0)
        for k, w in ((k0, 1 - w1), (k0 + 1, w1)):
            if w <= 0:
                continue
            if k < 0:
                if bp:
                    row[bp] = row.get(bp, 0) + w
                else:
                    row[names[0]] = row.get(names[0], 0) + w
            else:
                nm = names[min(k, n - 1)]
                row[nm] = row.get(nm, 0) + w
        rows.append(row)
    set_weights(idx, rows)
    REPORT['fixes'].append({'op': 'add_chain', 'bones': names, 'vertices': int(len(idx)),
                            'points': [[round(float(x), 3) for x in p] for p in pts]})
    log('add_chain', names, len(idx), 'vertices')
    return names


def fix_mirror_chain(f):
    src, names = f['src'], f['names']
    eb = edit_bones()
    prev = eb[f['parent']]
    for s, nm in zip(src, names):
        a = eb[s]
        b = eb.new(nm)
        b.head = Vector((-a.head.x, a.head.y, a.head.z))
        b.tail = Vector((-a.tail.x, a.tail.y, a.tail.z))
        b.roll = -a.roll
        b.parent = prev if s == src[0] else eb[names[src.index(a.parent.name)]] if a.parent and a.parent.name in src else prev
        b.use_deform = True
        prev = b
    object_mode()
    gnames, W = read_weights()
    srcset = [gnames.index(s) for s in src if s in gnames]
    dom = W.argmax(1)
    is_src = np.isin(dom, srcset) & (W.max(1) > 0)
    tg = f['target']
    ang = np.degrees(np.arctan2(PTS[:, 1], PTS[:, 0]))
    sign = 1 if tg.get('x_min', 0) > 0 else -1
    xs = sign * PTS[:, 0]
    tmask = ((xs > abs(tg.get('x_min', 0))) | ((xs > tg.get('x_min_inner', 1e9)) & (PTS[:, 2] < tg.get('z_inner', -1e9))))
    if 'angle' in tg:
        a = ang if sign > 0 else np.degrees(np.arctan2(PTS[:, 1], -PTS[:, 0]))
        tmask &= (a >= tg['angle'][0]) & (a <= tg['angle'][1])
    tidx = np.nonzero(tmask)[0]
    sp = PTS[is_src].copy()
    sp[:, 0] *= -1
    sidx = np.nonzero(is_src)[0]
    rows = []
    keep = []
    for i in tidx:
        d = np.linalg.norm(sp - PTS[i], axis=1)
        j = int(d.argmin())
        if d[j] > 0.03:
            continue
        sv = sidx[j]
        row = {}
        for g in np.nonzero(W[sv])[0]:
            gn = gnames[g]
            row[names[src.index(gn)] if gn in src else gn] = float(W[sv, g])
        rows.append(row)
        keep.append(i)
    set_weights(keep, rows)
    REPORT['fixes'].append({'op': 'mirror_chain', 'bones': names, 'vertices': len(keep)})
    log('mirror_chain', names, len(keep), 'vertices')


def fix_split(f):
    eb = edit_bones()
    b = eb.new(f['name'])
    b.head, b.tail = Vector(f['head']), Vector(f['tail'])
    b.roll = 0.0
    b.parent = eb[f['parent']]
    b.use_deform = True
    object_mode()
    mask = dominant_mask(f)
    idx = np.nonzero(mask)[0]
    (y0, z0), (y1, z1) = f['line']
    p = PTS[idx]
    zl = z0 + (p[:, 1] - y0) * (z1 - z0) / (y1 - y0)
    d = p[:, 2] - zl
    if f.get('below'):  # the new bone takes the skin under the line (a lower jaw)
        d = -d
    w = np.clip(0.5 + d / (2 * f.get('soft', 0.01)), 0, 1)
    w = w * w * (3 - 2 * w)
    rows = [{f['name']: float(x), f['flatten_to']: float(1 - x)} for x in w]
    set_weights(idx, rows)
    REPORT['fixes'].append({'op': 'split', 'bone': f['name'], 'vertices': int(len(idx)), 'moving': int((w > 0.5).sum())})
    log('split', f['name'], len(idx), 'vertices,', int((w > 0.5).sum()), 'on the new bone')


def fix_delete(f):
    eb = edit_bones()
    kill = []
    for n in f['bones']:
        b = eb.get(n)
        if not b:
            continue
        kill.append(b)
        if f.get('with_children'):
            kill.extend(b.children_recursive)
    names = sorted({b.name for b in kill})
    for b in {b.name: b for b in kill}.values():
        eb.remove(b)
    object_mode()
    # their skin weights go; a vertex left with nothing takes its nearest remaining deform bone
    gnames, W = read_weights()
    dead = [i for i, g in enumerate(gnames) if g in names]
    lost = []
    for i in range(len(PTS)):
        if W[i, dead].sum() > 0:
            lost.append(i)
    rest_rows = []
    heads = {b.name: (b.head_local + b.tail_local) / 2 for b in ARM.data.bones if b.use_deform}
    for i in lost:
        row = {gnames[g]: float(W[i, g]) for g in np.nonzero(W[i])[0] if g not in dead and gnames[g] in heads}
        if not row:
            p = Vector(PTS[i])
            row = {min(heads, key=lambda n: (heads[n] - p).length): 1.0}
        rest_rows.append(row)
    set_weights(lost, rest_rows)
    for g in list(MESH.vertex_groups):
        if g.name in names:
            MESH.vertex_groups.remove(g)
    REPORT['fixes'].append({'op': 'delete', 'bones': len(names), 'reweighted_vertices': len(lost)})
    log('delete', len(names), 'bones;', len(lost), 'vertices re-weighted')


def strip_stray(limit):
    """Tripo's auto weights leave a few far-away vertices on some bones (the chimera's tail tip
    owns 20 % of a vertex in the lion's mouth, the mimic's front-right foot a bit of its middle-left
    leg): they turn into spikes as soon as that bone moves. A weight is dropped when the vertex is
    farther than `limit` from the bone's family region (the skin dominated by the bone, its parent
    or its children, plus points along the bone itself); the vertex's other weights are
    renormalised."""
    from mathutils.kdtree import KDTree
    gnames, W = read_weights()
    dom = W.argmax(1)
    has = W.max(1) > 0
    bones = ARM.data.bones
    trees = {}
    for gi, g in enumerate(gnames):
        if g not in bones:
            continue
        b = bones[g]
        fam = [g] + ([b.parent.name] if b.parent else []) + [c.name for c in b.children]
        fam_i = [gnames.index(x) for x in fam if x in gnames]
        pts = [PTS[i] for i in np.nonzero(has & np.isin(dom, fam_i))[0]]
        pts += [b.head_local.lerp(b.tail_local, k / 4) for k in range(5)]
        kd = KDTree(len(pts))
        for k, q in enumerate(pts):
            kd.insert(Vector(q), k)
        kd.balance()
        trees[gi] = kd
    fix_idx, rows, dropped = [], [], {}
    for i in range(len(PTS)):
        nz = np.nonzero(W[i])[0]
        if len(nz) < 2:
            continue
        p = Vector(PTS[i])
        keep = {}
        for gi in nz:
            if gi == dom[i]:
                keep[gnames[gi]] = float(W[i, gi])
                continue
            d = trees[gi].find(p)[2] if gi in trees else 0.0
            if d > limit:
                dropped[gnames[gi]] = dropped.get(gnames[gi], 0) + 1
            else:
                keep[gnames[gi]] = float(W[i, gi])
        if len(keep) < len(nz):
            fix_idx.append(i)
            rows.append(keep)
    set_weights(fix_idx, rows)
    REPORT['fixes'].append({'op': 'strip_stray_weights', 'limit': limit, 'vertices': len(fix_idx), 'by_bone': dropped})
    log('strip_stray', len(fix_idx), 'vertices', dropped)


strip_stray(HINTS.get('stray_limit', 0.12))
for f in HINTS.get('fix', []):
    {'add_chain': fix_add_chain, 'mirror_chain': fix_mirror_chain, 'split': fix_split, 'delete': fix_delete}[f['op']](f)


# ------------------------------------------------------------------ rig model (pure mathutils FK)
class Rig:
    def __init__(self):
        bones = ARM.data.bones
        order, seen = [], set()

        def visit(b):
            order.append(b.name)
            seen.add(b.name)
            for c in b.children:
                visit(c)
        for b in bones:
            if b.parent is None:
                visit(b)
        self.order = order
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in bones}
        self.rest = {b.name: b.matrix_local.copy() for b in bones}
        self.rest_q = {n: m.to_quaternion() for n, m in self.rest.items()}
        self.rel = {n: (self.rest[p].inverted() @ self.rest[n]) if p else self.rest[n].copy() for n, p in self.parent.items()}
        self.head = {b.name: b.head_local.copy() for b in bones}
        self.tail = {b.name: b.tail_local.copy() for b in bones}
        self.roots = [n for n in order if self.parent[n] is None]
        self.children = {n: [c.name for c in bones[n].children] for n in order}
        gnames, W = read_weights()
        dom = W.argmax(1)
        has = W.max(1) > 0
        self.region = {}
        for gi, g in enumerate(gnames):
            m = has & (dom == gi)
            if m.sum():
                self.region[g] = PTS[m]

    def __contains__(self, n):
        return n in self.parent

    def fk(self, basis):
        pose = {}
        for n in self.order:
            p = self.parent[n]
            pose[n] = (pose[p] @ self.rel[n] if p else self.rel[n]) @ basis[n]
        return pose

    def fk_from(self, basis, pose, start):
        stack = [start]
        while stack:
            n = stack.pop()
            p = self.parent[n]
            pose[n] = (pose[p] @ self.rel[n] if p else self.rel[n]) @ basis[n]
            stack.extend(self.children[n])


RIG = Rig()


# ------------------------------------------------------------------ automatic chain survey
def survey():
    found = {}
    mid = 0.04 * H
    ground = [n for n, r in RIG.region.items() if len(r) >= 8 and r[:, 2].min() < FLOOR + 0.05 * H and n in RIG]
    chains = {}
    for g in ground:
        if abs(RIG.region[g][:, 0].mean()) < mid:
            continue
        chain = [g]
        b = RIG.parent[g]
        while b and RIG.parent[b] and abs(RIG.head[b].x) > mid:
            chain.insert(0, b)
            b = RIG.parent[b]
        key = chain[0]
        if key not in chains or len(chain) > len(chains[key]):
            chains[key] = chain
    legs = []
    for chain in chains.values():
        end = RIG.region[chain[-1]]
        legs.append({'chain': chain, 'side': 'L' if end[:, 0].mean() > 0 else 'R', 'y': round(float(end[:, 1].mean()), 3)})
    legs.sort(key=lambda l: (l['y'], l['side']))
    found['legs'] = legs
    in_leg = {b for l in legs for b in l['chain']}
    y0 = PTS[:, 1].min()
    front = {n: int((r[:, 1] < y0 + 0.2 * LEN_Y).sum()) for n, r in RIG.region.items() if n in RIG and n not in in_leg}
    head = max(front, key=front.get) if front else None
    found['head'] = head
    path = []
    b = head
    while b:
        path.insert(0, b)
        b = RIG.parent[b]
    found['spine_path'] = path
    y1 = PTS[:, 1].max()
    back = {n: int((r[:, 1] > y1 - 0.15 * LEN_Y).sum()) for n, r in RIG.region.items() if n in RIG and n not in in_leg}
    tail = max(back, key=back.get) if back else None
    tpath = []
    b = tail
    while b and b not in path:
        tpath.insert(0, b)
        b = RIG.parent[b]
    found['tail_path'] = tpath
    return found


SURVEY = survey()
log('bones', len(RIG.order), 'height', round(H, 3))
for l in SURVEY['legs']:
    log('  leg %s y=%+.2f: %s' % (l['side'], l['y'], ' > '.join(c.replace('tripo::', '') for c in l['chain'])))
log('  head', SURVEY['head'], '| spine', [s.replace('tripo::', '') for s in SURVEY['spine_path']], '| tail', SURVEY['tail_path'])
REPORT['survey'] = SURVEY
REPORT['bone_tree'] = bone_tree()


# ------------------------------------------------------------------ legs (FABRIK foot plant)
class Leg:
    """Foot plant for one leg chain without knee flips: the chain keeps its own shape, every inner
    joint bends by the same angle in the rest bend plane (curl) until the hip-to-tip distance fits,
    then the whole leg swings about the hip to point at the target. A 2-bone leg is exact 2-bone IK;
    longer insect / hock legs fold evenly. Solved in the rest frame of the hip's parent, so body
    turns carry over."""

    def __init__(self, name, ik, foot):
        self.name, self.ik, self.foot = name, list(ik), foot
        last = self.ik[-1]
        if foot:
            tip = RIG.head[foot]
        else:  # mesh tip: lowest skin point of the last bone (Tripo bones do not always follow the leg)
            r = RIG.region.get(last)
            low = r[r[:, 2] < r[:, 2].min() + 0.012]
            tip = Vector(low.mean(axis=0))
        self.tip_rest = Vector(tip)
        self.tip_local = RIG.rest[last].inverted() @ self.tip_rest
        J = [RIG.head[b].copy() for b in self.ik] + [self.tip_rest.copy()]
        self.J = J
        self.root = J[0].copy()
        self.lengths = [(J[i + 1] - J[i]).length for i in range(len(J) - 1)]
        self.side = 1 if self.tip_rest.x > 0 else -1
        self.foot_q = RIG.rest_q[foot] if foot else None
        line = (J[-1] - J[0]).normalized()
        best, n = 0.0, None
        for j in J[1:-1]:
            off = (j - J[0]) - line * (j - J[0]).dot(line)
            if off.length > best:
                best, n = off.length, line.cross(off).normalized()
        if n is None or best < 1e-3:
            n = line.cross(ZA).normalized() if abs(line.dot(ZA)) < 0.95 else XA.copy()
        self.n = n
        # bend sign of every inner joint in that plane (hock legs zig-zag: knee and hock fold opposite ways)
        self.sgn = [1.0]
        for j in range(1, len(J) - 1):
            b = (J[j] - J[j - 1]).cross(J[j + 1] - J[j]).dot(n)
            self.sgn.append(-1.0 if b < -1e-6 else 1.0)
        cs = [math.radians(a) for a in range(-150, 151)]
        ds = [(self.curl(c)[-1] - self.root).length for c in cs]
        k_star = int(np.argmax(ds))
        k0 = cs.index(0.0)
        step = 1 if k0 >= k_star else -1
        if k0 == k_star:  # straight at rest: bend the way that lifts the inner joints
            up = [sum(p.z for p in self.curl(math.radians(10 * s))[1:-1]) for s in (1, -1)]
            step = 1 if up[0] >= up[1] else -1
        branch_c, branch_d = [cs[k_star]], [ds[k_star]]
        k = k_star + step
        while 0 <= k < len(cs) and ds[k] < branch_d[-1]:
            branch_c.append(cs[k])
            branch_d.append(ds[k])
            k += step
        self.branch_c, self.branch_d = branch_c[::-1], branch_d[::-1]  # increasing distance
        self.rest_dist = (J[-1] - J[0]).length

    def curl(self, c):
        pts = [p.copy() for p in self.J]
        for j in range(1, len(pts) - 1):
            R = Matrix.Rotation(self.sgn[j] * c, 3, self.n)
            pivot = pts[j]
            for m in range(j + 1, len(pts)):
                pts[m] = pivot + R @ (pts[m] - pivot)
        return pts

    def solve(self, basis, pose, target, w):
        if w <= 0:
            return
        par = RIG.parent[self.ik[0]]
        M = pose[par] @ RIG.rest[par].inverted()  # how the hip's parent moved
        tgt = M.inverted() @ Vector(target)
        D = (tgt - self.root).length
        dmax = self.branch_d[-1]
        ds = 0.9 * dmax  # soft reach: the knee eases to straight instead of snapping
        if D > ds:
            D = ds + (dmax - ds) * (1 - math.exp(-(D - ds) / (dmax - ds)))
        c = float(np.interp(D, self.branch_d, self.branch_c))
        pts = self.curl(c)
        swing = (pts[-1] - self.root).rotation_difference(tgt - self.root)
        for i, b in enumerate(self.ik):
            delta = swing if i == 0 else Quaternion(self.n, self.sgn[i] * c)
            rq = RIG.rest_q[b]
            new = rq.inverted() @ delta @ rq
            old = basis[b].to_quaternion()
            if new.dot(old) < 0:
                new.negate()
            basis[b] = Matrix.LocRotScale(basis[b].translation, old.slerp(new, w) if w < 1 else new, None)
        RIG.fk_from(basis, pose, self.ik[0])
        if self.foot:
            f = self.foot
            base = pose[RIG.parent[f]] @ RIG.rel[f]
            new = base.to_quaternion().inverted() @ self.foot_q  # planted foot stays flat
            old = basis[f].to_quaternion()
            if new.dot(old) < 0:
                new.negate()
            basis[f] = Matrix.LocRotScale(basis[f].translation, old.slerp(new, w) if w < 1 else new, None)
            RIG.fk_from(basis, pose, f)


LEGS = {}
leg_hints = HINTS.get('legs', {})
if isinstance(leg_hints, dict):
    for k, v in leg_hints.items():
        LEGS[k] = Leg(k, v['ik'], v.get('foot'))
REPORT['legs'] = {k: {'ik': l.ik, 'foot': l.foot, 'tip': [round(x, 3) for x in l.tip_rest],
                      'reach': [round(min(l.branch_d), 3), round(l.rest_dist, 3), round(max(l.branch_d), 3)]}
                  for k, l in LEGS.items()}
for k, l in LEGS.items():
    log('  ik leg %s: %s (+%s) reach %.3f..%.3f, rest %.3f' % (k, ' > '.join(b.replace('tripo::', '') for b in l.ik),
                                                       l.foot, min(l.branch_d), max(l.branch_d), l.rest_dist))


# ------------------------------------------------------------------ pose builder
class Pose:
    """One frame: armature-space turns per bone (about its head, carried by its parents), a
    whole-body transform, IK foot targets (offset from the rest tip) and an optional pin."""

    def __init__(self):
        self.q = {}
        self.T = Matrix.Identity(4)
        self.feet = {}
        self.hold = {}  # bone -> armature-space turn from its rest orientation, whatever its parents do

    def rot(self, bone, axis, deg):
        if not bone or bone not in RIG or abs(deg) < 1e-9:
            return
        q = Quaternion(Vector(axis).normalized(), math.radians(deg))
        self.q[bone] = q @ self.q.get(bone, Quaternion())

    # creature-relative names (forward -Y, up +Z, its left +X)
    def pitch(self, bone, deg):  # + = nose up / lean back
        self.rot(bone, XA, -deg)

    def yaw(self, bone, deg):  # + = turn to its left
        self.rot(bone, ZA, deg)

    def roll(self, bone, deg):  # + = top toward its left (lies on its left side at 90)
        self.rot(bone, YA, deg)

    def move(self, x=0.0, y=0.0, z=0.0):
        self.T = Matrix.Translation((x, y, z)) @ self.T

    def turn(self, axis, deg, pivot):
        p = Vector(pivot)
        self.T = Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, Vector(axis)) @ Matrix.Translation(-p) @ self.T

    def body_pitch(self, deg, pivot):
        self.turn(XA, -deg, pivot)

    def body_yaw(self, deg, pivot):
        self.turn(ZA, deg, pivot)

    def body_roll(self, deg, pivot):
        self.turn(YA, deg, pivot)

    def foot(self, leg, x=0.0, y=0.0, z=0.0, w=1.0):
        if leg in LEGS:
            self.feet[leg] = (Vector((x, y, z)), w)


def evaluate(P):
    basis = {}
    for n in RIG.order:
        q = P.q.get(n)
        if q is None:
            basis[n] = Matrix.Identity(4)
        else:
            rq = RIG.rest_q[n]
            basis[n] = (rq.inverted() @ q @ rq).to_matrix().to_4x4()
    for r in RIG.roots:
        basis[r] = RIG.rest[r].inverted() @ P.T @ RIG.rest[r] @ basis[r]
    pose = RIG.fk(basis)
    for b in [n for n in RIG.order if n in P.hold]:
        base = pose[RIG.parent[b]] @ RIG.rel[b]
        q = base.to_quaternion().inverted() @ P.hold[b] @ RIG.rest_q[b]
        basis[b] = Matrix.LocRotScale(basis[b].translation, q, None)
        RIG.fk_from(basis, pose, b)
    for name, (off, w) in P.feet.items():
        LEGS[name].solve(basis, pose, LEGS[name].tip_rest + off, w)
    return basis


# ------------------------------------------------------------------ gait helper
def gait(P, t, period, phases, stride, lift, duty, w=1.0, cycles=1, side_sway=0.0):
    """Planted walk in place: in stance the foot slides back on the floor (stride per stance), in
    swing it lifts and swings forward. phases: leg -> offset in cycles."""
    for leg, off in phases.items():
        u = (cycles * t / period + off) % 1.0
        if u < duty:
            s = u / duty
            y = -stride / 2 + stride * s  # forward is -Y: the planted foot slides toward +Y
            z = 0.0
        else:
            s = (u - duty) / (1 - duty)
            y = stride / 2 - stride * smooth(s)
            z = lift * math.sin(math.pi * s) ** 2  # zero vertical speed at lift-off and touch-down
        x = side_sway * (LEGS[leg].side if leg in LEGS else 1) * (z / lift if lift else 0)
        P.foot(leg, x, y, z, w)


# ================================================================== motion programs
def open_jaw(P, bone, deg):
    """Lower jaw down by deg (its chin goes down = a nose-down turn of the jaw bone)."""
    P.pitch(bone, -deg)


CLIP_LEN = {}


def legs_auto():
    """Survey legs as FK chains (centipede): list of (chain, side, rank 0..1 front->back)."""
    legs = [l for l in SURVEY['legs']]
    ys = sorted({l['y'] for l in legs})
    out = []
    for l in legs:
        rank = ys.index(l['y']) / max(1, len(ys) - 1)
        out.append((l['chain'], 1 if l['side'] == 'L' else -1, rank, l['y']))
    return out


# ---------------------------------------------------------------- centipede (forest, weak)
def centipede(clip, t, P):
    h = HINTS
    front, head, body = h['front'], h['head'], h['body']
    legs = CENT_LEGS
    jaws, ant, arms = h['jaws'], h['antennae'], h['arms']

    def leg_wave(period, swing, lift, waves=1.2, cycles=1, curl=10.0, scale=1.0):
        for chain, side, rank, y in legs:
            ph = TAU * (cycles * t / period) - TAU * waves * rank + (math.pi if side < 0 else 0)
            fwd = math.sin(ph)
            up = max(0.0, math.cos(ph)) ** 0.7
            P.rot(chain[0], ZA, -side * swing * fwd * scale)
            P.rot(chain[0], YA, -side * lift * up * scale)
            if len(chain) > 1:
                P.rot(chain[1], YA, -side * curl * up * scale)

    def jaw_snap(a):
        for j in jaws:
            s = 1 if RIG.head[j].x > 0 else -1
            P.rot(j, ZA, s * a)

    if clip == 'idle':
        T = CLIP_LEN[clip]
        for i, b in enumerate(front[1:]):
            P.yaw(b, 5 * wave(t, T, 1, -0.7 * i))
            P.pitch(b, 2.5 * wave(t, T, 2, -0.5 * i))
        P.yaw(head, 9 * wave(t, T, 1, 1.2))
        P.pitch(head, 5 * wave(t, T, 2, 0.4))
        for i, b in enumerate(body):
            P.yaw(b, 2.5 * wave(t, T, 1, -0.8 * i))
        leg_wave(T, 7, 6, waves=1.0, cycles=2, curl=4)
        jaw_snap(6 * max(0, wave(t, T, 4)) ** 3)
        for k, a in enumerate(ant):
            P.pitch(a, 10 * wave(t, T, 3, k * 1.7))
        for k, a in enumerate(arms):
            s = 1 if RIG.head[a].x > 0 else -1
            P.rot(a, ZA, -s * 10 * wave(t, T, 2, -0.9 * (k // 2) + (math.pi if s < 0 else 0)))
        P.move(z=0.004 * (1 - math.cos(TAU * 2 * t / T)))
    elif clip in ('walk', 'run'):
        T = CLIP_LEN[clip]
        run = clip == 'run'
        cyc = 2
        leg_wave(T, 30 if run else 22, 24 if run else 16, waves=1.4, cycles=cyc, curl=14 if run else 10)
        for i, b in enumerate(body):
            P.yaw(b, (9 if run else 6) * wave(t, T, 1, -1.0 * i))
        P.pitch(front[1], -(14 if run else 6))  # lean the raised front forward to scuttle
        P.pitch(front[2], -(8 if run else 3))
        for i, b in enumerate(front[1:]):
            P.yaw(b, (-4 if run else -3) * wave(t, T, 1, 0.8 - 0.6 * i))
            P.pitch(b, (3 if run else 2) * wave(t, T, 2 * cyc, -0.6 * i))
        P.pitch(head, 4 * wave(t, T, 2 * cyc, 1.0))
        for k, a in enumerate(arms):
            s = 1 if RIG.head[a].x > 0 else -1
            P.rot(a, ZA, -s * 18 * wave(t, T, cyc, -0.9 * (k // 2) + (math.pi if s < 0 else 0)))
        for k, a in enumerate(ant):
            P.pitch(a, -12 + 8 * wave(t, T, 2, k))
        P.move(z=(0.006 if run else 0.004) * (1 - math.cos(TAU * 2 * cyc * t / T)))
    elif clip == 'attack':
        rear = bump(t, 0.0, 0.42, 0.56)
        strike = bump(t, 0.42, 0.56, 1.05)
        P.pitch(front[0], 10 * rear)
        P.pitch(front[1], 18 * rear - 48 * strike)
        P.pitch(front[2], 10 * rear - 30 * strike)
        P.pitch(front[3], 6 * rear - 16 * strike)
        P.pitch(head, 14 * rear - 10 * strike)
        P.yaw(head, 6 * shake(t, 0.56, 6, 7))
        jaw_snap(-28 * ramp(t, 0.1, 0.4) * (1 - ramp(t, 0.5, 0.58)) + 14 * bump(t, 0.5, 0.58, 0.9))
        for k, a in enumerate(arms):
            s = 1 if RIG.head[a].x > 0 else -1
            P.rot(a, ZA, s * 30 * rear - s * 20 * strike)
        for i, b in enumerate(body):
            P.yaw(b, 3 * rear * (1 if i % 2 else -1))
        leg_wave(0.6, 10, 8, waves=1.0, cycles=1, curl=6, scale=ramp(t, 0.0, 0.3) * (1 - ramp(t, 0.9, 1.2)))
        P.move(y=0.03 * rear - 0.05 * strike)
    elif clip == 'hurt':
        hit = bump(t, 0.0, 0.09, 0.55)
        P.pitch(front[0], 14 * hit)
        P.pitch(front[1], 16 * hit)
        P.yaw(front[2], 14 * hit)
        P.pitch(head, 18 * hit)
        P.yaw(head, -10 * hit + 6 * shake(t, 0.08, 7, 8))
        for i, b in enumerate(body):
            P.yaw(b, 9 * hit)  # coil into a C
        for chain, side, rank, y in legs:
            P.rot(chain[0], YA, -side * 18 * hit)
        jaw_snap(-20 * hit)
        P.move(y=0.035 * hit)
    elif clip == 'death':
        # rolls onto its left side; the raised front folds forward and the body curls in a C (all bends
        # in its own side plane, so once it lies on its side they lie flat on the floor)
        spasm = bump(t, 0.0, 0.18, 0.4)
        fall = ramp(t, 0.2, 0.7)
        flip = ramp(t, 0.35, 0.85)
        curl = ramp(t, 0.5, 1.2)
        P.pitch(front[0], 12 * spasm)
        P.pitch(front[1], 10 * spasm - 40 * fall)
        P.pitch(front[2], -15 * fall)
        P.pitch(front[3], -10 * fall)
        P.pitch(head, 20 * spasm - 10 * fall)
        for i, b in enumerate(body):
            P.pitch(b, -6 * curl + 2 * shake(t, 0.9, 5, 4))
        jaw_snap(-25 * spasm + 10 * fall)
        tw = shake(t, 1.1, 6, 3.5)
        tuck = ramp(t, 0.2, 0.45)
        for chain, side, rank, y in legs:
            if side > 0:  # the side it falls on: legs fold up out of the way, flat on the floor afterwards
                P.rot(chain[0], YA, -70 * tuck + 8 * tw * math.sin(rank * 9))
            else:  # the legs left in the air curl over the belly, twitching
                P.rot(chain[0], YA, -55 * curl + 10 * tw * math.sin(rank * 9))
            if len(chain) > 1:
                P.rot(chain[1], YA, side * 40 * curl)
        for a in arms:
            s = 1 if RIG.head[a].x > 0 else -1
            P.rot(a, YA, s * 45 * curl)
        P.body_roll(95 * flip, (0.25, 0.0, 0.0))
        P.move(x=-0.2 * flip)


# ---------------------------------------------------------------- mimic (desert, weak)
def mimic(clip, t, P):
    h = HINTS
    lid = h['lid']
    T = CLIP_LEN[clip]
    tri_a = {'FL': 0.0, 'MR': 0.0, 'BL': 0.0, 'FR': 0.5, 'ML': 0.5, 'BR': 0.5}
    if clip == 'idle':
        breath = wave(t, T, 1, -math.pi / 2)  # starts closed-ish
        P.pitch(lid, 6 + 7 * breath + 1.5 * wave(t, T, 3))
        P.move(z=0.005 * (1 + breath))
        P.body_pitch(1.2 * breath, (0, 0, 0.3))
        shifts = {'FL': 0.25, 'BR': 0.62, 'MR': 1.05, 'BL': 1.4}
        for leg in LEGS:
            z = y = 0.0
            if leg in shifts:
                b = bump(t, shifts[leg], shifts[leg] + 0.12, shifts[leg] + 0.26)
                z = 0.035 * b
                y = -0.015 * b
            P.foot(leg, 0, y, z)
    elif clip in ('walk', 'run'):
        run = clip == 'run'
        cyc = 2 if run else 1
        gait(P, t, T, tri_a, 0.16 if run else 0.11, 0.07 if run else 0.05, 0.45 if run else 0.55, cycles=cyc)
        bob = 0.5 * (1 - math.cos(TAU * 2 * cyc * t / T))
        P.move(z=(0.022 if run else 0.012) * bob)
        P.body_roll((4 if run else 3) * wave(t, T, cyc), (0, 0, 0.25))
        P.body_pitch(-(7 if run else 2) + 2 * wave(t, T, 2 * cyc, 0.6), (0, 0, 0.25))
        P.body_yaw(3 * wave(t, T, cyc, 0.5), (0, 0, 0.25))
        P.pitch(lid, 6 + (10 if run else 6) * bob)
    elif clip == 'attack':
        crouch = bump(t, 0.0, 0.3, 0.45)
        lunge = bump(t, 0.3, 0.46, 1.0)
        P.move(y=0.035 * crouch - 0.12 * lunge, z=-0.03 * crouch + 0.035 * bump(t, 0.3, 0.4, 0.52))
        P.body_pitch(10 * crouch - 12 * lunge, (0, 0, 0.25))
        P.body_yaw(5 * shake(t, 0.5, 7, 6), (0, 0, 0.25))
        opened = ramp(t, 0.05, 0.32) * (1 - ramp(t, 0.42, 0.55))
        P.pitch(lid, 6 + 52 * opened - 12 * bump(t, 0.42, 0.55, 0.8))
        step = ramp(t, 0.3, 0.46) * (1 - ramp(t, 0.72, 1.0))
        lift = bump(t, 0.3, 0.38, 0.46) + bump(t, 0.72, 0.86, 1.0)
        for leg in LEGS:
            k = {'F': 1.0, 'M': 0.75, 'B': 0.5}[leg[0]]
            P.foot(leg, 0, -0.11 * k * step, 0.05 * k * lift)
    elif clip == 'hurt':
        jolt = bump(t, 0.0, 0.08, 0.5)
        P.move(y=0.05 * jolt, z=0.015 * bump(t, 0.0, 0.06, 0.2))
        P.body_pitch(12 * jolt, (0, 0.1, 0.2))
        P.body_roll(4 * shake(t, 0.05, 9, 8), (0, 0, 0.2))
        P.pitch(lid, 6 - 13 * ramp(t, 0.0, 0.06) * (1 - ramp(t, 0.3, 0.55)) + 4 * shake(t, 0.08, 10, 9))
        for leg in LEGS:
            P.foot(leg, 0, 0.03 * jolt * (1 if leg[0] == 'B' else 0.5), 0.0)
    elif clip == 'death':
        shudder = bump(t, 0.0, 0.12, 0.3)
        give = ramp(t, 0.1, 0.45)  # legs give way, the chest drops
        tip = ramp(t, 0.45, 0.95)  # and tips onto its side
        ikw = 1 - ramp(t, 0.08, 0.3)
        P.body_roll(5 * shake(t, 0.0, 8, 6), (0, 0, 0.25))
        P.move(z=-0.13 * give)
        P.body_roll(95 * tip, (0.21, 0.0, 0.04))
        P.move(x=-0.3 * tip)  # roll in place instead of sliding off sideways
        tw = shake(t, 1.05, 5, 3.0)
        for leg, l in LEGS.items():
            P.foot(leg, 0, 0, 0, ikw)
            # splay flat as it drops; the side it falls on folds its legs up and over so they end flat
            # on the ground, the upper legs stick up and curl, twitching
            if l.side > 0:  # folds up ahead of the tip, so it never digs in and ends flat on the floor
                P.rot(l.ik[0], YA, -40 * give - 105 * ramp(t, 0.25, 0.85))
            else:
                P.rot(l.ik[0], YA, 40 * give)
            P.rot(l.ik[1], YA, l.side * (35 * ramp(t, 0.6, 1.2) + 8 * tw) * (0.4 if l.side > 0 else 1))
        P.pitch(lid, 6 + 10 * shudder + 62 * ramp(t, 0.55, 1.1) - 6 * shake(t, 1.1, 3, 4))


def fall_legs(P, t, buckle, rollv, c0, c1, ik_off=(0.55, 0.8)):
    """Quadruped falling onto its left (+X) side: feet stay planted while the body sinks, then the
    legs let go and relax in their own rest direction (body-down = flat along the floor once it lies
    on its side), front legs reaching forward, hind legs back, knees half bent; the upper pair lifts
    a little off the lower pair."""
    ikw = 1 - ramp(t, *ik_off)
    r = ramp(t, c0, c1)
    for leg, l in LEGS.items():
        P.foot(leg, 0.03 * l.side * buckle, 0, 0, ikw)
        front = leg[0] == 'F'
        P.rot(l.ik[0], XA, (-25 if front else 20) * r)
        P.rot(l.ik[0], YA, l.side * 28 * r)  # toward the midline: lower legs lie flat, upper ones droop on them
        for k, b in enumerate(l.ik[1:]):
            P.rot(b, XA, (25 if front else -20) * r)


# ---------------------------------------------------------------- basilisk (desert, mid)
def basilisk(clip, t, P):
    h = HINTS
    sp, neck, head, jaw, tail = h['spine'], h['neck'], h['head'], h['jaw'], h['tail']
    pelvis = Vector(h['pelvis'])
    T = CLIP_LEN[clip]
    diag = {'FL': 0.0, 'HR': 0.0, 'FR': 0.5, 'HL': 0.5}

    def tail_sway(amp, cyc, lag=0.7, base=0.0):
        for i, b in enumerate(tail):
            P.yaw(b, amp * (0.6 + 0.15 * i) * wave(t, T, cyc, -lag * (i + 1) + base))

    if clip == 'idle':
        br = wave(t, T, 2)
        for b in sp:
            P.pitch(b, 0.8 * br)
        P.yaw(neck[0], 14 * wave(t, T, 1))
        P.pitch(neck[0], 4 * wave(t, T, 2, 1.0))
        P.yaw(head, 6 * wave(t, T, 1, -0.6))
        open_jaw(P, jaw, 4 + 4 * max(0.0, wave(t, T, 3)) ** 4)
        tail_sway(5, 1, 0.6)
        P.move(z=0.003 * (1 + br))
        for leg in LEGS:
            P.foot(leg)
    elif clip in ('walk', 'run'):
        run = clip == 'run'
        gait(P, t, T, diag, 0.17 if run else 0.11, 0.06 if run else 0.04, 0.42 if run else 0.62)
        bob = 0.5 * (1 - math.cos(TAU * 2 * t / T))
        P.move(z=(0.018 if run else 0.008) * bob - (0.012 if run else 0.004))
        sw = wave(t, T, 1)
        P.body_roll((3.5 if run else 2.5) * sw, pelvis)
        P.body_yaw((4 if run else 3) * sw, pelvis)
        P.body_pitch(-(4 if run else 0) + 1.5 * wave(t, T, 2, 0.5), pelvis)
        for i, b in enumerate(sp):
            P.yaw(b, -(2.5 if run else 2) * wave(t, T, 1, 0.5 * i))
        P.yaw(neck[0], -(4 if run else 3) * sw)
        P.pitch(neck[0], (2 if run else 1.5) * wave(t, T, 2, 1.2) + (6 if run else 0))
        open_jaw(P, jaw, 8 if run else 3)
        tail_sway(-(9 if run else 7), 1, 0.55)
        for b in tail[:2]:
            P.pitch(b, -(5 if run else 2))  # tail held up a little (pitch + would lower a backward bone)
    elif clip == 'attack':
        back = bump(t, 0.0, 0.38, 0.52)
        lunge = bump(t, 0.38, 0.54, 1.25)
        P.move(y=0.045 * back - 0.11 * lunge, z=-0.012 * back)
        P.body_pitch(6 * back - 9 * lunge, pelvis)
        P.pitch(neck[0], 22 * back - 22 * lunge)
        P.pitch(head, 10 * back - 8 * lunge)
        P.yaw(head, 5 * shake(t, 0.54, 6, 6))
        for b in sp:
            P.pitch(b, 2 * back - 3 * lunge)
        open_jaw(P, jaw, 24 * ramp(t, 0.08, 0.38) * (1 - ramp(t, 0.47, 0.54)) + 2)
        step = ramp(t, 0.32, 0.56) * (1 - ramp(t, 0.8, 1.15))
        lift = bump(t, 0.32, 0.44, 0.56) + bump(t, 0.8, 0.97, 1.15)
        for leg in LEGS:
            k = 1.0 if leg[0] == 'F' else 0.35
            P.foot(leg, 0, -0.08 * k * step, 0.045 * k * lift)
        tail_sway(10 * back - 6 * lunge, 1, 0.5)
        for b in tail:
            P.pitch(b, 3 * lunge)
    elif clip == 'hurt':
        hit = bump(t, 0.0, 0.1, 0.6)
        P.move(x=0.04 * hit, z=0.008 * bump(t, 0.0, 0.06, 0.18))
        P.body_roll(-7 * hit, pelvis)
        for i, b in enumerate(sp):
            P.yaw(b, 6 * hit)
        P.yaw(neck[0], 22 * hit)
        P.pitch(neck[0], 14 * hit)
        open_jaw(P, jaw, 2 + 20 * hit)
        for i, b in enumerate(tail):
            P.yaw(b, -8 * hit + 6 * shake(t, 0.1, 4, 5) * (i + 1) / len(tail))
        for leg in LEGS:
            P.foot(leg)
    elif clip == 'death':
        pain = bump(t, 0.0, 0.25, 0.6)
        buckle = ramp(t, 0.3, 0.75)
        rollv = ramp(t, 0.6, 1.25)
        P.pitch(neck[0], 22 * pain - 10 * ramp(t, 0.9, 1.5))
        open_jaw(P, jaw, 2 + 22 * pain + 14 * ramp(t, 1.0, 1.5))
        P.move(z=-0.11 * buckle)
        P.body_roll(88 * rollv, (0.3, 0.0, 0.0))  # pivot outside the feet: they lift as it rolls
        P.move(x=-0.38 * rollv)
        fall_legs(P, t, buckle, rollv, 0.7, 1.3)
        for i, b in enumerate(tail):  # body-frame pitch = a limp curl along the floor once on its side
            P.pitch(b, -4 * (i + 1) * ramp(t, 0.8, 1.6) - 3 * shake(t, 1.2, 3, 4))
        for b in sp:
            P.pitch(b, -3 * ramp(t, 0.7, 1.4))


# ---------------------------------------------------------------- naga (desert, mid)
def naga(clip, t, P):
    h = HINTS
    snake, bend = h['snake'], h['bend_index']
    sp, neck, head = h['spine'], h['neck'], h['head']
    arms = h['arms']
    T = CLIP_LEN[clip]
    axes = NAGA_AXES
    pivot = RIG.head[snake[bend]]

    def sway(amp, cyc, lag, amp_tail=None, ph=0.0, scale=1.0):
        """Lateral S: the upright part bends sideways about each bone's binormal, the part on the
        floor (held flat from the bend on) winds about the vertical; one travelling wave."""
        at = amp if amp_tail is None else amp_tail
        for i, b in enumerate(snake):
            a = scale * (amp if i < bend else at) * wave(t, T, cyc, -lag * i + ph)
            if i < bend:
                P.rot(b, axes[b], a)
            elif i == bend:
                P.hold[b] = Quaternion(ZA, math.radians(a))
            else:
                P.rot(b, ZA, a)

    def lean(deg):
        """Lean the whole upright part (+ = back) about the bend joint; the tail stays on the floor
        (the bend bone is held)."""
        P.body_pitch(deg, pivot)
        if snake[bend] not in P.hold:
            P.hold[snake[bend]] = Quaternion()

    def arm(side, up=0.0, fwd=0.0, out=0.0, elbow=0.0):
        c, u, f, hd = arms[side]
        s = 1 if side == 'L' else -1
        P.rot(u, YA, -s * up)  # raise sideways
        P.rot(u, XA, -fwd)  # swing forward
        P.rot(u, ZA, s * out)
        P.rot(f, XA, -elbow)

    def claws(amount):
        for side in ('L', 'R'):
            for b in RIG.order:
                if b.startswith(side + '_') and any(k in b for k in h['fingers']) and b[-1] in '123':
                    P.rot(b, XA, amount)

    sway_amp = {'idle': 5, 'walk': 7, 'run': 9, 'attack': 4, 'hurt': 4, 'death': 4}[clip]
    if clip == 'idle':
        sway(sway_amp, 1, 0.9, amp_tail=7)
        for i, b in enumerate(sp):
            P.roll(b, -2.5 * wave(t, T, 1, -0.9 * bend - 0.4 * i))
            P.pitch(b, 1.2 * wave(t, T, 2))
        P.yaw(neck[0], 10 * wave(t, T, 1, 0.8))
        P.pitch(neck[1], 4 * wave(t, T, 2, 0.3))
        P.yaw(head, 6 * wave(t, T, 1, 1.4))
        for side in ('L', 'R'):
            s = 1 if side == 'L' else -1
            arm(side, up=-6 + 3 * wave(t, T, 2, 0.5 * s), fwd=8, elbow=10 + 4 * wave(t, T, 2, 1 + s))
        claws(8 + 6 * wave(t, T, 2))
        lean(1.5 * wave(t, T, 2, 0.5))
    elif clip in ('walk', 'run'):
        run = clip == 'run'
        sway(sway_amp, 1, 0.75, amp_tail=sway_amp * 1.2)
        lean(-(12 if run else 5) + 2 * wave(t, T, 2))
        P.move(z=(0.012 if run else 0.007) * 0.5 * (1 - math.cos(TAU * 2 * t / T)))
        for i, b in enumerate(sp):
            P.roll(b, -(4 if run else 3) * wave(t, T, 1, -0.75 * bend - 0.4 * i))
            P.pitch(b, -(4 if run else 1.5))
        P.pitch(neck[0], (10 if run else 4))
        P.yaw(head, -3 * wave(t, T, 1))
        for side in ('L', 'R'):
            s = 1 if side == 'L' else -1
            sw = wave(t, T, 1, 0 if s > 0 else math.pi)
            if run:
                arm(side, up=-10, fwd=-25 + 25 * sw, elbow=35)
            else:
                arm(side, up=-6, fwd=6 + 14 * sw, elbow=18)
        claws(12)
    elif clip == 'attack':
        sway(sway_amp, 1, 0.9)
        coil = bump(t, 0.0, 0.4, 0.55)
        strike = bump(t, 0.4, 0.58, 1.2)
        lean(16 * coil - 22 * strike)
        P.move(z=0.03 * coil - 0.01 * strike)
        for b in sp:
            P.pitch(b, 6 * coil - 9 * strike)
        P.pitch(neck[0], 10 * coil - 12 * strike)
        P.pitch(head, 6 * coil - 6 * strike)
        for side in ('L', 'R'):  # claws raised high in front, then raked forward and down
            arm(side, up=25 * coil - 5 * strike, fwd=70 * coil + 60 * strike, out=-8 * strike, elbow=75 * coil + 5 * strike)
        claws(-12 * coil + 30 * strike)
    elif clip == 'hurt':
        sway(sway_amp, 1, 0.9)
        hit = bump(t, 0.0, 0.1, 0.6)
        lean(14 * hit)
        P.move(z=0.04 * hit)
        for b in sp:
            P.pitch(b, 8 * hit)
        P.pitch(neck[0], 12 * hit)
        P.pitch(head, 10 * hit)
        P.yaw(head, 8 * shake(t, 0.06, 6, 7))
        for side in ('L', 'R'):
            arm(side, up=14 * hit, fwd=-28 * hit, elbow=35 * hit)
        claws(20 * hit)
    elif clip == 'death':
        recoil = bump(t, 0.0, 0.2, 0.45)
        slump = ramp(t, 0.3, 1.1)
        coilup = ramp(t, 0.5, 1.5)
        damp = 1 - ramp(t, 0.3, 0.9)
        sway(sway_amp, 1, 0.9, scale=damp)
        lean(10 * recoil - 45 * slump)
        P.move(z=0.03 * recoil)
        for i, b in enumerate(snake[1:bend]):
            P.rot(b, XA, 14 * slump)  # the upright part folds forward
        P.roll(snake[0], 22 * slump)
        P.hold[snake[bend]] = Quaternion(ZA, math.radians(-20 * coilup)) @ P.hold.get(snake[bend], Quaternion())
        for i, b in enumerate(snake[bend + 1:]):
            P.rot(b, ZA, -26 * coilup)  # tail curls into a coil on the floor
        for b in sp:
            P.pitch(b, 8 * recoil - 10 * slump)
        P.pitch(neck[0], 15 * recoil - 25 * slump)
        P.roll(head, 20 * slump)
        for side in ('L', 'R'):
            arm(side, up=35 * recoil - 15 * slump, fwd=-10 * recoil + 40 * slump, elbow=30 * recoil + 20 * slump)
        claws(20 * recoil)


# ---------------------------------------------------------------- chimera (desert boss)
def chimera(clip, t, P):
    h = HINTS
    sp, chest, hr = h['spine'], h['chest'], h['heads_root']
    # Tripo hung the front legs on the neck chain (Head_0 > Head_1 > shoulders): heads move from Head_2
    lion, jaw, goats, tail = h['lion'], h['jaw'], h['goats'], h['tail']
    pelvis = Vector(h['pelvis'])
    shoulder = Vector((0, -0.2, 0.36))
    T = CLIP_LEN[clip]

    def tail_wave(amp, cyc, lag=0.55, ph=0.0, lift=0.0):
        for i, b in enumerate(tail):
            P.yaw(b, amp * (0.4 + 0.08 * i) * wave(t, T, cyc, -lag * i + ph))
            P.pitch(b, -lift * (0.5 + 0.05 * i))  # + lift raises the tail

    def goat(side, yaw=0.0, pitch=0.0):
        b = goats[side]
        P.yaw(b, yaw)
        P.pitch(b, pitch)

    if clip == 'idle':
        br = wave(t, T, 2)
        for b in sp:
            P.pitch(b, 0.7 * br)
        P.pitch(chest, 0.8 * br)
        P.yaw(hr, 9 * wave(t, T, 1))
        P.pitch(lion[0], 4 * wave(t, T, 2, 0.7))
        P.yaw(lion[1], 5 * wave(t, T, 1, -0.8))
        open_jaw(P, jaw, 3 + 4 * max(0.0, wave(t, T, 2, 0.4)) ** 3)
        goat('L', yaw=18 * wave(t, T, 1, 1.8), pitch=7 * wave(t, T, 2, 0.2))
        goat('R', yaw=16 * wave(t, T, 1, 3.6), pitch=6 * wave(t, T, 2, 2.4))
        tail_wave(12, 1, 0.5)
        P.move(x=0.004 * wave(t, T, 1), z=0.002 * (1 + br))
        for leg in LEGS:
            P.foot(leg)
    elif clip == 'walk':
        seq = {'HL': 0.0, 'FL': 0.25, 'HR': 0.5, 'FR': 0.75}
        gait(P, t, T, seq, 0.15, 0.05, 0.64)
        P.move(z=0.007 * 0.5 * (1 - math.cos(TAU * 2 * t / T)) - 0.004)
        P.body_roll(2.2 * wave(t, T, 1, 0.8), pelvis)
        P.body_yaw(2.0 * wave(t, T, 1, 0.3), pelvis)
        for i, b in enumerate(sp):
            P.yaw(b, -1.5 * wave(t, T, 1, 0.3 + 0.4 * i))
        P.pitch(hr, 2.5 * wave(t, T, 2, 1.0))
        P.yaw(hr, -2.5 * wave(t, T, 1, 0.3))
        goat('L', yaw=6 * wave(t, T, 1, 2.0))
        goat('R', yaw=6 * wave(t, T, 1, 4.0))
        open_jaw(P, jaw, 4)
        tail_wave(14, 1, 0.5)
    elif clip == 'run':
        bound = {'HL': 0.0, 'HR': 0.09, 'FL': 0.46, 'FR': 0.55}
        gait(P, t, T, bound, 0.2, 0.07, 0.42)
        ph = TAU * t / T
        P.move(z=0.02 * max(0.0, math.sin(ph - 0.6)) ** 1.5 + 0.008 * max(0.0, math.sin(ph + 2.4)) - 0.024)
        P.body_pitch(6 * math.sin(ph - 1.2), pelvis.lerp(shoulder, 0.3))
        for i, b in enumerate(sp):
            P.pitch(b, -1.5 * math.sin(ph - 0.4 - 0.3 * i))  # back flexes and extends (front legs hang off the far end)
        P.pitch(hr, -6 * math.sin(ph - 1.5) - 4)
        open_jaw(P, jaw, 10)
        goat('L', pitch=-6 * math.sin(ph - 1.2), yaw=4)
        goat('R', pitch=-6 * math.sin(ph - 1.0), yaw=-4)
        tail_wave(8, 1, 0.5, lift=4)
        for i, b in enumerate(tail):
            P.pitch(b, 3 * math.sin(ph - 0.6 * i))
    elif clip == 'attack':
        rear = bump(t, 0.0, 0.45, 0.68)
        pounce = bump(t, 0.45, 0.68, 1.35)
        P.body_pitch(30 * rear - 6 * pounce, pelvis)
        P.move(y=0.02 * rear - 0.11 * pounce, z=0.02 * rear + 0.035 * bump(t, 0.5, 0.62, 0.78))  # carried forward, lands on its paws
        front_ik = 1 - ramp(t, 0.04, 0.34) * (1 - ramp(t, 0.56, 0.8))
        for leg in ('FL', 'FR'):
            s = LEGS[leg].side
            l = LEGS[leg]
            raise_ = ramp(t, 0.06, 0.4) * (1 - ramp(t, 0.44, 0.72))
            P.rot(l.ik[0], XA, -55 * raise_ + 6 * bump(t, 0.45, 0.6, 0.8))  # paws rake down
            P.rot(l.ik[1], XA, 70 * raise_)
            P.rot(l.ik[0], ZA, s * 10 * raise_)
            P.foot(leg, 0, -0.14 * ramp(t, 0.5, 0.72) * (1 - ramp(t, 0.85, 1.25)),
                   0.03 * bump(t, 0.5, 0.62, 0.74) + 0.06 * bump(t, 0.85, 1.05, 1.25), front_ik)
        for leg in ('HL', 'HR'):
            P.foot(leg, 0, -0.03 * pounce, 0)
        for b in sp:
            P.pitch(b, 4 * rear - 3 * pounce)
        P.pitch(hr, 10 * rear - 14 * pounce)
        open_jaw(P, jaw, 2 + 22 * ramp(t, 0.1, 0.4) * (1 - ramp(t, 0.6, 0.7)) + 10 * bump(t, 0.7, 0.8, 1.1))
        goat('L', pitch=25 * rear - 15 * pounce, yaw=10 * rear)
        goat('R', pitch=25 * rear - 15 * pounce, yaw=-10 * rear)
        tail_wave(20, 2, 0.5, lift=10 * rear)
    elif clip == 'hurt':
        hit = bump(t, 0.0, 0.1, 0.65)
        P.move(y=0.035 * hit)
        P.body_pitch(5 * hit, pelvis)
        sh = shake(t, 0.05, 4.5, 4)
        P.yaw(hr, 16 * sh)
        P.rot(hr, YA, 6 * sh)
        goat('L', yaw=-22 * shake(t, 0.08, 5, 4), pitch=10 * hit)
        goat('R', yaw=22 * shake(t, 0.1, 5, 4), pitch=10 * hit)
        P.yaw(lion[1], -10 * shake(t, 0.06, 5.5, 4))
        P.pitch(hr, 10 * hit)
        open_jaw(P, jaw, 4 + 22 * hit)
        tail_wave(10, 2, 0.5)
        for leg in LEGS:
            P.foot(leg, 0, 0.02 * hit if leg[0] == 'F' else 0, 0)
    elif clip == 'death':
        roar = bump(t, 0.0, 0.3, 0.6)
        buckle = ramp(t, 0.35, 0.85)
        rollv = ramp(t, 0.7, 1.35)
        P.pitch(hr, 16 * roar - 18 * ramp(t, 0.9, 1.5))
        open_jaw(P, jaw, 2 + 22 * roar + 12 * ramp(t, 1.1, 1.6))
        goat('L', pitch=24 * roar - 30 * ramp(t, 1.0, 1.6), yaw=15 * roar)
        goat('R', pitch=24 * roar - 25 * ramp(t, 1.05, 1.7), yaw=-15 * roar)
        P.move(x=0.01 * shake(t, 0.2, 3, 3), z=-0.16 * buckle)
        P.body_roll(88 * rollv, (0.26, 0.0, 0.0))  # pivot outside the paws
        P.move(x=-0.35 * rollv)
        fall_legs(P, t, buckle, rollv, 0.8, 1.4, ik_off=(0.65, 0.9))
        for i, b in enumerate(tail):
            P.pitch(b, -3 * (i % 3 + 1) * ramp(t, 0.9, 1.7))


# ---------------------------------------------------------------- frost dragon (frost boss, winged biped)
def dragon(clip, t, P):
    h = HINTS
    sp, neck, head, jaw = h['spine'], h['neck'], h['head'], h['jaw']
    arms, tail, wings = h['arms'], h['tail'], h['wings']
    hip = Vector(h['pelvis'])
    T = CLIP_LEN[clip]

    def wing(side, up=0.0, fold=0.0, tip=0.0):
        """up: tip raised (flap up), fold: swept back along the body, tip: outer half folds further."""
        b = wings[side]
        s = 1 if side == 'L' else -1
        P.rot(b[0], YA, -s * up)
        P.rot(b[0], ZA, s * fold)
        P.rot(b[2], ZA, s * tip)

    def arm(side, fwd=0.0, out=0.0, elbow=0.0):
        c, u, f, hd = arms[side]
        s = 1 if side == 'L' else -1
        P.rot(u, XA, -fwd)
        P.rot(u, YA, -s * out)
        P.rot(f, XA, -elbow)

    def tail_sway(amp, cyc, lag=0.45, ph=0.0, lift=0.0):
        for i, b in enumerate(tail):
            P.yaw(b, amp * (0.45 + 0.07 * i) * wave(t, T, cyc, -lag * i + ph))
            if lift:
                P.pitch(b, -lift)  # + lift raises the tail

    if clip == 'idle':
        br = wave(t, T, 2)
        for b in sp:
            P.pitch(b, 1.4 * br)
        P.move(z=0.006 * (1 + br))
        P.pitch(neck[0], 3 * wave(t, T, 2, 0.6))
        P.yaw(neck[1], 9 * wave(t, T, 1))
        P.yaw(head, 4 * wave(t, T, 1, -0.7))
        open_jaw(P, jaw, 2 + 6 * max(0.0, br) ** 2)
        f = 0.5 * (1 + wave(t, T, 1, -math.pi / 2))  # 0 = half folded, 1 = open
        for side in ('L', 'R'):
            wing(side, up=4 + 10 * f, fold=28 * (1 - f) - 4, tip=22 * (1 - f))
            arm(side, fwd=4, elbow=6 + 4 * br)
        tail_sway(6, 1, 0.5)
        for leg in LEGS:
            P.foot(leg)
    elif clip in ('walk', 'run'):
        run = clip == 'run'
        gait(P, t, T, {'L': 0.0, 'R': 0.5}, 0.26 if run else 0.15, 0.09 if run else 0.06, 0.42 if run else 0.62)
        ph = TAU * t / T
        P.move(x=(0.012 if run else 0.022) * math.sin(ph - 0.4),
               z=(0.03 if run else 0.016) * 0.5 * (1 - math.cos(2 * ph)) - (0.03 if run else 0.012))
        P.body_yaw((5 if run else 4) * math.sin(ph), hip)
        P.body_roll((2.5 if run else 3) * math.sin(ph - 0.4), hip)
        P.body_pitch(-(16 if run else 2) + 2 * math.sin(2 * ph), hip)
        for b in sp:
            P.pitch(b, -3 if run else 0)
            P.yaw(b, -1.2 * math.sin(ph))
        P.pitch(neck[0], (12 if run else 1.5) + 2 * math.sin(2 * ph + 1))
        P.yaw(neck[1], -3 * math.sin(ph))
        open_jaw(P, jaw, 10 if run else 2)
        for side in ('L', 'R'):
            s = 1 if side == 'L' else -1
            sw = math.sin(ph + (0 if s > 0 else math.pi))
            if run:
                wing(side, up=12 + 4 * math.sin(2 * ph), fold=36, tip=20)
                arm(side, fwd=28 - 10 * sw, elbow=40)
            else:
                wing(side, up=3 * math.sin(2 * ph), fold=24, tip=20)
                arm(side, fwd=-12 * sw, elbow=10)
        tail_sway(-(7 if run else 9), 1, 0.45, lift=5 if run else 0)
    elif clip == 'attack':
        rear = bump(t, 0.0, 0.5, 0.7)
        thrust = ramp(t, 0.5, 0.7) * (1 - ramp(t, 1.05, 1.45))
        P.body_pitch(14 * rear - 15 * thrust, hip)
        P.move(y=0.03 * rear - 0.05 * thrust)
        for b in sp:
            P.pitch(b, 4 * rear - 4 * thrust)
        P.pitch(neck[0], 12 * rear - 14 * thrust)
        P.pitch(neck[1], 6 * rear - 6 * thrust)
        P.pitch(head, 6 * rear - 2 * thrust)
        P.yaw(head, 5 * math.sin(TAU * 5 * t) * bump(t, 0.7, 0.85, 1.05))
        open_jaw(P, jaw, 2 + 8 * rear + 24 * thrust)
        for side in ('L', 'R'):
            wing(side, up=28 * rear - 18 * thrust, fold=-12 * rear - 14 * thrust, tip=-8 * rear)
            arm(side, fwd=-10 * rear + 32 * thrust, out=22 * rear, elbow=30 * rear + 10 * thrust)
        tail_sway(10, 1, 0.5, lift=6 * rear - 4 * thrust)
        for leg in LEGS:
            P.foot(leg)
    elif clip == 'hurt':
        hit = bump(t, 0.0, 0.1, 0.65)
        P.move(y=0.035 * hit)
        P.body_pitch(8 * hit, hip)
        P.yaw(neck[0], 14 * shake(t, 0.04, 4.5, 4))
        P.yaw(neck[1], 10 * shake(t, 0.06, 4.5, 4))
        P.pitch(neck[0], 10 * hit)
        P.rot(head, YA, 8 * shake(t, 0.05, 4.5, 4))
        open_jaw(P, jaw, 2 + 18 * hit)
        for side in ('L', 'R'):
            wing(side, up=16 * hit, fold=-8 * hit)
            arm(side, fwd=-12 * hit, out=12 * hit, elbow=20 * hit)
        tail_sway(10, 2, 0.5, lift=5 * hit)
        for leg in LEGS:
            P.foot(leg)
    elif clip == 'death':
        roar = bump(t, 0.0, 0.3, 0.6)
        droop = ramp(t, 0.45, 1.0)
        buckle = ramp(t, 0.5, 0.95)
        fall = ramp(t, 0.85, 1.5)
        P.pitch(neck[0], 20 * roar - 22 * ramp(t, 1.2, 1.8))
        P.pitch(neck[1], 8 * roar)
        open_jaw(P, jaw, 2 + 22 * roar + 10 * ramp(t, 1.4, 1.9))
        # the wing it falls on folds back along the body, the other droops over it
        wing('L', up=25 * roar - 25 * droop, fold=-6 * roar + 65 * droop, tip=30 * droop)
        wing('R', up=25 * roar - 40 * droop, fold=-6 * roar + 25 * droop, tip=20 * droop)
        P.move(z=-0.10 * buckle)
        P.body_roll(82 * fall, (0.3, hip.y, 0.0))
        P.move(x=-0.35 * fall)
        ikw = 1 - ramp(t, 0.8, 1.05)
        for leg, l in LEGS.items():
            P.foot(leg, 0.02 * l.side * buckle, 0, 0, ikw)
            P.rot(l.ik[0], XA, -20 * ramp(t, 1.0, 1.6))
            P.rot(l.ik[1], XA, 25 * ramp(t, 1.0, 1.6))
        arm('L', fwd=10 * roar + 60 * fall, out=10 * roar - 10 * fall, elbow=30 * roar + 20 * fall)  # the arm it lands on reaches forward
        arm('R', fwd=10 * roar + 15 * fall, out=10 * roar, elbow=30 * roar + 10 * fall)
        for i, b in enumerate(tail):
            P.yaw(b, 3 * ramp(t, 1.0, 1.8) * (1 if i < 4 else -1))
            P.pitch(b, -5 * ramp(t, 0.9, 1.7))


PROGRAMS = {'centipede': centipede, 'mimic': mimic, 'basilisk': basilisk, 'naga': naga, 'chimera': chimera, 'dragon': dragon}
# clip lengths (seconds) and which ones loop, per species: fast skitter for the small ones, heavy for the big
LENGTHS = {
    'centipede': {'idle': 2.0, 'walk': 0.8, 'run': 0.6, 'attack': 1.2, 'hurt': 0.6, 'death': 1.8},
    'mimic': {'idle': 2.0, 'walk': 0.6, 'run': 0.8, 'attack': 1.1, 'hurt': 0.6, 'death': 1.7},
    'basilisk': {'idle': 3.0, 'walk': 1.2, 'run': 0.7, 'attack': 1.3, 'hurt': 0.65, 'death': 2.0},
    'naga': {'idle': 2.4, 'walk': 1.2, 'run': 0.8, 'attack': 1.2, 'hurt': 0.6, 'death': 2.0},
    'chimera': {'idle': 3.0, 'walk': 1.3, 'run': 0.7, 'attack': 1.4, 'hurt': 0.7, 'death': 2.2},
    'dragon': {'idle': 3.0, 'walk': 1.4, 'run': 0.8, 'attack': 1.5, 'hurt': 0.7, 'death': 2.4},
}
LOOPS = ('idle', 'walk', 'run')
CLIP_LEN.update(LENGTHS[MID])

# species-specific precomputation
if MID == 'centipede':
    CENT_LEGS = [l for l in legs_auto() if l[0][0] not in HINTS.get('arms', [])]
    REPORT['fk_legs'] = [[c[0][0], c[1], round(c[2], 2)] for c in CENT_LEGS]
if MID == 'naga':
    NAGA_AXES = {}
    for b in HINTS['snake']:
        d = (RIG.tail[b] - RIG.head[b]).normalized()
        ax = d.cross(XA)
        NAGA_AXES[b] = ax.normalized() if ax.length > 1e-4 else ZA


# ------------------------------------------------------------------ bake
LOWEST_AT = {}


def lowest(basis):
    for n, pb in ARM.pose.bones.items():
        pb.matrix_basis = basis[n]
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    z = 1e9
    for m in MESHES:
        ev = m.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        mw = np.array(ev.matrix_world)
        zz = co.reshape(-1, 3) @ mw[2, :3] + mw[2, 3]
        k = int(zz.argmin())
        if zz[k] < z:
            z = float(zz[k])
            LOWEST_AT['v'] = (m.name, k)
        ev.to_mesh_clear()
    return z


def dominant_group(obj_name, v):
    gs = bpy.data.objects[obj_name].data.vertices[v].groups
    if not len(gs):
        return None
    g = max(gs, key=lambda g: g.weight)
    return bpy.data.objects[obj_name].vertex_groups[g.group].name


def envelope(x, loop, half=4, sigma=1.5):
    n = len(x)
    pad = half + int(3 * sigma) + 1
    if loop:
        xp = np.concatenate([x[-pad - 1:-1], x, x[1:pad + 1]])
    else:
        xp = np.concatenate([np.full(pad, x[0]), x, np.full(pad, x[-1])])
    env = np.array([xp[max(0, i - half):i + half + 1].max() for i in range(len(xp))])
    k = np.exp(-0.5 * (np.arange(-3 * sigma, 3 * sigma + 1) / sigma) ** 2)
    sm = np.convolve(env, k / k.sum(), mode='same')
    return sm[pad:pad + n]


def lift_root(basis, dz):
    for r in RIG.roots:
        basis[r] = RIG.rest[r].inverted() @ Matrix.Translation((0, 0, dz)) @ RIG.rest[r] @ basis[r]


for pb in ARM.pose.bones:
    pb.rotation_mode = 'QUATERNION'
prog = PROGRAMS[MID]
actions = {}
for clip, seconds in LENGTHS[MID].items():
    loop = clip in LOOPS
    n = int(round(seconds * FPS)) + 1
    frames = []
    for i in range(n):
        t = i / FPS
        if loop and i == n - 1:
            t = 0.0  # the last frame of a loop is its first pose
        P = Pose()
        prog(clip, t, P)
        frames.append(evaluate(P))
    low, low_by = [], []
    for b in frames:
        low.append(lowest(b))
        low_by.append(dominant_group(*LOWEST_AT['v']))
    low = np.array(low)
    if low.min() < FLOOR - 0.01 * H:
        k = int(low.argmin())
        log('  %s sinks %.3f H at frame %d (lowest skin on %s)' % (clip, (FLOOR - low[k]) / H, k, low_by[k]))
    info = {'seconds': round((n - 1) / FPS, 3), 'frames': n, 'loop': loop,
            'lowest_before_fix': round(float(low.min() - FLOOR) / H, 4)}
    pen = np.maximum(0.0, FLOOR - low)  # lift needed so nothing sinks under the floor
    dz = envelope(pen, loop) if pen.max() > 0 else pen
    if clip == 'death':  # once it lies down, rest it on the floor (raise or lower)
        w = np.array([ramp(i / FPS, 0.3 * seconds, 0.55 * seconds) for i in range(n)])
        dz = np.maximum(dz, w * (FLOOR - low))
        k = np.exp(-0.5 * (np.arange(-4, 5) / 1.5) ** 2)
        dz = np.convolve(np.concatenate([np.full(4, dz[0]), dz, np.full(4, dz[-1])]), k / k.sum(), mode='same')[4:-4]
        dz = np.maximum(dz, pen)
    if np.abs(dz).max() > 1e-6:
        for b, d in zip(frames, dz):
            lift_root(b, float(d))
        low = np.array([lowest(b) for b in frames])
    info['root_lift_max_ratio'] = round(float(dz.max()) / H, 4)
    info['root_drop_max_ratio'] = round(float(-min(0.0, dz.min())) / H, 4)
    info['lowest_ratio'] = round(float(low.min() - FLOOR) / H, 4)
    info['lowest_end_ratio'] = round(float(low[-1] - FLOOR) / H, 4)
    # largest turn per frame (pop check, the build warns above 30 degrees)
    big, where = 0.0, None
    for fi, (a, b) in enumerate(zip(frames[:-1], frames[1:])):
        for nme in RIG.order:
            qa, qb = a[nme].to_quaternion(), b[nme].to_quaternion()
            ang = math.degrees(qa.rotation_difference(qb).angle)
            ang = min(ang, 360 - ang)
            if ang > big:
                big, where = ang, [nme, fi]
    info['max_bone_deg_per_frame'] = round(big, 2)
    info['max_bone_turn_at'] = where
    # write keys
    act = bpy.data.actions.new('proc_' + clip)
    act.use_fake_user = True
    if not ARM.animation_data:
        ARM.animation_data_create()
    ARM.animation_data.action = act
    if hasattr(ARM.animation_data, 'action_slot') and ARM.animation_data.action_slot is None and len(act.slots):
        ARM.animation_data.action_slot = act.slots[0]
    fr = np.arange(n, dtype=np.float64)
    for nme in RIG.order:
        locs = np.array([list(b[nme].to_translation()) for b in frames])
        qs = [b[nme].to_quaternion() for b in frames]
        for i in range(1, n):
            if qs[i].dot(qs[i - 1]) < 0:
                qs[i].negate()
        qa = np.array([list(q) for q in qs])
        for path, arr, size in (('location', locs, 3), ('rotation_quaternion', qa, 4), ('scale', np.ones((n, 3)), 3)):
            for k in range(size):
                fc = act.fcurves.new('pose.bones["%s"].%s' % (nme, path), index=k, action_group=nme)
                fc.keyframe_points.add(n)
                fc.keyframe_points.foreach_set('co', np.column_stack([fr, arr[:, k]]).ravel())
                fc.keyframe_points.foreach_set('interpolation', [1] * n)
                fc.update()
    actions[clip] = act
    REPORT['clips'][clip] = info
    log('clip %-6s %.2fs n=%d lowest=%+.4f lift=%.4f drop=%.4f maxdeg=%.1f %s' % (
        clip, info['seconds'], n, info['lowest_ratio'], info['root_lift_max_ratio'], info['root_drop_max_ratio'],
        info['max_bone_deg_per_frame'], where))
    if info['max_bone_deg_per_frame'] > 25:
        REPORT['warnings'].append('%s: %.0f degrees in one frame' % (clip, info['max_bone_deg_per_frame']))
    if info['lowest_ratio'] < -0.01:
        REPORT['warnings'].append('%s: mesh %.3f H under the floor' % (clip, -info['lowest_ratio']))

# ------------------------------------------------------------------ save
for pb in ARM.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
ARM.animation_data.action = actions['idle']
scene.render.fps = FPS
scene.render.fps_base = 1
scene.frame_start = 0
scene.frame_end = int(round(LENGTHS[MID]['idle'] * FPS))
out_dir = os.path.dirname(os.path.abspath(OUT))
os.makedirs(out_dir, exist_ok=True)
src_dir = os.path.dirname(os.path.abspath(SRC))
for d in os.listdir(src_dir):
    if d.lower().endswith('.fbm') and os.path.isdir(os.path.join(src_dir, d)):
        dst = os.path.join(out_dir, d)
        if os.path.abspath(dst) != os.path.abspath(os.path.join(src_dir, d)):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(os.path.join(src_dir, d), dst)
        for img in bpy.data.images:
            if img.filepath and os.path.basename(img.filepath) in os.listdir(os.path.join(src_dir, d)):
                img.filepath = os.path.join(dst, os.path.basename(img.filepath))
bpy.ops.export_scene.fbx(
    filepath=OUT, use_selection=False, object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False,
    bake_anim=True, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
    bake_anim_force_startend_keying=True, bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
    path_mode='RELATIVE', embed_textures=False, armature_nodetype='NULL', use_armature_deform_only=False)
REPORT['bones_out'] = len(ARM.data.bones)
REPORT['actions'] = sorted(a.name for a in actions.values())
REPORT['output'] = OUT
json.dump(REPORT, open(REPORT_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('PROC_OK', MID, json.dumps({k: v for k, v in REPORT.items() if k in ('clips', 'warnings', 'fixes')}, ensure_ascii=False))
