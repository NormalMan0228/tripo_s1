import bpy,bmesh,json,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_young_bob_face_cleanup_v3/assembly';O.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_face_multiview_meshhair_v2/head/explorer_b_integrated_face_open_workbench.blend'))
o=bpy.data.objects['FACE_Tripo_integrated_0'];bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.separate(type='LOOSE');bpy.ops.object.mode_set(mode='OBJECT')
parts=sorted([a for a in bpy.context.selected_objects if a.type=='MESH'],key=lambda a:-len(a.data.vertices));report=[]
for i,a in enumerate(parts):
 a.name='PART_%02d_%d'%(i,len(a.data.vertices));lo=[min(v.co[j] for v in a.data.vertices) for j in range(3)];hi=[max(v.co[j] for v in a.data.vertices) for j in range(3)];report.append({'name':a.name,'vertices':len(a.data.vertices),'faces':len(a.data.polygons),'bounds':[lo,hi]})
skin=parts[0];skin.data.calc_loop_triangles();tree=BVHTree.FromPolygons([v.co for v in skin.data.vertices],[t.vertices for t in skin.data.loop_triangles],all_triangles=True)
profile=[]
for z in np.linspace(-.22,.015,471):
 p,*_=tree.ray_cast(Vector((1,0,z)),Vector((-1,0,0)));profile.append([float(z),p.x if p else None])
(O/'components.json').write_text(json.dumps({'parts':report,'center_profile':profile},indent=2),encoding='utf-8');bpy.ops.wm.save_as_mainfile(filepath=str(O/'component_probe.blend'))
sc=bpy.context.scene;sc.cycles.samples=12;sc.render.resolution_x=1000;sc.render.resolution_y=800
cam=sc.camera;target=Vector((.18,0,-.08));cam.location=target+Vector((3,-.7,.2));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.42
# Show isolated oral components with label colors for semantic diagnosis.
for a in parts:
 a.hide_render=not (a!=skin and max(v.co.z for v in a.data.vertices)<.02)
 if not a.hide_render:
  i=parts.index(a);m=bpy.data.materials.new(a.name);m.diffuse_color=((i*.37)%1,(i*.61)%1,(i*.83)%1,1);m.use_nodes=True;m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=m.diffuse_color;a.data.materials.clear();a.data.materials.append(m)
sc.render.filepath=str(O/'oral_components.png');bpy.ops.render.render(write_still=True)
print('PROBE_READY',O)
