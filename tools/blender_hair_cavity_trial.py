"""Non-destructive source preservation; make a separate interior-clearance trial."""
from pathlib import Path
import bpy, math, json, hashlib
from mathutils import Vector
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/characters/explorer_b_faceit_comparison_p2_v1'
OUT=BASE/'hair_cavity_trial';OUT.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
source=BASE/'hair_v2/model.fbx';digest=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.import_scene.fbx(filepath=str(source),use_anim=False)
hair=next(o for o in bpy.context.scene.objects if o.type=='MESH')
bpy.context.view_layer.objects.active=hair
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
hair.name='Hair_Interior_Clearance_Trial'
solid=hair.modifiers.new('Give open surfaces thickness before volume repair','SOLIDIFY');solid.thickness=.008;solid.offset=0;solid.use_even_offset=True
bpy.ops.object.modifier_apply(modifier=solid.name)
rem=hair.modifiers.new('Unify intersecting internal surfaces','REMESH');rem.mode='VOXEL';rem.voxel_size=.005;rem.use_smooth_shade=True
bpy.ops.object.modifier_apply(modifier=rem.name)
print('REMESH',len(hair.data.polygons),flush=True)
# One continuous cutter: open-bottom clearance volume, rounded crown.
N=128;R=40;verts=[];faces=[]
for j in range(R+1):
    if j==0:r=1.;z=-.75
    else:
        angle=(j-1)/(R-1)*(math.pi/2-.002)
        r=math.cos(angle);z=.04+.335*math.sin(angle)
    for i in range(N):
        a=2*math.pi*i/N;verts.append((-.035+.315*r*math.cos(a),.35*r*math.sin(a),z))
for j in range(R):
    for i in range(N):
        a=j*N+i;b=j*N+(i+1)%N;faces.append((a,b,b+N,a+N))
faces.append(tuple(reversed(range(N))));faces.append(tuple(R*N+i for i in range(N)))
me=bpy.data.meshes.new('ClearanceVolume');me.from_pydata(verts,[],faces);me.update()
cutter=bpy.data.objects.new('Clearance_Volume',me);bpy.context.scene.collection.objects.link(cutter)
bo=hair.modifiers.new('Remove inward protrusions','BOOLEAN');bo.operation='DIFFERENCE';bo.solver='FAST';bo.object=cutter
bpy.context.view_layer.objects.active=hair;bpy.ops.object.modifier_apply(modifier=bo.name)
bpy.data.objects.remove(cutter,do_unlink=True)
for p in hair.data.polygons:p.use_smooth=True
mat=bpy.data.materials.new('Neutral_Clay');mat.diffuse_color=(.42,.46,.5,1);mat.use_nodes=True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=mat.diffuse_color
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.7
hair.data.materials.clear();hair.data.materials.append(mat)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
world=bpy.data.worlds.new('Studio');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.6,.65,.7,1);world.node_tree.nodes['Background'].inputs[1].default_value=.5;scene.world=world
for name,pos,power in [('Key',(2,-3,3),350),('Fill',(3,3,-2),280),('Rim',(-3,1,2),400)]:
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.size=3
    ob=bpy.data.objects.new(name,d);scene.collection.objects.link(ob);ob.location=pos;ob.rotation_euler=(-ob.location).to_track_quat('-Z','Y').to_euler();ob.hide_set(True)
cam=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(cam);scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=1.3
def camera(pos):
    cam.location=pos;cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler()
camera((2.4,-1,-2.8))
for o in bpy.context.selected_objects:o.select_set(False)
hair.select_set(True);bpy.context.view_layer.objects.active=hair
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            s=area.spaces.active;s.shading.type='SOLID';s.shading.show_cavity=True
            s.region_3d.view_location=(0,0,0);s.region_3d.view_distance=1.8;s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_perspective='ORTHO'
cam.hide_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'hair_cavity_trial.blend'))
for name,pos in [('inside',(2.4,-1,-2.8)),('front',(4,0,0)),('back',(-4,0,0))]:
    camera(pos);scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
counts=Counter(tuple(sorted(e)) for p in hair.data.polygons for e in p.edge_keys)
report={'source_sha256':digest,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==digest,'vertices':len(hair.data.vertices),'polygons':len(hair.data.polygons),'boundary_edges':sum(x==1 for x in counts.values()),'overused_edges':sum(x>2 for x in counts.values()),'method':'solidify 0.008 offset 0, voxel 0.005, FAST rounded open-bottom cavity subtraction','production_ready':False,'head_fit_verified':False,'UVs_require_rebuild':True,'credits_used':0}
(OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
