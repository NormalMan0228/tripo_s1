import bpy
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_tripo_retopo_v14';bpy.ops.wm.open_mainfile(filepath=str(A/'face_retopology_assembly_v14.blend'));sc=bpy.context.scene;o=bpy.data.objects['FACE_Tripo_Smart_Retopo_v14']
c=bpy.data.curves.new('Provider_topology_lines','CURVE');c.dimensions='3D';c.resolution_u=1;c.bevel_depth=.0005;c.bevel_resolution=0
mat=bpy.data.materials.new('Topology_green');mat.use_nodes=True;bs=mat.node_tree.nodes['Principled BSDF'];bs.inputs['Base Color'].default_value=(.005,.02,.008,1)
bpy.context.view_layer.update()
coords=[o.matrix_world@v.co-(o.matrix_world.to_3x3()@v.normal).normalized()*.002 for v in o.data.vertices]
print('WIRE_DEBUG',len(o.data.edges),[min(p[i] for p in coords) for i in range(3)],[max(p[i] for p in coords) for i in range(3)])
for e in o.data.edges:
 s=c.splines.new('POLY');s.points.add(1)
 for p,i in zip(s.points,e.vertices):p.co=(*coords[i],1)
w=bpy.data.objects.new('TEMP_topology',c);sc.collection.objects.link(w);c.materials.append(mat)
bpy.data.objects['HAIR_user_brown_v11'].hide_render=True;cam=sc.camera;t=Vector((0,0,.035));cam.location=t+Vector((3,0,0));cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.84;sc.cycles.samples=16;sc.render.filepath=str(A/'wire.png');bpy.ops.render.render(write_still=True)
