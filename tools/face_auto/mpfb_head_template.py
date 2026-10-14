"""Build the universal head template for the face pipeline from MPFB (MakeHuman, CC0 base mesh + targets).

Output: <out>/mpfb_head.blend (object "head" + eyes/teeth/tongue as separate objects) and <out>/mpfb_head.json
  - skin boundary loops: eye openings (L/R), mouth opening, neck cut
  - mirror vertex pairs (template is exactly symmetric)
  - joint centres from MPFB's joint cubes: jaw, eyes, head, neck
  - expression shape keys baked as absolute positions: ARKit face units + visemes (MakeHuman targets)
Run with the face-v3 Blender profile (MPFB installed):
  BLENDER_USER_RESOURCES=.tools/blender-profiles/face-v3 blender -b -P mpfb_head_template.py -- <out_dir>
"""
import bpy, bmesh, sys, os, json
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

OUT = sys.argv[sys.argv.index("--") + 1]
os.makedirs(OUT, exist_ok=True)
from bl_ext.user_default.mpfb.services.humanservice import HumanService
from bl_ext.user_default.mpfb.services.faceservice import FaceService

for o in list(bpy.data.objects): bpy.data.objects.remove(o)
bm_obj = HumanService.create_human(mask_helpers=False, detailed_helpers=True, extra_vertex_groups=True,
                                   feet_on_ground=True, scale=0.1)
FaceService.load_targets(bm_obj, load_microsoft_visemes=True, load_meta_visemes=True, load_arkit_faceunits=True)
me = bm_obj.data; kb = me.shape_keys.key_blocks
expr = [k.name for k in kb[1:] if not k.name.startswith('$md')]
print('EXPR', len(expr), expr[:12])

def evaluated():
    dg = bpy.context.evaluated_depsgraph_get(); ev = bm_obj.evaluated_get(dg)
    m = ev.to_mesh(); P = np.array([tuple(bm_obj.matrix_world @ v.co) for v in m.vertices]); ev.to_mesh_clear(); return P
for k in expr: kb[k].value = 0.0
P0 = evaluated()
PK = {}
for k in expr:
    kb[k].value = 1.0; PK[k] = evaluated(); kb[k].value = 0.0

groups = {g.name: g.index for g in bm_obj.vertex_groups}
def members(name):
    gi = groups[name]; return np.array([v.index for v in me.vertices if any(g.group == gi and g.weight > 0.5 for g in v.groups)])
def centre(name): return P0[members(name)].mean(0)
joints = {n: centre('joint-' + n).tolist() for n in ('jaw', 'head', 'head-2', 'neck', 'l-eye', 'r-eye') if 'joint-' + n in groups}
chin_z = P0[members('body')][:, 2]
body = members('body')
neck_z = joints['neck'][2] - 0.01
head_ids = body[P0[body, 2] > neck_z]
parts = {'eye_L': 'helper-l-eye', 'eye_R': 'helper-r-eye', 'teeth_up': 'helper-upper-teeth', 'teeth_lo': 'helper-lower-teeth',
         'tongue': 'helper-tongue', 'lash_L': 'helper-l-eyelashes-1', 'lash_R': 'helper-r-eyelashes-1'}

def build(name, ids):
    ids = np.array(sorted(set(ids.tolist()))); remap = {int(v): i for i, v in enumerate(ids)}
    faces = [[remap[v] for v in p.vertices] for p in me.polygons if all(v in remap for v in p.vertices)]
    m = bpy.data.meshes.new(name); m.from_pydata(P0[ids].tolist(), [], faces); m.update()
    ob = bpy.data.objects.new(name, m); bpy.context.scene.collection.objects.link(ob)
    ob.shape_key_add(name='Basis')
    for k in expr:
        d = np.abs(PK[k][ids] - P0[ids]).max()
        if d < 1e-6: continue
        sk = ob.shape_key_add(name=k)
        for i, v in enumerate(ids): sk.data[i].co = Vector(PK[k][v])
    for p in m.polygons: p.use_smooth = True
    return ob, ids
head, hid = build('head', head_ids)
part_ids = {}
for nm, g in parts.items():
    if g in groups:
        ob, ids = build(nm, members(g)); part_ids[nm] = ids.tolist()

# topology facts on the head skin
H = np.array([tuple(v.co) for v in head.data.vertices])
b = bmesh.new(); b.from_mesh(head.data)
bnd = [e for e in b.edges if e.is_boundary]
adj = {}
for e in bnd:
    a_, c_ = e.verts[0].index, e.verts[1].index; adj.setdefault(a_, []).append(c_); adj.setdefault(c_, []).append(a_)
loops, seen = [], set()
for s in adj:
    if s in seen: continue
    cyc = [s]; seen.add(s); prev, cur = None, s
    while True:
        nx = [n for n in adj[cur] if n != prev and n not in seen]
        if not nx: break
        prev, cur = cur, nx[0]; cyc.append(cur); seen.add(cur)
    loops.append(cyc)
info = {}
for L in loops:
    c = H[L].mean(0)
    if c[2] < neck_z + 0.03 and len(L) > 30: info['neck'] = L
    elif abs(c[0]) < 0.01: info['mouth'] = L if 'mouth' not in info or len(L) > len(info['mouth']) else info['mouth']
    elif c[0] > 0.01: info['eye_L'] = L
    else: info['eye_R'] = L
print('LOOPS', {k: len(v) for k, v in info.items()}, 'all', [len(L) for L in loops])
kd = KDTree(len(H))
for i, p in enumerate(H): kd.insert(p, i)
kd.balance()
mirror = [kd.find(Vector((-p[0], p[1], p[2])))[1] for p in H]
mirr_err = float(np.max([np.linalg.norm(H[m] * [-1, 1, 1] - H[i]) for i, m in enumerate(mirror)]))
meta = {'loops': info, 'mirror': mirror, 'mirror_max_err_m': mirr_err, 'joints': joints,
        'expr': [k.name for k in head.data.shape_keys.key_blocks[1:]], 'verts': len(H), 'faces': len(head.data.polygons)}
json.dump(meta, open(os.path.join(OUT, 'mpfb_head.json'), 'w'))
bpy.data.objects.remove(bm_obj)
for o in list(bpy.data.objects):
    if o.type == 'ARMATURE': bpy.data.objects.remove(o)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'mpfb_head.blend'))
print('TEMPLATE', meta['verts'], 'verts', meta['faces'], 'faces', len(meta['expr']), 'keys', 'mirror err', mirr_err, 'joints', list(joints))
