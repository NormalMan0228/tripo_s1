import bpy,json,collections,math,bmesh
import numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];OUT=R/'art/characters/explorer_b_face_rig_manual_v2e';FILE=OUT/'explorer_face_contours_v2e.blend'
bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;sc.frame_set(1)
head=bpy.data.objects['01_Face_skin_neck'];rig=bpy.data.objects['FACE_RIG__select_Custom_Properties'];mesh=head.data
shapes={k.name:[v.co.copy() for v in k.data] for k in mesh.shape_keys.key_blocks};base=shapes['Basis'];faces=[list(f.vertices) for f in mesh.polygons]
drivers={fc.data_path:(fc.driver.expression,fc.driver.variables[0].targets[0].data_path) for fc in mesh.shape_keys.animation_data.drivers}
ec=collections.Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
bad=[e for e,n in ec.items() if n!=2 and all(base[i].x>.2 and -.23<base[i].z<-.1 for i in e)]
remove=set();loops=[]
for sign in [-1,1]:
 seed={i for e in bad for i in e if base[i].y*sign>0}
 selected={j for j,f in enumerate(faces) if any(i in seed for i in f)};remove.update(selected)
 remaining=collections.Counter(tuple(sorted((a,b))) for k,f in enumerate(faces) if k not in selected for a,b in zip(f,f[1:]+f[:1]))
 region={i for k in selected for i in faces[k]};boundary=[e for e,n in remaining.items() if n==1 and all(i in region for i in e)]
 adj=collections.defaultdict(list)
 for a,b in boundary:adj[a].append(b);adj[b].append(a)
 assert all(len(v)==2 for v in adj.values())
 loop=[min(adj)];prev=None
 while True:
  nxt=next(i for i in adj[loop[-1]] if i!=prev)
  if nxt==loop[0]:break
  prev=loop[-1];loop.append(nxt)
 assert len(loop)==len(adj);loops.append(loop)
newfaces=[f for i,f in enumerate(faces) if i not in remove]
for loop in loops:
 idx=len(shapes['Basis'])
 for name,coords in shapes.items():coords.append(sum((coords[i] for i in loop),Vector())/len(loop))
 for a,b in zip(loop,loop[1:]+loop[:1]):newfaces.append([a,b,idx])
used=sorted({i for f in newfaces for i in f});mapping={i:j for j,i in enumerate(used)}
m=bpy.data.meshes.new('Face_skin_contours_v2e_repaired_commissures');m.from_pydata([shapes['Basis'][i] for i in used],[],[[mapping[i] for i in f] for f in newfaces])
for mat in mesh.materials:m.materials.append(mat)
bm=bmesh.new();bm.from_mesh(m);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m);bm.free()
for f in m.polygons:f.use_smooth=True
head.data=m
for vg in list(head.vertex_groups):head.vertex_groups.remove(vg)
vg=head.vertex_groups.new(name='head');vg.add(list(range(len(used))),1,'REPLACE')
for name,coords in shapes.items():
 k=head.shape_key_add(name=name)
 for v,i in zip(k.data,used):v.co=coords[i]
 path='key_blocks["'+name+'"].value'
 if path in drivers:
  expression,prop=drivers[path];d=k.driver_add('value').driver;d.expression=expression
  var=d.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path=prop

# Close only the tiny commissure gaps introduced by relaxation, with broad falloff.
ks=m.shape_keys.key_blocks;base=[v.co.copy() for v in ks['Basis'].data]
m.calc_loop_triangles();bvh=BVHTree.FromPolygons(base,[t.vertices[:] for t in m.loop_triangles],all_triangles=True)
ys=np.linspace(-.095,.095,151);bounds=[]
for y in ys:
 gaps=[]
 for z in np.linspace(-.172,-.137,141):
  hit=bvh.ray_cast(Vector((1,float(y),float(z))),Vector((-1,0,0)),2)[0]
  if hit is not None and hit.x<.235:gaps.append(float(z))
 bounds.append((min(gaps)-.0003,max(gaps)+.0003) if gaps else (0,0))
