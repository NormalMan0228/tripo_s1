"""Read-only source analysis and separate mouth cutaway preview."""
import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_open_mouth_p2_v1'
bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_open_mouth_P2_workbench.blend'))
bpy.context.preferences.filepaths.save_version=0
sc=bpy.context.scene;heads=[o for o in sc.objects if o.type=='MESH' and o.name.startswith('HEAD_P2_EDIT')]
for col in list(bpy.data.collections):
    if col.name.startswith('80_ORAL_CUTAWAY'):
        for obj in list(col.objects):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.collections.remove(col)
for obj in list(bpy.data.objects):
    if obj.type=='CAMERA' and obj.name.startswith(('Mouth_detail','Mouth_section')):
        bpy.data.objects.remove(obj,do_unlink=True)
report=json.loads((O/'inspection-report.json').read_text())
components=[]
for obj in heads:
    bm=bmesh.new();bm.from_mesh(obj.data);bm.verts.ensure_lookup_table();seen=set()
    for v in bm.verts:
        if v.index in seen:continue
        stack=[v];seen.add(v.index);group=[]
        while stack:
            a=stack.pop();group.append(a)
            for e in a.link_edges:
                b=e.other_vert(a)
                if b.index not in seen:seen.add(b.index);stack.append(b)
        components.append({'object':obj.name,'vertices':len(group),'bounds':[[min(v.co[i] for v in group),max(v.co[i] for v in group)] for i in range(3)]})
    bm.free()
report['connected_components']=sorted(components,key=lambda c:-c['vertices'])
lo,hi=[Vector(a) for a in report['bounds']];size=max(hi-lo);center=(lo+hi)/2
target=Vector((0,0,center.z-.09*size))
def camera(name,offset,scale):
    c=bpy.data.objects.new(name,bpy.data.cameras.new(name));bpy.data.collections['99_Review_cameras'].objects.link(c)
    c.location=target+Vector(offset)*size;c.rotation_euler=(target-c.location).to_track_quat('-Z','Y').to_euler()
    c.data.type='ORTHO';c.data.ortho_scale=scale*size;c.hide_select=True;c.hide_set(True);return c
cam=camera('Mouth_detail',(4,0,0),.38);sc.camera=cam;sc.render.filepath=str(O/'mouth_detail.png');bpy.ops.render.render(write_still=True)
cutcol=bpy.data.collections.new('80_ORAL_CUTAWAY_preview_only_hidden');sc.collection.children.link(cutcol)
copies=[]
for head in heads:
    c=head.copy();c.data=head.data.copy();cutcol.objects.link(c);c.name='CUTAWAY_'+head.name
    c['purpose']='Section preview only, not production geometry'
    bm=bmesh.new();bm.from_mesh(c.data)
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.000001,
                          plane_co=(0,0,0),plane_no=(0,1,0),clear_inner=True,clear_outer=False)
    bm.to_mesh(c.data);bm.free();copies.append(c);head.hide_render=True
camcut=camera('Mouth_section',(1,-4,.1),.6);camcut.location.x+=.12*size;sc.camera=camcut;sc.render.filepath=str(O/'mouth_section.png');bpy.ops.render.render(write_still=True)
for c in copies:c.hide_render=True;c.hide_set(True);c.hide_select=True
cutcol.hide_render=True
for head in heads:head.hide_render=False
sc.camera=cam
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active;sp.region_3d.view_location=target
            sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.region_3d.view_distance=size*.72
            sp.clip_start=size*.0001;sp.shading.show_shadows=False
report['cutaway_collection']='80_ORAL_CUTAWAY_preview_only_hidden'
report['cutaway_is_separate_copy']=True
bpy.ops.wm.save_as_mainfile(filepath=str(O/'explorer_b_open_mouth_P2_workbench.blend'))
bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_open_mouth_P2_workbench.blend'))
assert all(not o.visible_get() for o in bpy.data.collections['80_ORAL_CUTAWAY_preview_only_hidden'].objects)
assert all(bpy.data.objects[e['editable_copy']].visible_get() for e in report['meshes'])
(O/'inspection-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'components':report['connected_components'],'mouth_view_saved':True}))
