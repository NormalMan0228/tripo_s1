"""Developer-only Stefan sculpt trial: native Mask Slice + sculpt brush strokes.

Run in a fresh Blender GUI process, not --background: native brush replay needs
an initialized 3D region. Source FBX files are never overwritten. No generation,
whole-body remesh, texture, or rigging is performed. Output is a review candidate.
"""
import bpy
import bmesh
import hashlib
import json
import math
import traceback
from collections import Counter
from pathlib import Path
from mathutils import Vector, Matrix
from bpy_extras.view3d_utils import location_3d_to_region_2d

ROOT=Path(__file__).resolve().parents[1]
CHAR=ROOT/'art/characters/explorer_b_fullbody_v2'
OUT=CHAR/'05_sculpt_trial'
OUT.mkdir(parents=True,exist_ok=True)
LOG={'state':'running','source_hashes':{},'cuts':[],'strokes':[],'joins':[],
     'whole_body_remesh':False,'rigged':False,'new_api_credits':0}
SOURCES={'body':CHAR/'03_generated_p2/model.fbx',
         **{p:CHAR/'04_replacement_parts_p2'/p/'model.fbx' for p in ('head','hand','hair')}}
for name,path in SOURCES.items():LOG['source_hashes'][name]={'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def store():
 (OUT/'sculpt-log.json').write_text(json.dumps(LOG,ensure_ascii=False,indent=2),encoding='utf-8')

def collection(name):
 c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c

def move(o,c):
 for old in list(o.users_collection):old.objects.unlink(o)
 c.objects.link(o)

def active(o):
 if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
 for old in bpy.context.selected_objects:old.select_set(False)
 o.hide_set(False);o.select_set(True);bpy.context.view_layer.objects.active=o

def import_mesh(path,name,c):
 prior=set(bpy.data.objects)
 bpy.ops.import_scene.fbx(filepath=str(path),use_anim=False)
 imported=[o for o in bpy.data.objects if o not in prior]
 objects=[o for o in imported if o.type=='MESH']
 if len(objects)!=1:raise RuntimeError(f'{name}: expected one source mesh, got {len(objects)}')
 o=objects[0]
 matrix=o.matrix_world.copy();o.parent=None;o.matrix_world=Matrix.Identity(4)
 for v in o.data.vertices:v.co=matrix@v.co
 o.name=name;o.data.name=name+'_Mesh';move(o,c)
 for extra in imported:
  if extra!=o:bpy.data.objects.remove(extra,do_unlink=True)
 return o

def groups(mesh):
 parent=list(range(len(mesh.vertices)))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for e in mesh.edges:
  a,b=map(find,e.vertices);parent[a]=b
 result={}
 for v in mesh.vertices:result.setdefault(find(v.index),[]).append(v.index)
 return sorted(result.values(),key=lambda g:-len(g))

def subset(source,ids,name,c):
 bm=bmesh.new();bm.from_mesh(source.data);bm.verts.ensure_lookup_table();wanted=set(ids)
 bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.index not in wanted],context='VERTS')
 data=bpy.data.meshes.new(name+'_Mesh');bm.to_mesh(data);bm.free()
 o=bpy.data.objects.new(name,data);c.objects.link(o);return o

def material(name,color):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=.73
 return m

def assign(o,m):
 o.data.materials.clear();o.data.materials.append(m)
 for p in o.data.polygons:p.material_index=0;p.use_smooth=True

def mask(o,values,label):
 a=o.data.attributes.get('.sculpt_mask') or o.data.attributes.new('.sculpt_mask','FLOAT','POINT')
 vals=[float(values(v)) for v in o.data.vertices]
 a.data.foreach_set('value',vals);o.data.update()
 o['mask_purpose']=label
 copy=o.data.attributes.get('review_mask') or o.data.attributes.new('review_mask','FLOAT','POINT')
 copy.data.foreach_set('value',vals)
 return vals

