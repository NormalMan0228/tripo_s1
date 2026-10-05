"""Faceit-free facial rig baseline on the user-approved P2 prototype.

Preserves source file; uses explicit eye loops, curved blink correctives,
closed-mouth rest, per-part morphs, rigid eye bones and deterministic tests.
This does not claim production retopology or all 52 ARKit expressions.
"""
import bpy,json,math,heapq,hashlib,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'art/characters/explorer_b_faceit_comparison_p2_v1/hair_v3_nape_locks_v2/character_nape_hair_locks.blend'
OUT=ROOT/'art/characters/explorer_b_face_rig_manual_v1';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SRC))
scene=bpy.context.scene
source_hash=hashlib.sha256(SRC.read_bytes()).hexdigest()
topology=json.loads((OUT/'source-topology.json').read_text(encoding='utf-8'))
head=bpy.data.objects['01_Face_skin_neck']
original_meshes=[o for o in scene.objects if o.type=='MESH']
original_eye_parts=[o for o in original_meshes if o.name.startswith(('04_','05_','11_','12_','13_','14_','15_','16_','17_','18_','19_'))]
archive=bpy.data.collections.new('SOURCE_AI_EYES__hidden_not_rigged');scene.collection.children.link(archive)
for o in original_eye_parts:
    for c in list(o.users_collection):c.objects.unlink(o)
    archive.objects.link(o);o.hide_render=True;o.hide_set(True)
archive.hide_render=True;archive.hide_viewport=True
active=[o for o in original_meshes if o not in original_eye_parts]
def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def material(name,color,rough=.5):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes['Principled BSDF'];p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough
    return m
white=material('Eye sclera ivory',(.78,.76,.69),.24)
iris_mats=[material('Iris '+str(i),c,.3) for i,c in enumerate([(.045,.018,.008),(.17,.065,.019),(.24,.115,.035),(.11,.045,.015),(.018,.007,.003)])]
pupilmat=material('Pupil',(.004,.003,.002),.2)
lashmat=material('Brow and lash chestnut',(.065,.027,.012),.65)
teethmat=material('Dental ivory',(.73,.70,.61),.38)
tonguemat=material('Tongue muted rose',(.34,.12,.11),.6)
for o in active:
    if o.name.startswith(('07_','08_','09_','10_')):o.data.materials.clear();o.data.materials.append(lashmat)
    if o.name.startswith(('02_','03_')):o.data.materials.clear();o.data.materials.append(teethmat)
    if o.name.startswith('06_'):o.data.materials.clear();o.data.materials.append(tonguemat)

# Explicit common landmark convention: character forward +X, left +Y, up +Z.
eyes={s:{'center':Vector((.133,.149*sign,.063)),'radii':Vector((.108,.097,.101))} for s,sign in [('L',1),('R',-1)]}
eye_col=bpy.data.collections.new('RIG_EYES__clean_rotatable_geometry');scene.collection.children.link(eye_col)
eye_objects={}
def addmesh(name,verts,faces,mats,collection):
    m=bpy.data.meshes.new(name+'_mesh');m.from_pydata(verts,[],faces);m.update()
    o=bpy.data.objects.new(name,m);collection.objects.link(o)
    for mat in mats:m.materials.append(mat)
    for p in m.polygons:p.use_smooth=True
    return o
