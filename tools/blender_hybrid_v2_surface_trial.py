import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_hybrid_bust_v2'
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_hybrid_bust_v1/explorer_b_hybrid_bust_v1.blend'))
o=bpy.data.objects['HEAD_P2_CLEANUP'];bm=bmesh.new();bm.from_mesh(o.data);bm.verts.ensure_lookup_table();seen=set();groups=[]
for v in bm.verts:
 if v.index in seen:continue
 stack=[v];seen.add(v.index);g=[]
 while stack:
  a=stack.pop();g.append(a)
  for e in a.link_edges:
   b=e.other_vert(a)
   if b.index not in seen:seen.add(b.index);stack.append(b)
 groups.append(g)
groups.sort(key=len,reverse=True)
for i,g in enumerate(groups[1:3]):
 ids={v.index:j for j,v in enumerate(g)};fs=list(set(f for v in g for f in v.link_faces));m=bpy.data.meshes.new('Eye_source');m.from_pydata([v.co[:] for v in g],[],[[ids[v.index] for v in f.verts] for f in fs]);ob=bpy.data.objects.new('EYE_SOURCE_'+str(i),m);bpy.context.collection.objects.link(ob)
 for p in m.polygons:p.use_smooth=True
 ob.data.materials.append(o.data.materials[0])
bmesh.ops.delete(bm,geom=[v for g in groups[1:] for v in g],context='VERTS');bm.to_mesh(o.data);bm.free()
bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
o.data.remesh_voxel_size=.0018;o.data.use_remesh_preserve_volume=True;bpy.ops.object.voxel_remesh()
print('REMESH',len(o.data.vertices),len(o.data.polygons))
mod=o.modifiers.new('Very_light_surface_relax','SMOOTH');mod.factor=.25;mod.iterations=3;bpy.ops.object.modifier_apply(modifier=mod.name)
mod=o.modifiers.new('Review_polycount','DECIMATE');mod.ratio=min(1,24000/len(o.data.polygons));bpy.ops.object.modifier_apply(modifier=mod.name)
for p in o.data.polygons:p.use_smooth=True
print('FINAL',len(o.data.vertices),len(o.data.polygons))
for ob in bpy.data.objects:
 if ob.type=='MESH' and ob!=o and not ob.name.startswith('EYE_SOURCE'):ob.hide_render=True
sc=bpy.context.scene;sc.render.engine='BLENDER_WORKBENCH';sc.display.shading.show_cavity=False
sc.render.filepath=str(O/'surface_trial.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(O/'surface_trial.blend'))
for z in [i/1000 for i in range(-110,-19,5)]:
 hit,loc,n,idx=o.ray_cast(Vector((2,0,z)),Vector((-1,0,0)));print('PROFILE',z,loc.x if hit else None)
