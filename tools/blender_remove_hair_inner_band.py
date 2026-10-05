"""Remove the user-identified isolated 125-vertex inner band only."""
import bpy,json,hashlib
from pathlib import Path
from collections import Counter
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/characters/explorer_b_faceit_comparison_p2_v1'
SOURCE=BASE/'hair_v3_cleanup/character_face_preparation.blend'
OUT=BASE/'hair_v3_cleanup_v2';OUT.mkdir(exist_ok=True)
source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene=bpy.context.scene
hair=next(o for o in scene.objects if o.type=='MESH' and o.name.startswith('Hair'))
mesh=hair.data
parent=list(range(len(mesh.vertices)))
def find(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for edge in mesh.edges:parent[find(edge.vertices[0])]=find(edge.vertices[1])
components={}
for vertex in mesh.vertices:components.setdefault(find(vertex.index),[]).append(vertex.index)
assert sorted(map(len,components.values()))==[125,5104], 'Unexpected source topology; do not delete.'
remove=set(next(ids for ids in components.values() if len(ids)==125))
assert all(-.30<mesh.vertices[i].co.x<.07 and abs(mesh.vertices[i].co.y)<.23 for i in remove)
faces_before=len(mesh.polygons)
removed_faces=sum(all(i in remove for i in p.vertices) for p in mesh.polygons)
def key_coords(key,indices):
    return Counter(tuple(round(c,8) for c in key.data[i].co) for i in indices)
keep=[i for i in range(len(mesh.vertices)) if i not in remove]
expected={k.name:key_coords(k,keep) for k in mesh.shape_keys.key_blocks}
def geometry_hash(o):
    d={'vertices':[v.co[:] for v in o.data.vertices], 'faces':[p.vertices[:] for p in o.data.polygons]}
    return hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
face_hashes={o.name:geometry_hash(o) for o in scene.objects if o.type=='MESH' and o!=hair}
for o in scene.objects:o.select_set(False)
hair.select_set(True);bpy.context.view_layer.objects.active=hair
hair.active_shape_key_index=0
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='DESELECT');bpy.ops.object.mode_set(mode='OBJECT')
for v in mesh.vertices:v.select=v.index in remove
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.delete(type='VERT');bpy.ops.object.mode_set(mode='OBJECT')
assert len(mesh.vertices)==5104
assert all(key_coords(k,range(len(mesh.vertices)))==expected[k.name] for k in mesh.shape_keys.key_blocks),'Surviving shape-key positions changed'
assert all(geometry_hash(bpy.data.objects[name])==digest for name,digest in face_hashes.items()),'Face geometry changed'
hair.name='Hair__face_clearance__inner_band_removed'
hair.active_shape_key_index=1
scene['QUALITY_STATUS']='User-identified disconnected inner band removed; exterior and face-clearance shape key preserved. Other interior defects are not certified repaired.'
cam=scene.camera;target=Vector((-.03,0,.15));cam.data.ortho_scale=1.45
def frame(pos):
    cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
frame((4,-1.7,.5))
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            s=area.spaces.active;s.region_3d.view_location=target;s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=2
bpy.context.preferences.filepaths.save_version=0
dest=OUT/'character_face_preparation_v2.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(dest))
for name,pos,show_head in [('front',(4,0,0),True),('angle',(4,-1.7,.5),True),('inside',(2.4,-1,-2.8),False),('bottom',(.001,0,-4),False)]:
    for o in scene.objects:
        if o.type=='MESH' and o!=hair:o.hide_render=not show_head
    frame(pos);scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
report={'source':str(SOURCE),'source_unchanged':source_hash==hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'removed_vertices':125,'removed_polygons':removed_faces,'remaining_vertices':len(mesh.vertices),'remaining_polygons':len(mesh.polygons),'surviving_shape_key_coordinates_unchanged':True,'face_parts_unchanged':True,'outer_hair_preserved':True,'api_credits_used':0,'scope':'Only the separate U-shaped inner protrusion identified by the user. Other interior surface issues remain outside this edit.','output':str(dest)}
(OUT/'removal-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
