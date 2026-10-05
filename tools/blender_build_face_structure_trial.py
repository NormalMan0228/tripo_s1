"""Prepare a reversible HD face construction study; no production rig or retopology."""
import hashlib
import json
import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/characters/explorer_b_hd_restart_v1'
OUT = ROOT/'art/characters/explorer_b_face_structure_v1'
OUT.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
report = {'stage':'HD assembly and face construction trial', 'retopologized':False,
          'rigged':False,'shape_keys_created':False,'api_credits_spent':0,
          'mouth_opening_functional':False,'sources':{},'operations':[]}

def collection(name):
    c=bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c
skin_col=collection('01_Head_Skin_HD')
eyes_col=collection('02_Eyeballs_Independent')
hair_col=collection('03_Hair_HD')
mouth_col=collection('04_Mouth_Interior_Layout_PENDING')
body_col=collection('05_Body_Fit_Study')
studio=collection('06_Review_Studio')

def material(name,color,roughness=.5):
    m=bpy.data.materials.new(name)
    m.use_nodes=True
    m.diffuse_color=(*color,1)
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=roughness
    return m
skin=material('Skin_Review_Uniform',(.64,.34,.19),.58)
hair_mat=material('Hair_Review_Brown',(.075,.034,.018),.58)
brow=material('Brows_And_Lashes_Review',(.047,.024,.015),.6)
lip=material('Lips_Review',(.49,.20,.13),.56)
white=material('Underclothes_Review',(.75,.75,.69),.75)
gum=material('Gum_Layout',(.27,.055,.052),.65)
teeth=material('Teeth_Layout',(.82,.78,.64),.33)
cavity=material('Mouth_Interior_Layout',(.065,.014,.018),.85)
tongue_mat=material('Tongue_Layout',(.42,.095,.10),.65)

