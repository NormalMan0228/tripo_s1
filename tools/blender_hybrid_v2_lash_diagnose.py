import bpy,numpy as np,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_hybrid_bust_v2';bpy.ops.wm.open_mainfile(filepath=str(O/'explorer_b_hybrid_bust_v2.blend'))
m=bpy.data.materials['Brow_Lash_RGBA_Atlas'];print('LINKS',[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in m.node_tree.links]);im=next(n.image for n in m.node_tree.nodes if n.type=='TEX_IMAGE');a=np.array(im.pixels[:]).reshape(im.size[1],im.size[0],4)[::-1,:,-1];print('IMAGE',im.name,im.size[:],float(a.max()),[(x,int(np.argmax(np.convolve((a[450:900,x-4:x+5]>.85).sum(1),np.ones(7),mode='same')))+450) for x in [120,300,500,700,900]])
o=bpy.data.objects['LASH_UPPER_Rooted'];print('UV',[(d.uv[:]) for d in o.data.uv_layers.active.data[:12]]);print('COL',[(d.color[:]) for d in o.data.color_attributes['EdgeFade'].data[:8]])