for side,e in eyes.items():
    center=e['center'];r=e['radii']
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=40,radius=1,location=center)
    eye=bpy.context.object;eye.name='Eye_white.'+side
    for v in eye.data.vertices:v.co=Vector((v.co.x*r.x,v.co.y*r.y,v.co.z*r.z))+center
    eye.location=(0,0,0)
    for c in list(eye.users_collection):c.objects.unlink(eye)
    eye_col.objects.link(eye);eye.data.materials.append(white)
    for p in eye.data.polygons:p.use_smooth=True
    eye_objects[side]=[eye]
    # Spherical colored iris cap follows the eye rather than a floating flat disc.
    verts=[tuple(center+Vector((r.x+.001,0,0)))];faces=[];segments=64;nr=12
    for j in range(1,nr+1):
        a=.48*j/nr
        for i in range(segments):
            phi=2*math.pi*i/segments
            verts.append(tuple(center+Vector(((r.x+.001)*math.cos(a),(r.y+.001)*math.sin(a)*math.cos(phi),(r.z+.001)*math.sin(a)*math.sin(phi)))))
    for i in range(segments):faces.append((0,1+i,1+(i+1)%segments))
    for j in range(nr-1):
        start=1+j*segments;nxt=start+segments
        for i in range(segments):faces.append((start+i,nxt+i,nxt+(i+1)%segments,start+(i+1)%segments))
    iris=addmesh('Iris_pupil.'+side,verts,faces,[pupilmat]+iris_mats,eye_col)
    for p in iris.data.polygons:
        radial=math.sqrt(((p.center.y-center.y)/r.y)**2+((p.center.z-center.z)/r.z)**2)
        p.material_index=0 if radial<.21 else (1 if radial>.44 else 3)
    eye_objects[side].append(iris)

# Named armature bones for head/eyes, with inspectable numerical morph controls.
rigdata=bpy.data.armatures.new('Manual_Face_Rig');rig=bpy.data.objects.new('FACE_RIG__select_Custom_Properties',rigdata);scene.collection.objects.link(rig)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
def bone(name,origin,tail,parent=None):
    b=rigdata.edit_bones.new(name);b.head=origin;b.tail=tail
    if parent:b.parent=rigdata.edit_bones[parent]
    return b
bone('root',(0,0,-.48),(0,0,-.35))
bone('head',(0,0,-.28),(0,0,.32),'root')
for side,e in eyes.items():bone('eye.'+side,e['center'],e['center']+Vector((0,.06,0)),'head')
bone('tongue',(.08,0,-.15),(.18,0,-.15),'head')
bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=False;rigdata.display_type='STICK'
props={'blink_L':(0,1),'blink_R':(0,1),'jaw_open':(0,1),'smile':(0,1),'frown':(0,1),'pucker':(0,1),'brow_up':(0,1),'brow_frown':(0,1),'look_lr':(-1,1),'look_ud':(-1,1)}
for name,(lo,hi) in props.items():
    rig[name]=0.0;rig.id_properties_ui(name).update(min=lo,max=hi,soft_min=lo,soft_max=hi,description='Manual baseline control: '+name)
def driver(target,path,expr,prop,index=None):
    fc=target.driver_add(path) if index is None else target.driver_add(path,index)
    d=fc.driver;d.type='SCRIPTED';d.expression=expr
    var=d.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path='["'+prop+'"]'
for side in eyes:
    pb=rig.pose.bones['eye.'+side];pb.rotation_mode='XYZ'
    driver(pb,'rotation_euler','-0.22*v','look_ud',1);driver(pb,'rotation_euler','0.28*v','look_lr',2)
def attach(o,bone_name):
    group=o.vertex_groups.new(name=bone_name);group.add(list(range(len(o.data.vertices))),1,'REPLACE')
    mod=o.modifiers.new('Manual facial armature','ARMATURE');mod.object=rig
for o in active:attach(o,'head')
for side,objects in eye_objects.items():
    for o in objects:attach(o,'eye.'+side)

