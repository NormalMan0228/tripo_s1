"""Developer art: preserve Tripo skin/face, author Haeru's own motion in Blender.

The imported rig is skinning only. No animation service, stock clips or retargeting.
Semantic material assignments change indices only; geometry and UVs are preserved.
"""
import bpy, math, json, sys, colorsys
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/dev-assets/haeru-tripo-p2'
TAU=math.tau
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT/'rig-original.glb'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
body=next(o for o in bpy.context.scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers))
for o in list(bpy.context.scene.objects):
    if o not in [rig,body]:bpy.data.objects.remove(o,do_unlink=True)
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
rig.name='Haeru_Original_Motion_Rig';body.name='Haeru_Skinned_Mesh'
rig.animation_data_clear();rig.animation_data_create()
source=body.data.materials[0]
tex=next(n for n in source.node_tree.nodes if n.type=='TEX_IMAGE' and n.image.name.startswith('Color_'))
pixels=list(tex.image.pixels[:]);w,h=tex.image.size
uv=body.data.uv_layers.active
families=['hair','coat','pants','boots','skin','detail'];samples={k:[] for k in families};counts={k:0 for k in families}
def rgb_at(poly):
    center=sum((uv.data[i].uv for i in poly.loop_indices),Vector((0,0)))/len(poly.loop_indices)
    x=max(0,min(w-1,int(center.x*w)));y=max(0,min(h-1,int(center.y*h)));i=(y*w+x)*4
    return tuple(pixels[i:i+3])
labels=[]
for p in body.data.polygons:
    c=body.matrix_world@p.center;rgb=rgb_at(p);sat=max(rgb)-min(rgb)
    if c.z<.18:part='boots'
    elif c.z<.44 and abs(c.y)<.18:part='pants'
    elif c.z>.77 and rgb[2]>rgb[0]*.90 and sat<.27:part='hair'
    elif c.z>.735 or (abs(c.y)>.16 and c.z<.59):part='skin'
    elif .435<c.z<.74:
        # Ivory undershirt and belt remain on the source textured material.
        part='detail' if (abs(c.y)<.044 and c.x>.058 and max(rgb)-min(rgb)<.075) or c.z<.465 else 'coat'
    else:part='detail'
    labels.append(part);samples[part].append(rgb);counts[part]+=1
palette={'hair':'2d3048','coat':'ad803b','pants':'353c52','boots':'a77437'}
def linear_hex(value):
    def linear(x):return x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4
    return tuple(linear(int(value[i:i+2],16)/255) for i in (0,2,4))
