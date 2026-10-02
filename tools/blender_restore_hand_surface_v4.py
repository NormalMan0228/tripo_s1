import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/characters/explorer-b-hand-v4'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer-b-hand.blend'))
scene=bpy.context.scene;body=bpy.data.objects['Explorer_B_SkinnedMesh'];rig=bpy.data.objects['Explorer_B_Body_Rig']
new_weights={tuple(round(x,6) for x in v.co):{body.vertex_groups[g.group].name:g.weight for g in v.groups} for v in body.data.vertices if abs(v.co.y)>.305}
with bpy.data.libraries.load(str(ROOT/'artifacts/characters/explorer-b-v1/explorer-b-custom.blend'),link=False) as (src,dst):dst.objects=['Explorer_B_SkinnedMesh']
original=dst.objects[0]
# The old linear split created dense flat patches. Restore the original smooth-normal surface.
body.data=original.data.copy()
for values in new_weights.values():
    for name in values:
        if name not in body.vertex_groups:body.vertex_groups.new(name=name)
changed=0
for v in body.data.vertices:
    if abs(v.co.y)<=.305:continue
    key=tuple(round(x,6) for x in v.co)
    assert key in new_weights
    for i in [g.group for g in v.groups]:body.vertex_groups[i].remove([v.index])
    for name,w in new_weights[key].items():body.vertex_groups[name].add([v.index],w,'REPLACE')
    changed+=1
rig.animation_data.action=bpy.data.actions['Hands_Open_Grasp'];scene.frame_set(25)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer-b-hand.blend'))
scene.cycles.samples=14;scene.render.resolution_x=720;scene.render.resolution_y=720
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
scene.cycles.device='GPU';cam=scene.camera;target=Vector((.09,.17,.65));cam.location=target+Vector((2,-3,2));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.23
scene.render.filepath=str(OUT/'after-original-surface.png');bpy.ops.render.render(write_still=True)
print('ORIGINAL_SURFACE_RESTORED',len(body.data.vertices),changed)
