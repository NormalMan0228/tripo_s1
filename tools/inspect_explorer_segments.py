"""Inspect Tripo labels against the animated explorer without changing originals."""
import bpy
import json
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/character-parts-20261003'
out.mkdir(parents=True, exist_ok=True)
source = bpy.data.objects['Explorer_B_Cohesive_Surface']
rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
points = np.array([source.matrix_world @ v.co for v in source.data.vertices])
lo, hi = points.min(axis=0), points.max(axis=0)
reference_center = (lo + hi) / 2
tree = KDTree(len(points))
for i, point in enumerate(points):
    tree.insert(Vector(point), i)
tree.balance()
old_objects = set(bpy.data.objects)
path = root / 'artifacts/detail-map-20261003/tripo/character_detail/body-detailed-segment/model.glb'
bpy.ops.import_scene.gltf(filepath=str(path))
segments = [o for o in bpy.data.objects if o not in old_objects and o.type == 'MESH']
raw = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in segments])
raw_center = (raw.min(axis=0) + raw.max(axis=0)) / 2
scale = (hi[2] - lo[2]) / (raw.max(axis=0)[2] - raw.min(axis=0)[2])
trials = []
for angle in (0, 90, 180, 270):
    rotation = Matrix.Rotation(np.radians(angle), 3, 'Z')
    transformed = [(rotation @ Vector(p - raw_center)) * scale + Vector(reference_center)
                   for p in raw[::12]]
    distances = np.array([tree.find(p)[2] for p in transformed])
    trials.append({'angle': angle, 'mean': float(distances.mean()),
                   'p95': float(np.quantile(distances, .95))})
angle = min(trials, key=lambda t: t['mean'])['angle']
rotation = Matrix.Rotation(np.radians(angle), 3, 'Z')
segments_report = []
for obj in segments:
    pts = np.array([(rotation @ (obj.matrix_world @ v.co - Vector(raw_center))) * scale + Vector(reference_center)
                    for v in obj.data.vertices])
    segments_report.append({'id': int(obj.name.rsplit('_', 1)[1]), 'name': obj.name,
                            'triangles': len(obj.data.polygons),
                            'center': pts.mean(axis=0).round(5).tolist(),
                            'lo': pts.min(axis=0).round(5).tolist(),
                            'hi': pts.max(axis=0).round(5).tolist(),
                            'material': [m.name for m in obj.data.materials if m],
                            'images': [{'name': n.image.name, 'size': list(n.image.size)}
                                       for m in obj.data.materials if m and m.use_nodes
                                       for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]})
report = {'source_bounds': [lo.tolist(), hi.tolist()], 'raw_bounds': [raw.min(axis=0).tolist(), raw.max(axis=0).tolist()],
          'source_center': reference_center.tolist(), 'raw_center': raw_center.tolist(),
          'scale': scale, 'rotation_deg': angle, 'alignment_trials': trials,
          'parts': sorted(segments_report, key=lambda p: p['id'])}
(out / 'segment-inspection.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('ALIGNMENT', json.dumps({k: v for k, v in report.items() if k != 'parts'}), flush=True)
for p in report['parts']:
    print('PART', p['id'], p['triangles'], p['center'], p['lo'], p['hi'], flush=True)
