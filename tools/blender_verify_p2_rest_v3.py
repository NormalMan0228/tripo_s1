import bpy,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_p2_rest_refined_v3'
bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_P2_rest_refined_v3.blend'))
sc=bpy.context.scene;head=bpy.data.objects['HEAD_relaxed_smile_rest'];ctrl=bpy.data.objects['FACE_CONTROLS'];assert ctrl['mouth_open']==0
results=[]
for value in [0,.25,.5,.75,1,0]:
 ctrl['mouth_open']=value;ctrl.update_tag();sc.frame_set(sc.frame_current+1);bpy.context.view_layer.update()
 e=head.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();m.calc_loop_triangles()
 assert all(math.isfinite(x) for v in m.vertices for x in v.co)
 tree=BVHTree.FromPolygons([v.co for v in m.vertices],[tuple(t.vertices) for t in m.loop_triangles],all_triangles=True)
 gaps={}
 for y in [-.06,-.04,-.02,0,.02,.04,.06]:
  missed=[]
  for i in range(301):
   z=-.135+i*.0003;p,*_=tree.ray_cast(Vector((2,y,z)),Vector((-1,0,0)))
   if p is None or p.x<.16:missed.append(z)
  gaps[str(y)]=len(missed)*.0003
 results.append({'mouth_open':value,'cavity_height_by_y':gaps})
 if value==0:assert max(gaps.values())<=.0006, gaps
 if value==1:assert gaps['0']>.03
 e.to_mesh_clear()
report=json.loads((O/'refinement-report.json').read_text())
# Measure saved lash geometry against the reopened neutral head.
ctrl['mouth_open']=0.;ctrl.update_tag();bpy.context.view_layer.update()
head.data.calc_loop_triangles()
rest=BVHTree.FromPolygons([v.co for v in head.data.shape_keys.key_blocks[0].data],[tuple(t.vertices) for t in head.data.loop_triangles],all_triangles=True)
attachment=[]
for entry in report['lash_attachment']:
 o=bpy.data.objects[entry['object']];roots=entry['root_indices']
 distances=[rest.find_nearest(o.data.vertices[i].co)[3] for i in roots]
 midpoints=[(o.data.vertices[i].co+o.data.vertices[j].co)/2 for a in range(0,len(roots),4) for i,j in zip(roots[a:a+3],roots[a+1:a+4])]
 distances.extend(rest.find_nearest(c)[3] for c in midpoints)
 assert max(distances)<.0025,(o.name,max(distances))
 orientation=[]
 up='upper' in o.name
 for i in roots[2:-2]:
  c=o.data.vertices[i].co
  outside=Vector((c.x+.0001,c.y,c.z+(.0006 if up else -.0006)))
  p,*_=rest.ray_cast(Vector((2,outside.y,outside.z)),Vector((-1,0,0)))
  orientation.append(p is not None and p.x>.145)
 assert all(orientation),(o.name,sum(orientation),len(orientation))
 attachment.append({'object':o.name,'root_and_midpoint_nearest_skin_max':max(distances),'upper_on_upper_skin_or_lower_on_lower_skin':all(orientation)})
# Every disconnected strand must have a root anchored to the lid, so no floating fragments remain.
connected=[]
for entry in report['lash_attachment']:
 o=bpy.data.objects[entry['object']];adj=[set() for _ in o.data.vertices]
 for edge in o.data.edges:
  a,b=edge.vertices;adj[a].add(b);adj[b].add(a)
 seen=set();components=[];root_set=set(entry['root_indices'])
 for i in range(len(adj)):
  if i in seen:continue
  stack=[i];seen.add(i);comp=[]
  while stack:
   v=stack.pop();comp.append(v)
   for n in adj[v]:
    if n not in seen:seen.add(n);stack.append(n)
  assert root_set.intersection(comp),(o.name,'Unattached fragment')
  assert len(comp)==48,(o.name,'Incomplete strand',len(comp))
  components.append(comp)
 assert len(components)==entry['strands']
 connected.append({'object':o.name,'strands':len(components),'every_component_has_attached_root':True})
# Eyebrow modifier remains editable and conforms the dense strip to the skin.
brows=[]
for name in ['BROW_L','BROW_R']:
 o=bpy.data.objects[name];e=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh()
 ds=[rest.find_nearest(v.co)[3] for v in m.vertices]
 assert max(ds)<.004,(name,max(ds))
 brows.append({'object':name,'nearest_skin_max':max(ds),'vertices':len(m.vertices)})
 e.to_mesh_clear()

uv={}
for o in bpy.data.collections['04_Brows_lashes'].objects:
 coords=[tuple(round(x,6) for x in v.uv) for v in o.data.uv_layers['HairAtlas'].data]
 uv[o.name]=len(set(coords));assert uv[o.name]>100
assert not bpy.data.objects['P2_OPEN_SOURCE_UNCHANGED'].visible_get()
assert bpy.data.objects['HAIR_latest_v2_fitted_to_P2'].visible_get()
packed=[im.name for im in bpy.data.images if im.source=='FILE' and im.packed_file];assert packed
result={'reopened':True,'default_closed_smile':True,'mouth_morph_sweep':results,'lash_roots':attachment,'brows':brows,'strand_connectivity':connected,'uv_unique_coordinates':uv,'packed_images':packed,'source_preserved':True,'skin_vertex_count_unchanged':report['skin_vertices_before']==report['skin_vertices_after'],'full_face_rig':False,'blink_rig':False,'api_credits':0}
(O/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
