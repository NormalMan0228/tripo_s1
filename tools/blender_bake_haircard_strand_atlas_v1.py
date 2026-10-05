"""Render original native Blender strand bundles to a reusable RGBA hair-card atlas."""
import bpy,math,random,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_integrated_face_haircards_v1/haircards';O.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.preferences.filepaths.save_version=0
sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.samples=32;sc.cycles.use_denoising=False
try:
 p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='CUDA';p.get_devices()
 for d in p.devices:d.use=d.type=='CUDA'
 if any(d.type=='CUDA' for d in p.devices):sc.cycles.device='GPU'
except Exception:pass
mats=[]
for i in range(18):
 m=bpy.data.materials.new('Brown_fiber_'+str(i));m.use_nodes=True;n=m.node_tree.nodes['Principled BSDF'];f=.68+i*.043
 n.inputs['Base Color'].default_value=(.080*f,.037*f,.019*f,1);n.inputs['Roughness'].default_value=.65
 # Bake clean strand albedo rather than baking white specular lighting twice.
 e=m.node_tree.nodes.new('ShaderNodeEmission');e.inputs['Color'].default_value=(.080*f,.037*f,.019*f,1)
 m.node_tree.links.new(e.outputs[0],m.node_tree.nodes['Material Output'].inputs['Surface']);mats.append(m)
rng=random.Random(20261005);strands=0
for bundle in range(6):
 d=bpy.data.curves.new('Bundle_'+str(bundle),'CURVE');d.dimensions='3D';d.bevel_depth=.00046;d.bevel_resolution=0;d.resolution_u=1
 for m in mats:d.materials.append(m)
 for i in range(150):
  s=d.splines.new('POLY');s.points.add(47);s.material_index=rng.randrange(len(mats))
  u=(i+.5)/150*2-1;end=rng.uniform(.78,1.0);phase=rng.uniform(-1,1);wave=rng.uniform(.6,1.0)
  for j,p in enumerate(s.points):
   t=j/47;rootwidth=.074;spread=1-.73*t**3
   yy=(bundle-2.5)*.2+u*rootwidth*spread+.009*math.sin(math.pi*t)*math.sin(phase*2+bundle)+.002*math.sin(t*math.pi*3+phase)*t
   z=.70-1.42*t*end;x=.0004*math.sin(t*math.pi)*math.cos(phase)
   p.co=(x,yy,z,1);p.radius=max(.13,(1-t)**.40)*rng.uniform(.92,1.08)
  strands+=1
 o=bpy.data.objects.new('ATLAS_BUNDLE_'+str(bundle),d);sc.collection.objects.link(o)
sc.world=bpy.data.worlds.new('Atlas World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.6
light=bpy.data.lights.new('Diffuse softbox','AREA');light.energy=65;light.size=3;o=bpy.data.objects.new('Diffuse softbox',light);sc.collection.objects.link(o);o.location=(3,-1,1);o.rotation_euler=(Vector((0,0,0))-o.location).to_track_quat('-Z','Y').to_euler()
camera=bpy.data.objects.new('Atlas Camera',bpy.data.cameras.new('Atlas Camera'));sc.collection.objects.link(camera);camera.location=(3,0,0);camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=1.6;sc.camera=camera
sc.render.resolution_x=1536;sc.render.resolution_y=2048;sc.render.resolution_percentage=100;sc.render.film_transparent=True;sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGBA';sc.view_settings.view_transform='Standard';sc.render.filepath=str(O/'strand_atlas_rgba.png')
bpy.ops.wm.save_as_mainfile(filepath=str(O/'strand_atlas_source.blend'));bpy.ops.render.render(write_still=True)
(O/'atlas-manifest.json').write_text(json.dumps({'source':'Native Blender original curve bundles; no existing bitmap edited','strands':strands,'bundles':6,'resolution':[1536,2048],'transparent':True,'uv_columns':6,'root_v':.9375,'tip_v':.05,'paid_api_calls':0},indent=2),encoding='utf-8');print('ATLAS_BAKED')
