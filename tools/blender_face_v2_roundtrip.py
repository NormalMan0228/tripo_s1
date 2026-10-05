import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'art/characters/explorer_b_face_refined_v2'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(OUT/'explorer_b_face_refined_v2.glb'))
scene=bpy.context.scene
report={'imported_glb':True,'poses':{}}
for frame,label in [(1,'neutral'),(19,'blink'),(84,'jaw'),(144,'loop_end')]:
    scene.frame_set(frame);bpy.context.view_layer.update()
    report['poses'][label]={o.name:{k.name:round(float(k.value),5) for k in o.data.shape_keys.key_blocks if k.name!='Basis'} for o in scene.objects if o.type=='MESH' and o.data.shape_keys}
head=bpy.data.objects.get('Face_Skin');assert head is not None
assert report['poses']['blink']['Face_Skin']['Blink_L']>.99
assert report['poses']['blink']['Face_Skin']['Blink_R']>.99
assert report['poses']['jaw']['Face_Skin']['Jaw_Open']>.79
assert report['poses']['jaw']['Lower_Dental_Arch']['Jaw_Open']>.79
assert report['poses']['neutral']==report['poses']['loop_end']
(OUT/'glb-roundtrip.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ROUNDTRIP_PASS',flush=True)
