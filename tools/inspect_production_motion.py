"""Blender offline motion and mesh audit; writes only to this experiment."""
import bpy, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/production-lab-20261003'
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT/'tripo/motion/preset-original.glb'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
actions=list(bpy.data.actions)
report={'rig_name':rig.name,'rig_transform':[list(row) for row in rig.matrix_world],
 'bones':[{ 'name':b.name,'head':list(b.head_local),'tail':list(b.tail_local),'parent':b.parent.name if b.parent else None} for b in rig.data.bones],
 'meshes':[{'name':o.name,'vertices':len(o.data.vertices),'triangles':sum(len(p.vertices)-2 for p in o.data.polygons),
 'materials':[m.name for m in o.data.materials],'bounds':[list(o.matrix_world@__import__('mathutils').Vector(p)) for p in o.bound_box]} for o in meshes],
 'clips':{}}
scene=bpy.context.scene
for a in actions:
 rig.animation_data.action=a
 if hasattr(a,'slots') and a.slots: rig.animation_data.action_slot=a.slots[0]
 samples=[]
 for f in range(math.ceil(a.frame_range[0]),math.floor(a.frame_range[1])+1):
  scene.frame_set(f); bpy.context.view_layer.update()
  samples.append({n:list(rig.matrix_world@rig.pose.bones[n].head) for n in ['Hip','L_Foot','R_Foot','L_Hand','R_Hand'] if n in rig.pose.bones})
 report['clips'][a.name]={'frame_range':list(a.frame_range),'fps':scene.render.fps,
   'samples':samples, 'rig_object_location':list(rig.location)}
(OUT/'source-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('SOURCE_AUDIT',json.dumps({k:{'range':v['frame_range'],'first':v['samples'][0],'last':v['samples'][-1]} for k,v in report['clips'].items()}))
