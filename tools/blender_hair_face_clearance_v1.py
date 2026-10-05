"""Small reversible hair clearance adjustment and facial component review setup."""
import bpy,json,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/characters/explorer_b_faceit_comparison_p2_v1'
OUT=BASE/'hair_v3_cleanup';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(BASE/'hair_v3/head_hair_v3_fit_review.blend'))
scene=bpy.context.scene
hair=next(o for o in scene.objects if o.type=='MESH' and o.name.startswith('HAIR'))
head=next(o for o in scene.objects if o.type=='MESH' and o.name.startswith('HEAD'))
def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def tree(o,coords=None):
    m=o.data;m.calc_loop_triangles()
    return BVHTree.FromPolygons([o.matrix_world@v for v in coords] if coords else [o.matrix_world@v.co for v in m.vertices],[t.vertices[:] for t in m.loop_triangles],all_triangles=True)
def front_pairs(coords=None):
    pairs=tree(hair,coords).overlap(tree(head));m=hair.data
    points=[hair.matrix_world@v for v in coords] if coords else [hair.matrix_world@v.co for v in m.vertices]
    front=[(a,b) for a,b in pairs if (sum((points[i] for i in m.loop_triangles[a].vertices),Vector())/3).x>.12 and (sum((points[i] for i in m.loop_triangles[a].vertices),Vector())/3).z<.35]
    return {'all_triangle_pairs':len(pairs),'front_triangle_pairs':len(front),'front_hair_triangles':len(set(a for a,b in front))}
before=front_pairs()
hair.shape_key_add(name='Basis');key=hair.shape_key_add(name='Face_clearance_local');key.value=1
inverse=hair.matrix_world.inverted();moved=0;max_shift=0
for i,v in enumerate(hair.data.vertices):
    p=hair.matrix_world@v.co
    w=smooth(.035,.135,p.x)*smooth(.10,.18,abs(p.y))*(1-smooth(.32,.44,abs(p.y)))*smooth(-.32,-.22,p.z)*(1-smooth(.25,.43,p.z))
    shift=Vector((.045, .09*(1 if p.y>=0 else -1),0))*w
    key.data[i].co=inverse@(p+shift)
    if shift.length>1e-6:moved+=1;max_shift=max(max_shift,shift.length)
coords=[v.co.copy() for v in key.data]
# Resolve the few residual front contacts with small local, feathered steps.
adj=[set() for _ in hair.data.vertices]
for edge in hair.data.edges:
    a,b=edge.vertices;adj[a].add(b);adj[b].add(a)
for iteration in range(8):
    points=[hair.matrix_world@v for v in coords]
    pairs=tree(hair,coords).overlap(tree(head));seeds=set()
    for a,b in pairs:
        indices=hair.data.loop_triangles[a].vertices
        center=sum((points[i] for i in indices),Vector())/3
        if center.x>.12 and center.z<.35:seeds.update(indices)
    if not seeds:break
    weights={i:1.0 for i in seeds}
    for i in seeds:
        for j in adj[i]:weights[j]=max(weights.get(j,0),.5)
    for i,w in weights.items():
        p=points[i];p+=Vector((.004,.009*(1 if p.y>=0 else -1),0))*w
        coords[i]=inverse@p;key.data[i].co=coords[i]
moved=sum((coords[i]-v.co).length>1e-6 for i,v in enumerate(hair.data.vertices))
max_shift=max((hair.matrix_world.to_3x3()@(coords[i]-v.co)).length for i,v in enumerate(hair.data.vertices))
after=front_pairs(coords)
hair.name='Hair__local_face_clearance__toggle_shape_key_to_compare'

# Split existing disconnected islands only. No retopology, remesh, or invention
# of eye/mouth geometry here. Semantic names remain explicitly provisional.
for o in scene.objects:o.select_set(False)
head.select_set(True);bpy.context.view_layer.objects.active=head
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.separate(type='LOOSE');bpy.ops.object.mode_set(mode='OBJECT')
parts=[o for o in bpy.context.selected_objects if o.type=='MESH']
face_collection=bpy.data.collections.new('Face_parts__semantic_labels_provisional');scene.collection.children.link(face_collection)
records=[]
labels={7681:'Face_skin_neck',1809:'Upper_dental_candidate',1504:'Lower_dental_candidate',591:'Tongue_candidate',993:'Eye_candidate',930:'Eye_candidate',544:'Upper_lash_candidate',317:'Brow_candidate'}
for i,o in enumerate(sorted(parts,key=lambda o:len(o.data.vertices),reverse=True)):
    n=len(o.data.vertices);cy=sum(v.co.y for v in o.data.vertices)/n
    label=labels.get(n,'Eye_detail_unclassified')
    if n in (993,930,544,317) or label=='Eye_detail_unclassified':label+=('_posY' if cy>0 else '_negY')
    o.name=f'{i+1:02d}_{label}'
    for c in list(o.users_collection):c.objects.unlink(o)
    face_collection.objects.link(o)
    o['classification']='Provisional geometry-based label; inspect before binding or retopology.'
    records.append({'object':o.name,'vertices':n})
for o in scene.objects:o.select_set(False)
hair.select_set(True);bpy.context.view_layer.objects.active=hair
scene['QUALITY_STATUS']='Local face clearance only. Interior hair defects retained; face islands prepared for topology review. Not production ready.'
cam=scene.camera;target=Vector((0,0,.04));cam.data.ortho_scale=1.5
def frame(pos):
    cam.location=target+Vector(pos);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
frame((4,-1.7,.5))
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'character_face_preparation.blend'))
for name,pos in [('front',(4,0,0)),('angle',(4,-1.7,.5)),('side',(0,-4,0)),('opposite',(4,1.7,.5))]:
    frame(pos);scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
report={'scope':'Small local hair adjustment and disconnected face island separation only','before':before,'after':after,'moved_hair_vertices':moved,'max_world_displacement':max_shift,'reversible_shape_key':'Face_clearance_local','face_components':records,'face_vertex_count_preserved':sum(len(o.data.vertices) for o in parts)==16303,'api_credits_used':0,'hair_interior_fixed':False,'retopology_done':False,'rigged':False,'production_ready':False}
(OUT/'cleanup-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
