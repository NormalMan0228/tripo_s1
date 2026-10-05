"""Preserve and inspect the new textured Tripo face without replacing its facial parts."""
import bpy,bmesh,json,math,hashlib,sys
from pathlib import Path
from mathutils import Vector,Matrix
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_integrated_face_haircards_v1/head'
if '--' in sys.argv:O=Path(sys.argv[sys.argv.index('--')+1]).resolve()
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.preferences.filepaths.save_version=0
sc=bpy.context.scene
def col(name):
 c=bpy.data.collections.new(name);sc.collection.children.link(c);return c
srcCol=col('90_TRIPO_FACE_preserved');work=col('01_Integrated_face');studio=col('99_Studio')
bpy.ops.import_scene.fbx(filepath=str(O/'model.fbx'),use_anim=False)
working=[];entries=[]
for i,s in enumerate([o for o in sc.objects if o.type=='MESH']):
 s.name='SOURCE_Tripo_face_'+str(i)
 for c in list(s.users_collection):c.objects.unlink(s)
 srcCol.objects.link(s)
 o=s.copy();o.data=s.data.copy();work.objects.link(o);o.name='FACE_Tripo_integrated_'+str(i)
 o.data.transform(o.matrix_world);o.parent=None;o.matrix_world=Matrix.Identity(4)
 for p in o.data.polygons:p.use_smooth=True
 s.hide_render=True;s.hide_set(True);s.hide_select=True
 bm=bmesh.new();bm.from_mesh(o.data);bm.verts.ensure_lookup_table();seen=set();groups=[]
 for v in bm.verts:
  if v.index in seen:continue
  stack=[v];seen.add(v.index);g=[]
  while stack:
   a=stack.pop();g.append(a)
   for e in a.link_edges:
    b=e.other_vert(a)
    if b.index not in seen:seen.add(b.index);stack.append(b)
  groups.append({'vertices':len(g),'bounds':[[min(v.co[j] for v in g),max(v.co[j] for v in g)] for j in range(3)]})
 entries.append({'object':o.name,'vertices':len(bm.verts),'faces':len(bm.faces),'quads':sum(len(f.verts)==4 for f in bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'components':sorted(groups,key=lambda g:-g['vertices']),'materials':[m.name for m in o.data.materials]})
 bm.free();working.append(o)
# P2 quad FBX references external textures. Obtain the same generated maps from
# a portable conversion, then assign its material while preserving the quad UVs.
textureCol=col('91_Texture_payload_hidden')
existing=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(O/'texture_payload/model.glb'))
payload=[o for o in bpy.data.objects if o not in existing]
payload_mats=list(dict.fromkeys(m for o in payload if o.type=='MESH' for m in o.data.materials))
assert payload_mats, 'No embedded generated texture material'
for o in list(srcCol.objects)+working:
 o.data.materials.clear()
 for m in payload_mats:o.data.materials.append(m)
for o in payload:
 for c in list(o.users_collection):c.objects.unlink(o)
 textureCol.objects.link(o);o.hide_render=True;o.hide_set(True);o.hide_select=True
for e,o in zip(entries,working):e['materials']=[m.name for m in o.data.materials]
for m in list(bpy.data.materials):
 if m.users==0:bpy.data.materials.remove(m)
for im in list(bpy.data.images):
 if im.users==0 and not im.has_data:bpy.data.images.remove(im)
for im in bpy.data.images:
 print('IMAGE_META',im.name,list(im.size),bool(im.packed_file),im.users)
 if im.source=='FILE' and im.has_data and not im.packed_file and Path(bpy.path.abspath(im.filepath)).exists():im.pack()
pts=[v.co for o in working for v in o.data.vertices];lo=Vector([min(p[j] for p in pts) for j in range(3)]);hi=Vector([max(p[j] for p in pts) for j in range(3)]);center=(hi+lo)/2;size=max(hi-lo)
sc.world=bpy.data.worlds.new('Soft Studio');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs[0].default_value=(.45,.47,.5,1);sc.world.node_tree.nodes['Background'].inputs[1].default_value=.4
sc.render.engine='CYCLES';sc.cycles.samples=24;sc.cycles.use_denoising=True
try:
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='CUDA'
 if any(d.type=='CUDA' for d in prefs.devices):sc.cycles.device='GPU'
except Exception:pass
for name,loc,power,scale in [('Key',(2,-2,2),130,1.6),('Fill',(2,2,1),110,1.8),('Rim',(-1,0,2),120,1.5)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=scale*size;o=bpy.data.objects.new(name,d);studio.objects.link(o);o.location=center+Vector(loc)*size;o.rotation_euler=(center-o.location).to_track_quat('-Z','Y').to_euler();o.hide_set(True)
cam=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));studio.objects.link(cam);cam.data.type='ORTHO';sc.camera=cam;cam.hide_set(True)
sc.render.resolution_x=900;sc.render.resolution_y=1000;sc.view_settings.view_transform='AgX'
def view(pos,target=center,scale=1.15):
 cam.location=target+Vector(pos)*size;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=size*scale
view((3,0,0))
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   sp=a.spaces.active;sp.shading.type='MATERIAL';sp.overlay.show_floor=False;sp.overlay.show_extras=False
   sp.region_3d.view_location=center;sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.region_3d.view_distance=size*1.7;sp.region_3d.view_perspective='ORTHO'
bpy.ops.object.select_all(action='DESELECT');working[0].select_set(True);bpy.context.view_layer.objects.active=working[0]
notes=bpy.data.texts.new('READ_ME');notes.write('New Tripo P2 textured face with integrated eyelids, eyebrows and lashes. Source in hidden collection, visible copy unmodified. Mouth intentionally open for oral inspection. Hair generated separately and rebuilt as cards. No face rig yet.\n')
blend=O/'explorer_b_integrated_face_open_workbench.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
for name,pos in [('front',(3,0,0)),('angle',(3,-2,0)),('side',(0,-3,0))]:
 view(pos);sc.render.filepath=str(O/(name+'.png'));bpy.ops.render.render(write_still=True)
view((3,-.2,0),center+Vector((.15,0,-.09*size)),.38);sc.render.filepath=str(O/'mouth_detail.png');bpy.ops.render.render(write_still=True)
view((3,-.2,0),center+Vector((.15,0,.13*size)),.50);sc.render.filepath=str(O/'eyes_detail.png');bpy.ops.render.render(write_still=True)
report={'source_sha256':hashlib.sha256((O/'model.fbx').read_bytes()).hexdigest(),'file':str(blend),'bounds':[list(lo),list(hi)],'meshes':entries,'source_preserved':True,'geometry_modified':False,'packed_images':[im.name for im in bpy.data.images if im.packed_file],'credits':120,'facial_rig':False,'mouth_rest_prepared':False}
(O/'inspection-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
