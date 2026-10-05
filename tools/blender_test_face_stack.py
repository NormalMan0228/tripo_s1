"""Exercise MPFB assets, facial targets and Rigify on an unstyled template."""
import bpy
import addon_utils
import json
import math
from pathlib import Path
from mathutils import Vector
from bl_ext.user_default.mpfb.services.humanservice import HumanService
from bl_ext.user_default.mpfb.services.faceservice import FaceService, ARKIT_FACEUNITS
from bl_ext.user_default.mpfb.services.locationservice import LocationService
from bl_ext.user_default.mpfb.services.rigservice import RigService

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_pipeline_v3/01_template_test'
REPORT=ROOT/'artifacts/face-stack-test-20261004'
OUT.mkdir(parents=True,exist_ok=True)
REPORT.mkdir(parents=True,exist_ok=True)
assert addon_utils.check('rigify')[1]
assert addon_utils.check('bl_ext.user_default.mpfb')[1]
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
human=HumanService.create_human()
human.name='Template_Face_Body'
human.use_shape_key_edit_mode=True
data=Path(LocationService.get_user_data())
parts={}
for kind, path in [
    ('Eyes','eyes/high-poly/high-poly.mhclo'),
    ('Eyebrows','eyebrows/eyebrow001/eyebrow001.mhclo'),
    ('Eyelashes','eyelashes/eyelashes01/eyelashes01.mhclo'),
    ('Teeth','teeth/teeth_base/teeth_base.mhclo'),
    ('Tongue','tongue/tongue01/tongue01.mhclo'),
]:
    part=HumanService.add_mhclo_asset(str(data/path),human,asset_type=kind,subdiv_levels=1,set_up_rigging=False)
    parts[kind]=part
    print('BODY_PART',kind,part.name,flush=True)

FaceService.load_targets(human,load_microsoft_visemes=True,load_meta_visemes=True,load_arkit_faceunits=True)
FaceService.interpolate_targets(human)
keys=human.data.shape_keys.key_blocks
assert all(name in keys for name in ARKIT_FACEUNITS)
for part in parts.values():
    if not part.data.shape_keys: continue
    for key in part.data.shape_keys.key_blocks:
        if key.name=='Basis' or key.name not in keys: continue
        curve=key.driver_add('value')
        driver=curve.driver
        driver.type='AVERAGE'
        var=driver.variables.new();var.name='source';var.type='SINGLE_PROP'
        var.targets[0].id_type='KEY';var.targets[0].id=human.data.shape_keys
        var.targets[0].data_path=keys[key.name].path_from_id('value')

# Keep the official template geometry untouched; only use a neutral review material.
skin=bpy.data.materials.new('Template_Review_Skin')
skin.diffuse_color=(0.52,0.31,0.22,1)
skin.use_nodes=True
bsdf=skin.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Base Color'].default_value=(0.52,0.31,0.22,1)
bsdf.inputs['Roughness'].default_value=.48
human.data.materials.clear();human.data.materials.append(skin)
for p in human.data.polygons:p.use_smooth=True
subd=human.modifiers.new('Review subdivision','SUBSURF');subd.levels=1;subd.render_levels=1

# Verify real Rigify generation on the standard MPFB body. Facial bones remain at rest;
# facial shape keys are the sole expression source in this test.
meta=HumanService.add_builtin_rig(human,'rigify.human',import_weights=True)
rig=RigService.generate_rigify_rig(meta,name='Template_Control_Rig',meta_rig_action='hide')
assert rig and len(rig.pose.bones)>100
rig.hide_render=True
rig.hide_set(True)
for collection in bpy.data.collections:
    if collection.name.startswith('WGTS'):collection.hide_render=True

scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=24
scene.cycles.use_denoising=True
scene.render.resolution_x=560;scene.render.resolution_y=560;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.fps=30;scene.frame_start=1;scene.frame_end=660
scene.world.color=(.14,.14,.14)
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.13,.17,.20,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.45
scene.view_settings.view_transform='AgX'
scene.view_settings.exposure=-1.3
bpy.context.view_layer.update()
points=[parts['Eyes'].matrix_world@v.co for v in parts['Eyes'].data.vertices]
eye_center=sum(points,Vector())/len(points)
target=eye_center+Vector((0,0,-.042))
camera_data=bpy.data.cameras.new('Face_Review_Camera');camera=bpy.data.objects.new('Face_Review_Camera',camera_data)
scene.collection.objects.link(camera);scene.camera=camera
camera_data.type='ORTHO';camera_data.ortho_scale=.43
def camera_at(angle):
    angle=math.radians(angle)
    camera.location=target+Vector((math.sin(angle)*1.2,-math.cos(angle)*1.2,.035))
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
camera_at(0)
for name, offset, energy, size in [('Key',(-.5,-.6,.7),75,.65),('Fill',(.55,-.3,.2),45,.5),('Rim',(.1,.4,.6),90,.5)]:
    light_data=bpy.data.lights.new(name,'AREA');light_data.energy=energy;light_data.shape='DISK';light_data.size=size
    light=bpy.data.objects.new(name,light_data);scene.collection.objects.link(light)
    light.location=target+Vector(offset);light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()

