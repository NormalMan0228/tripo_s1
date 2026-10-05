import bpy,json,colorsys
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_clean_edges_v5/assembly';bpy.ops.wm.open_mainfile(filepath=str(A/'baseline.blend'));sc=bpy.context.scene;o=bpy.data.objects['FACE_skin_eyelids_lashes'];gs=json.loads((A/'lash-uv-islands.json').read_text())
for i,g in enumerate(gs):
 if g['faces']>200:continue
 m=bpy.data.materials.new('UV_ISLAND_%02d'%i);m.diffuse_color=(*colorsys.hsv_to_rgb(i/18,.95,.8),1);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=m.diffuse_color;b.inputs['Roughness'].default_value=.7;o.data.materials.append(m)
 for p in g['indices']:o.data.polygons[p].material_index=len(o.data.materials)-1
bpy.data.objects['HAIR_sculptural_bob_mesh'].hide_render=True;cam=sc.camera;target=Vector((.18,0,.145));cam.location=target+Vector((3,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.53;sc.cycles.samples=12;sc.render.filepath=str(A/'debug_islands.png');bpy.ops.render.render(write_still=True)
