import bpy,json,math,struct
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_expressions_v7';FILE=A/'explorer_b_expressions_v7.blend';bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;head=bpy.data.objects['FACE_skin_eyelids_lashes'];hair=bpy.data.objects['HAIR_sculptural_bob_mesh'];rig=bpy.data.objects['Explorer_B_Rigify_Face_Rig'];checks=[]
def tree(o):
 eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();me.calc_loop_triangles();t=BVHTree.FromPolygons([o.matrix_world@v.co for v in me.vertices],[tuple(t.vertices) for t in me.loop_triangles],all_triangles=True);eo.to_mesh_clear();return t
for f in [1,47,70,100,160,190,220,280,310,340,400,430,460,520,550,580,640,690,720]:
 sc.frame_set(f);bpy.context.view_layer.update();finite=True
 for o in [head,hair,bpy.data.objects['BROW_L'],bpy.data.objects['BROW_R']]:
  eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();finite &= all(math.isfinite(c) for v in me.vertices for c in v.co);eo.to_mesh_clear()
 assert finite
 checks.append({'frame':f,'expression':{p:float(rig.pose.bones['head'][p]) for p in ['happy','concern','determined','surprise']},'mouth_open':float(bpy.data.objects['FACE_CONTROLS']['mouth_open'])})
assert all(v==0 for v in checks[0]['expression'].values());assert checks[0]['expression']==checks[-1]['expression'];assert all(any(0<x['expression'][p]<1 for x in checks) for p in ['happy','concern','determined','surprise'])
sc.frame_set(1);bpy.context.view_layer.update();t=tree(head);hair_inside=[]
for i,v in enumerate(hair.data.vertices):
 p=hair.matrix_world@v.co
 if not (.08<p.x and -.19<p.z<.32 and abs(p.y)<.29):continue
 q,n,_,dist=t.find_nearest(p)
 if q is not None and dist<.04 and q.x>.11 and -.17<q.z<.28 and (p-q).dot(n)<-.0007:hair_inside.append(i)
(A/'hair-residual.json').write_text(json.dumps({'count':len(hair_inside),'vertices':hair_inside}));print('HAIR_REMAINING',len(hair_inside))
bpy.ops.object.select_all(action='DESELECT')
for o in sc.objects:
 if (o.type=='MESH' and not o.hide_render and not o.hide_get() and not o.name.startswith('WGT')) or o==rig:o.select_set(True)
bpy.context.view_layer.objects.active=rig;available=set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys());opts={'filepath':str(A/'explorer_b_expressions_v7.glb'),'export_format':'GLB','use_selection':True,'export_animations':True,'export_morph':True,'export_frame_range':True,'export_force_sampling':True,'export_def_bones':True,'export_animation_mode':'ACTIVE_ACTIONS','export_morph_animation':True,'export_bake_animation':True};bpy.ops.export_scene.gltf(**{k:v for k,v in opts.items() if k in available})
buf=(A/'explorer_b_expressions_v7.glb').read_bytes();n,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+n]);paths={c['target']['path'] for a in g['animations'] for c in a['channels']};assert 'weights' in paths and 'rotation' in paths and g['skins'];assert all('bufferView' in i for i in g['images'])
report={'status':'passed','sampled_frames':checks,'rest_loop_equal':True,'hair_penetration_vertices_remaining':len(hair_inside),'embedded_textures':True,'animated_glb':True,'new_Tripo_credits':0,'full_facial_expression_library':False};(A/'verification.json').write_text(json.dumps(report,indent=2));print('V7_CHECKED',json.dumps({k:v for k,v in report.items() if k!='sampled_frames'}))