def topology(o):
 bm=bmesh.new();bm.from_mesh(o.data)
 report={'vertices':len(bm.verts),'polygons':len(bm.faces),
         'polygon_sides':dict(Counter(len(f.verts) for f in bm.faces)),
         'boundary_edges':sum(e.is_boundary for e in bm.edges),
         'nonmanifold_multiface_edges':sum(len(e.link_faces)>2 for e in bm.edges)}
 bm.free();return report

def slice_mask(o,c,label):
 active(o);before=topology(o)
 with bpy.context.temp_override(window=bpy.context.window,area=AREA,region=REGION):
  bpy.ops.object.mode_set(mode='SCULPT')
  result=bpy.ops.sculpt.paint_mask_slice(mask_threshold=.5,fill_holes=False,new_object=False)
  bpy.ops.object.mode_set(mode='OBJECT')
 LOG['cuts'].append({'object':o.name,'method':'bpy.ops.sculpt.paint_mask_slice',
                      'label':label,'fill_holes':False,'result':list(result),'before':before,'after':topology(o)})
 if len(o.data.vertices)==0:raise RuntimeError('Mask Slice removed whole mesh: '+o.name)
 move(o,c);store()

def ring(o,point,normal,tolerance):
 bm=bmesh.new();bm.from_mesh(o.data)
 result=[e for e in bm.edges if e.is_boundary and all(abs((v.co-point).dot(normal))<tolerance for v in e.verts)]
 coords=[v.co.copy() for e in result for v in e.verts]
 bm.free();return coords