def load(part,col):
    path=BASE/part/f'{part}_HD.blend'
    report['sources'][part]={'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    with bpy.data.libraries.load(str(path),link=False) as (a,b):
        b.objects=[n for n in a.objects if n.startswith(f'HD_{part}_')]
    assert len(b.objects)==1
    obj=b.objects[0]
    col.objects.link(obj)
    obj.hide_select=False
    obj.hide_viewport=False
    obj.hide_render=False
    obj.hide_set(False)
    return obj

def arrays(obj):
    m=obj.data
    v=np.empty(len(m.vertices)*3,dtype=np.float32)
    m.vertices.foreach_get('co',v)
    v=v.reshape(-1,3)
    m.calc_loop_triangles()
    f=np.empty(len(m.loop_triangles)*3,dtype=np.int32)
    m.loop_triangles.foreach_get('vertices',f)
    return v,f.reshape(-1,3)

def rebuild(obj,v,f,keep):
    retained=f[keep]
    used,inverse=np.unique(retained,return_inverse=True)
    fresh=bpy.data.meshes.new(obj.name+'_WorkingGeometry')
    fresh.from_pydata(v[used].tolist(),[],inverse.reshape(-1,3).tolist())
    fresh.update()
    old=obj.data
    obj.data=fresh
    if old.users==0: bpy.data.meshes.remove(old)
    for p in fresh.polygons:p.use_smooth=True
    return v[used]

# Preserve the native generated face silhouette. Remove only fused eye fronts
# within measured apertures, leaving the surrounding skin and eyelid surfaces.
head=load('head',skin_col)
head.name='Head_Skin_HD_Working'
v,f=arrays(head)
centers=v[f].mean(1)
eye_y=.169
eye_z=-.012
aperture_y=.073
aperture_z=.052
eye_region=((np.abs(centers[:,1])-eye_y)/aperture_y)**2+((centers[:,2]-eye_z)/aperture_z)**2
remove=(eye_region<1)&(centers[:,0]>.12)
# The bottom neck is a fitting boundary, not an anatomical facial split.
keep=(~remove)&(centers[:,2]>-.410)
old_count=len(f)
v=rebuild(head,v,f,keep)
# Replace the lower generated neck with a short clean connector.
nv,nf=arrays(head)
edges=np.sort(np.concatenate([nf[:,[0,1]],nf[:,[1,2]],nf[:,[2,0]]]),axis=1)
unique,counts=np.unique(edges,axis=0,return_counts=True)
neck_edges=unique[(counts==1)&(nv[unique].mean(1)[:,2]<-.400)]
adj={}
for a,b in neck_edges:
    adj.setdefault(int(a),[]).append(int(b));adj.setdefault(int(b),[]).append(int(a))
assert all(len(neighbors)==2 for neighbors in adj.values())
unvisited=set(adj);loops=[]
while unvisited:
    ordered=[min(unvisited)];previous=-1;current=ordered[0]
    while True:
        nxt=next(i for i in adj[current] if i!=previous)
        if nxt==ordered[0]:break
        ordered.append(nxt);previous,current=current,nxt
    unvisited.difference_update(ordered);loops.append(np.array(ordered,dtype=np.int32))
ordered=max(loops,key=lambda loop:np.linalg.norm(nv[loop]-np.roll(nv[loop],1,axis=0),axis=1).sum())
report['neck_cut_boundary_loops']=len(loops)
nv[ordered,2]=-.410
theta=np.arctan2(nv[ordered,1]/.118,(nv[ordered,0]-.011)/.116)
end=np.column_stack([.011+.1385*np.cos(theta),.134*np.sin(theta),np.full(len(theta),(.294-.387)/.213)])
start=len(nv)
bridge=[]
for i in range(len(ordered)):
    j=(i+1)%len(ordered)
    bridge.extend([[int(ordered[i]),int(ordered[j]),start+j],[int(ordered[i]),start+j,start+i]])
v=rebuild(head,np.concatenate([nv,end]),np.concatenate([nf,np.array(bridge,dtype=np.int32)]),np.ones(len(nf)+len(bridge),dtype=bool))
report['operations'].append({'operation':'replace lower neck with connected fitting bridge','boundary_vertices':len(ordered),'body_join_welded':False})
report['operations'].append({'operation':'remove fused generated eye fronts and trim neck on working copy',
                             'source_triangles':old_count,'working_triangles':len(head.data.polygons),
                             'eye_front_triangles_removed':int(remove.sum()),
                             'eye_apertures':{'center_y_abs':eye_y,'center_z':eye_z,'radius_y':aperture_y,'radius_z':aperture_z}})
head.data.materials.clear()
for m in [skin,brow,lip]:head.data.materials.append(m)
# Review palette follows the existing raised features; it is not a baked texture.
hv,hf=arrays(head)
hc=hv[hf].mean(1)
abs_y=np.abs(hc[:,1])
brow_z=.14-.42*(abs_y-.16)**2
is_brow=(hc[:,0]>.16)&(abs_y>.075)&(abs_y<.31)&(np.abs(hc[:,2]-brow_z)<.020)
is_lash=(hc[:,0]>.22)&(abs_y>.085)&(abs_y<.28)&(hc[:,2]>.027)&(hc[:,2]<.063)
is_lip=(hc[:,0]>.28)&(abs_y<.132)&(hc[:,2]>-.303)&(hc[:,2]<-.258)
indices=np.zeros(len(hc),dtype=np.int32)
indices[is_brow|is_lash]=1
indices[is_lip]=2
head.data.polygons.foreach_set('material_index',np.zeros(len(hc),dtype=np.int32))
# Soft point colors follow curved features rather than rectangular polygon masks.
color=head.data.color_attributes.new(name='Review_Feature_Color',type='FLOAT_COLOR',domain='POINT')
ay=np.abs(hv[:,1])
t=np.clip((ay-.070)/.245,0,1)
curve=.114-.028*t+.050*np.sin(math.pi*t)
width=.010+.014*np.sin(math.pi*t)
bw=np.exp(-((hv[:,2]-curve)/width)**4)
bw*=((ay>.070)&(ay<.315)&(hv[:,0]>.16))
et=np.clip((ay-eye_y)/.102,-1,1)
lash_curve=eye_z+.068*np.sqrt(np.maximum(0,1-et*et))
lw=np.exp(-((hv[:,2]-lash_curve)/.009)**4)
lw*=((ay>.085)&(ay<.276)&(hv[:,0]>.22)&(hv[:,2]>.018))
lip_curve=-.280+.52*hv[:,1]**2
pw=np.exp(-((hv[:,2]-lip_curve)/.011)**4)*np.clip((.14-ay)/.025,0,1)
pw*=hv[:,0]>.28
colors=np.tile(np.array([.64,.34,.19,1],dtype=np.float32),(len(hv),1))
weight=np.maximum(bw,lw)[:,None]
colors[:,:3]=colors[:,:3]*(1-weight)+np.array([.047,.024,.015])*weight
colors[:,:3]=colors[:,:3]*(1-pw[:,None]) +np.array([.49,.20,.13])*pw[:,None]
color.data.foreach_set('color',colors.ravel())
attribute=skin.node_tree.nodes.new('ShaderNodeVertexColor');attribute.layer_name='Review_Feature_Color'
skin.node_tree.links.new(attribute.outputs['Color'],skin.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])

