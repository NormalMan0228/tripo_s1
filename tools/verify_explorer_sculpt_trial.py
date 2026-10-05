"""Independently compare saved Blender geometry, not just operator return codes."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'art/characters/explorer_b_fullbody_v2/05_sculpt_trial'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'02_fitted_before_brush.blend'),load_ui=False,use_scripts=False)
before={o.name:[v.co.copy() for v in o.data.vertices] for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render}
head=bpy.data.objects['Head_and_Neck_P2'];parent=list(range(len(head.data.vertices)))
def find(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
for e in head.data.edges:
 a,b=map(find,e.vertices);parent[a]=b
groups={}
for v in head.data.vertices:groups.setdefault(find(v.index),[]).append(v.index)
largest=max(groups.values(),key=len);small=set(range(len(head.data.vertices)))-set(largest)
bpy.ops.wm.open_mainfile(filepath=str(OUT/'03_sculpt_candidate.blend'),load_ui=False,use_scripts=False)
report={'geometry_vertices_stable':True,'all_coordinates_finite':True,'per_object':{}}
for name,coords in before.items():
 o=bpy.data.objects[name];assert len(coords)==len(o.data.vertices),name
 deltas=[(v.co-co).length for v,co in zip(o.data.vertices,coords)]
 assert all(all(math.isfinite(c) for c in v.co) for v in o.data.vertices)
 report['per_object'][name]={'changed_vertices':sum(d>1e-8 for d in deltas),'max_delta_m':max(deltas,default=0)}
head=bpy.data.objects['Head_and_Neck_P2']
report['head_small_islands_max_delta_m']=max((head.data.vertices[i].co-before[head.name][i]).length for i in small)
assert report['head_small_islands_max_delta_m']<=1e-7
arm=bpy.data.objects['Arm_Hand_PosY_P2'];wrist=Vector((.018,.382,.858));direction=Vector((0,.6,-.8))
digits=[i for i,co in enumerate(before[arm.name]) if (co-wrist).dot(direction)>.04]
report['protected_hand_vertices']=len(digits)
report['hand_beyond_wrist_band_max_delta_m']=max((arm.data.vertices[i].co-before[arm.name][i]).length for i in digits)
assert report['hand_beyond_wrist_band_max_delta_m']<=1e-7
report['exact_y_mirror_parts']=[o.name for o in bpy.context.scene.objects if not o.hide_render and any(m.type=='MIRROR' and tuple(m.use_axis)==(False,True,False) for m in o.modifiers)]
assert 'Arm_Hand_PosY_P2' in report['exact_y_mirror_parts'] and 'Leg_PosY' in report['exact_y_mirror_parts']
report['state']='passed_geometry_protection_checks_not_rig_validation'
(OUT/'geometry-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
