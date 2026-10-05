import bpy,json
from collections import Counter
o=bpy.data.objects['Face_Neck_Clavicle']
c=Counter(tuple(sorted((a,b))) for p in o.data.polygons for a,b in zip(list(p.vertices),list(p.vertices)[1:]+list(p.vertices)[:1]))
print('EDGE_COUNTS',Counter(c.values()))
print('BOTTOM',[(tuple(o.data.vertices[a].co),tuple(o.data.vertices[b].co)) for (a,b),n in c.items() if n!=2 and min(o.data.vertices[a].co.z,o.data.vertices[b].co.z)<.02][:20])
o=bpy.data.objects['Eyes']
for m in o.data.materials:
 print('MATERIAL',m.name)
 print('LINKS',[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in m.node_tree.links])
 for n in m.node_tree.nodes:
  if n.type=='TEX_IMAGE':print('TEX',n.image.filepath)
for side in [-1,1]:
 inds=sorted((v.index for v in o.data.vertices if v.co.x*side>0),key=lambda i:o.data.vertices[i].co.y)[:5]
 for i in inds:
  print('EYE_FRONT_VERTEX',tuple(o.data.vertices[i].co),[tuple(o.data.uv_layers.active.data[l.index].uv) for l in o.data.loops if l.vertex_index==i][:2])
