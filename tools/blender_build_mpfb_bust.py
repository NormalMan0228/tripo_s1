"""Style the tested MPFB topology as an Explorer B clavicle bust.

One common coordinate map is applied to Basis AND every facial target on all
parts. This keeps the template's eyelid/lash correspondence through styling.
The full template file is never overwritten.
"""
import bpy, math, json
from pathlib import Path
from collections import Counter,defaultdict
from mathutils import Vector
from bl_ext.user_default.mpfb.services.faceservice import ARKIT_FACEUNITS,META_VISEMES,MICROSOFT_VISEMES

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_pipeline_v3/02_clavicle_bust'
REPORT=ROOT/'artifacts/mpfb-clavicle-bust-20261004'
OUT.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene;scene.frame_set(1)
source=bpy.data.objects['Template_Face_Body']
FACIAL=set(ARKIT_FACEUNITS)|set(META_VISEMES)|set(MICROSOFT_VISEMES)

def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)))
    return t*t*(3-2*t)

def monotone(value,knots):
    # Shape-preserving cubic interpolation: continuous first derivatives and no folds.
    xs=[k[0] for k in knots];ys=[k[1] for k in knots]
    hs=[b-a for a,b in zip(xs,xs[1:])]
    ds=[(b-a)/h for a,b,h in zip(ys,ys[1:],hs)]
    ms=[ds[0]]
    for i in range(1,len(xs)-1):
        a,b=ds[i-1],ds[i];w1=2*hs[i]+hs[i-1];w2=hs[i]+2*hs[i-1]
        ms.append((w1+w2)/(w1/a+w2/b) if a*b>0 else 0)
    ms.append(ds[-1])
    if value<=xs[0]:return ys[0]+(value-xs[0])*ms[0]
    if value>=xs[-1]:return ys[-1]+(value-xs[-1])*ms[-1]
    i=next(i for i in range(len(hs)) if value<=xs[i+1]);t=(value-xs[i])/hs[i]
    return (2*t**3-3*t*t+1)*ys[i]+(t**3-2*t*t+t)*hs[i]*ms[i]+(-2*t**3+3*t*t)*ys[i+1]+(t**3-t*t)*hs[i]*ms[i+1]

def style(co):
    x,y,z=map(float,co)
    x*=.55+.90*smooth(1.375,1.535,z)
    y*=.84
    dx_total=dz_total=0.0
    for cx in [-.046,.046]:
        dx=x-cx;dz=z-1.553
        r=math.sqrt((dx/.065)**2+(dz/.072)**2+((y+.104)/.095)**2)
        # Compact C2 field ends before the mouth. It does not compress whole
        # horizontal bands of facial skin or change the neutral mouth corners.
        w=(1-r)**4*(4*r+1) if r<1 else 0
        dx_total+=.85*dx*w;dz_total+=1.2*dz*w
    x+=dx_total;z+=dz_total
    z=z-1.395+.020*(1-smooth(1.375,1.430,z))
    return Vector((x,y,z))

def mixed_basis(obj):
    sk=obj.data.shape_keys
    coords=[v.co.copy() for v in obj.data.vertices]
    if sk:
        basis=sk.key_blocks[0]
        coords=[p.co.copy() for p in basis.data]
        for key in sk.key_blocks[1:]:
            if key.name in FACIAL or abs(key.value)<1e-8:continue
            for i,point in enumerate(key.data):coords[i]+=(point.co-basis.data[i].co)*key.value
        if 'mouthClose' in sk.key_blocks:
            for i,point in enumerate(sk.key_blocks['mouthClose'].data):coords[i]+=(point.co-basis.data[i].co)*.20
        for name in ['eyeWideLeft','eyeWideRight']:
            if name in sk.key_blocks:
                for i,point in enumerate(sk.key_blocks[name].data):coords[i]+=(point.co-basis.data[i].co)*.95
    return coords

