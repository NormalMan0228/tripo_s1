"""Minimal source preparation: trim the generated lower flap, leave face unchanged."""
import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_open_mouth_hd_v1'
bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_open_mouth_HD_workbench.blend'))
bpy.context.preferences.filepaths.save_version=0
sc=bpy.context.scene;obj=bpy.data.objects['HEAD_HD_EDIT_01']
bpy.context.view_layer.objects.active=obj
before=len(obj.data.polygons)
if obj.data.has_custom_normals:bpy.ops.mesh.customdata_custom_splitnormals_clear()
bm=bmesh.new();bm.from_mesh(obj.data)
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.000001,
                      plane_co=(0,0,-.365),plane_no=(0,0,1),clear_inner=True,clear_outer=False)
cut=[e for e in bm.edges if e.is_boundary and all(abs(v.co.z+.365)<.00001 for v in e.verts)]
if cut:bmesh.ops.holes_fill(bm,edges=cut,sides=0)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
boundaries=sum(e.is_boundary for e in bm.edges)
bm.to_mesh(obj.data);bm.free()
for p in obj.data.polygons:p.use_smooth=True
obj.data.update()
obj['stage']='HD form refinement prepared; generated base flap trimmed; face unsculpted'
report=json.loads((O/'inspection-report.json').read_text())
report['initial_cleanup']={'lower_cut_z':-.365,'faces_before':before,'faces_after':len(obj.data.polygons),
                         'boundary_edges_after':boundaries,'custom_split_normals_cleared':True,
                         'facial_vertices_sculpted':False}
report['geometry_edited']=True
report['remaining_form_work']=['Replace generated iris and catchlight relief with separate smooth eyeballs',
    'Inspect and deepen oral cavity; separate tooth and tongue geometry before rigging',
    'Refine lip, eyelid and nose surfaces while retaining approved character proportions',
    'Only after form approval: retopology with mouth and eyelid deformation loops']
for name in ['front','angle','side']:
    sc.camera=bpy.data.objects[name];sc.render.filepath=str(O/('prepared_'+name+'.png'));bpy.ops.render.render(write_still=True)
# A front close-up to examine lip separation and generated oral relief.
cam=bpy.data.objects.new('Mouth_detail',bpy.data.cameras.new('Mouth_detail'))
bpy.data.collections['99_Review_cameras'].objects.link(cam)
target=Vector((.22,0,-.09));cam.location=(3,0,-.09);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=.36;cam.hide_set(True);cam.hide_select=True
sc.camera=cam;sc.render.filepath=str(O/'mouth_detail.png');bpy.ops.render.render(write_still=True)
# Real surface depth along the centerline, not a texture-only opening.
rays=[]
for z in [-.045,-.06,-.075,-.09,-.105,-.12,-.135,-.15,-.165]:
    hit,loc,normal,index=obj.ray_cast(Vector((2,0,z)),Vector((-1,0,0)))
    rays.append({'z':z,'front_x':loc.x if hit else None})
report['mouth_centerline_surface_samples']=rays
sc.camera=bpy.data.objects['front']
bpy.ops.wm.save_as_mainfile(filepath=str(O/'explorer_b_open_mouth_HD_workbench.blend'))
bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_open_mouth_HD_workbench.blend'))
assert not bpy.data.objects['HD_SOURCE_01'].visible_get()
assert bpy.data.objects['HEAD_HD_EDIT_01'].visible_get()
assert len(bpy.data.objects['HD_SOURCE_01'].data.polygons)==before
report['cleanup_verified_after_reopen']=True
(O/'inspection-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'cleanup':report['initial_cleanup'],'rays':rays}))
