"""Export baked clips without the source file's unskinned preview sphere."""
import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/video-motion-20261003'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer_video_motions.blend'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'
        and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
for obj in list(bpy.context.scene.objects):
    if obj.type=='MESH' and obj not in meshes:
        print('REMOVE_PREVIEW_HELPER',obj.name,flush=True)
        bpy.data.objects.remove(obj,do_unlink=True)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
for mesh in meshes:mesh.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(ROOT/'labs/video_motion_lab/assets/explorer_video_motions.glb'),
    export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIONS',
    export_force_sampling=True,export_anim_slide_to_zero=True,export_def_bones=True)
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_video_motions.blend'))