def source_groups(obj):
    return {g.name:{v.index for v in obj.data.vertices if any(m.group==g.index and m.weight>.5 for m in v.groups)} for g in obj.vertex_groups if g.name in ['body','lips']}

def build_part(obj,name,is_skin=False):
    base=mixed_basis(obj);groups=source_groups(obj)
    # Clip the actual polygon edges at a single clavicle plane. Interpolate all
    # shape keys and UVs at new cut vertices instead of dragging jagged rows down.
    cut_z=1.375
    weights=[];index={};polys=[];uvpolys=[];matids=[]
    def register(ws):
        ident=tuple(sorted((i,round(w,8)) for i,w in ws.items() if w>1e-8))
        if ident not in index:index[ident]=len(weights);weights.append(dict(ident))
        return index[ident]
    for poly in obj.data.polygons:
        if is_skin and not all(i in groups['body'] for i in poly.vertices):continue
        entries=[(base[i],{i:1.0},obj.data.uv_layers.active.data[li].uv.copy() if obj.data.uv_layers else Vector((0,0))) for i,li in zip(poly.vertices,poly.loop_indices)]
        if is_skin:
            clipped=[]
            for a,b in zip(entries,entries[1:]+entries[:1]):
                ain=a[0].z>=cut_z;bin=b[0].z>=cut_z
                if ain:clipped.append(a)
                if ain!=bin:
                    t=(cut_z-a[0].z)/(b[0].z-a[0].z)
                    ws={i:w*(1-t) for i,w in a[1].items()}
                    for i,w in b[1].items():ws[i]=ws.get(i,0)+w*t
                    clipped.append((a[0].lerp(b[0],t),ws,a[2].lerp(b[2],t)))
            entries=clipped
        if len(entries)<3:continue
        polys.append(tuple(register(e[1]) for e in entries));uvpolys.append([e[2] for e in entries]);matids.append(poly.material_index)
    bases=[sum((base[i]*w for i,w in ws.items()),Vector()) for ws in weights]
    styled=[style(co) for co in bases]
    counts=Counter(tuple(sorted((a,b))) for face in polys for a,b in zip(face,face[1:]+face[:1]))
    cut=set();fixed={}
    if is_skin:
        for (a,b),count in counts.items():
            if count==1 and max(abs(bases[a].z-cut_z),abs(bases[b].z-cut_z))<1e-5:cut.update((a,b))
        # Align only the lower cut rim; none of the facial vertices are moved here.
        for i in cut:styled[i].z=0
        adjacency=defaultdict(list)
        for (a,b),count in counts.items():
            if count==1 and a in cut and b in cut:adjacency[a].append(b);adjacency[b].append(a)
        if adjacency:
            start=min(adjacency);loop=[start];prev=None;cur=start
            while True:
                options=[i for i in adjacency[cur] if i!=prev]
                if not options:break
                nex=next((i for i in options if i not in loop),options[0])
                if nex==start or nex in loop:break
                loop.append(nex);prev,cur=cur,nex
            if len(loop)>4:
                area=sum(styled[a].x*styled[b].y-styled[b].x*styled[a].y for a,b in zip(loop,loop[1:]+loop[:1]))
                if area<0:loop.reverse()
                center=sum((styled[i] for i in loop),Vector())/len(loop)
                previous=loop
                for scale,depth in [(1.0,-.0015),(.975,-.0035),(.90,-.004)]:
                    ring=[]
                    for i in loop:
                        coord=center+(styled[i]-center)*scale;coord.z=depth
                        j=len(styled);ring.append(j);styled.append(coord);fixed[j]=coord.copy()
                        weights.append(weights[i].copy());bases.append(bases[i].copy())
                    for a,b,na,nb in zip(previous,previous[1:]+previous[:1],ring,ring[1:]+ring[:1]):polys.append((b,a,na,nb))
                    previous=ring
                polys.append(tuple(reversed(previous)))
    mesh=bpy.data.meshes.new(name+'_Mesh');mesh.from_pydata(styled,[],polys);mesh.update()
    result=bpy.data.objects.new(name,mesh);scene.collection.objects.link(result)
    for mat in obj.data.materials:mesh.materials.append(mat)
    for p,mi in zip(mesh.polygons,matids):p.material_index=mi;p.use_smooth=True
    if obj.data.uv_layers:
        uv=mesh.uv_layers.new(name='UVMap')
        for p,coords in zip(mesh.polygons,uvpolys):
            for newli,coord in zip(p.loop_indices,coords):uv.data[newli].uv=coord
    result.shape_key_add(name='Basis')
    if obj.data.shape_keys:
        original_basis=obj.data.shape_keys.key_blocks[0]
        for key in obj.data.shape_keys.key_blocks:
            if key.name not in FACIAL:continue
            new=result.shape_key_add(name=key.name)
            for j,ws in enumerate(weights):
                delta=sum(((key.data[i].co-original_basis.data[i].co)*w for i,w in ws.items()),Vector())
                if key.name in ['eyeBlinkLeft','eyeBlinkRight']:
                    wide=obj.data.shape_keys.key_blocks.get(key.name.replace('Blink','Wide'))
                    if wide:delta-=sum(((wide.data[i].co-original_basis.data[i].co)*w*.95 for i,w in ws.items()),Vector())
                new.data[j].co=style(bases[j]+delta)
                if j in cut:new.data[j].co.z=0
                if j in fixed:new.data[j].co=fixed[j]
    if is_skin:
        lips=result.vertex_groups.new(name='Lips')
        lip_ids=[j for j,ws in enumerate(weights) if sum(w for i,w in ws.items() if i in groups.get('lips',set()))>.5]
        if lip_ids:lips.add(lip_ids,1,'REPLACE')
    sub=result.modifiers.new('Surface smoothing (1 level)','SUBSURF');sub.levels=1;sub.render_levels=1
    return result,{'vertices':len(weights),'faces':len(polys),'shape_keys':len(result.data.shape_keys.key_blocks),'cut_rim_vertices':len(cut)},cut