def close_mouth(p,oral=False):
    q=p.copy();x,y,z=p
    # Monotone vertical map avoids the self-folding of a spatially weighted
    # jaw rotation on this AI topology. Nose and upper lip remain untouched.
    knots=[(-.50,-.50),(-.44,-.44),(-.28,-.18),(-.22,-.108),(-.085,-.085)]
    if z<=knots[0][0] or z>=knots[-1][0]:return q
    slopes=[(knots[i+1][1]-knots[i][1])/(knots[i+1][0]-knots[i][0]) for i in range(len(knots)-1)]
    tangents=[1]+[2*slopes[i-1]*slopes[i]/(slopes[i-1]+slopes[i]) for i in range(1,len(slopes))]+[1]
    for i in range(len(knots)-1):
        a,va=knots[i];b,vb=knots[i+1]
        if a<=z<=b:
            t=(z-a)/(b-a);h=b-a
            target=(2*t**3-3*t*t+1)*va+(t**3-2*t*t+t)*h*tangents[i]+(-2*t**3+3*t*t)*vb+(t**3-t*t)*h*tangents[i+1]
            w=(1-smooth(.14,.28,abs(y)))*(1 if oral else smooth(0,.18,x))
            q.z+=(target-z)*w;break
    return q
def newkey(o,name,coords,prop,expr='v'):
    key=o.shape_key_add(name=name)
    for dst,p in zip(key.data,coords):dst.co=p
    driver(key,'value',expr,prop);return key
sources={}
neutrals={}
mouth_objects=[o for o in active if o.name.startswith(('01_','02_','03_','06_'))]
for o in mouth_objects:
    source=[v.co.copy() for v in o.data.vertices];sources[o.name]=source
    neutral=[close_mouth(p,o!=head) for p in source];neutrals[o.name]=neutral
    for v,p in zip(o.data.vertices,neutral):v.co=p
    o.shape_key_add(name='Basis')
    newkey(o,'jawOpen',source,'jaw_open')

# Geodesic masks grow from the actual two eye aperture boundary loops.
head_source=sources[head.name];adj=[[] for _ in head_source]
for e in head.data.edges:
    a,b=e.vertices;d=(head_source[a]-head_source[b]).length;adj[a].append((b,d));adj[b].append((a,d))
loops=next(o for o in topology['objects'] if o['name']==head.name)['boundary_components']
eye_loops={side:next(b['ids'] for b in loops if b['n'] in (32,33) and b['center'][1]*(1 if side=='L' else -1)>0) for side in eyes}
def distances(seeds):
    ds=[float('inf')]*len(adj);heap=[]
    for i in seeds:ds[i]=0;heapq.heappush(heap,(0,i))
    while heap:
        d,i=heapq.heappop(heap)
        if d!=ds[i] or d>.14:continue
        for j,l in adj[i]:
            nd=d+l
            if nd<ds[j]:ds[j]=nd;heapq.heappush(heap,(nd,j))
    return ds
def blink_point(p,side,amount,w):
    e=eyes[side];c=e['center'];r=e['radii'];q=p.copy()
    u=(p.y-c.y)/.086;seam=.046+.014*min(1,u*u)
    q.z+=(seam-p.z)*w*amount
    inside=1-((p.y-c.y)/r.y)**2-((q.z-c.z)/r.z)**2
    surface=c.x+r.x*math.sqrt(max(0,inside))+.004
    if inside>0:q.x+=max(0,surface-p.x)*min(1,amount*2)
    return q
for side in eyes:
    ds=distances(eye_loops[side]);neutral=neutrals[head.name]
    weights=[math.exp(-(d/.052)**2) for d in ds]
    full=[blink_point(p,side,1,w) for p,w in zip(neutral,weights)]
    half=[blink_point(p,side,.5,w) for p,w in zip(neutral,weights)]
    # Retain source skin unchanged; dedicated clean lid strips below provide
    # predictable deformation rather than stretching the uneven AI eye topology.
    correction=[p+(h-p)-.5*(f-p) for p,h,f in zip(neutral,half,full)]
    lash=bpy.data.objects['08_Upper_lash_candidate_posY' if side=='L' else '07_Upper_lash_candidate_negY']
    base=[v.co.copy() for v in lash.data.vertices];lash.shape_key_add(name='Basis')
    ws=[math.exp(-(max(0,abs((p.y-eyes[side]['center'].y)/.086)-.95)/.42)**2) for p in base]
    lf=[blink_point(p,side,1,w) for p,w in zip(base,ws)];lh=[blink_point(p,side,.5,w) for p,w in zip(base,ws)]
    newkey(lash,'eyeBlink_'+side,lf,'blink_'+side)
    newkey(lash,'eyeBlinkArc_'+side,[p+(h-p)-.5*(f-p) for p,h,f in zip(base,lh,lf)],'blink_'+side,'4*v*(1-v)')

