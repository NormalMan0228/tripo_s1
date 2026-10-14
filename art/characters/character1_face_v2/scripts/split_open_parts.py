"""Split the open-mouth P2 head into parts by connected components + position.
Body / Tongue / TeethUpper / TeethLower (+ Eye.L/R if they are separate components).
Writes open/parts.blend and open/parts.json.  Usage: blender --background open/candidates.blend --python split_open_parts.py -- <out_dir>
"""
import bpy, bmesh, sys, os, json
import numpy as np
out = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
src = next(o for o in bpy.data.objects if o.type == 'MESH')
bpy.context.view_layer.objects.active = src; src.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.separate(type='LOOSE'); bpy.ops.object.mode_set(mode='OBJECT')
parts = sorted([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: -len(o.data.vertices))
body = parts[0]
def cen(o): return np.array([v.co[:] for v in o.data.vertices]).mean(0)
def sphere_res(o):
    P = np.array([v.co[:] for v in o.data.vertices]); A = np.c_[2 * P, np.ones(len(P))]; b = (P ** 2).sum(1)
    s = np.linalg.lstsq(A, b, rcond=None)[0]; c = s[:3]; r = np.sqrt(s[3] + c @ c)
    return float(np.abs(np.linalg.norm(P - c, axis=1) - r).max() / r), c, float(r)
info = {"Body": len(body.data.vertices)}
rest = parts[1:]
eyes = [o for o in rest if len(o.data.vertices) > 300 and sphere_res(o)[0] < 0.08 and cen(o)[2] > 0.55]
tongue = max([o for o in rest if o not in eyes], key=lambda o: len(o.data.vertices))
teeth = [o for o in rest if o not in eyes and o is not tongue]
mz = cen(tongue)[2] + 0.03 if teeth else 0
# split teeth by z relative to the gap between the upper row and lower row (largest z gap)
tz = sorted(cen(o)[2] for o in teeth)
gaps = [(tz[i + 1] - tz[i], (tz[i + 1] + tz[i]) / 2) for i in range(len(tz) - 1)]
zsplit = max(gaps)[1] if gaps else mz
up = [o for o in teeth if cen(o)[2] > zsplit]; lo = [o for o in teeth if cen(o)[2] <= zsplit]
def join(objs, name):
    if not objs: return None
    for o in bpy.data.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1: bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active; o.name = name; o.data.name = name
    return o
body.name = "Body"; body.data.name = "Body"
tongue.name = "Tongue"; tongue.data.name = "Tongue"
join(up, "TeethUpper"); join(lo, "TeethLower")
for e in eyes:
    nm = "Eye.L" if cen(e)[0] > 0 else "Eye.R"; e.name = nm; e.data.name = nm
info.update(Tongue=len(tongue.data.vertices), TeethUpper_pieces=len(up), TeethLower_pieces=len(lo), Eyes=[e.name for e in eyes], zsplit=zsplit)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "parts.blend"))
json.dump(info, open(os.path.join(out, "parts.json"), "w"), indent=1)
print("SPLIT", json.dumps(info))
