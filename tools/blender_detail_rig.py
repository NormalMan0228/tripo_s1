"""Extend Explorer B locally. Preserve the source; author real deform bones and morphs."""
import bpy, bmesh, math, json, sys
from pathlib import Path
from mathutils import Vector, Matrix
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/characters/explorer-b-detailed-v2'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'artifacts/characters/explorer-b-v1/explorer-b-custom.blend'))
scene=bpy.context.scene
rig=next(o for o in scene.objects if o.type=='ARMATURE')
body=bpy.data.objects['Explorer_B_SkinnedMesh']
rig.animation_data_clear()
for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
rig.name='Explorer_B_Detailed_Rig'
bpy.context.view_layer.update()
# More geometry around finger joints, without changing the body silhouette or UV layout.
bm=bmesh.new();bm.from_mesh(body.data)
hand_edges=[e for e in bm.edges if all(abs(v.co.y)>.305 and .675<v.co.z<.735 for v in e.verts)]
bmesh.ops.subdivide_edges(bm,edges=hand_edges,cuts=2,use_grid_fill=True)
bm.to_mesh(body.data);bm.free();body.data.update()

def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def material(name,color,rough=.65):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough
    return m
skin=material('Eyelid_skin',(.53,.32,.205));white=material('Eye_ivory',(.82,.80,.72),.24)
lashmat=material('Eyelash_soft_brown',(.038,.021,.014),.8)
iris=material('Iris_warm_brown',(.16,.068,.025),.25);pupil=material('Pupil',(.008,.005,.003),.22)
mouthmat=material('Mouth_interior',(.032,.006,.009));lipmat=material('Lip_edge',(.38,.18,.11))

# Finger landmarks in the character's rest pose (+X forward, +Z up).
paths={
 'Thumb':[(.017,.315,.698),(.026,.333,.693),(.035,.346,.691),(.039,.350,.691)],
 'Index':[(.009,.339,.708),(.014,.361,.711),(.017,.380,.711),(.018,.389,.710)],
 'Middle':[(-.007,.340,.710),(-.007,.365,.714),(-.007,.389,.714),(-.007,.397,.713)],
 'Ring':[(-.024,.338,.710),(-.028,.359,.713),(-.032,.383,.711),(-.033,.391,.710)],
 'Little':[(-.038,.334,.705),(-.046,.351,.708),(-.051,.371,.707),(-.052,.377,.706)]}
finger_specs={}
bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
def bone(name,head,tail,parent,deform=True):
    b=rig.data.edit_bones.new(name);b.head=head;b.tail=tail;b.parent=rig.data.edit_bones[parent];b.use_deform=deform;b.align_roll(Vector((0,0,1)));return b
for side,sign in [('L',1),('R',-1)]:
    for digit,points in paths.items():
        points=[Vector((x,y*sign,z)) for x,y,z in points]
        names=[]
        for i in range(3):
            name=f'{side}_{digit}_{i+1:02d}';bone(name,points[i],points[i+1],f'{side}_Hand' if i==0 else names[-1]);names.append(name)
        finger_specs[(side,digit)]=(points,names)
bone('Face_Jaw',(.018,0,.838),(.074,0,.800),'Head')
for side,sign in [('L',1),('R',-1)]:bone('Face_Eye_'+side,(.043,sign*.040,.868),(.065,sign*.040,.868),'Head')
# Non-deforming IK handles: existing body animations remain usable with influence zero.
for side in ['L','R']:
    for part,upper,lower,end,offset in [('Hand','Upperarm','Forearm','Hand',(-.12,0,-.08)),('Foot','Thigh','Calf','Foot',(.15,0,0))]:
        p=rig.data.edit_bones[f'{side}_{end}'].head.copy()
        bone(f'CTRL_{side}_{part}_IK',p,p+Vector((0,0,.04)),'Root',False)
        pole=rig.data.edit_bones[f'{side}_{lower}'].head+Vector(offset)
        bone(f'CTRL_{side}_{part}_Pole',pole,pole+Vector((0,0,.025)),'Root',False)
bpy.ops.object.mode_set(mode='OBJECT')
rig.show_in_front=True
for side in ['L','R']:
    for part,lower in [('Hand','Forearm'),('Foot','Calf')]:
        c=rig.pose.bones[f'{side}_{lower}'].constraints.new('IK');c.name='Optional_IK_'+part;c.target=rig;c.subtarget=f'CTRL_{side}_{part}_IK';c.pole_target=rig;c.pole_subtarget=f'CTRL_{side}_{part}_Pole';c.chain_count=2;c.influence=0

def group(obj,name):return obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
for pts,names in finger_specs.values():
    for n in names:group(body,n)
