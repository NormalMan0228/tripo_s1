"""Preserve HD source and prepare a separate editable copy for form refinement."""
import bpy, bmesh, json, hashlib, math
from pathlib import Path
from mathutils import Vector, Matrix
R=Path(__file__).resolve().parents[1]
O=R/'art/characters/explorer_b_open_mouth_hd_v1'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version=0
sc=bpy.context.scene
def collection(name):
    c=bpy.data.collections.new(name);sc.collection.children.link(c);return c
sourcecol=collection('90_HD_SOURCE_preserved')
workcol=collection('01_HD_HEAD_form_refinement')
studiocol=collection('99_Review_cameras')
bpy.ops.import_scene.gltf(filepath=str(O/'model.glb'))
sources=[o for o in sc.objects if o.type=='MESH']
working=[]; entries=[]
clay=bpy.data.materials.new('Neutral_clay_geometry_review');clay.diffuse_color=(.57,.44,.35,1)
for i,src in enumerate(sources):
    src.name=f'HD_SOURCE_{i+1:02}'
    for c in list(src.users_collection):c.objects.unlink(src)
    sourcecol.objects.link(src)
    obj=src.copy();obj.data=src.data.copy();workcol.objects.link(obj)
    obj.name=f'HEAD_HD_EDIT_{i+1:02}'
    matrix=obj.matrix_world.copy();obj.parent=None;obj.data.transform(matrix);obj.matrix_world=Matrix.Identity(4)
    obj.data.materials.clear();obj.data.materials.append(clay)
    for p in obj.data.polygons:p.use_smooth=True
    obj['stage']='HD source review before form refinement and retopology'
    obj['source_glb']='model.glb'
    src.hide_render=True;src.hide_set(True);src.hide_select=True
    bm=bmesh.new();bm.from_mesh(obj.data)
    entry={'source':src.name,'editable_copy':obj.name,'vertices':len(bm.verts),'faces':len(bm.faces),
           'boundary_edges':sum(e.is_boundary for e in bm.edges),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
           'loose_vertices':sum(not v.link_faces for v in bm.verts),'finite_coordinates':all(math.isfinite(x) for v in bm.verts for x in v.co)}
    bm.free();entries.append(entry);working.append(obj)
sourcecol.hide_render=True
pts=[v.co for o in working for v in o.data.vertices]
lo=Vector([min(v[i] for v in pts) for i in range(3)]);hi=Vector([max(v[i] for v in pts) for i in range(3)])
center=(lo+hi)/2;size=max(hi-lo)
sc.render.engine='BLENDER_WORKBENCH'
sc.render.resolution_x=1000;sc.render.resolution_y=1100;sc.render.resolution_percentage=100
sc.render.image_settings.file_format='PNG'
sc.world=bpy.data.worlds.new('Review World');sc.world.color=(.08,.08,.08)
sh=sc.display.shading;sh.light='STUDIO';sh.studiolight_rotate_z=.3;sh.color_type='MATERIAL'
sh.show_shadows=True;sh.show_cavity=True;sh.cavity_type='BOTH';sh.curvature_ridge_factor=1.0;sh.curvature_valley_factor=.7
sh.show_specular_highlight=True;sh.background_type='WORLD'
def camera(name,target,offset,scale):
    c=bpy.data.objects.new(name,bpy.data.cameras.new(name));studiocol.objects.link(c)
    c.location=target+Vector(offset)*size;c.rotation_euler=(target-c.location).to_track_quat('-Z','Y').to_euler()
    c.data.type='ORTHO';c.data.ortho_scale=scale*size;c.data.clip_start=size*.001;c.data.clip_end=size*100
    c.hide_set(True);c.hide_select=True;return c
cameras=[]
for name,offset in [('front',(4,0,0)),('angle',(4,-2.5,.1)),('side',(0,-4,0)),('back',(-4,0,0))]:
    cam=camera(name,center,offset,1.18);sc.camera=cam;cameras.append(cam)
    sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
sc.camera=cameras[0]
bpy.ops.object.select_all(action='DESELECT')
for obj in working:obj.select_set(True)
bpy.context.view_layer.objects.active=working[0]
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active;sp.shading.type='SOLID';sp.shading.color_type='MATERIAL';sp.overlay.show_floor=False
            sp.overlay.show_axis_x=False;sp.overlay.show_axis_y=False
            sp.region_3d.view_location=center;sp.region_3d.view_rotation=cameras[1].rotation_euler.to_quaternion()
            sp.region_3d.view_distance=size*1.65;sp.region_3d.view_perspective='ORTHO'
text=bpy.data.texts.new('READ_ME_workflow')
text.write('HD source for open-mouth head. 90_HD_SOURCE_preserved is hidden; 01_HD_HEAD_form_refinement is the editable copy.\nNext: inspect oral cavity and refine face silhouette, then retopology with facial edge loops. UV/bake and facial rig come afterward.\nNo automatic decimation, voxel remesh, texture projection, or facial rig has been applied.\n')
report={'source_glb_sha256':hashlib.sha256((O/'model.glb').read_bytes()).hexdigest(),'meshes':entries,
        'bounds':[list(lo),list(hi)],'geometry_edited':False,'retopology_complete':False,'rigged':False,
        'texture_generated':False,'source_preserved':True,'vertices':sum(e['vertices'] for e in entries),'faces':sum(e['faces'] for e in entries)}
file=O/'explorer_b_open_mouth_HD_workbench.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(file))
bpy.ops.wm.open_mainfile(filepath=str(file))
assert all(e['finite_coordinates'] for e in entries)
assert all(bpy.data.objects[e['editable_copy']].visible_get() for e in entries)
assert all(not bpy.data.objects[e['source']].visible_get() for e in entries)
assert all(bpy.data.objects[e['editable_copy']].data != bpy.data.objects[e['source']].data for e in entries)
report['verified_after_reopen']=True
(O/'inspection-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('HD_HEAD_VERIFIED',json.dumps(report))
