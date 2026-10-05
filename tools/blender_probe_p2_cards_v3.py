import bpy,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_p2_rest_refined_v3'
bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_P2_rest_refined_v3.blend'))
sc=bpy.context.scene;head=bpy.data.objects['HEAD_relaxed_smile_rest'];ctrl=bpy.data.objects['FACE_CONTROLS'];assert ctrl['mouth_open']==0

for name in ['BROW_L','LASH_upper_L']:
 o=bpy.data.objects[name]
 print(name, 'UV', [tuple(u.uv) for u in o.data.uv_layers.active.data][:10])
 print('COLOR', [tuple(u.color) for u in o.data.color_attributes['EdgeFade'].data][:5])
 print('MAT',o.data.materials[0].name)
 for n in o.data.materials[0].node_tree.nodes:
  print(n.name,n.type, n.image.name if n.type=='TEX_IMAGE' else '')
