import bpy,json,numpy as np
from pathlib import Path
R=Path(__file__).resolve().parents[1]
for key in ['haeru','naru']:
 bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/npc_cast_idle_v10'/key/(key+'_rigged_idle.blend')))
 rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH');bpy.context.scene.frame_set(1 if key=='haeru' else 391);bpy.context.view_layer.update()
 for side in ['L','R']:
  for name in ['UpperArm','Forearm','Hand']:
   b=rig.pose.bones[name+'.'+side];print('POSE',key,b.name,list(b.head),list(b.tail),list(b.rotation_quaternion),flush=True)
 image=next(n.image for m in mesh.data.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'normal' not in n.image.name.lower())
 pixels=np.array(image.pixels[:]).reshape(image.size[1],image.size[0],4);uv=mesh.data.uv_layers.active.data;colors={}
 for poly in mesh.data.polygons:
  for i in poly.loop_indices:
   coord=uv[i].uv;rgb=pixels[min(image.size[1]-1,int(coord.y*image.size[1])),min(image.size[0]-1,int(coord.x*image.size[0])),:3];colors[mesh.data.loops[i].vertex_index]=rgb
 bag=[v.co[:] for v in mesh.data.vertices if .57<v.co.z<1.05 and colors[v.index][0]>.10 and colors[v.index][0]<.65 and colors[v.index][0]>colors[v.index][1]*1.18 and colors[v.index][1]>colors[v.index][2]*1.15]
 if bag:print('BAG_CLOUD',key,len(bag),np.min(bag,axis=0),np.max(bag,axis=0),flush=True)
