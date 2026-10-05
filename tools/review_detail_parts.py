"""Inspect separated AI parts and retain editable sources without grafting to the game skin."""
import bpy, math, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/detail-map-20261003/character';OUT.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT/'artifacts/detail-map-20261003/tripo/character_detail'
def clear():
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def bounds(objects):
 pts=[o.matrix_world@Vector(v) for o in objects for v in o.bound_box]
 return Vector(tuple(min(p[i] for p in pts) for i in range(3))),Vector(tuple(max(p[i] for p in pts) for i in range(3)))
def lighting(target,size):
 scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
 world=bpy.data.worlds.new('Pale studio');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.67,.70,.68,1);world.node_tree.nodes['Background'].inputs[1].default_value=.7;scene.world=world
 for pos,energy,scale in [((3,-4,6),700,4),((-4,-1,3),500,3),((2,5,4),800,3)]:
  bpy.ops.object.light_add(type='AREA',location=target+Vector(pos)*size);o=bpy.context.object;o.data.energy=energy*size**2;o.data.shape='DISK';o.data.size=scale*size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
 bpy.ops.object.camera_add(location=target+Vector((3,-4,2.1))*size);cam=bpy.context.object;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=size*1.5;scene.camera=cam
 scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
results={}
for name in ['bob-hair','detailed-left-hand','body-detailed-segment','open-hand-image']:
 clear();bpy.ops.import_scene.gltf(filepath=str(SOURCE/name/'model.glb'));objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];lo,hi=bounds(objects)
 stat={'mesh_parts':len(objects),'vertices':sum(len(o.data.vertices) for o in objects),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects),'bounds':list(hi-lo),'skeletons':sum(o.type=='ARMATURE' for o in bpy.context.scene.objects),'facial_morphs':sum(len(o.data.shape_keys.key_blocks)-1 if o.data.shape_keys else 0 for o in objects),'production_skin_replaced':False}
 # A partition preserves positions; it does not create clean deformation topology.
 if name=='body-detailed-segment':
  stat['part_names']=[o.name for o in objects];stat['assessment']='87 fragments; requires semantic grouping and cap/retopology inspection before modular character use'
  center=(lo+hi)*.5
  for o in objects:
   b0,b1=bounds([o]);offset=(b0+b1)*.5-center;o.location+=offset*.18
 elif name=='detailed-left-hand':stat['assessment']='REJECTED: text-only hand has unnatural finger proportions and palm connection; do not graft to production skin'
 elif name=='open-hand-image':stat['assessment']='image-conditioned open-hand experiment; isolated part, not yet fitted to explorer or animated'
 else:stat['assessment']='standalone reusable hair shell; head fit and underside must be checked before attaching'
 lo,hi=bounds(objects);target=(lo+hi)*.5;size=max(hi-lo)
 lighting(target,size);bpy.context.scene.render.filepath=str(OUT/f'{name}.png')
 bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/source'/f'{name}_20261003.blend'))
 bpy.ops.render.render(write_still=True);results[name]=stat
clear()
try:
 bpy.ops.preferences.addon_enable(module='rigify');bpy.ops.object.armature_human_metarig_add()
 rig=bpy.context.object;names=[b.name for b in rig.data.bones]
 results['rigify']={'available':True,'bones':len(names),'face_bones':[n for n in names if any(s in n.lower() for s in ['face','lip','lid','jaw','brow'])],'finger_bones':[n for n in names if any(s in n for s in ['f_index','f_middle','f_ring','f_pinky','thumb'])],'fit_to_generated_skin':False,'purpose':'editable face/hand skeleton reference, not a fitted finished character'}
 bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/source/explorer_detail_rig_template.blend'))
except Exception as e:results['rigify']={'available':False,'error_type':type(e).__name__}
(OUT/'parts-audit.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print('DETAIL_PARTS_AUDIT',json.dumps(results,ensure_ascii=False))
