import bpy,bmesh,json,addon_utils
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_face_animated_v6';A.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_clean_edges_v5/assembly/explorer_b_clean_edges_v5.blend'));o=bpy.data.objects['FACE_skin_eyelids_lashes'];m=o.data
bm=bmesh.new();bm.from_mesh(m);bm.verts.ensure_lookup_table();seen=set();groups=[]
for e in bm.edges:
 if not e.is_boundary or e in seen:continue
 stack=[e];seen.add(e);g=[]
 while stack:
  q=stack.pop();g.append(q)
  for v in q.verts:
   for a in v.link_edges:
    if a.is_boundary and a not in seen:seen.add(a);stack.append(a)
 vs=set(v for a in g for v in a.verts);groups.append({'edges':len(g),'verts':[v.index for v in vs],'min':[min(v.co[k] for v in vs) for k in range(3)],'max':[max(v.co[k] for v in vs) for k in range(3)]})
(A/'boundary-probe.json').write_text(json.dumps(groups,indent=2));print('BOUNDARIES',json.dumps([{k:v for k,v in a.items() if k!='verts'} for a in groups if a['edges']>8]));addon_utils.enable('rigify',default_set=False,persistent=False);import rigify;print('RIGIFY',rigify.__file__);bm.free()
