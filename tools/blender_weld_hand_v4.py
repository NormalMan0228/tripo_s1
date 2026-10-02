import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/characters/explorer-b-hand-v4'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer-b-hand.blend'))
body=bpy.data.objects['Explorer_B_SkinnedMesh'];rig=bpy.data.objects['Explorer_B_Body_Rig'];scene=bpy.context.scene
before=len(body.data.vertices)
bm=bmesh.new();bm.from_mesh(body.data)
hand=[v for v in bm.verts if abs(v.co.y)>.303 and .67<v.co.z<.74]
bmesh.ops.remove_doubles(bm,verts=hand,dist=.000001)
for e in bm.edges:
    if all(abs(v.co.y)>.303 and .67<v.co.z<.74 for v in e.verts):e.smooth=True
bm.to_mesh(body.data);bm.free();body.data.update()
normals=[tuple(n.vector) for n in body.data.corner_normals]
for i,loop in enumerate(body.data.loops):
    p=body.data.vertices[loop.vertex_index].co
    if abs(p.y)>.303 and .67<p.z<.74:normals[i]=(0,0,0)
body.data.normals_split_custom_set(normals)
bpy.context.view_layer.update()
rig.animation_data.action=bpy.data.actions['Hands_Open_Grasp'];scene.frame_set(25)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer-b-hand.blend'))
scene.cycles.samples=14;scene.render.resolution_x=720;scene.render.resolution_y=720
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
scene.cycles.device='GPU';cam=scene.camera;target=Vector((.09,.17,.65));cam.location=target+Vector((2,-3,2));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.23
scene.render.filepath=str(OUT/'after-weld.png');bpy.ops.render.render(write_still=True)
print('WELD',before,len(body.data.vertices))
