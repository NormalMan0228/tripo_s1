"""Split a one-material character into the recolourable parts the game tints (avatar_tint.gdshader):
hair, skin, coat, pants, boots, plus detail (left as it is). Each part becomes a copy of the original
material named <part>__<rrggbb>, the hex being the part's median colour (the shader's reference
colour), exactly like the old player models (explorer.glb: hair__183631, coat__a95f0d, ...).

  blender -b --factory-startup -P tools/body_gen/part_split.py -- <in.glb> <out.glb> [report.json]

Every face is first given a body region by its nearest bone (game bone names from
retarget_player.py: Head, Spine02, L_Upperarm, L_Thigh, L_Foot, ...), then the part whose
reference colour is closest among the parts allowed in that region (head: hair/skin, arms:
coat/skin, torso: coat/pants/skin, legs: pants/skin/boots, feet: boots/skin). Reference colours are
medians over typical faces (hands for skin, chest for coat, thighs for pants, feet for boots, crown
for hair). Faces far from every allowed reference become detail (belts, bags, scarves). A few
neighbour-majority passes remove speckle.
"""
import json
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
src, out = a[0], a[1]
rep_path = a[2] if len(a) > 2 else None

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
arm = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE'][0]
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
mesh = max(meshes, key=lambda o: len(o.data.polygons))
mat = mesh.data.materials[0]
img = None
for n in mat.node_tree.nodes:
    if n.type == 'BSDF_PRINCIPLED' and n.inputs['Base Color'].is_linked:
        img = n.inputs['Base Color'].links[0].from_node.image
if img is None:
    img = next(n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
W, H = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)[:, :, :3]
px = np.clip(px, 0, 1) ** (1 / 2.2) if img.colorspace_settings.name == 'Linear' else px

REGION = {}
for b in arm.data.bones:
    n = b.name
    if n in ('Head', 'NeckTwist01') or 'HeadTop' in n:
        REGION[n] = 'head'
    elif any(k in n for k in ('Upperarm', 'Forearm', 'Clavicle')):
        REGION[n] = 'arm'
    elif n.endswith('_Hand') or 'Hand' in n:
        REGION[n] = 'hand'
    elif any(k in n for k in ('Thigh', 'Calf')):
        REGION[n] = 'leg'
    elif any(k in n for k in ('Foot', 'Toe')):
        REGION[n] = 'foot'
    elif n in ('Hip', 'Waist', 'Spine01', 'Spine02'):
        REGION[n] = 'torso'
segs = [(arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local, REGION[b.name], b.name)
        for b in arm.data.bones if b.name in REGION]
A = np.array([s[0] for s in segs]); B = np.array([s[1] for s in segs])

bm = bmesh.new()
bm.from_mesh(mesh.data)
bm.faces.ensure_lookup_table()
uvl = bm.loops.layers.uv.active
mw = mesh.matrix_world
cent = np.array([tuple(mw @ f.calc_center_median()) for f in bm.faces])
cols = np.zeros((len(bm.faces), 3), np.float32)
for i, f in enumerate(bm.faces):
    acc = np.zeros(3, np.float32)
    for lp in f.loops:  # corners plus centre, robust to seams
        u, v = lp[uvl].uv
        acc += px[min(H - 1, max(0, int(v * H))), min(W - 1, max(0, int(u * W)))]
    cols[i] = acc / len(f.loops)
# nearest bone segment per face
AB = B - A
t = np.clip(np.einsum('fsk,sk->fs', cent[:, None, :] - A[None], AB) / np.maximum((AB * AB).sum(1), 1e-9), 0, 1)
P = A[None] + t[..., None] * AB[None]
d = np.linalg.norm(cent[:, None, :] - P, axis=2)
near = d.argmin(1)
region = np.array([segs[k][2] for k in near])
bone = np.array([segs[k][3] for k in near])
z = cent[:, 2]
head_z = min(s[0].z for s in segs if s[3] == 'Head')