# Assemble on a 1.6 m reference body. All fitting is in a derived file.
body_scale=1.6/.9802217781543732
head_scale=.213*body_scale
head_offset=Vector((-.027*body_scale,0,.387*body_scale+.4899250567*body_scale))
head.matrix_world=Matrix.Translation(head_offset)@Matrix.Scale(head_scale,4)
head['review_stage']='HD construction; final retopology and facial deformation pending'
head['skin_eyelids_lips_one_mesh']=True

def head_point(p):return head.matrix_world@Vector(p)
def ellipsoid(name,p,radii,mat,col,segments=64,rings=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=head_point(p))
    o=bpy.context.object
    o.name=name
    o.scale=Vector(radii)*head_scale
    for c in list(o.users_collection):c.objects.unlink(o)
    col.objects.link(o)
    o.data.materials.clear()
    o.data.materials.append(mat)
    for poly in o.data.polygons:poly.use_smooth=True
    o.hide_select=False
    return o

eye_mat=material('Eyes_Procedural_Review',(.9,.88,.8),.26)
nodes=eye_mat.node_tree.nodes
links=eye_mat.node_tree.links
coord=nodes.new('ShaderNodeTexCoord')
separate=nodes.new('ShaderNodeSeparateXYZ')
links.new(coord.outputs['Generated'],separate.inputs[0])
def math_node(operation,a,b=None):
    n=nodes.new('ShaderNodeMath');n.operation=operation
    if hasattr(a,'node'):links.new(a,n.inputs[0])
    else:n.inputs[0].default_value=a
    if b is not None:
        if hasattr(b,'node'):links.new(b,n.inputs[1])
        else:n.inputs[1].default_value=b
    return n.outputs[0]
y=math_node('SUBTRACT',separate.outputs['Y'],.5)
z=math_node('SUBTRACT',separate.outputs['Z'],.5)
r=math_node('SQRT',math_node('ADD',math_node('MULTIPLY',y,y),math_node('MULTIPLY',z,z)))
front=math_node('GREATER_THAN',separate.outputs['X'],.6)
iris=math_node('MULTIPLY',math_node('LESS_THAN',r,.29),front)
pupil=math_node('MULTIPLY',math_node('LESS_THAN',r,.17),front)
mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MIX'
mix.inputs[1].default_value=(.9,.88,.81,1)
mix.inputs[2].default_value=(.095,.043,.014,1)
links.new(iris,mix.inputs[0])
mix2=nodes.new('ShaderNodeMixRGB');mix2.blend_type='MIX'
mix2.inputs[2].default_value=(.009,.008,.006,1)
links.new(pupil,mix2.inputs[0]);links.new(mix.outputs[0],mix2.inputs[1])
links.new(mix2.outputs[0],nodes.get('Principled BSDF').inputs['Base Color'])
for side,sign in [('L',1),('R',-1)]:
    eye=ellipsoid(f'Eyeball_{side}',(.187,eye_y*sign,eye_z),(.055,.100,.085),eye_mat,eyes_col)
    eye['purpose']='Independent eyeball for later gaze rig; procedural iris, no embossed pupil'
    eye['character_side']=side

