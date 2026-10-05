import bpy,json,math,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_hybrid_bust_v2';src=R/'art/characters/explorer_b_hybrid_bust_v1/explorer_b_hybrid_bust_v1.blend'
bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_hybrid_bust_v2.blend'))
head=bpy.data.objects['HEAD_P2_Local_Repair'];ctrl=bpy.data.objects['MOUTH_INSPECTION_control'];sc=bpy.context.scene
tests=[]
for value in [0,.25,.5,.75,1,0]:
 ctrl['open']=value;ctrl.update_tag();sc.frame_set(sc.frame_current+1);bpy.context.view_layer.update()
 ev=head.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();assert all(math.isfinite(c) for v in m.vertices for c in v.co);ev.to_mesh_clear()
 assert abs(head.data.shape_keys.key_blocks['Mouth_Open_Inspection'].value-value)<.001
 tests.append(value)
for name in ['LASH_UPPER_Rooted','LASH_LOWER_Rooted']:
 o=bpy.data.objects[name];uvs=[tuple(d.uv) for d in o.data.uv_layers['HairAtlas'].data];assert all(0<=x<=1 and 0<=y<=1 for x,y in uvs);assert len(set(uvs))>60
 assert o.modifiers.get('Mirror_other_eye')
for name in ['ORAL_CAVITY_mucosa','UPPER_GUM','LOWER_GUM','UPPER_TEETH_10','LOWER_TEETH_10','TONGUE']:assert bpy.data.objects.get(name)
assert all(i.packed_file for i in bpy.data.images if i.source=='FILE')
ctrl['open']=0.;ctrl.update_tag();sc.frame_set(1);bpy.context.view_layer.update()
report={'reopened':True,'mouth_inspection_samples':tests,'finite_coordinates':True,'UV_atlas_coordinates_checked':True,'texture_files_packed':True,'neutral_closed_control':float(ctrl['open']),'source_v1_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'head_vertices':len(head.data.vertices),'head_faces':len(head.data.polygons),'api_credits_spent':0,'full_face_rig':False,'limitations':['Inspection mouth morph is not production facial animation.','Generated topology and preview projection require final retopology and texturing.']}
(O/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
