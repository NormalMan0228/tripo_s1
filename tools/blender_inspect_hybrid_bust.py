import bpy,json,math
from pathlib import Path
from mathutils import Vector,Matrix
R=Path(__file__).resolve().parents[1]
O=R/'art/characters/explorer_b_hybrid_bust_v1'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(O/'head/model.fbx'),use_anim=False)
meshes=[o for o in bpy.data.objects if o.type=='MESH']
info=[]
for o in meshes:
    coords=[o.matrix_world@v.co for v in o.data.vertices]
    info.append({'name':o.name,'verts':len(coords),'polys':len(o.data.polygons),'bounds':[[min(v[i] for v in coords),max(v[i] for v in coords)] for i in range(3)],'matrix':[list(r) for r in o.matrix_world]})
(O/'head/mesh-inspection.json').write_text(json.dumps(info,indent=2))
print(json.dumps(info))
for o in meshes:
    o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
    for p in o.data.polygons:p.use_smooth=True
    m=bpy.data.materials.new('Clay');m.diffuse_color=(.62,.43,.32,1);o.data.materials.clear();o.data.materials.append(m)
coords=[v.co for o in meshes for v in o.data.vertices]
center=Vector([(min(v[i] for v in coords)+max(v[i] for v in coords))/2 for i in range(3)])
height=max(v.z for v in coords)-min(v.z for v in coords)
sc=bpy.context.scene
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=900;sc.render.resolution_y=1000;sc.render.resolution_percentage=100
sc.world=bpy.data.worlds.new('World');sc.world.color=(.12,.12,.12)
sc.display.shading.light='STUDIO';sc.display.shading.color_type='MATERIAL';sc.display.shading.show_shadows=True;sc.display.shading.show_cavity=True
bpy.ops.object.camera_add(location=center+Vector((3,0,0))*height)
c=bpy.context.object;c.rotation_euler=(center-c.location).to_track_quat('-Z','Y').to_euler();c.data.type='ORTHO';c.data.ortho_scale=height*1.15;sc.camera=c
sc.render.filepath=str(O/'head/front_inspection.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(O/'head/inspection.blend'))