def join_seam(a,b,name,point,normal,tolerance):
 active(a);b.select_set(True);bpy.ops.object.join();a.name=name
 bm=bmesh.new();bm.from_mesh(a.data)
 seam=[e for e in bm.edges if e.is_boundary]
 # Require exactly two complete boundary loops. Never silently bridge face holes.
 pending=set(seam);loops=[]
 while pending:
  seed=pending.pop();edges={seed};verts=set(seed.verts);changed=True
  while changed:
   changed=False
   for e in list(pending):
    if any(v in verts for v in e.verts):pending.remove(e);edges.add(e);verts.update(e.verts);changed=True
  distance=sum((v.co-point).dot(normal) for v in verts)/len(verts)
  if abs(distance)<tolerance*2:
   if any(sum(e in edges for e in v.link_edges)!=2 for v in verts):
    bm.free();raise RuntimeError('Non-loop seam boundary: '+name)
   loops.append(edges)
 if len(loops)!=2:
  bm.free();raise RuntimeError(f'{name}: expected 2 seam loops, got {len(loops)}')
 seam=[e for loop in loops for e in loop]
 # Match ordered cross sections before bridging. Mask Slice follows source
 # vertices, so its raw border can be jagged and larger than the new part.
 axis_u=Vector((1,0,0));axis_u=(axis_u-normal*axis_u.dot(normal)).normalized()
 axis_v=normal.cross(axis_u).normalized()
 rings=[list({v for e in loop for v in e.verts}) for loop in loops]
 rings.sort(key=lambda vs:sum((v.co-point).dot(normal) for v in vs)/len(vs))
 centers=[sum((v.co for v in vs),Vector())/len(vs) for vs in rings]
 extents=[(max(abs((v.co-c).dot(axis_u)) for v in vs),max(abs((v.co-c).dot(axis_v)) for v in vs)) for c,vs in zip(centers,rings)]
 if 'Arm' in name:
  # New wrist is the positive-distance ring, retaining its original oval size.
  ru,rv=extents[1];center=point
 else:
  ru=(extents[0][0]+extents[1][0])*.5;rv=(extents[0][1]+extents[1][1])*.5
  center=(centers[0]+centers[1])*.5;center-=normal*(center-point).dot(normal)
 distance=.004 if 'Arm' in name else .0035
 for side,vs in enumerate(rings):
  c=centers[side];eu,ev=extents[side]
  # Fit the adjacent band as well as the border. Moving just border vertices
  # leaves a cuff-like flange and pinched triangles immediately beside it.
  island=set(vs);stack=list(vs)
  while stack:
   v=stack.pop()
   for e in v.link_edges:
    other=e.other_vert(v)
    if other not in island:island.add(other);stack.append(other)
  for v in island-set(vs):
   depth=abs((v.co-c).dot(normal));falloff=max(0,1-depth/.065)
   if not falloff:continue
   falloff=falloff*falloff*(3-2*falloff)
   offset=v.co-c
   desired=center+axis_u*(offset.dot(axis_u)*ru/max(eu,1e-6))+axis_v*(offset.dot(axis_v)*rv/max(ev,1e-6))+normal*(offset.dot(normal)+(side-.5)*distance)
   v.co=v.co.lerp(desired,falloff)
  def angle(v):return math.atan2((v.co-c).dot(axis_v)/max(ev,1e-6),(v.co-c).dot(axis_u)/max(eu,1e-6))
  neighbors={v:[e.other_vert(v) for e in loops[0].union(loops[1]) if v in e.verts] for v in vs}
  start=min(vs,key=angle);ordered=[start];previous=None;current=start
  while len(ordered)<len(vs):
   following=next(v for v in neighbors[current] if v!=previous and (v!=start or len(ordered)==len(vs)))
   ordered.append(following);previous,current=current,following
  area=sum((ordered[i].co-c).dot(axis_u)*(ordered[(i+1)%len(vs)].co-c).dot(axis_v)
           -(ordered[(i+1)%len(vs)].co-c).dot(axis_u)*(ordered[i].co-c).dot(axis_v) for i in range(len(vs)))
  if area<0:ordered=[ordered[0]]+list(reversed(ordered[1:]))
  # Circular order follows actual boundary angles; positive normal offsets keep
  # the loops apart. Only seam vertices are fitted, not the face or fingers.
  for i,v in enumerate(ordered):
   theta=-math.pi+i*2*math.pi/len(ordered);v.co=center+axis_u*(math.cos(theta)*ru)+axis_v*(math.sin(theta)*rv)+normal*((side-.5)*distance)
  rings[side]=ordered
 a_ring,b_ring=rings;n,m=len(a_ring),len(b_ring);i=j=0
 count_before=len(bm.faces)
 while i<n or j<m:
  ai=a_ring[i%n];bj=b_ring[j%m]
  ni=(i+1)/n if i<n else float('inf');nj=(j+1)/m if j<m else float('inf')
  if abs(ni-nj)<.48/max(n,m):
   face=bm.faces.new((ai,a_ring[(i+1)%n],b_ring[(j+1)%m],bj));i+=1;j+=1
  elif ni<nj:
   face=bm.faces.new((ai,a_ring[(i+1)%n],bj));i+=1
  else:
   face=bm.faces.new((ai,b_ring[(j+1)%m],bj));j+=1
  face.smooth=True
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
 remaining=sum(e.is_boundary for e in seam)
 LOG['joins'].append({'object':name,'method':'ordered oval boundary fit and quad/triangle zipper bridge',
                      'boundary_loop_edges':[len(x) for x in loops],
         'new_faces':len(bm.faces)-count_before,'seam_edges_still_open':remaining,
         'ellipse_radius_m':[ru,rv],'seam_gap_m':distance})
 if remaining:bm.free();raise RuntimeError('Bridge left seam edges open: '+name)
 bm.to_mesh(a.data);bm.free();store();return a

def save(name):
 bpy.context.preferences.filepaths.save_version=0
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/name))

