"""Render actual generated cottage from four directions before map placement."""
import bpy, math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/detail-map-20261003/map-orientation';OUT.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'artifacts/detail-map-20261003/modules/ai_teal-cottage.glb'))
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12
scene.render.resolution_x=600;scene.render.resolution_y=600;scene.render.resolution_percentage=100
scene.world.color=(.5,.5,.5);scene.view_settings.view_transform='AgX'
target=Vector((0,0,1.8))
bpy.ops.object.light_add(type='AREA',location=(0,-6,10));light=bpy.context.object;light.data.energy=1600;light.data.size=8;light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=7;scene.camera=cam
for i,(x,y) in enumerate([(0,-9),(9,0),(0,9),(-9,0)]):
 cam.location=Vector((x,y,6));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(OUT/f'direction-{i}.png');bpy.ops.render.render(write_still=True)
