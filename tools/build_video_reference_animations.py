"""Retarget the measured video channels to the same cohesive B explorer skin.

No Tripo/Mixamo preset motion is used. Side-view depth lanes and joint limits
are authored corrections, while timing and sagittal motion come from tracking.
"""
import bpy
import json
import math
from pathlib import Path
import numpy as np
from mathutils import Vector, Matrix, Quaternion

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/video-motion-20261003'
DEST=ROOT/'labs/video_motion_lab/assets'
DEST.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'artifacts/production-lab-20261003/explorer_b_reusable.blend'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'
        and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
for obj in list(bpy.context.scene.objects):
    if obj.type=='MESH' and obj not in meshes:bpy.data.objects.remove(obj,do_unlink=True)
for action in list(bpy.data.actions):bpy.data.actions.remove(action)
rig.animation_data_clear();rig.animation_data_create()
rig.name='Explorer_B_Video_Reference_Rig'
scene=bpy.context.scene;scene.render.fps=60
bones=list(rig.pose.bones)
rest={b.name:b.bone.matrix_local.copy() for b in bones}
offset={b.name:(rest[b.parent.name].inverted()@rest[b.name] if b.parent else rest[b.name]) for b in bones}
global_pose={};audit={};actions={}

def reset_pose():
    for bone in bones:
        bone.rotation_mode='QUATERNION';bone.matrix_basis=Matrix.Identity(4)
    refresh()

def refresh():
    for b in bones:
        global_pose[b.name]=(global_pose[b.parent.name] if b.parent else Matrix.Identity(4))@offset[b.name]@b.matrix_basis

def orient(name,desired):
    b=rig.pose.bones[name]
    parent=global_pose[b.parent.name] if b.parent else Matrix.Identity(4)
    base=(parent@offset[name]).to_quaternion()
    b.rotation_quaternion=base.inverted()@desired
    refresh()

def planar(name,angle,spread=0.0):
    b=rig.pose.bones[name]
    original=(b.bone.tail_local-b.bone.head_local).normalized()
    direction=Vector((math.cos(angle),spread,math.sin(angle))).normalized()
    desired=original.rotation_difference(direction)@rest[name].to_quaternion()
    orient(name,desired)

# Cache linear-blend-skinning influences of actual low boot vertices.
sole_sets={}
for side in ('L','R'):
    records=[]
    foot_head=rig.data.bones[side+'_Foot'].head_local
    for mesh in meshes:
        for vertex in mesh.data.vertices:
            influences=[(mesh.vertex_groups[g.group].name,g.weight) for g in vertex.groups
                        if mesh.vertex_groups[g.group].name in rest and g.weight>1e-6]
            foot_weight=sum(w for n,w in influences if n in (side+'_Foot',side+'_ToeBase'))
            if foot_weight>.45 and vertex.co.z<foot_head.z+.006:
                records.append((np.array([*vertex.co,1.0]),influences))
    if not records:raise RuntimeError('No weighted boot sole samples: '+side)
    sole_sets[side]=records

def soles():
    skin={n:np.array(global_pose[n]@rest[n].inverted()) for n in rest}
    result={}
    for side,vertices in sole_sets.items():
        positions=[]
        for position,influences in vertices:
            v=sum((skin[n]@position)*w for n,w in influences)/sum(w for _,w in influences)
            positions.append(v[:3])
        points=np.asarray(positions)
        bottom=points[points[:,2]<np.quantile(points[:,2],.08)+.002]
        result[side]={'z':float(points[:,2].min()),'x':float(bottom[:,0].mean()),'y':float(bottom[:,1].mean())}
    return result

def record_pose():
    return {b.name:(b.location.copy(),b.rotation_quaternion.copy(),b.scale.copy()) for b in bones}