poses=[
 ('Neutral',{}),
 ('Blink_25',{'eyeBlinkLeft':.25,'eyeBlinkRight':.25}),
 ('Blink_50',{'eyeBlinkLeft':.5,'eyeBlinkRight':.5}),
 ('Blink_75',{'eyeBlinkLeft':.75,'eyeBlinkRight':.75}),
 ('Blink_100',{'eyeBlinkLeft':1,'eyeBlinkRight':1}),
 ('Look_Left',{'eyeLookOutLeft':.6,'eyeLookInRight':.6}),
 ('Look_Right',{'eyeLookInLeft':.6,'eyeLookOutRight':.6}),
 ('Jaw_Open',{'jawOpen':.65}),
 ('Smile',{'mouthSmileLeft':.7,'mouthSmileRight':.7}),
 ('Pucker',{'mouthPucker':.7}),
 ('Gaze_Blink',{'eyeLookOutLeft':.5,'eyeLookInRight':.5,'eyeBlinkLeft':.5,'eyeBlinkRight':.5}),
 ('Viseme_AA',{'viseme_aa':.8}),
]
animated=sorted({n for _,p in poses for n in p})
for n in animated:assert n in keys,n
def set_pose(values):
    for name in animated:keys[name].value=values.get(name,0)
    bpy.context.view_layer.update()

report={'blender':bpy.app.version_string,'mpfb':'2.0.17','template_geometry_customized':False,
    'rigify_generated':True,'rigify_bones':len(rig.data.bones),'faceunit_count':len(ARKIT_FACEUNITS),
    'base_vertices_with_helpers':len(human.data.vertices),'eye_center':list(eye_center),'parts':{},'shape_tests':{},'rendered':[]}
for name,part in parts.items():
    child_keys=part.data.shape_keys.key_blocks if part.data.shape_keys else []
    report['parts'][name]={'object':part.name,'vertices':len(part.data.vertices),'keys':[k.name for k in child_keys],'drivers':len(part.data.shape_keys.animation_data.drivers) if part.data.shape_keys and part.data.shape_keys.animation_data else 0}
for name in animated:
    distance=max((a.co-b.co).length for a,b in zip(keys[name].data,keys['Basis'].data))
    assert math.isfinite(distance) and distance>0,name
    report['shape_tests'][name]={'max_displacement_m':distance}
assert all(n in parts['Eyelashes'].data.shape_keys.key_blocks for n in ['eyeBlinkLeft','eyeBlinkRight'])

# A slow inspection sequence: each expression eases in, pauses, then eases out.
for name in animated:
    keys[name].value=0;keys[name].keyframe_insert('value',frame=1)
for index,(label,values) in enumerate(poses[1:]):
    start=1+index*60
    for frame,p in [(start,{}),(start+18,values),(start+36,values),(start+54,{})]:
        set_pose(p)
        for name in animated:keys[name].keyframe_insert('value',frame=frame)
    scene.timeline_markers.new(label,frame=start+18)
action=human.data.shape_keys.animation_data.action
action.name='Template_Face_Slow_Test_22s'
for fc in action.fcurves:
    for key in fc.keyframe_points:key.interpolation='BEZIER';key.handle_left_type='AUTO_CLAMPED';key.handle_right_type='AUTO_CLAMPED'
for space_screen in bpy.data.screens:
    for area in space_screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.region_3d.view_perspective='CAMERA'
            space.overlay.show_overlays=False
            space.shading.type='MATERIAL'
            space.show_region_ui=True
scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT')
human.select_set(True);bpy.context.view_layer.objects.active=human
human.active_shape_key_index=keys.find('eyeBlinkLeft')
note=bpy.data.texts.new('READ_ME_Face_Stack_Test')
note.write('MPFB 2.0.17 + bundled Rigify / Blender 4.5.3\nUnmodified template geometry; NOT Explorer B final design.\nSpace: play 22-second slow expression test. Frame 1: neutral.\nExpressions are shape-key driven; facial rig bones remain neutral.\nEyes, lashes, eyebrows, teeth, tongue use official system assets.\n')
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'mpfb_template_face_test.blend'))
(REPORT/'test-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('TEST_SCENE_SAVED',json.dumps({'bones':len(rig.data.bones),'keys':len(keys),'eye_center':list(eye_center)}),flush=True)

# Clear animation only in memory so stills can independently exercise all requested weights.
human.data.shape_keys.animation_data.action=None
for label,values in poses:
    set_pose(values);camera_at(0)
    scene.render.filepath=str(REPORT/(label+'.png'))
    bpy.ops.render.render(write_still=True)
    report['rendered'].append(label+'.png')
for label,values,angle in [('Profile_Neutral',{},85),('ThreeQuarter_Blink',{'eyeBlinkLeft':1,'eyeBlinkRight':1},45),('ThreeQuarter_Gaze',{'eyeLookOutLeft':.6,'eyeLookInRight':.6},45),('Profile_Jaw',{'jawOpen':.65},85)]:
    set_pose(values);camera_at(angle)
    scene.render.filepath=str(REPORT/(label+'.png'));bpy.ops.render.render(write_still=True)
    report['rendered'].append(label+'.png')
(REPORT/'test-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('FACE_TEST_DONE',len(report['rendered']),flush=True)