sources=[source]+[bpy.data.objects['Template_Face_Body.'+suffix] for suffix in ['high-poly','eyebrow001','eyelashes01','teeth_base','tongue01']]
names=['Face_Neck_Clavicle','Eyes','Eyebrows','Eyelashes','Teeth','Tongue']
parts={};stats={}
for original,name in zip(sources,names):
    ob,info,cut=build_part(original,name,name=='Face_Neck_Clavicle')
    parts[name]=ob;stats[name]=info
    if name=='Face_Neck_Clavicle':rim=cut
for ob in list(bpy.data.objects):
    if ob not in parts.values():bpy.data.objects.remove(ob,do_unlink=True)
human=parts['Face_Neck_Clavicle'];keys=human.data.shape_keys.key_blocks
for ob in parts.values():
    if ob==human:continue
    for key in ob.data.shape_keys.key_blocks:
        if key.name=='Basis' or key.name not in keys:continue
        driver=key.driver_add('value').driver;driver.type='AVERAGE'
        var=driver.variables.new();var.name='face_value';var.type='SINGLE_PROP'
        var.targets[0].id_type='KEY';var.targets[0].id=human.data.shape_keys;var.targets[0].data_path=keys[key.name].path_from_id('value')

def mat(name,color,rough=.48):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough
    return m