body.data.materials.clear()
for part in families:
    values=samples[part];median=tuple(sorted(v[i] for v in values)[len(values)//2] for i in range(3)) if values else (1,1,1)
    m=source.copy();m.name=part+'__'+''.join(f'{int(c*255):02x}' for c in median)
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    for field,value in [('Metallic',0),('Roughness',.86),('Specular IOR Level',.22)]:
        for link in list(p.inputs[field].links):m.node_tree.links.remove(link)
        p.inputs[field].default_value=value
    if part in palette:
        # Exportable multiply factor retains generated cloth detail and shading.
        target=linear_hex(palette[part]);factor=tuple(min(1.0,target[i]/max(median[i],.02)) for i in range(3))
        links=list(p.inputs['Base Color'].links)
        if links:
            upstream=links[0].from_socket;m.node_tree.links.remove(links[0])
            multiply=m.node_tree.nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY';multiply.inputs[0].default_value=1
            multiply.inputs[2].default_value=(*factor,1);m.node_tree.links.new(upstream,multiply.inputs[1]);m.node_tree.links.new(multiply.outputs[0],p.inputs['Base Color'])
    body.data.materials.append(m)
for p,part in zip(body.data.polygons,labels):p.material_index=families.index(part);p.use_smooth=True
for mod in body.modifiers:
    if mod.type=='ARMATURE':mod.use_deform_preserve_volume=False

# Use reusable analytic IK mathematics, with this character's own contact targets.
helper=(ROOT/'tools/blender_explorer_b.py').read_text(encoding='utf-8')
helper=helper[helper.index('pb=rig.pose.bones;'):helper.index('def pose(kind,t):')]
exec(compile(helper,'analytic_pose_math','exec'),globals())
def pose(kind,t):
    reset();phase=TAU*t/1.25
    cycle=1.25 if kind=='walk' else 4 if kind=='fish' else 6
    hip=pb['Hip'];m=hip.matrix.copy();m.translation+=Vector((0,.004*math.sin(TAU*t/cycle),-.009+.002*math.sin(TAU*t/cycle)))
    if kind=='walk':m.translation.z+=.007*math.cos(phase*2)
    hip.matrix=m;update()
    rotate_inherited('Spine02',rot((0,0,1),2*math.sin(phase) if kind=='walk' else 1.5*math.sin(TAU*t/cycle)))
    rotate_inherited('Head',rot((0,0,1),(2 if kind=='walk' else 8)*math.sin(TAU*t/cycle))@rot((0,1,0),-1.8*math.sin(TAU*t/cycle)))
    for side,sign in [('L',1),('R',-1)]:
        foot=side+'_Foot';target=heads[foot].copy();pitch=0
        if kind=='walk':
            x,z,pitch=footpath(t/1.25+(0 if side=='L' else .5),.18,.045,.64);target+=Vector((x,0,z))
        end=chain(side+'_Thigh',side+'_Calf',foot,target,(1,0,.05))
        pb[foot].matrix=Matrix.Translation(end)@rot((0,1,0),pitch).to_matrix().to_4x4()@rest[foot].to_3x3().to_4x4();update()
        wrist=Vector((.025,sign*.18,.46))
        if kind=='walk':wrist.x-=.042*math.cos(phase+(0 if sign==1 else math.pi));wrist.z+=.005*math.sin(phase)
        if kind in ('fish','greet') and side=='R':wrist=Vector((.125,-.12,.57))
        if kind=='fish':wrist.x+=.003*math.sin(TAU*t/4);wrist.z+=.006*math.sin(TAU*t/4)
        if kind=='greet' and side=='L':
            amount=envelope(t,.12,.6,1.55,2.2)
            wrist=wrist.lerp(Vector((.05,.22,.80)),amount)
        chain(side+'_Upperarm',side+'_Forearm',side+'_Hand',wrist,(-.65,sign*.7,-.2))
        if kind=='greet' and side=='L':
            # Turn the relaxed fingers upward with the palm facing the listener.
            # The former inherited wrist left the hand curled toward his face.
            raised=envelope(t,.12,.6,1.55,2.2)
            hand=pb['L_Hand'];current=hand.matrix.copy()
            rest_direction=(rig.data.bones['L_Hand'].tail_local-heads['L_Hand']).normalized()
            upright=rest_direction.rotation_difference(Vector((.02,0,1)).normalized())@rest['L_Hand'].to_quaternion()
            upright=rot((0,0,1),180)@upright
            q=current.to_quaternion().slerp(upright,raised)
            hand.matrix=Matrix.Translation(current.translation)@q.to_matrix().to_4x4();update()
            rotate_inherited('L_Hand',rot((1,0,0),12*math.sin(TAU*t*2)*envelope(t,.5,.75,1.45,1.65)))
    update()

scene=bpy.context.scene;scene.render.fps=24
clips=[('idle','idle',144),('walk','walk',30),('fishing','fish',96),('greet','greet',60)]
actions={};manifest={}
for name,kind,frames in clips:
    rig.animation_data.action=None;previous={}
    for frame in range(frames+1):
        pose(kind,frame/24)
        for b in pb:
            q=b.rotation_quaternion
            if b.name in previous and q.dot(previous[b.name])<0:q.negate()
            previous[b.name]=q.copy()
            b.keyframe_insert('location',frame=frame+1,group=b.name);b.keyframe_insert('rotation_quaternion',frame=frame+1,group=b.name)
    action=rig.animation_data.action;action.name=name;action.use_fake_user=True;actions[name]=action
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for key in fc.keyframe_points:key.interpolation='LINEAR'
    manifest[name]={'duration':frames/24,'loop':kind!='greet','authored_in_blender':True}
rig.animation_data.action=actions['idle'];scene.frame_start=1;scene.frame_end=145;scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(ROOT/'game/assets/haeru_v1.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_anim_slide_to_zero=True)

# Neutral review stage. The face remains exactly the original weighted mesh.
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=800;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.12,.16,.15,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
scene.view_settings.view_transform='AgX'
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.008));floor=bpy.context.object
mat=bpy.data.materials.new('Sage_review_floor');mat.diffuse_color=(.12,.18,.17,1);floor.data.materials.append(mat)
target=Vector((0,0,.53))
for position,energy,size in [((2,-3,3),130,3),((2,3,2),65,3),((-2,1,2.5),150,2)]:
    bpy.ops.object.light_add(type='AREA',location=position);o=bpy.context.object;o.data.energy=energy;o.data.size=size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(3,-2,1.35));cam=bpy.context.object;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.32;scene.camera=cam
bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/source/haeru_v1.blend'),compress=True)
(OUT/'animation-manifest.json').write_text(json.dumps({'geometry_source':'Tripo P2-20260801','rig_source':'Tripo v1.0-20240301','credits_generation':120,'credits_rig':25,'face':'Original geometry, UV, skin weights and texture; no added face mesh or morphs','bones':len(pb),'semantic_faces':counts,'clips':manifest},indent=2),encoding='utf-8')
for name,kind,frames in clips:
    rig.animation_data.action=actions[name];scene.frame_set(25 if name=='greet' else 1);scene.render.filepath=str(OUT/('haeru-'+name+'.png'));bpy.ops.render.render(write_still=True)
print('HAERU_AUTHORING_COMPLETE',json.dumps(manifest))
