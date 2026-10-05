"""Prepare the two untouched P2 sources side by side for manual review."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector

root=Path(__file__).resolve().parents[1]
folder=root/'art/characters/explorer_b_faceit_comparison_p2_v1'
hair_retry='--hair-v2' in sys.argv
bpy.ops.wm.read_factory_settings(use_empty=True)
all_meshes=[]
for part,offset in [('head',0.65),('hair',-0.65)]:
    coll=bpy.data.collections.new('01_Head_and_Neck' if part=='head' else '02_Hair')
    bpy.context.scene.collection.children.link(coll)
    before=set(bpy.data.objects)
    source_part='hair_v2' if part=='hair' and hair_retry else part
    bpy.ops.import_scene.fbx(filepath=str(folder/source_part/'model.fbx'),use_anim=False)
    for obj in set(bpy.data.objects)-before:
        for owner in list(obj.users_collection):owner.objects.unlink(obj)
        coll.objects.link(obj)
        if obj.parent is None:obj.location.y+=offset
        obj.hide_select=False
        obj.hide_set(False)
        if obj.type=='MESH':
            obj.name='HEAD_P2' if part=='head' else 'HAIR_P2'
            all_meshes.append(obj)
for obj in bpy.context.selected_objects:obj.select_set(False)
for obj in all_meshes:obj.select_set(True)
bpy.context.view_layer.objects.active=next(o for o in all_meshes if o.name=='HEAD_P2')
rotation=Vector((-1,0,0)).to_track_quat('-Z','Y')
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.shading.type='SOLID'
            space.shading.color_type='SINGLE'
            space.shading.single_color=(0.66,0.68,0.72)
            space.shading.show_cavity=True
            space.overlay.show_floor=False
            space.overlay.show_axis_x=False
            space.overlay.show_axis_y=False
            space.region_3d.view_rotation=rotation
            space.region_3d.view_location=(0,0,0)
            space.region_3d.view_distance=3.3
            space.region_3d.view_perspective='ORTHO'
bpy.context.preferences.filepaths.save_version=0
dest=folder/('explorer_b_P2_head_hair_v2_workbench.blend' if hair_retry else 'explorer_b_P2_head_hair_workbench.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(dest))
print('SAVED',dest,'MESHES',len(all_meshes),flush=True)