# Clean annular lid geometry with four curved interpolation samples per blink.
# The outer ring conforms to the original skin. The inner edge closes over
# the eye; no original face polygons are deleted or remeshed.
from mathutils.bvhtree import BVHTree
head.data.calc_loop_triangles()
skin_tree=BVHTree.FromPolygons([v.co for v in head.data.vertices],[t.vertices[:] for t in head.data.loop_triangles],all_triangles=True)
lid_col=bpy.data.collections.new('RIG_EYELIDS__clean_deformation_strips');scene.collection.children.link(lid_col)
for side,e in eyes.items():
    c=e['center'];r=e['radii'];segments=64;nr=8
    def lid_coordinates(blink):
        points=[]
        for j in range(nr+1):
            t=j/nr
            for i in range(segments):
                a=2*math.pi*i/segments
                iy=c.y+.080*math.cos(a);iz=c.z+.077*math.sin(a)
                seam=.046+.014*math.cos(a)**2
                iz=iz*(1-blink)+seam*blink
                oy=c.y+.113*math.cos(a);oz=c.z+.112*math.sin(a)
                y=iy*(1-t)+oy*t;z=iz*(1-t)+oz*t
                inside=1-((y-c.y)/r.y)**2-((z-c.z)/r.z)**2
                sx=c.x+r.x*math.sqrt(max(0,inside))+.008
                hit=skin_tree.ray_cast(Vector((1,y,z)),Vector((-1,0,0)),2)[0]
                hx=hit.x if hit else c.x
                x=sx*(1-t*t)+hx*t*t+.001
                if inside>0:x=max(x,sx)
                if j==nr:x=hx-.002
                points.append(Vector((x,y,z)))
        return points
    base=lid_coordinates(0);faces=[]
    for j in range(nr):
        for i in range(segments):
            a=j*segments+i;b=j*segments+(i+1)%segments;d=(j+1)*segments+i;cc=(j+1)*segments+(i+1)%segments
            faces.append((a,d,cc,b))
    lid=addmesh('Eyelids.'+side,base,faces,[head.data.materials[0]],lid_col);attach(lid,'head')
    lid.shape_key_add(name='Basis')
    for k in range(1,5):newkey(lid,'Blink_'+str(k*25),lid_coordinates(k/4),'blink_'+side,'max(0,1-abs(4*v-'+str(k)+'))')

# Local facial expression targets on the same neutral topology.
neutral=neutrals[head.name]
for name in ['smile','frown','pucker','brow_up','brow_frown']:
    coords=[]
    for p in neutral:
        q=p.copy();x,y,z=p;front=smooth(.10,.21,x)
        corner=math.exp(-((abs(y)-.105)/.070)**2-((z+.13)/.075)**2)*front
        if name=='smile':q.y+=(1 if y>0 else -1)*.010*corner;q.z+=.016*corner
        elif name=='frown':q.z-=.018*corner
        elif name=='pucker':
            w=math.exp(-(y/.135)**4-((z+.135)/.070)**4)*front;q.y-=y*.22*w;q.x+=.018*w
        elif name=='brow_up':q.z+=.025*math.exp(-((abs(y)-.15)/.11)**2-((z-.22)/.085)**2)*front
        else:q.z-=.02*math.exp(-((abs(y)-.10)/.08)**2-((z-.21)/.075)**2)*front
        coords.append(q)
    newkey(head,name,coords,name)
