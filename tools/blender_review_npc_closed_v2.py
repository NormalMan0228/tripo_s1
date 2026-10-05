import bpy,json,sys
from pathlib import Path
from mathutils import Vector,Matrix
R=Path(__file__).resolve().parents[1];A=R/'art/characters/npc_cast_closed_v2';key=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'sora';O=A/key
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(O/'model.glb'));sc=bpy.context.scene
meshes=[o for o in sc.objects if o.type=='MESH'];assert meshes and not any(o.type=='ARMATURE' for o in sc.objects)
bpy.context.view_layer.update();points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices];lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)])
height={'sora':1.65,'moru':1.65,'naru':1.55,'haeru':1.85}[key];s=height/(hi.z-lo.z);offset=Vector((-(lo.x+hi.x)/2,-(lo.y+hi.y)/2,-lo.z));T=Matrix.Scale(s,4)@Matrix.Translation(offset)
for o in meshes:
 world=T@o.matrix_world;coords=[world@v.co for v in o.data.vertices];o.parent=None;o.matrix_world=Matrix.Identity(4)
 for v,p in zip(o.data.vertices,coords):v.co=p
 o.data.update()
for o in list(bpy.data.objects):
 if o.type=='EMPTY':bpy.data.objects.remove(o,do_unlink=True)
for im in bpy.data.images:
 if im.has_data and not im.packed_file:im.pack()
stats=[]
for o in meshes:
 o.data.calc_loop_triangles();stats.append({'name':o.name,'vertices':len(o.data.vertices),'triangles':len(o.data.loop_triangles),'uv_layers':len(o.data.uv_layers),'materials':len(o.data.materials),'shape_keys':bool(o.data.shape_keys)})
sc.render.engine='CYCLES';sc.cycles.samples=16;sc.cycles.use_denoising=True;sc.render.resolution_x=720;sc.render.resolution_y=900;sc.render.resolution_percentage=100
world=bpy.data.worlds.new('Studio');sc.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.35,.38,.43,1);world.node_tree.nodes['Background'].inputs[1].default_value=.5
def light(name,pos,power,size):
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);sc.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector((0,0,height*.55))-o.location).to_track_quat('-Z','Y').to_euler()
light('Key',(3,-3,4),450,4);light('Fill',(2,3,2.5),300,3);light('Rim',(-2,1,3),400,3)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.005));floor=bpy.context.object;floor.name='STUDIO_FLOOR';m=bpy.data.materials.new('Floor');m.use_nodes=True;m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.24,.27,.30,1);m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8;floor.data.materials.append(m)
d=bpy.data.cameras.new('ReviewCamera');cam=bpy.data.objects.new('ReviewCamera',d);sc.collection.objects.link(cam);sc.camera=cam;d.type='ORTHO'
def render(name,pos,target,scale):
 cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();d.ortho_scale=scale;sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
target=(0,0,height*.5);render('front',(4,0,height*.5),target,height*1.13);render('angle',(4,-2,height*.6),target,height*1.13);render('back',(-4,0,height*.5),target,height*1.13);render('face',(4,0,height*.88),(0,0,height*.88),height*.32)
cam.location=(4,0,height*.5);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();d.ortho_scale=height*1.13
bpy.ops.object.select_all(action='DESELECT')
for o in meshes:o.select_set(True)
bpy.context.view_layer.objects.active=meshes[0]
bpy.ops.wm.save_as_mainfile(filepath=str(O/(key+'_static.blend')))
bpy.ops.export_scene.gltf(filepath=str(O/(key+'_static.glb')),export_format='GLB',use_selection=True,export_animations=False,export_morph=False)
report={'id':key,'height_m':height,'triangles':sum(x['triangles'] for x in stats),'vertices':sum(x['vertices'] for x in stats),'meshes':stats,'embedded_images':len(bpy.data.images),'face_rig':False,'body_rig':False,'animations':False,'geometry_changes':'Only common scale and grounding; original generated form preserved. No retopology or facial sculpting.','reference':'Generated closed-mouth front/right/back v2','status':'exported_awaiting_visual_review'}
(O/'inspection.json').write_text(json.dumps(report,indent=2));print('STATIC_NPC_EXPORTED',key,report['triangles'])