def setweights(obj,index,weights):
    for g in list(obj.data.vertices[index].groups):obj.vertex_groups[g.group].remove([index])
    weights={n:w for n,w in weights.items() if w>1e-6};total=sum(weights.values())
    for n,w in weights.items():group(obj,n).add([index],w/total,'REPLACE')
def segdist(p,a,b):
    t=max(0,min(1,(p-a).dot(b-a)/(b-a).length_squared));return (p-a.lerp(b,t)).length,t
finger_counts={n:0 for pts,names in finger_specs.values() for n in names}
for v in body.data.vertices:
    p=body.matrix_world@v.co
    if abs(p.y)<.312 or not .67<p.z<.74:continue
    side='L' if p.y>0 else 'R'
    candidates=[]
    for digit in paths:
        pts,names=finger_specs[(side,digit)]
        dist,t=segdist(p,pts[0],pts[-1]);candidates.append((dist,digit,t))
    dist,digit,t=min(candidates)
    pts,names=finger_specs[(side,digit)]
    amount=smooth(-.15,.19,t) if digit=='Thumb' else smooth(.324,.350,abs(p.y))
    if amount<.001:continue
    along=max(0,min(2,t*3-.48));i=min(1,int(along));f=along-i
    weights={f'{side}_Hand':1-amount,names[i]:amount*(1-f),names[i+1]:amount*f}
    setweights(body,v.index,weights)
    for n,w in weights.items():
        if n in finger_counts and w>.02:finger_counts[n]+=1

# Smooth only the hand weights. Matching coordinates keep UV-seam duplicates in sync.
keys={v.index:tuple(round(x,6) for x in v.co) for v in body.data.vertices}
members={};adj={}
for v in body.data.vertices:
    if abs(v.co.y)>.31 and .67<v.co.z<.74:members.setdefault(keys[v.index],[]).append(v.index)
for e in body.data.edges:
    a,b=[keys[i] for i in e.vertices]
    if a in members and b in members and a!=b:adj.setdefault(a,set()).add(b);adj.setdefault(b,set()).add(a)
weights={k:{body.vertex_groups[g.group].name:g.weight for g in body.data.vertices[indices[0]].groups} for k,indices in members.items()}
for iteration in range(3):
    out={}
    for k,w in weights.items():
        neighbors=adj.get(k,[]);mixed={n:v*.6 for n,v in w.items()}
        if not neighbors:out[k]=w;continue
        for other in neighbors:
            for n,v in weights[other].items():mixed[n]=mixed.get(n,0)+.4*v/len(neighbors)
        out[k]=dict(sorted(mixed.items(),key=lambda item:item[1],reverse=True)[:4])
    weights=out
for k,indices in members.items():
    for index in indices:setweights(body,index,weights[k])

# Add a restrained jaw deformation, leaving hair, neck and the upper face alone.
group(body,'Face_Jaw')
for v in body.data.vertices:
    p=body.matrix_world@v.co
    amount=(1-smooth(.809,.831,p.z))*smooth(.781,.798,p.z)*smooth(.015,.043,p.x)*(1-smooth(.055,.08,abs(p.y)))*.7
    if amount>.001:
        weights={body.vertex_groups[g.group].name:g.weight*(1-amount) for g in v.groups}
        weights['Face_Jaw']=amount;setweights(body,v.index,weights)

def meshobj(name,verts,faces,mat,bone_name='Head'):
    m=bpy.data.meshes.new(name);m.from_pydata(verts,[],faces);m.update()
    o=bpy.data.objects.new(name,m);scene.collection.objects.link(o);m.materials.append(mat)
    for p in m.polygons:p.use_smooth=True
    o.parent=rig;mod=o.modifiers.new('Character_skin','ARMATURE');mod.object=rig
    group(o,bone_name).add(list(range(len(verts))),1,'REPLACE');return o
def shape(obj,name,coords):
    if obj.data.shape_keys is None:obj.shape_key_add(name='Basis')
    k=obj.shape_key_add(name=name)
    for v,p in zip(k.data,coords):v.co=p
    return k
def spherepoint(center,theta,phi,extra=0):
    return (center[0]+(.021+extra)*math.cos(phi)*math.cos(theta),center[1]+(.0215+extra)*math.cos(phi)*math.sin(theta),center[2]+(.0195+extra)*math.sin(phi))