hair=load('hair',hair_col)
hair.name='Hair_HD_Fitted_Study'
hair.matrix_world=head.matrix_world@Matrix.Translation(Vector((.020,0,.110)))@Matrix.Diagonal(Vector((1.25,1.035,1.02,1)))
hair.data.materials.clear();hair.data.materials.append(hair_mat)
# A separate inner hair cap covers exposed scalp between generated locks.
# It is derived from the existing head surface, without changing the face skin.
cap_centers=hv[hf].mean(1)
cap_limit=.02+.30*np.clip((cap_centers[:,0]+.08)/.25,0,1)
cap_keep=cap_centers[:,2]>cap_limit
cap_mesh=bpy.data.meshes.new('Hair_Inner_Cap_WorkingGeometry')
cap=bpy.data.objects.new('Hair_Inner_Cap_Study',cap_mesh);hair_col.objects.link(cap)
cap_v=hv.copy()
cap_origin=np.array([-.11,0,.16],dtype=np.float32)
cap_v=cap_origin+(cap_v-cap_origin)*1.018
rebuild(cap,cap_v,hf,cap_keep)
cap.matrix_world=head.matrix_world.copy()
cap.data.materials.append(hair_mat)
cap['status']='Inner scalp cover for fitting study; strand integration pending'
report['operations'].append({'operation':'add independent inner hair cap to cover exposed scalp', 'final_strand_integration':False})

body=load('fullbody',body_col)
body.name='Body_HD_Head_Replaced_Study'
bv,bf=arrays(body)
bc=bv[bf].mean(1)
bv=rebuild(body,bv,bf,bc[:,2]<.294)
bv,bf=arrays(body)
be=np.sort(np.concatenate([bf[:,[0,1]],bf[:,[1,2]],bf[:,[2,0]]]),axis=1)
be,be_count=np.unique(be,axis=0,return_counts=True)
bb=np.unique(be[be_count==1]);bb=bb[bv[bb,2]>.285]
theta=np.arctan2(bv[bb,1]/(.134*.213),(bv[bb,0]-(.011*.213-.027))/(.1385*.213))
bv[bb,0]=(.011+.1385*np.cos(theta))*.213-.027
bv[bb,1]=.134*np.sin(theta)*.213
bv[bb,2]=.294
body.data.vertices.foreach_set('co',bv.astype(np.float32).ravel());body.data.update()
body.matrix_world=Matrix.Translation(Vector((0,0,.4899250567*body_scale)))@Matrix.Scale(body_scale,4)
body_clay=material('Body_Fit_Clay',(.42,.46,.51),.7)
body.data.materials.clear();body.data.materials.append(body_clay)
body_neck_skin=material('Body_Neck_Review_Skin',(.64,.34,.19),.58)
body.data.materials.append(body_neck_skin)
bv,bf=arrays(body)
bc=bv[bf].mean(1)
clothes=((bc[:,2]>-.105)&(bc[:,2]<.258)&(np.abs(bc[:,1])<.12))|((bc[:,2]>-.218)&(bc[:,2]<-.085)&(np.abs(bc[:,1])<.131))
body.data.polygons.foreach_set('material_index',(bc[:,2]>.257).astype(np.int32))
body['neck_seam_status']='Placement study; not welded, final retopology needed'

# Internal parts are a layout only. The closed HD lip seam remains unchanged.
oral=ellipsoid('Mouth_Interior_Layout',(.245,0,-.277),(.060,.105,.058),cavity,mouth_col)
ov,of=arrays(oral)
rebuild(oral,ov,of,ov[of].mean(1)[:,0]<0)
oral.data.materials.append(cavity)
ellipsoid('Tongue_Layout',(.266,0,-.313),(.040,.065,.012),tongue_mat,mouth_col)
for label,z in [('Upper',-.253),('Lower',-.299)]:
    ellipsoid(f'{label}_Gum_Layout',(.272,0,z),(.018,.084,.014),gum,mouth_col)
    components=[]
    for i in range(6):
        y=(i-2.5)*.024
        x=.295-.9*y*y
        bpy.ops.mesh.primitive_cube_add(size=1,location=head_point((x,y,z+(-.010 if label=='Upper' else .010))))
        tooth=bpy.context.object;tooth.name=f'{label}_Tooth_{i+1}'
        tooth.scale=Vector((.019,.021,.024))*head_scale
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        bevel=tooth.modifiers.new('Rounded tooth edges','BEVEL');bevel.width=.003*head_scale;bevel.segments=3
        bpy.ops.object.modifier_apply(modifier=bevel.name)
        tooth.data.materials.append(teeth)
        for c in list(tooth.users_collection):c.objects.unlink(tooth)
        mouth_col.objects.link(tooth);components.append(tooth)
    bpy.ops.object.select_all(action='DESELECT')
    for o in components:o.select_set(True)
    bpy.context.view_layer.objects.active=components[0]
    bpy.ops.object.join()
    components[0].name=f'{label}_Teeth_Layout'
