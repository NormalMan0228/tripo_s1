"""Reimport video-derived GLB and inspect evaluated poses and weighted skin."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/video-motion-20261003'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.render.fps=60
bpy.ops.import_scene.gltf(filepath=str(ROOT/'labs/video_motion_lab/assets/explorer_video_motions.glb'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
# The glTF importer creates an unskinned Icosphere as a bone display helper.
# It is not part of the exported skin and must not be treated as a boot surface.
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'
        and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
scene=bpy.context.scene;results={};signatures={}
for action in list(bpy.data.actions):
    rig.animation_data.action=action
    if action.slots:rig.animation_data.action_slot=action.slots[0]
    start,end=action.frame_range;first=None;previous=None;max_step=0;hips=[];angles=[];surface_minima=[]
    for frame in range(round(start),round(end)+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        pose={b.name:(b.location.copy(),b.rotation_quaternion.copy()) for b in rig.pose.bones}
        if first is None:first=pose
        if previous:max_step=max(max_step,max(math.degrees(v[1].rotation_difference(previous[n][1]).angle) for n,v in pose.items()))
        previous=pose;hips.append(list(rig.pose.bones['Hip'].head))
        angles.append([list(rig.pose.bones[n].rotation_quaternion) for n in ['L_Thigh','R_Thigh','L_Upperarm','R_Upperarm']])
        if round(frame-start)%6==0 or frame==round(end):
            deps=bpy.context.evaluated_depsgraph_get()
            # Inspect the actual reimported, evaluated surface, not the builder's sole estimate.
            lowest=math.inf
            for mesh in meshes:
                evaluated=mesh.evaluated_get(deps)
                data=evaluated.to_mesh()
                lowest=min(lowest,min((evaluated.matrix_world@v.co).z for v in data.vertices))
                evaluated.to_mesh_clear()
            surface_minima.append(lowest)
    results[action.name]={'duration_s':(end-start)/60,'frames':len(hips),
        'hip_horizontal_range_m':max(max(v[i] for v in hips)-min(v[i] for v in hips) for i in [0,1]),
        'max_joint_step_deg_60hz':max_step,'endpoint_rotation_gap_deg':max(math.degrees(v[1].rotation_difference(previous[n][1]).angle) for n,v in first.items()),
        'endpoint_local_position_gap_m':max((v[0]-previous[n][0]).length for n,v in first.items()),
        'surface_floor_min_m':min(surface_minima),'surface_floor_max_m':max(surface_minima),'surface_samples':len(surface_minima)}
    signatures[action.name]=angles
report={'clips':results,'bone_count':len(rig.data.bones),'distinct_full_sequences':len({json.dumps(signatures[n]) for n in signatures if n.endswith('_sequence')})==3,
    'pass':len(results)==6 and all(v['hip_horizontal_range_m']<.002 and v['max_joint_step_deg_60hz']<30 for v in results.values())
        and all(v['endpoint_rotation_gap_deg']<.15 and v['endpoint_local_position_gap_m']<.0001 for n,v in results.items() if n.endswith('_loop'))
        and all(-.002<v['surface_floor_min_m'] and v['surface_floor_max_m']<.015 for v in results.values())}
(OUT/'reimport-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('VIDEO_REIMPORT_AUDIT',json.dumps(report),flush=True)