closed=0
for i,p in enumerate(base):
 if p.x<.24 or abs(p.y)>.095 or not -.22<p.z<-.11:continue
 lo=float(np.interp(p.y,ys,[a for a,b in bounds]));hi=float(np.interp(p.y,ys,[b for a,b in bounds]))
 if hi-lo<.0005 or hi-lo>.012:continue
 mid=(lo+hi)/2;edge=lo if p.z<mid else hi
 w=math.exp(-((p.z-edge)/.016)**2)
 dz=((mid+.00035-lo) if p.z<mid else (mid-.00035-hi))*w
 for key in ks:
  if key.name!='jawOpen':key.data[i].co.z+=dz
 closed+=1
for v,p in zip(m.vertices,ks['Basis'].data):v.co=p.co
m.update()
sc.frame_set(2);sc.frame_set(1);rig.update_tag();bpy.context.view_layer.update()
cam=sc.camera
def camera(target,offset,scale):
 target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
def render(name):sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
camera((.25,0,-.17),(4,0,0),.38);render('mouth-front')
camera((.24,0,-.16),(.25,-4,0),.48);render('mouth-profile')
camera((.1,0,0),(4,-.35,.12),1.3);render('neutral')

# Sample all existing facial animation frames for broken data and loop discontinuity.
objects=[o for o in sc.objects if o.type=='MESH' and o.visible_get() and not o.hide_render and not o.name.startswith(('Hair','Nape'))]
first=None;last=None;maxstep=0.
for f in range(1,241):
 sc.frame_set(f);deps=bpy.context.evaluated_depsgraph_get();samples=[]
 for o in objects:
  ev=o.evaluated_get(deps);me=ev.to_mesh();samples.extend([v.co[:] for v in me.vertices]);ev.to_mesh_clear()
 a=np.array(samples);assert np.isfinite(a).all()
 if first is None:first=a.copy()
 if last is not None:maxstep=max(maxstep,float(np.linalg.norm(a-last,axis=1).max()))
 last=a
assert np.abs(first-last).max()<1e-7
sc.frame_set(1)
ec=collections.Counter(tuple(sorted((a,b))) for f in m.polygons for a,b in zip(list(f.vertices),list(f.vertices)[1:]+list(f.vertices)[:1]))
mouth_bad=[e for e,n in ec.items() if n!=2 and all(m.vertices[i].co.x>.2 and -.23<m.vertices[i].co.z<-.1 for i in e)]
assert not mouth_bad
report=json.loads((OUT/'correction-report.json').read_text())
report.update(mouth_nonmanifold_edges_before=len(bad),mouth_nonmanifold_edges_after=len(mouth_bad),mouth_corner_faces_replaced=len(remove),mouth_gap_corrected_vertices=closed,frames_checked=240,loop_max_difference=float(np.abs(first-last).max()),max_frame_displacement=maxstep,status='rendered front/side open/half/closed eyes and neutral mouth; prototype review',limitations=['No Godot playback test in this revision.','No claim of complete facial collision validation across arbitrary control combinations.'])
for side in report['lashes']:report['lashes'][side]['binding']='Original rest mesh preserved; displacement sampled from actual upper eyelid edge at identical four blink keys.'
(OUT/'correction-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
txt=bpy.data.texts.get('READ_ME_FACE_CONTROLS') or bpy.data.texts.new('READ_ME_FACE_CONTROLS');txt.clear();txt.write('V2e facial contour repair\nClosed neutral mouth. Local lip/chin contour smoothing; repaired non-manifold commissure faces.\nEyelid ring spacing rebuilt, orbital depth relaxed, globe depth flattened without retreating the frontal apex. Original lash mesh preserved; four blink targets follow actual lid-edge displacement.\nSelect FACE_RIG__select_Custom_Properties. Space plays the 240-frame comparison. For manual poses first unlink the demo action.\nControls: blink_L/R, jaw_open, smile, frown, pucker, brow_up/frown, look_lr/ud.\nRendered eye closeups hide hair for inspection. Original hair remains visible in saved scene.\nPrototype: visual review required; arbitrary combined poses and Godot not validated.\nSource V2d preserved; no API credits used.\n')
for o in sc.objects:o.select_set(False)
head.hide_set(False);head.select_set(True);bpy.context.view_layer.objects.active=head
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(FILE))
print('FACE_V2E_FINISHED',json.dumps(report),flush=True)