for o in mouth_col.objects:o['status']='Internal layout only; opening, lip topology and binding pending'

scene.unit_settings.system='METRIC'
scene.render.engine='CYCLES'
scene.cycles.samples=32
scene.cycles.use_denoising=True
try:
    p=bpy.context.preferences.addons['cycles'].preferences
    p.compute_device_type='CUDA';p.get_devices()
    for d in p.devices:d.use=d.type=='CUDA'
    if any(d.type=='CUDA' for d in p.devices):scene.cycles.device='GPU'
except Exception:pass
world=bpy.data.worlds.new('Face_Review_World');world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.62,.67,.72,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.45
scene.world=world
face_center=head_point((0,0,-.02))
for name,offset,power in [('Key',(1,-1.2,1.8),130),('Fill',(1,1,.3),65),('Rim',(-1,0,1.4),110)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.size=.8
    obj=bpy.data.objects.new(name,data);studio.objects.link(obj)
    obj.location=face_center+Vector(offset)
    obj.rotation_euler=(face_center-obj.location).to_track_quat('-Z','Y').to_euler()
    obj.hide_select=True;obj.hide_set(True)
camera=bpy.data.objects.new('Face_Review_Camera',bpy.data.cameras.new('Face_Review_Camera'))
studio.objects.link(camera);camera.data.type='ORTHO';camera.hide_select=True;camera.hide_set(True)
scene.camera=camera
scene.view_settings.view_transform='AgX'
scene.render.image_settings.file_format='PNG'
def view(name,center,offset,scale,width=1100,height=1100):
    camera.location=center+Vector(offset)
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.ortho_scale=scale
    scene.render.resolution_x=width;scene.render.resolution_y=height
    scene.render.resolution_percentage=100
    scene.render.filepath=str(OUT/f'{name}.png')
    bpy.ops.render.render(write_still=True)
view('face-front',face_center,(3,0,0),.43)
view('face-angle',face_center,(3,-1.4,.15),.46)
view('face-side',face_center,(.15,-3,0),.46)
view('body-fit-front',Vector((0,0,.83)),(4,0,0),1.85,1000,1500)
view('body-fit-angle',Vector((0,0,.83)),(4,-1.7,.12),1.85,1000,1500)
head.hide_render=True;hair.hide_render=True;cap.hide_render=True;body.hide_render=True
for o in eyes_col.objects:o.hide_render=True
view('mouth-layout-cutaway',head_point((.27,0,-.275)),(2,-.6,.15),.10)
head.hide_render=False;hair.hide_render=False;cap.hide_render=False;body.hide_render=False
for o in eyes_col.objects:o.hide_render=False
camera.location=face_center+Vector((3,-.6,.12))
camera.rotation_euler=(face_center-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.ortho_scale=.46
bpy.ops.object.select_all(action='DESELECT');head.select_set(True)
bpy.context.view_layer.objects.active=head
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active
            sp.shading.type='MATERIAL'
            sp.overlay.show_floor=False;sp.overlay.show_axis_x=False;sp.overlay.show_axis_y=False
            sp.region_3d.view_location=face_center
            sp.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
            sp.region_3d.view_perspective='ORTHO';sp.region_3d.view_distance=.9
target=OUT/'explorer_b_HD_face_structure_trial.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(target))
report['blend_file']=str(target)
report['mesh_objects']=[{'name':o.name,'vertices':len(o.data.vertices),'polygons':len(o.data.polygons),'selectable':not o.hide_select} for o in bpy.data.objects if o.type=='MESH']
report['limitations']=['HD geometry, not deformation-ready topology.',
    'Eye apertures are construction cuts requiring boundary cleanup in final retopology.',
    'Body/head neck is a placement study, not a welded final seam.',
    'Inner hair cap covers scalp; detailed integration with generated locks remains pending.',
    'Internal mouth is a separate layout. Closed lip seam is unchanged and cannot yet open.',
    'Review colors and procedural eyes are not UV textures.',
    'Garments, replacement hands and shoes are not fitted in this face-focused trial.']
(OUT/'construction-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('FACE_STRUCTURE_TRIAL_READY',flush=True)
