"""Render the real before/after sculpt files and stored masks; no mesh edits."""
import bpy, sys, argparse, math, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_fullbody_v2/05_sculpt_trial'
p=argparse.ArgumentParser();p.add_argument('--stage',choices=['before','after','cut-mask','face-mask','wrist-mask'],required=True)
p.add_argument('--views',nargs='+',default=['front','angle','side','back','face','neck','wrist']);args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
files={'before':'02_fitted_before_brush.blend','after':'03_sculpt_candidate.blend','cut-mask':'01_cut_masks.blend','face-mask':'mask_face.blend','wrist-mask':'mask_wrist.blend'}
bpy.ops.wm.open_mainfile(filepath=str(OUT/files[args.stage]),load_ui=False,use_scripts=False)
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
try:
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='CUDA'
 scene.cycles.device='GPU' if any(d.type=='CUDA' for d in prefs.devices) else 'CPU'
except Exception:scene.cycles.device='CPU'
scene.render.resolution_x=1000;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
scene.render.film_transparent=False
world=bpy.data.worlds.new('Sculpt Review Studio');world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.53,.55,.58,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.5;scene.world=world
meshes=[o for o in scene.objects if o.type=='MESH' and not o.hide_render]
if args.stage=='cut-mask':
 other=bpy.data.objects.get('Arm_NegY')
 if other:other.hide_render=False;meshes.append(other)
if args.stage.endswith('mask'):
 m=bpy.data.materials.new('Stored sculpt mask diagnostic - orange masked');m.use_nodes=True
 nodes=m.node_tree.nodes;attr=nodes.new('ShaderNodeAttribute');attr.attribute_name='review_mask'
 mix=nodes.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(.16,.29,.39,1);mix.inputs[2].default_value=(.95,.31,.055,1)
 m.node_tree.links.new(attr.outputs['Fac'],mix.inputs[0]);m.node_tree.links.new(mix.outputs[0],nodes.get('Principled BSDF').inputs['Base Color'])
 nodes.get('Principled BSDF').inputs['Roughness'].default_value=.8
 for o in meshes:
  o.data.materials.clear();o.data.materials.append(m)
  for f in o.data.polygons:f.material_index=0
for name,offset,power,size in [('Key',(3,-3,4),650,3),('Fill',(2,3,2),370,2.5),('Rim',(-3,0,3),550,2)]:
 light=bpy.data.lights.new(name,'AREA');light.energy=power;light.shape='DISK';light.size=size
 o=bpy.data.objects.new(name,light);scene.collection.objects.link(o);o.location=Vector((0,0,1))+Vector(offset)
 o.rotation_euler=(Vector((0,0,1))-o.location).to_track_quat('-Z','Y').to_euler();o.hide_select=True
camera=bpy.data.objects.new('Review Camera',bpy.data.cameras.new('Review Camera'));scene.collection.objects.link(camera);scene.camera=camera
camera.data.type='ORTHO';camera.data.clip_start=.01;camera.data.clip_end=30;camera.hide_select=True
views={'front':((0,0,.89),(4,0,0),1.96), 'angle':((0,0,.89),(4,-2.0,.6),1.96),
 'side':((0,0,.89),(0,-4,0),1.96),'back':((0,0,.89),(-4,0,0),1.96),
 'face':((.0,0,1.515),(4,0,.0),.455),'neck':((.02,0,1.343),(4,-1,.2),.185),
 'wrist':((.02,.392,.84),(4,1.2,.5),.26),'hand':((.015,.431,.80),(4,0,.2),.27)}
for name in args.views:
 center,offset,scale=views[name];center=Vector(center)
 camera.location=center+Vector(offset);camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=scale
 scene.render.resolution_x=1000;scene.render.resolution_y=1100 if name in ('front','angle','side','back') else 1000
 scene.render.filepath=str(OUT/(args.stage+'-'+name+'.png'));bpy.ops.render.render(write_still=True)
 print('RENDERED',args.stage,name,flush=True)