def stroke(o,brush_name,points,radius,strength,label):
 active(o);o.data.update()
 before=[v.co.copy() for v in o.data.vertices]
 masks=[x.value for x in o.data.attributes['.sculpt_mask'].data]
 with bpy.context.temp_override(window=bpy.context.window,area=AREA,region=REGION):
  bpy.ops.object.mode_set(mode='SCULPT')
  result=bpy.ops.brush.asset_activate(asset_library_type='ESSENTIALS',
      relative_asset_identifier='brushes/essentials_brushes-mesh_sculpt.blend/Brush/'+brush_name)
  if result!={'FINISHED'}:raise RuntimeError('brush activation failed')
  brush=bpy.context.scene.tool_settings.sculpt.brush
  brush.strength=strength;brush.use_locked_size='SCENE';brush.unprojected_radius=radius
  unified=bpy.context.scene.tool_settings.unified_paint_settings
  unified.use_unified_size=False;unified.use_unified_strength=False
  sculpt=bpy.context.scene.tool_settings.sculpt
  sculpt.use_symmetry_x=False;sculpt.use_symmetry_y=False;sculpt.use_symmetry_z=False
  AREA.spaces.active.region_3d.update()
  projected=[location_3d_to_region_2d(REGION,AREA.spaces.active.region_3d,p) for p in points]
  if any(p is None for p in projected):raise RuntimeError('stroke projection failed')
  samples=[dict(name=label,mouse=tuple(projected[i]),mouse_event=tuple(projected[i]),location=tuple(p),
                size=100,pressure=1,time=i*.1,is_start=i==0,x_tilt=0,y_tilt=0) for i,p in enumerate(points)]
  result=bpy.ops.sculpt.brush_stroke(stroke=samples,override_location=False)
  bpy.ops.object.mode_set(mode='OBJECT')
 deltas=[(v.co-before[i]).length for i,v in enumerate(o.data.vertices)]
 changed=sum(d>1e-8 for d in deltas)
 record={'object':o.name,'brush':brush_name,'method':'bpy.ops.sculpt.brush_stroke',
         'label':label,'radius_m':radius,'strength':strength,'path':[list(p) for p in points],
         'result':list(result),'changed_vertices':changed,'max_delta_m':max(deltas,default=0),
         'fully_masked_vertices':sum(m>.999 for m in masks),
         'fully_masked_max_delta_m':max((d for d,m in zip(deltas,masks) if m>.999),default=0)}
 LOG['strokes'].append(record);store()
 if record['fully_masked_max_delta_m']>1e-7:raise RuntimeError('Protected mesh moved')
 print('SCULPT_STROKE',label,changed,record['max_delta_m'],flush=True)