extras=[]
for side,sign in [('L',1),('R',-1)]:
    center=(.043,sign*.040,.868)
    # Sclera and a separate curved iris/pupil are genuinely controlled by eye bones.
    verts=[];faces=[];nt=48;np=24
    for j in range(np+1):
        phi=-math.pi/2+math.pi*j/np
        for i in range(nt+1):verts.append(spherepoint(center,-math.pi+math.tau*i/nt,phi))
    for j in range(np):
        for i in range(nt):a=j*(nt+1)+i;faces.append((a,a+1,a+nt+2,a+nt+1))
    extras.append(meshobj('Eye_'+side,verts,faces,white,'Face_Eye_'+side))
    for label,radius,mat,extra in [('Iris',.0142,iris,.0003),('Pupil',.0090,pupil,.0006)]:
        verts=[spherepoint(center,0,0,extra)];faces=[]
        for j in range(1,7):
            r=radius*j/6
            for i in range(48):
                a=math.tau*i/48;yy=r*math.cos(a);zz=r*math.sin(a)
                xx=.021*math.sqrt(max(0,1-(yy/.0215)**2-(zz/.0195)**2))+extra
                verts.append((center[0]+xx,center[1]+yy,center[2]+zz))
        for i in range(48):faces.append((0,1+i,1+(i+1)%48))
        for j in range(5):
            for i in range(48):a=1+j*48+i;b=1+j*48+(i+1)%48;faces.append((a,b,b+48,a+48))
        extras.append(meshobj(label+'_'+side,verts,faces,mat,'Face_Eye_'+side))
    for label,sgn,opening in [('Upper',1,.64),('Lower',-1,.68)]:
        verts=[];closed=[];wide=[];faces=[];nt=40;nr=10
        for j in range(nr+1):
            t=j/nr
            for i in range(nt+1):
                theta=-math.pi/2+math.pi*i/nt
                # Rounded corners: eyelids meet near the sides of the eye.
                edge=abs(math.sin(theta))**4
                base=opening+(1.3-opening)*edge
                for arr,angle in [(verts,sgn*base),(closed,-.12*math.cos(theta)**2),(wide,sgn*(base+.15))]:
                    phi=angle+(sgn*math.pi/2-angle)*t
                    arr.append(spherepoint(center,theta,phi,.0009))
        for j in range(nr):
            for i in range(nt):a=j*(nt+1)+i;faces.append((a,a+1,a+nt+2,a+nt+1))
        lid=meshobj(label+'_Lid_'+side,verts,faces,skin);shape(lid,'Blink_'+side,closed);shape(lid,'EyesWide',wide);extras.append(lid)
        if label=='Upper':
            vv=[];cc=[];ww=[];ff=[]
            for row in range(2):
                for i in range(nt+1):
                    theta=-math.pi/2+math.pi*i/nt;edge=abs(math.sin(theta))**4;base=opening+(1.3-opening)*edge
                    for arr,angle in [(vv,base),(cc,-.12*math.cos(theta)**2),(ww,base+.15)]:arr.append(spherepoint(center,theta,angle+row*.038,.0011))
            for i in range(nt):ff.append((i,i+1,i+nt+2,i+nt+1))
            lash=meshobj('Lash_'+side,vv,ff,lashmat);shape(lash,'Blink_'+side,cc);shape(lash,'EyesWide',ww);extras.append(lash)

# Blend shapes retain the original UVs. Facial texture is not regenerated.
base=[v.co.copy() for v in body.data.vertices]
for name in ['Smile','BrowRaise','BrowConcern']:
    coords=[]
    for p in base:
        q=p.copy();front=smooth(.015,.045,p.x)
        if name=='Smile':
            w=math.exp(-((abs(p.y)-.022)/.018)**2-((p.z-.818)/.013)**2)*front
            q.z+=.005*w;q.y+=math.copysign(.002*w,p.y)
        else:
            w=math.exp(-((abs(p.y)-.039)/.028)**2-((p.z-.899)/.010)**2)*front
            q.z+=(.004 if name=='BrowRaise' else .004*(1-abs(p.y)/.045))*w
        coords.append(q)
    shape(body,name,coords)

# A small stylized mouth interior and rim support opening without stretching a painted slit.
N=64;verts=[];faces=[];opened=[];smiled=[]
for ring in range(4):
    for i in range(N):
        a=math.tau*i/N;yy=.024*math.cos(a);curve=.818+.003*(abs(yy)/.024)**2
        rz=[.0010,.0018,.0035,.0065][ring];x=[.0800,.0803,.0801,.0790][ring]
        zz=curve+rz*math.sin(a)
        verts.append((x,yy,zz));op=curve+(.004 if math.sin(a)>0 else .012)*math.sin(a)-.002
        opened.append((x,yy,zz+(op-zz)*[1,1,.65,.10][ring]))
        smiled.append((x,yy*1.06,zz+.005*(abs(yy)/.024)**2))
for ring in range(3):
    for i in range(N):a=ring*N+i;b=ring*N+(i+1)%N;faces.append((a,b,b+N,a+N))