def med(mask, k=3):
    """Centre of the largest colour cluster among the masked faces (small k-means), so a scarf or a
    belt on the chest does not become the shirt's colour."""
    c = cols[mask]
    if len(c) <= 20:
        return None
    rng = np.random.default_rng(0)
    cen = c[rng.choice(len(c), k, replace=False)]
    for _ in range(12):
        lab = ((c[:, None, :] - cen[None]) ** 2).sum(2).argmin(1)
        cen = np.array([c[lab == j].mean(0) if (lab == j).any() else cen[j] for j in range(k)])
    big = np.bincount(lab, minlength=k).argmax()
    return np.median(c[lab == big], 0)


def dist(c, ref):
    # colour distance weighted towards chroma so shading does not split a part
    dc = c - ref
    lum = dc @ np.array([0.299, 0.587, 0.114])
    chroma = dc - lum[:, None]
    return np.sqrt((chroma ** 2).sum(1) * 3.0 + lum ** 2)


refs = {'skin': med(region == 'hand', k=2)}
not_skin = dist(cols, refs['skin']) > 0.16
refs['coat'] = med(((region == 'torso') | (region == 'arm')) & not_skin & (z > np.percentile(z[region == 'torso'], 40)))
refs['pants'] = med((region == 'leg') & np.isin(bone, ['L_Thigh', 'R_Thigh']) & not_skin & (z < np.percentile(z[region == 'leg'], 80)))
refs['boots'] = med(region == 'foot')
refs['hair'] = med((region == 'head') & not_skin & (z > head_z + 0.6 * (z.max() - head_z)))
refs = {k: v for k, v in refs.items() if v is not None}
ALLOW = {'head': ['hair', 'skin'], 'arm': ['coat', 'skin', 'hair'], 'hand': ['skin', 'coat'], 'torso': ['coat', 'pants', 'skin', 'hair'],
         'leg': ['pants', 'skin', 'boots', 'coat'], 'foot': ['boots', 'skin', 'pants']}
names = ['hair', 'skin', 'coat', 'pants', 'boots', 'detail']
label = np.full(len(cols), 5)
for r, allowed in ALLOW.items():
    m = region == r
    allowed = [p for p in allowed if p in refs]
    if not m.any() or not allowed:
        continue
    D = np.stack([dist(cols[m], refs[p]) for p in allowed], 1)
    best = D.argmin(1)
    lab = np.array([names.index(allowed[k]) for k in best])
    lab[D.min(1) > 0.30] = 5
    label[m] = lab
# neighbour majority, a few passes
adj = [[e.index for e in f.edges] for f in bm.faces]
edge_faces = [[lf.index for lf in e.link_faces] for e in bm.edges]
for _ in range(3):
    new = label.copy()
    for i in range(len(label)):
        nb = [label[j] for e in adj[i] for j in edge_faces[e] if j != i]
        if nb:
            vals, cnt = np.unique(nb, return_counts=True)
            if cnt.max() >= 2 and vals[cnt.argmax()] != label[i] and cnt.max() > len(nb) / 2:
                new[i] = vals[cnt.argmax()]
    label = new
# materials
used = sorted(set(label.tolist()))
slot = {}
mesh.data.materials.clear()
report = {'faces': len(label), 'parts': {}}
for li in used:
    part = names[li]
    c = np.median(cols[label == li], 0)
    hx = '%02x%02x%02x' % tuple(int(round(float(x) * 255)) for x in np.clip(c, 0, 1))
    m2 = mat.copy()
    m2.name = '%s__%s' % (part, hx)
    mesh.data.materials.append(m2)
    slot[li] = len(mesh.data.materials) - 1
    report['parts'][part] = {'faces': int((label == li).sum()), 'hex': hx}
for i, f in enumerate(bm.faces):
    f.material_index = slot[int(label[i])]
bm.to_mesh(mesh.data)
bm.free()
print('PARTS', json.dumps(report))
if rep_path:
    json.dump(report, open(rep_path, 'w'), indent=1)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=out, use_selection=True, export_animations=True, export_animation_mode='NLA_TRACKS')
print('WROTE', out)