def main():
 global AREA,REGION
 try:
  for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
  AREA=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
  REGION=next(r for r in AREA.regions if r.type=='WINDOW')
  AREA.spaces.active.region_3d.view_rotation=Vector((-1,0,0)).to_track_quat('-Z','Y')
  AREA.spaces.active.region_3d.view_perspective='ORTHO'
  AREA.spaces.active.region_3d.view_location=(0,0,1.1)
  AREA.spaces.active.region_3d.view_distance=2.3
  original=collection('00_SOURCE_REFERENCE_DO_NOT_EDIT')
  bodycol=collection('10_BODY_P2_WORKING')
  facecol=collection('20_HEAD_EYES_WORKING')
  haircol=collection('30_HAIR_REPLACEABLE')
  clothcol=collection('40_UNDERLAYER_SEPARATE')
  skin=material('Review Skin - unified clay',(.61,.53,.46))
  cloth=material('Review Opaque Underlayer',(.26,.36,.43))
  hairmat=material('Review Hair',(.09,.085,.13))
  source=import_mesh(SOURCES['body'],'Fullbody_P2_Source',original)
  height=max(v.co.z for v in source.data.vertices)-min(v.co.z for v in source.data.vertices)
  bottom=min(v.co.z for v in source.data.vertices)
  factor=1.7/height
  for v in source.data.vertices:v.co=Vector((v.co.x*factor,v.co.y*factor,(v.co.z-bottom)*factor))
  source['normalization']='1.7m original body height, front +X, left/right Y'
  ids=groups(source.data)
  if len(ids)!=7:raise RuntimeError('Fullbody island structure changed')
  parts=[]
  for i,g in enumerate(ids):
   if i==0:name='Neck_From_Base';c=bodycol
   elif i in (1,2):name='Arm_PosY' if sum(source.data.vertices[n].co.y for n in g)>0 else 'Arm_NegY';c=bodycol
   elif i in (3,4):name='Leg_PosY' if sum(source.data.vertices[n].co.y for n in g)>0 else 'Leg_NegY';c=bodycol
   else:name='Underlayer_Top' if i==5 else 'Underlayer_Shorts';c=clothcol
   o=subset(source,g,name,c);assign(o,cloth if i>=5 else skin);parts.append(o)
  source.hide_render=True;source.hide_set(True)
  neck=parts[0];arm=next(o for o in parts if o.name=='Arm_PosY')
  otherarm=next(o for o in parts if o.name=='Arm_NegY');otherarm.hide_render=True;otherarm.hide_set(True);move(otherarm,original)
  leg=next(o for o in parts if o.name=='Leg_PosY')
  otherleg=next(o for o in parts if o.name=='Leg_NegY');otherleg.hide_render=True;otherleg.hide_set(True);move(otherleg,original)
  legmirror=leg.modifiers.new('Opposite leg - exact Y mirror','MIRROR');legmirror.use_axis=(False,True,False)
  neck_z=1.332
  wrist=Vector((.018,.382,.858));direction=Vector((0,.6,-.8))
  mask(neck,lambda v:1 if v.co.z>neck_z else 0,'cut mask: remove original head, keep lower neck')
  mask(arm,lambda v:1 if (v.co-wrist).dot(direction)>0 else 0,'cut mask: remove original hand')
  save('01_cut_masks.blend')
  slice_mask(neck,bodycol,'original head removal, lower neck retained')
  slice_mask(arm,bodycol,'original hand removal, forearm retained')
  # Freeze a copy of actual cut masks for later viewport inspection.
  head=import_mesh(SOURCES['head'],'Head_P2_Replacement',facecol)
  for v in head.data.vertices:v.co=Vector((v.co.x*.33-.0166,v.co.y*.365,v.co.z*.375+1.510))
  assign(head,skin)
  mask(head,lambda v:1 if v.co.z<1.339 else 0,'cut mask: trim replacement neck base')
  slice_mask(head,facecol,'replacement head lower neck trim')
  hand=import_mesh(SOURCES['hand'],'Hand_P2_Replacement_PosY',bodycol)
  mask(hand,lambda v:1 if v.co.z<-.477 else 0,'cut mask: trim generated open wrist boundary')
  slice_mask(hand,bodycol,'replacement hand wrist trim')
  # Close only tiny side slits, excluding the main wrist loop.
  bm=bmesh.new();bm.from_mesh(hand.data)
  pending={e for e in bm.edges if e.is_boundary};holes=[]
  while pending:
   seed=pending.pop();loop={seed};vertices=set(seed.verts);changed=True
   while changed:
    changed=False
    for e in list(pending):
     if any(v in vertices for v in e.verts):pending.remove(e);loop.add(e);vertices.update(e.verts);changed=True
   if len(loop)<=12 and min(v.co.z for v in vertices)>-.45:holes.append(loop)
  for loop in holes:bmesh.ops.holes_fill(bm,edges=list(loop),sides=12)
  LOG['hand_small_holes_repaired']=len(holes)
  bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(hand.data);bm.free()
  rot=Matrix.Rotation(math.radians(-143.1301),3,'X')@Matrix.Rotation(math.pi,3,'Z')
  # Palm faces front, thumb points toward torso; opposite arm is a Y mirror.
  for v in hand.data.vertices:v.co=wrist+direction*.007+rot@((v.co-Vector((0,0,-.477)))*.16)
  assign(hand,skin)
  head=join_seam(neck,head,'Head_and_Neck_P2',Vector((0,0,1.3355)),Vector((0,0,1)),.009)
  move(head,facecol)
  arm=join_seam(arm,hand,'Arm_Hand_PosY_P2',wrist+direction*.0035,direction,.013)
  move(arm,bodycol)
  mirror=arm.modifiers.new('Opposite arm and hand - exact Y mirror','MIRROR');mirror.use_axis=(False,True,False);mirror.use_clip=True
  hair=import_mesh(SOURCES['hair'],'Hair_P2_Independent',haircol)
  for v in hair.data.vertices:v.co=Vector((v.co.x*.39-.0166,v.co.y*.375,v.co.z*.48+1.540))
  assign(hair,hairmat)
  # A fitted scalp shell is a conventional separate base beneath hair strands.
  # Derive it from the actual head dome; keep forehead, ears, eyes and face out.
  largest=set(groups(head.data)[0])
  def scalp_region(v):
   t=max(0,min(1,(v.co.x+.10)/.23));t=t*t*(3-2*t)
   return v.index in largest and v.co.z>1.49+.155*t
  cap=subset(head,[v.index for v in head.data.vertices if scalp_region(v)],'Hair_Scalp_Base_Blender',haircol)
  for v in cap.data.vertices:v.co+=v.normal*.003
  assign(cap,hairmat)
  cap['construction']='Head-derived upper skull shell, 3mm normal offset, independent hair base'
  LOG['scalp_shell']={'source':'Head_and_Neck_P2 upper skull only','normal_offset_m':.003,'topology':topology(cap)}
  # Before/after renders use these exact same fitted parts and camera transforms.
  for o in (head,arm,hair):mask(o,lambda v:1,'protected by default until local brush pass')
  save('02_fitted_before_brush.blend')
  # Neck band: leave face/eyes and chest unaffected, smooth the real bridge.
  mask(head,lambda v:min(1,max(0,(abs(v.co.z-1.3355)-.012)/.023)), 'brush protection: only neck seam editable')
  for x,y in ((.028,0),(-.048,0),(-.014,.042),(-.014,-.042)):
   target=Vector((x,y,1.336))
   q=min((v.co for v in head.data.vertices if 1.31<v.co.z<1.36),key=lambda co:(co-target).length).copy()
   stroke(head,'Smooth',[q,q+Vector((0,0,.003)),q+Vector((0,0,-.003))],.035,.20,'neck seam local smooth')
  # Work around the complete neck band, protecting chin/face and upper chest.
  mask(head,lambda v:min(1,max(0,(abs(v.co.z-1.333)-.021)/.025)), 'brush protection: neck transition, face and chest locked')
  save('mask_neck.blend')
  for _ in range(2):
   for i in range(8):
    theta=i*math.pi/4;target=Vector((-.018+math.cos(theta)*.048,math.sin(theta)*.053,1.333))
    q=min((v.co for v in head.data.vertices if 1.315<v.co.z<1.352),key=lambda co:(co-target).length).copy()
    stroke(head,'Smooth',[q,q+Vector((0,0,.003))],.05,.32,'circumferential neck transition smooth')
  # Mouth corners only; separate eye/brow/lash islands are fully protected.
  largest=set(groups(head.data)[0])
  corners=[]
  for s in (-1,1):
   guess=Vector((.085,s*.054,1.412))
   candidates=[v for v in head.data.vertices if v.index in largest and v.co.x>.035 and 1.385<v.co.z<1.425]
   corners.append(min(candidates,key=lambda v:(v.co-guess).length).co.copy())
  def face_mask(v):
   if v.index not in largest:return 1
   d=min((v.co-q).length for q in corners)
   return min(1,max(0,(d-.009)/.012))
  mask(head,face_mask,'brush protection: mouth corners only; eyes and brows locked')
  save('mask_face.blend')
  for q in corners:
   for _ in range(2):stroke(head,'Smooth',[q,q+Vector((0,.002,0))],.022,.23,'mouth corner pinching cleanup')
  # Keep all fingers and nails fixed; only the wrist transition can move.
  mask(arm,lambda v:min(1,max(0,(abs((v.co-wrist).dot(direction))-.014)/.021)), 'brush protection: wrist band only; digits and nails locked')
  save('mask_wrist.blend')
  for sign in (-1,1):
   target=wrist+Vector((sign*.019,0,0))
   q=min((v.co for v in arm.data.vertices if abs((v.co-wrist).dot(direction))<.02),key=lambda co:(co-target).length).copy()
   stroke(arm,'Inflate/Deflate',[q],.025,.075,'wrist transition subtle volume')
   stroke(arm,'Smooth',[q,q+direction*.004,q-direction*.004],.034,.16,'wrist bridge local smooth')
  # Small grab on the side of the lower neck; protected face cannot move.
  mask(head,lambda v:min(1,max(0,(abs(v.co.z-1.3355)-.01)/.017)), 'brush protection: lower neck silhouette only')
  target=Vector((-.015,.045,1.339))
  q=min((v.co for v in head.data.vertices if 1.32<v.co.z<1.355),key=lambda co:(co-target).length).copy()
  stroke(head,'Grab',[q,q+Vector((0,.0015,0))],.025,.24,'lower neck silhouette 1.5mm grab')
  # Fit only the rear hair shell where profile inspection showed scalp exposure.
  # Side projection makes the depth adjustment a real screen-space Grab stroke.
  mask(hair,lambda v:min(1,max(0,(v.co.x+.055)/.055, (1.59-v.co.z)/.045)), 'brush protection: upper rear hair cap editable, bangs and tips locked')
  save('mask_hair.blend')
  AREA.spaces.active.region_3d.view_rotation=Vector((0,1,0)).to_track_quat('-Z','Y')
  AREA.spaces.active.region_3d.view_location=(0,0,1.56);AREA.spaces.active.region_3d.view_distance=.65
  for sign in (-1,1):
   target=Vector((-.13,sign*.05,1.66))
   q=min((v.co for v in hair.data.vertices if v.co.x<-.06 and v.co.z>1.60),key=lambda co:(co-target).length).copy()
   stroke(hair,'Grab',[q,q+Vector((-.04,0,.012))],.15,.85,'upper rear hair cap fit to scalp')
  # Mirror counterpart gets identical stroke by modifier, not independent sculpt.
  LOG['final_topology']={o.name:topology(o) for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render}
  LOG['known_limitations']=['Review candidate only; no UV, rig or deformation approval.',
       'Generated head/hair eye islands and residual nonmanifold topology still need targeted review.',
       'Base skin under the opaque top/shorts is not proven continuous; garments remain independent.',
       'Palm/thumbnail orientation is fitted geometrically, not yet checked by finger articulation.',
       'A separate head-derived scalp shell conceals gaps in generated hair; hair border topology still needs repair.']
  LOG['state']='awaiting_user_sculpt_review';LOG['native_brush_replay']=True
  LOG['source_hashes_unchanged']=all(hashlib.sha256(SOURCES[k].read_bytes()).hexdigest()==v['sha256'] for k,v in LOG['source_hashes'].items())
  if not LOG['source_hashes_unchanged']:raise RuntimeError('immutable source changed')
  active(head)
  AREA.spaces.active.region_3d.view_rotation=Vector((-1,0,0)).to_track_quat('-Z','Y')
  AREA.spaces.active.shading.type='SOLID';AREA.spaces.active.shading.color_type='MATERIAL'
  AREA.spaces.active.region_3d.view_location=(0,0,1.15);AREA.spaces.active.region_3d.view_distance=2.3
  for o in (head,arm,hair):o.hide_select=False
  store();save('03_sculpt_candidate.blend')
  print('SCULPT_TRIAL_COMPLETE',str(OUT),flush=True)
 except Exception:
  LOG['state']='failed';LOG['error']=traceback.format_exc();store();print(LOG['error'],flush=True)
 bpy.ops.wm.quit_blender()

bpy.app.timers.register(main,first_interval=3)