for o in [bpy.data.objects['09_Brow_candidate_negY'],bpy.data.objects['10_Brow_candidate_posY']]:
    base=[v.co.copy() for v in o.data.vertices];o.shape_key_add(name='Basis')
    newkey(o,'brow_up',[p+Vector((0,0,.035)) for p in base],'brow_up')
    newkey(o,'brow_frown',[p+Vector((0,0,-.035*(1-smooth(.08,.25,abs(p.y))))) for p in base],'brow_frown')

def set_pose(values):
    for p in props:rig[p]=float(values.get(p,0))
    rig.update_tag();bpy.context.view_layer.update()
cam=scene.camera;target=Vector((.10,0,.04));cam.location=target+Vector((4,-.35,.12));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.35
scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.render.fps=24;scene.frame_start=1;scene.frame_end=240
scene.cycles.samples=16
POSES={'neutral':{},'blink':{'blink_L':1,'blink_R':1},'half-blink':{'blink_L':.5,'blink_R':.5},'jaw-open':{'jaw_open':1},'smile':{'smile':1},'surprise':{'brow_up':1,'jaw_open':.65},'look-left':{'look_lr':.8},'frown':{'frown':1,'brow_frown':1}}
for name,values in POSES.items():
    set_pose(values);scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
set_pose({})
# Fixed comparison sequence; shared for future Faceit and model/effort trials.
keys=[(1,{}),(12,{}),(18,{'blink_L':1,'blink_R':1}),(24,{}),(35,{'blink_L':1}),(43,{}),(54,{'look_lr':-.8}),(66,{'look_lr':.8}),(76,{'look_ud':.6}),(85,{}),(98,{'jaw_open':1}),(110,{}),(124,{'smile':1}),(132,{'smile':1,'blink_L':1,'blink_R':1}),(140,{'smile':1}),(150,{}),(165,{'jaw_open':.65,'brow_up':1}),(179,{}),(194,{'frown':1,'brow_frown':1}),(208,{}),(221,{'pucker':1}),(234,{}),(240,{})]
for f,values in keys:
    for p in props:rig[p]=float(values.get(p,0));rig.keyframe_insert(data_path='["'+p+'"]',frame=f)
if rig.animation_data and rig.animation_data.action:rig.animation_data.action.name='Face_Comparison_Test_10s_24fps'
for name,frame in [('Neutral',1),('Blink pair',12),('Wink',30),('Gaze',48),('Jaw',88),('Smile + blink',115),('Surprise',155),('Frown',184),('Pucker',213),('Neutral end',234)]:scene.timeline_markers.new(name,frame=frame)
scene.frame_set(1)
for o in scene.objects:o.select_set(False)
rig.select_set(True);bpy.context.view_layer.objects.active=rig
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            s=area.spaces.active;s.region_3d.view_location=target;s.region_3d.view_rotation=cam.rotation_euler.to_quaternion();s.region_3d.view_distance=1.8;s.region_3d.view_perspective='ORTHO';s.overlay.show_extras=False
scene['RIG_STATUS']='Faceit-free manual prototype baseline. Original P2 topology retained; not production retopology. Neutral-mouth morph, eye bones, curved blinks and fixed comparison action.'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_manual_face_rig.blend'))
report={'source':str(SRC),'source_sha256':source_hash,'source_unchanged':source_hash==hashlib.sha256(SRC.read_bytes()).hexdigest(),'faceit_used':False,'agent_model_identity':'Not programmatically verified; do not infer a model name from asset name.','api_credits_used':0,'controls':list(props),'bones':[b.name for b in rigdata.bones],'source_eyes_preserved_hidden':len(original_eye_parts),'comparison_poses':POSES,'comparison_keyframes':keys,'fps':24,'frame_range':[1,240],'production_retopology':False,'all_52_arkit_shapes':False,'visual_validation':'Pending rendered pose review'}
(OUT/'rig-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('MANUAL_RIG_SAVED',flush=True)