rim=meshobj('Mouth_Rim',verts,faces,lipmat);rim.data.materials.append(skin)
for p in rim.data.polygons:p.material_index=0 if p.index<N else 1
shape(rim,'MouthOpen',opened);shape(rim,'Smile',smiled);extras.append(rim)
verts=[(.0795,0,.818)]+verts[:N];faces=[(0,1+i,1+(i+1)%N) for i in range(N)]
inside=meshobj('Mouth_Interior',verts,faces,mouthmat);shape(inside,'MouthOpen',[(.0795,0,.815)]+opened[:N]);shape(inside,'Smile',[(.0795,0,.818)]+smiled[:N]);extras.append(inside)

character=[body]+extras
for obj in character:
    for poly in obj.data.polygons:poly.use_smooth=True
def setshape(name,value):
    for obj in character:
        if obj.data.shape_keys and name in obj.data.shape_keys.key_blocks:obj.data.shape_keys.key_blocks[name].value=value
def pose(t):
    # Dedicated inspection motion: open hand -> grip -> relax, blink, gaze and expressions.
    for b in rig.pose.bones:b.rotation_mode='XYZ';b.rotation_euler=(0,0,0);b.location=(0,0,0);b.scale=(1,1,1)
    grip=smooth(.5,1.6,t)*(1-smooth(2.7,3.6,t))
    for (side,digit),(pts,names) in finger_specs.items():
        for i,n in enumerate(names):rig.pose.bones[n].rotation_euler.x=-math.radians(([25,35,25] if digit=='Thumb' else [45,65,40])[i])*grip
    for name in ['Blink_L','Blink_R','Smile','BrowRaise','BrowConcern','EyesWide','MouthOpen']:setshape(name,0)
    blink=max(0,1-abs(t-1.0)/.15)+max(0,1-abs(t-4.0)/.15)
    setshape('Blink_L',min(blink,1));setshape('Blink_R',min(blink,1))
    smile=smooth(1.6,2.4,t)*(1-smooth(3.0,3.7,t));setshape('Smile',smile)
    surprise=smooth(4.25,4.7,t)*(1-smooth(5.4,6,t));setshape('BrowRaise',surprise);setshape('EyesWide',surprise);setshape('MouthOpen',surprise*.8)
    for side in ['L','R']:
        rig.pose.bones['Face_Eye_'+side].rotation_euler.z=math.radians(12)*math.sin(t*math.tau/6)
    rig.pose.bones['Face_Jaw'].rotation_euler.x=math.radians(3)*surprise
    bpy.context.view_layer.update()

# Keep a neutral authoring pose; export only character objects.
scene.render.fps=24;scene.frame_start=1;scene.frame_end=145
rig.animation_data_create()
for frame in range(1,146):
    pose((frame-1)/24)
    for b in rig.pose.bones:
        if b.name.startswith('CTRL_'):continue
        b.keyframe_insert('rotation_euler',frame=frame,group=b.name)
    for obj in character:
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                if key.name!='Basis':key.keyframe_insert('value',frame=frame)
rig.animation_data.action.name='Detail_Demo';rig.animation_data.action.use_fake_user=True
for obj in character:
    if obj.data.shape_keys and obj.data.shape_keys.animation_data:
        obj.data.shape_keys.animation_data.action.name='Detail_Demo_'+obj.name
scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
for o in character:o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'explorer-b-detailed.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='SCENE',export_frame_range=True,export_force_sampling=True,export_skins=True,export_morph=True,export_def_bones=True)
sys.path.insert(0,str(ROOT/'tools'))
from merge_detail_tracks import merge
merge(OUT/'explorer-b-detailed.glb')
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer-b-detailed.blend'))
report={'source':'explorer-b-v1/explorer-b-custom.blend','tripo_credits_spent':0,'bone_count':len(rig.data.bones),'finger_bones':30,'eye_bones':2,'jaw_bones':1,'ik_controls':8,'finger_influenced_vertices':finger_counts,'shape_keys':{o.name:[k.name for k in o.data.shape_keys.key_blocks] for o in character if o.data.shape_keys},'notes':['Stylized eye and mouth components added locally.','Optional IK constraints default to influence 0 to preserve FK motion.','Basic expressions, not full ARKit or phoneme coverage.']}
(OUT/'rig-manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

scene.render.resolution_x=900;scene.render.resolution_y=900;scene.cycles.samples=16
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
scene.cycles.device='GPU'
cam=scene.camera
for name,frame,target,offset,scale in [('face-neutral',1,(0,0,.855),(3,0,.1),.30),('face-blink',25,(0,0,.855),(3,0,.1),.30),('face-smile',61,(0,0,.855),(3,0,.1),.30),('face-surprise',121,(0,0,.855),(3,0,.1),.30),('hand-open',1,(0,.34,.705),(.15,-.1,3),.16),('hand-grip',49,(0,.34,.705),(.15,-.1,3),.16)]:
    scene.frame_set(frame);target=Vector(target);cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
print('DETAIL_RIG_COMPLETE',json.dumps(report),flush=True)
