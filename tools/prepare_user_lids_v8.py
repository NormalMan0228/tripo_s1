from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=(R/'tools/blender_probe_eye_patch_v6.py').read_text();s=s.replace('explorer_b_face_animated_v6','explorer_b_user_head_v8').replace("R/'art/characters/explorer_b_clean_edges_v5/assembly/explorer_b_clean_edges_v5.blend'","A/'assembled_workbench.blend'").replace("'FACE_skin_eyelids_lashes'","'FACE_user_head'");a=s.index(';groups=json.loads');b=s.index('\nfor sign',a);s=s[:a]+ ';finfaces=set()'+s[b:];s=s.replace('(c.z-.122)/.061','(c.z-.105)/.058');(R/'tools/blender_probe_user_eye_patch_v8.py').write_text(s)
s=(R/'tools/blender_rebuild_lids_close_corners_v6.py').read_text();s=s.replace('explorer_b_face_animated_v6','explorer_b_user_head_v8').replace("R/'art/characters/explorer_b_clean_edges_v5/assembly/explorer_b_clean_edges_v5.blend'","A/'assembled_workbench.blend'").replace("'FACE_skin_eyelids_lashes'","'FACE_user_head'").replace("ctrl=bpy.data.objects['FACE_CONTROLS']","ctrl=bpy.data.objects.new('FACE_CONTROLS',None);sc.collection.objects.link(ctrl)")
pos=s.index('\ndef smooth')
s=s[:pos]+"\nfor obj in list(sc.objects):\n if obj.name.startswith(('LASH_upper_','LID_SKIN')):bpy.data.objects.remove(obj,do_unlink=True)\n"+s[pos:]
s=s.replace(" and 'Color' in n.image.name",'')
a=s.index(';groups=json.loads',s.index('old.calc_loop_triangles()'));b=s.index('\nfor sign',a);s=s[:a]+';skin_tree=source_tree'+s[b:]
s=s.replace('mid=.108+.014*(u+1)/2;upper=mid+.049','mid=.105+.012*(u+1)/2;upper=mid+.048').replace('lower=mid-.047','lower=mid-.050')
a=s.index('# Mouth corners:');b=s.index("me=bpy.data.meshes.new",a);s=s[:a]+'mouthchanged=0\n'+s[b:]
pos=s.index("lash=bpy.data.materials.new")
insert="""
# Preserve retargeted MPFB face units on retained skin and interpolate them across the local eye patch.
from mathutils.kdtree import KDTree
kt=KDTree(len(basis))
for i,p in enumerate(basis):kt.insert(p,i)
kt.balance()
for name,coords in oldkeys.items():
 if not name.startswith('!ex-'):continue
 key=head.shape_key_add(name=name)
 for i,oldid in enumerate(used):key.data[i].co=vertices[i]+coords[oldid]-basis[oldid]
 for i in range(new_start,len(vertices)):
  near=kt.find_n(vertices[i],4);ws=[1/max(.001,d)**2 for _,j,d in near];total=sum(ws);delta=sum(((coords[j]-basis[j])*(w/total) for (_,j,d),w in zip(near,ws)),Vector());key.data[i].co=vertices[i]+delta
"""
s=s[:pos]+insert+s[pos:];s=s.replace("'face_repaired_workbench.blend'","'lids_repaired_workbench.blend'")
(R/'tools/blender_rebuild_user_lids_v8.py').write_text(s)