def write_action(name,samples):
    rig.animation_data.action=None
    previous={}
    for i,sample in enumerate(samples):
        for b in bones:
            location,q,scale=sample[b.name]
            b.location=location;b.rotation_quaternion=q;b.scale=scale
            if b.name in previous and q.dot(previous[b.name])<0:b.rotation_quaternion.negate()
            previous[b.name]=b.rotation_quaternion.copy()
            b.keyframe_insert('location',frame=i+1,group=b.name)
            b.keyframe_insert('rotation_quaternion',frame=i+1,group=b.name)
            b.keyframe_insert('scale',frame=i+1,group=b.name)
        if i==0:rig.animation_data.action.name=name
    action=rig.animation_data.action;action.name=name;action.use_fake_user=True
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
    actions[name]=action

for source in ('seedance2','pixverse6','kling3'):
    data=json.loads((OUT/source/'motion-channels.json').read_text())
    source_times=np.asarray(data['times_s']);channels=data['channels']
    frames=round(data['duration_s']*60)
    samples=[];sole_trace=[];knee_repairs=0
    for frame in range(frames+1):
        time=frame/60
        ch={name:float(np.interp(time,source_times,values)) for name,values in channels.items()}
        reset_pose()
        # Global torso pitch is distributed through the spine, preserving skin joins.
        for name,fraction in [('Waist',.28),('Spine01',.65),('Spine02',1.0)]:
            orient(name,Quaternion((0,1,0),ch['torso_pitch']*fraction)@rest[name].to_quaternion())
        for name in ('NeckTwist01','NeckTwist02','Head'):
            orient(name,Quaternion((0,1,0),ch['torso_pitch']+ch['head_pitch'])@rest[name].to_quaternion())
        for side,sign in [('L',1),('R',-1)]:
            thigh=float(np.clip(ch[side+'_thigh'],math.radians(-135),math.radians(-38)))
            calf=float(np.clip(ch[side+'_calf'],thigh-math.radians(115),thigh))
            if abs(calf-ch[side+'_calf'])>.015:knee_repairs+=1
            planar(side+'_Thigh',thigh,sign*.018)
            planar(side+'_Calf',calf,sign*.035)
            foot=rig.data.bones[side+'_Foot']
            direction=foot.tail_local-foot.head_local
            base=math.atan2(direction.z,direction.x)
            planar(side+'_Foot',base+ch[side+'_foot_pitch'],sign*.04)
            # Toe roll shares the boot surface rather than separating geometry.
            orient(side+'_ToeBase',global_pose[side+'_Foot'].to_quaternion()@
                   (rest[side+'_Foot'].to_quaternion().inverted()@rest[side+'_ToeBase'].to_quaternion()))
            upper=float(np.clip(ch[side+'_upperarm'],math.radians(-150),math.radians(-30)))
            fore=float(np.clip(ch[side+'_forearm'],upper-math.radians(6),upper+math.radians(100)))
            planar(side+'_Upperarm',upper,sign*.19)
            planar(side+'_Forearm',fore,sign*.08)
            hand_rest=rig.data.bones[side+'_Hand'].tail_local-rig.data.bones[side+'_Hand'].head_local
            hand_angle=math.atan2(hand_rest.z,hand_rest.x)
            rest_fore=rig.data.bones[side+'_Forearm'].tail_local-rig.data.bones[side+'_Forearm'].head_local
            rest_fore_angle=math.atan2(rest_fore.z,rest_fore.x)
            planar(side+'_Hand',float(np.clip(hand_angle+fore-rest_fore_angle,-math.pi+.1,-.2)),sign*.11)
            # Twist bones follow their parent chain without retaining preset animation.
            for part in ('Thigh','Calf','Upperarm','Forearm'):
                for suffix in ('Twist01','Twist02'):
                    twist=side+'_'+part+suffix
                    if twist in rest:rig.pose.bones[twist].rotation_quaternion=Quaternion((1,0,0,0))
            refresh()
        contact=soles()
        shift=.001-min(v['z'] for v in contact.values())
        rig.pose.bones['Hip'].location=rest['Hip'].to_3x3().inverted()@Vector((0,0,shift))
        refresh()
        contact=soles();sole_trace.append(contact)
        samples.append(record_pose())
    clip=source+'_sequence';write_action(clip,samples)
    audit[clip]={'source_video':source+'.mp4','source_sha256':data['source_sha256'],
        'duration_s':frames/60,'frames':len(samples),'fps':60,'loop':False,'horizontal_root_motion':False,
        'knee_limit_repairs':knee_repairs,'weighted_sole_vertices':{k:len(v) for k,v in sole_sets.items()},
        'minimum_sole_z_m':min(v['z'] for s in sole_trace for v in s.values()),'sole_trace':sole_trace}
    # Add a loop only as an explicitly corrected derivative of a measured segment.
    loop=data['loop_segment']
    if loop:
        first=round(loop['start_s']*60);last=round(loop['end_s']*60)
        loop_samples=samples[first:last+1]
        first_pose,last_pose=loop_samples[0],loop_samples[-1]
        gap=max(math.degrees(v[1].rotation_difference(last_pose[n][1]).angle) for n,v in first_pose.items())
        for i,sample in enumerate(loop_samples):
            w=i/(len(loop_samples)-1);w=w*w*(3-2*w)
            for n,(loc,q,scale) in list(sample.items()):
                qfix=last_pose[n][1].rotation_difference(first_pose[n][1])
                sample[n]=(loc+(first_pose[n][0]-last_pose[n][0])*w,
                           q@Quaternion((1,0,0,0)).slerp(qfix,w),scale.copy())
        loop_samples[-1]={n:tuple(v.copy() for v in values) for n,values in loop_samples[0].items()}
        loop_soles=[]
        for i,sample in enumerate(loop_samples):
            for b in bones:b.location,b.rotation_quaternion,b.scale=sample[b.name]
            refresh();contact=soles()
            shift=.001-min(v['z'] for v in contact.values())
            rig.pose.bones['Hip'].location+=rest['Hip'].to_3x3().inverted()@Vector((0,0,shift))
            refresh();loop_soles.append(soles());loop_samples[i]=record_pose()
        loop_samples[-1]={n:tuple(v.copy() for v in values) for n,values in loop_samples[0].items()}
        slopes=[]
        for side in ('L','R'):
            for a,b in zip(loop_soles[:-2],loop_soles[1:-1]):
                if max(a[side]['z'],b[side]['z'])<.012 and b[side]['x']<a[side]['x']:
                    slopes.append((a[side]['x']-b[side]['x'])*60*1.7)
        reference_speed=float(np.median(slopes)) if slopes else 0.0
        name=source+'_loop';write_action(name,loop_samples)
        audit[name]={'duration_s':(last-first)/60,'frames':len(loop_samples),'fps':60,'loop':True,
                     'source_segment':loop,'original_endpoint_gap_deg':gap,'endpoint_correction':'distributed quaternion correction; needs engine contact review'}
        audit[name].update(reference_speed_mps=reference_speed,minimum_sole_z_m=min(v['z'] for s in loop_soles for v in s.values()),sole_trace=loop_soles)
    print('BAKED_VIDEO_MOTION',source,frames+1,flush=True)

rig.animation_data.action=actions['kling3_sequence'];scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
for mesh in meshes:mesh.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(DEST/'explorer_video_motions.glb'),export_format='GLB',use_selection=True,
    export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_anim_slide_to_zero=True,
    export_def_bones=True)
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_video_motions.blend'))
report={'method':'MediaPipe Heavy video tracking -> filtered sagittal channels -> Blender FK retargeting, joint limits and weighted boot sole correction -> GLB',
    'clips':audit,'rig_bones':len(bones),'source_motion_presets_used':False,'new_generation_api_calls':0,
    'individual_finger_capture':False,'facial_capture':False,'forward_axis':'+X','game_scale':1.7,
    'status':'baked; awaiting GLB reimport and Godot visual verification'}
(OUT/'animation-manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('VIDEO_ANIMATIONS_EXPORTED',DEST/'explorer_video_motions.glb',flush=True)
