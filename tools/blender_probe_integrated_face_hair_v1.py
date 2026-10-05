"""Preserve and inspect the new textured Tripo face without replacing its facial parts."""
import bpy,bmesh,json,math,hashlib
from pathlib import Path
from mathutils import Vector,Matrix
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_integrated_face_haircards_v1/head'
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.preferences.filepaths.save_version=0
sc=bpy.context.scene
def col(name):
 c=bpy.data.collections.new(name);sc.collection.children.link(c);return c
srcCol=col('90_TRIPO_FACE_preserved');work=col('01_Integrated_face');studio=col('99_Studio')
bpy.ops.import_scene.fbx(filepath=str(O/'model.fbx'),use_anim=False)
working=[];entries=[]
for i,s in enumerate([o for o in sc.objects if o.type=='MESH']):
 s.name='SOURCE_Tripo_face_'+str(i)
 for c in list(s.users_collection):c.objects.unlink(s)
 srcCol.objects.link(s)
 o=s.copy();o.data=s.data.copy();work.objects.link(o);o.name='FACE_Tripo_integrated_'+str(i)
 o.data.transform(o.matrix_world);o.parent=None;o.matrix_world=Matrix.Identity(4)
 for p in o.data.polygons:p.use_smooth=True
 s.hide_render=True;s.hide_set(True);s.hide_select=True
 bm=bmesh.new();bm.from_mesh(o.data);bm.verts.ensure_lookup_table();seen=set();groups=[]
 for v in bm.verts:
  if v.index in seen:continue
  stack=[v];seen.add(v.index);g=[]
  while stack:
   a=stack.pop();g.append(a)
   for e in a.link_edges:
    b=e.other_vert(a)
    if b.index not in seen:seen.add(b.index);stack.append(b)
  groups.append({'vertices':len(g),'bounds':[[min(v.co[j] for v in g),max(v.co[j] for v in g)] for j in range(3)]})
 entries.append({'object':o.name,'vertices':len(bm.verts),'faces':len(bm.faces),'quads':sum(len(f.verts)==4 for f in bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'components':sorted(groups,key=lambda g:-g['vertices']),'materials':[m.name for m in o.data.materials]})
 bm.free();working.append(o)
# P2 quad FBX references external textures. Obtain the same generated maps from
# a portable conversion, then assign its material while preserving the quad UVs.
textureCol=col('91_Texture_payload_hidden')
existing=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(O/'texture_payload/model.glb'))
payload=[o for o in bpy.data.objects if o not in existing]
payload_mats=list(dict.fromkeys(m for o in payload if o.type=='MESH' for m in o.data.materials))
assert payload_mats, 'No embedded generated texture material'
for o in list(srcCol.objects)+working:
 o.data.materials.clear()
 for m in payload_mats:o.data.materials.append(m)
for o in payload:
 for c in list(o.users_collection):c.objects.unlink(o)
 textureCol.objects.link(o);o.hide_render=True;o.hide_set(True);o.hide_select=True
for e,o in zip(entries,working):e['materials']=[m.name for m in o.data.materials]
for m in list(bpy.data.materials):
 if m.users==0:bpy.data.materials.remove(m)

import numpy as np
source=working[0]
print('HEAD_BOUND',[[min(v.co[j] for v in source.data.vertices),max(v.co[j] for v in source.data.vertices)] for j in range(3)])
print('COMPONENTS',json.dumps(entries))
bpy.ops.import_scene.gltf(filepath=str(R/'art/characters/explorer_b_integrated_face_haircards_v1/hair/model.glb'))
hair=next(o for o in sc.objects if o.type=='MESH' and o not in working and o.name not in srcCol.objects and o not in payload)
hair.data.transform(hair.matrix_world);hair.matrix_world=Matrix.Identity(4)
print('HAIR_BOUND',[[min(v.co[j] for v in hair.data.vertices),max(v.co[j] for v in hair.data.vertices)] for j in range(3)])
print('HAIR_COUNTS',len(hair.data.vertices),len(hair.data.polygons))
out=R/'art/characters/explorer_b_integrated_face_haircards_v1/hair'
(out/'bounds.json').write_text(json.dumps({'bounds':[[min(v.co[j] for v in hair.data.vertices),max(v.co[j] for v in hair.data.vertices)] for j in range(3)],'vertices':len(hair.data.vertices),'faces':len(hair.data.polygons)}),encoding='utf-8')