skin=mat('Warm peach skin',(.50,.24,.13),.47)
skin.node_tree.nodes['Principled BSDF'].inputs['Subsurface Weight'].default_value=.065
lips=mat('Soft rose lips',(.42,.145,.105),.40)
mucosa=mat('Inner mouth mucosa',(.20,.036,.042),.55)
human.data.materials.clear()
for material in [skin,lips,mucosa]:human.data.materials.append(material)
lipgroup=human.vertex_groups.get('Lips')
lipverts={v.index for v in human.data.vertices if any(g.group==lipgroup.index for g in v.groups)}
for poly in human.data.polygons:
    if sum(i in lipverts for i in poly.vertices)>=len(poly.vertices)-1:poly.material_index=1
    else:poly.material_index=0
    c=sum((human.data.vertices[i].co for i in poly.vertices),Vector())/len(poly.vertices)
    # Oral color comes from the separate tongue; do not classify external neck
    # or jaw faces as mucosa merely because they lie behind the lips.

# Brown eyes with larger round pupils and clear wet highlights, using the official
# texture plus shader adjustments. No reference bitmap is edited.
eyes=parts['Eyes']
cornea=mat('Clear cornea',(.98,.98,.98),.035)
cornea.node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value=1.0
cornea.node_tree.nodes['Principled BSDF'].inputs['IOR'].default_value=1.376
cornea_index=len(eyes.data.materials)
cornea_faces=set()
for p in eyes.data.polygons:
    if all(eyes.data.uv_layers.active.data[li].uv.x>.83 and eyes.data.uv_layers.active.data[li].uv.y<.18 for li in p.loop_indices):cornea_faces.add(p.index)
for point in eyes.data.uv_layers.active.data:
    if point.uv.x>.83 and point.uv.y<.18:continue
    cx,cy=(.29,.285) if point.uv.x<.5 else (.705,.70)
    point.uv.x=cx+(point.uv.x-cx)*.80
    point.uv.y=cy+(point.uv.y-cy)*.96
for material in eyes.data.materials:
    if not material or not material.use_nodes:continue
    nodes=material.node_tree.nodes;links=material.node_tree.links
    shader=next((n for n in nodes if n.type=='BSDF_PRINCIPLED'),None)
    tex=next((n for n in nodes if n.type=='TEX_IMAGE'),None)
    if not shader or not tex:continue
    color=nodes.new('ShaderNodeHueSaturation');color.inputs['Hue'].default_value=.53;color.inputs['Saturation'].default_value=.6;color.inputs['Value'].default_value=.80
    links.new(tex.outputs['Color'],color.inputs['Color'])
    uv=nodes.new('ShaderNodeTexCoord');dists=[]
    for center in [(.29,.285,0),(.705,.70,0)]:
        sub=nodes.new('ShaderNodeVectorMath');sub.operation='SUBTRACT';sub.inputs[1].default_value=center;links.new(uv.outputs['UV'],sub.inputs[0])
        length=nodes.new('ShaderNodeVectorMath');length.operation='LENGTH';links.new(sub.outputs[0],length.inputs[0]);dists.append(length.outputs['Value'])
    minimum=nodes.new('ShaderNodeMath');minimum.operation='MINIMUM';links.new(dists[0],minimum.inputs[0]);links.new(dists[1],minimum.inputs[1])
    ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.050;ramp.color_ramp.elements[0].color=(1,1,1,1);ramp.color_ramp.elements[1].position=.057;ramp.color_ramp.elements[1].color=(0,0,0,1)
    links.new(minimum.outputs[0],ramp.inputs[0])
    mix=nodes.new('ShaderNodeMixRGB');mix.inputs[2].default_value=(.002,.001,.0005,1);links.new(ramp.outputs['Color'],mix.inputs[0]);links.new(color.outputs[0],mix.inputs[1]);links.new(mix.outputs[0],shader.inputs['Base Color'])
    shader.inputs['Roughness'].default_value=.16;shader.inputs['Coat Weight'].default_value=.42;shader.inputs['Coat Roughness'].default_value=.08
eyes.data.materials.append(cornea)
for i in cornea_faces:eyes.data.polygons[i].material_index=cornea_index

