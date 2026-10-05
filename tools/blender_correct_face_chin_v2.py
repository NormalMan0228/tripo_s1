"""Restore the approved chin and confine mouth rest correction to the lips."""
import bpy, math, json, hashlib
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'art/characters/explorer_b_face_rig_manual_v1/explorer_manual_face_rig.blend'
OUT=ROOT/'art/characters/explorer_b_face_rig_manual_v2';OUT.mkdir(exist_ok=True)
source_hash=hashlib.sha256(SRC.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SRC))
scene=bpy.context.scene;rig=bpy.data.objects['FACE_RIG__select_Custom_Properties']
scene.frame_set(1)
head=bpy.data.objects['01_Face_skin_neck']
head_keys=head.data.shape_keys.key_blocks
source=[p.co.copy() for p in head_keys['jawOpen'].data]

def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)

def lip_rest(p,oral=False):
    q=p.copy();x,y,z=p
    # Local lip correction only. Chin, jaw outline, neck and cheeks are anchors.
    front=smooth(.17,.24,x)
    width=1-smooth(.07,.145,abs(y))
    lower=smooth(-.265,-.215,z)*(1-smooth(-.195,-.14,z))
    upper=smooth(-.165,-.13,z)*(1-smooth(-.105,-.08,z))
    q.z+=front*width*(.037*lower-.010*upper)
    return q

stats={}
for name in ['01_Face_skin_neck','02_Upper_dental_candidate','03_Lower_dental_candidate','06_Tongue_candidate']:
    obj=bpy.data.objects[name];keys=obj.data.shape_keys.key_blocks
    original=[p.co.copy() for p in keys['jawOpen'].data]
    old=[p.co.copy() for p in keys['Basis'].data]
    # Teeth/tongue recover their original positions; do not compress oral geometry.
    neutral=[lip_rest(p) if obj==head else p.copy() for p in original]
    for key in keys:
        for i,p in enumerate(key.data):
            if key.name=='Basis':p.co=neutral[i]
            elif key.name=='jawOpen':p.co=original[i]
            else:p.co=neutral[i]+(p.co-old[i])
    for v,p in zip(obj.data.vertices,neutral):v.co=p
    stats[name]={'previous_max_displacement':max((p-q).length for p,q in zip(original,old)),
                 'new_max_displacement':max((p-q).length for p,q in zip(original,neutral))}
    obj.data.update()

# Preserve jaw/neck outline in every expression, including old broad mouth masks.
for key in head_keys:
    if key.name in ('Basis','jawOpen'):continue
    for i,p in enumerate(key.data):
        base=head_keys['Basis'].data[i].co
        w=smooth(-.265,-.235,source[i].z)
        p.co=base+(p.co-base)*w

scene.frame_set(1);rig.update_tag();bpy.context.view_layer.update()
scene['RIG_STATUS']='Chin restored from approved original; local lip-only neutral correction. Manual Faceit-free prototype.'
scene.render.resolution_x=800;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.cycles.samples=24
camera=scene.camera;target=Vector((.1,0,.0))
camera.location=target+Vector((4,-.35,.12));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=1.30
report={'source':str(SRC),'source_sha256':source_hash,'api_credits_used':0,'changes':stats}
for name,frame in [('neutral',1),('jaw-open',98),('smile',124)]:
    scene.frame_set(frame);scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
scene.frame_set(1)
target=Vector((.18,0,-.17));camera.location=target+Vector((4,0,0));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=.64
scene.render.filepath=str(OUT/'chin-closeup.png');bpy.ops.render.render(write_still=True)
target=Vector((.13,0,-.12));camera.location=target+Vector((3,-3,.02));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=.9
scene.render.filepath=str(OUT/'chin-angle.png');bpy.ops.render.render(write_still=True)
target=Vector((.1,0,.0));camera.location=target+Vector((4,-.35,.12));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=1.30
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            s=area.spaces.active;s.region_3d.view_location=target;s.region_3d.view_rotation=camera.rotation_euler.to_quaternion();s.region_3d.view_distance=1.65;s.region_3d.view_perspective='ORTHO'
            s.overlay.show_extras=False
report['chin_anchors_max_difference']=max((head_keys['Basis'].data[i].co-p).length for i,p in enumerate(source) if p.z<=-.265)
assert report['chin_anchors_max_difference']<1e-7
report['source_unchanged']=source_hash==hashlib.sha256(SRC.read_bytes()).hexdigest()
assert report['source_unchanged']
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_manual_face_rig_v2.blend'))
(OUT/'chin-correction-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('CHIN_RESTORED',json.dumps(report),flush=True)
