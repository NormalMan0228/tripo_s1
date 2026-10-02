import bpy,sys
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/characters/explorer-b-detailed-v2'
sys.path.insert(0,str(ROOT/'tools'))
from merge_detail_tracks import merge
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer-b-detailed.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['Explorer_B_Detailed_Rig']
character=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers)]
for obj in character:
    for poly in obj.data.polygons:poly.use_smooth=True
    if obj.data.has_custom_normals:obj.data.normals_split_custom_set([(0,0,0)]*len(obj.data.loops))
groups={n:rig.data.collections.new(n) for n in ['Body','Fingers','Face','IK Controls']}
for b in rig.data.bones:
    name='IK Controls' if b.name.startswith('CTRL_') else 'Face' if b.name.startswith('Face_') else 'Fingers' if any(d in b.name for d in ['Thumb_','Index_','Middle_','Ring_','Little_']) else 'Body'
    groups[name].assign(b)
rig.data.display_type='STICK'
scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
for o in character:o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'explorer-b-detailed.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='SCENE',export_frame_range=True,export_force_sampling=True,export_skins=True,export_morph=True,export_def_bones=True)
merge(OUT/'explorer-b-detailed.glb')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer-b-detailed.blend'))
# Separate neutral authoring copy: keyframes do not override manual edits.
for a in bpy.data.actions:a.use_fake_user=True
rig.animation_data_clear()
for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
for obj in character:
    if obj.data.shape_keys:
        obj.data.shape_keys.animation_data_clear()
        for key in obj.data.shape_keys.key_blocks:key.value=0
text=bpy.data.texts.new('START_HERE.txt')
text.write('''EXPLORER B - DETAIL RIG AUTHORING
This neutral copy retains the demonstration Actions, but disconnects them for editing.
Pose Mode: L/R_Thumb, Index, Middle, Ring, Little 01-03. Curl around local X.
Face_Eye_L/R: rotate locally to aim the eyes. Face_Jaw: use a small rotation.
Shape Keys on mesh objects: Blink_L/R, Smile, BrowRaise, BrowConcern, EyesWide, MouthOpen.
Blink affects upper lid, lower lid and lash together. MouthOpen affects rim and interior together.
The Godot viewer provides unified sliders for these controls.
Optional IK: choose L/R_Forearm or Calf, set Optional_IK influence to 1,
then move CTRL_L/R_Hand/Foot_IK. Pole controls set the bend direction.
IK controls are Blender authoring controls; the GLB contains 74 deform bones.
This is a first detail pass: strong grip silhouettes and eyelid/mouth seams need art polish.
No new API calls were made. Original B-v1 and Tripo walk are preserved.
''')
bpy.context.view_layer.update()
scene.camera.location=Vector((3,-.3,1.0));target=Vector((0,0,.55));scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=1.2
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer-b-authoring.blend'))
print('DETAIL_DELIVERY_READY')