# All the face targets remain available; a compact slow sequence makes review easy.
poses=[('Neutral',{}),('Blink',{'eyeBlinkLeft':1,'eyeBlinkRight':1}),('Look_Left',{'eyeLookOutLeft':.45,'eyeLookInRight':.45}),('Look_Right',{'eyeLookInLeft':.45,'eyeLookOutRight':.45}),('Smile',{'mouthSmileLeft':.5,'mouthSmileRight':.5}),('Jaw_Open',{'jawOpen':.45}),('Pucker',{'mouthPucker':.5})]
animated=sorted({n for _,p in poses for n in p})
for n in animated:keys[n].value=0;keys[n].keyframe_insert('value',frame=1)
for i,(name,values) in enumerate(poses[1:]):
    start=i*90+1
    for frame,settings in [(start,{}),(start+25,values),(start+55,values),(start+80,{})]:
        for n in animated:keys[n].value=settings.get(n,0);keys[n].keyframe_insert('value',frame=frame)
    scene.timeline_markers.new(name,frame=start+25)
action=human.data.shape_keys.animation_data.action;action.name='Explorer_Bust_Face_Review_18s'
for fc in action.fcurves:
    for k in fc.keyframe_points:k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
scene.frame_start=1;scene.frame_end=540;scene.render.fps=30

scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
scene.render.resolution_x=820;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.16,.20,.23,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.45
scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-.7
camera_data=bpy.data.cameras.new('Portrait');camera=bpy.data.objects.new('Portrait',camera_data);scene.collection.objects.link(camera);scene.camera=camera;camera_data.type='ORTHO';camera_data.ortho_scale=.34
target=Vector((0,-.015,.147))
def camera_at(angle):
    a=math.radians(angle);camera.location=target+Vector((math.sin(a)*1.3,-math.cos(a)*1.3,.012));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
camera_at(0)
for name,offset,power,size in [('Key',(-.45,-.55,.65),45,.6),('Fill',(.5,-.35,.25),22,.5),('Rim',(.25,.38,.55),60,.45)]:
    ld=bpy.data.lights.new(name,'AREA');ld.energy=power;ld.shape='DISK';ld.size=size
    light=bpy.data.objects.new(name,ld);scene.collection.objects.link(light);light.location=target+Vector(offset);light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');human.select_set(True);bpy.context.view_layer.objects.active=human
human.active_shape_key_index=keys.find('eyeBlinkLeft')
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active;space.region_3d.view_perspective='CAMERA';space.region_3d.view_camera_zoom=5;space.overlay.show_overlays=False;space.shading.type='MATERIAL';space.show_region_ui=False
for text in list(bpy.data.texts):bpy.data.texts.remove(text)
note=bpy.data.texts.new('READ_ME_Explorer_Bust')
note.write('Explorer B / MPFB clavicle bust / 2026-10-04\nNeutral closed mouth: frame 1. Space: 18-second expression review.\nFace_Neck_Clavicle shape keys drive lashes, brows and oral parts.\nSkin is a single connected MPFB-derived surface. No detached eyelid patches.\nReference: art/references/explorer_b_faceit_comparison_v1/03_head_neck_clavicle.png\nThis is a design review sculpt, not a final game export.\n')
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_b_clavicle_bust_v1.blend'))
report={'source':'MPFB 2.0.17 tested template','reference':'art/references/explorer_b_faceit_comparison_v1/03_head_neck_clavicle.png','parts':stats,'facial_units':len(ARKIT_FACEUNITS),'animation_seconds':18,'rendered':[],'paid_api_calls':0}
(REPORT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
for label,frame,angle in [('front',1,0),('three_quarter',1,40),('profile',1,90),('blink',26,0),('smile',296,0),('mouth_open',386,0)]:
    scene.frame_set(frame);camera_at(angle);scene.render.filepath=str(REPORT/(label+'.png'));bpy.ops.render.render(write_still=True);report['rendered'].append(label+'.png')
(REPORT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('BUST_COMPLETE',json.dumps(report),flush=True)
