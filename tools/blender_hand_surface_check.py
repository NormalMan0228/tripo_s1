import bpy,json
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/characters/explorer-b-hand-v4'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer-b-hand.blend'))
scene=bpy.context.scene;body=bpy.data.objects['Explorer_B_SkinnedMesh'];rig=bpy.data.objects['Explorer_B_Body_Rig']
with bpy.data.libraries.load(str(ROOT/'artifacts/characters/explorer-b-v1/explorer-b-custom.blend'),link=False) as (src,dst):dst.objects=['Explorer_B_SkinnedMesh']
original=dst.objects[0];bvh=BVHTree.FromPolygons([v.co for v in original.data.vertices],[list(p.vertices) for p in original.data.polygons])
distances=[bvh.find_nearest(v.co)[3] for v in body.data.vertices if abs(v.co.y)>.31]
print('HAND_REST_DISTANCE',min(distances),max(distances),sum(distances)/len(distances),flush=True)
rig.animation_data_clear()
for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
bpy.context.view_layer.update()
scene.cycles.samples=12;scene.render.resolution_x=720;scene.render.resolution_y=720
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
scene.cycles.device='GPU';cam=scene.camera;target=Vector((0,.34,.70));cam.location=target+Vector((0,0,3));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.145
scene.render.filepath=str(OUT/'rest-hand.png');bpy.ops.render.render(write_still=True)
