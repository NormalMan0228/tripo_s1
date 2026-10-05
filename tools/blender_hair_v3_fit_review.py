"""Non-destructive trial fit of immutable P2 outputs, not a finished assembly."""
import bpy, json, hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/characters/explorer_b_faceit_comparison_p2_v1'
OUT=BASE/'hair_v3'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'review.blend'))
scene=bpy.context.scene
hair=next(o for o in scene.objects if o.type=='MESH')
hair.name='HAIR_V3_MULTIVIEW__INTERIOR_REVIEW_REQUIRED'
hair.scale=(1.05,)*3
hair.location=(-.03,0,.15)
before=set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=str(BASE/'head/model.fbx'),use_anim=False)
head=next(o for o in set(bpy.data.objects)-before if o.type=='MESH')
head.name='HEAD_REFERENCE__UNCHANGED'
def material(name,color):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=.7
    return m
hair.data.materials.clear();hair.data.materials.append(material('Review hair uniform brown - NOT generated texture',(.17,.075,.035)))
head.data.materials.clear();head.data.materials.append(material('Review head uniform clay',(.58,.49,.38)))
bpy.context.view_layer.update()
def bvh(o):
    m=o.data;m.calc_loop_triangles()
    return BVHTree.FromPolygons([o.matrix_world@v.co for v in m.vertices],[tuple(t.vertices) for t in m.loop_triangles],all_triangles=True)
overlaps=bvh(hair).overlap(bvh(head))
report={'status':'review_only_not_accepted','generation_credits':100,'remaining_authorized_credits':320,'hair_uniform_scale':1.05,'hair_location':list(hair.location),'head_transform_unchanged':True,'fit_is_provisional':True,'intersecting_triangle_pairs_in_trial_fit':len(overlaps),'hair_triangles_in_intersections':len(set(a for a,b in overlaps)),'findings':['Interior cross-band and uneven internal surfaces remain visible in raw underside renders.','Four-view generation did not establish a clean scalp cavity.','Boundary and nonmanifold edges require local inspection.'],'production_ready':False,'mesh_geometry_edited':False,'source_sha256':hashlib.sha256((OUT/'model.fbx').read_bytes()).hexdigest()}
(OUT/'quality-notes.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
cam=scene.camera;cam.data.ortho_scale=1.5
target=Vector((0,0,.04))
def frame(pos):
    cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
frame((4,-1.7,.5))
for o in scene.objects:o.select_set(False)
hair.select_set(True);bpy.context.view_layer.objects.active=hair
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            s=area.spaces.active;s.shading.type='SOLID';s.shading.color_type='MATERIAL';s.shading.show_cavity=True
            s.region_3d.view_location=target;s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=2;s.region_3d.view_perspective='ORTHO'
            s.overlay.show_extras=False
for obj in scene.objects:
    if obj.type in ('CAMERA','LIGHT'):obj.hide_set(True)
scene['QUALITY_STATUS']='REVIEW ONLY: interior band remains, trial fit has intersections. No production acceptance.'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'head_hair_v3_fit_review.blend'))
for name,pos in [('fit-front',(4,0,0)),('fit-angle',(4,-1.7,.5)),('fit-side',(0,-4,0))]:
    frame(pos);scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
print(json.dumps(report),flush=True)
