"""Texture step 3 of 3: materials with the baked image textures on the UV'd asset (uv_parts.py -> uv.blend).

skin    'face' slots skin + mouth_inner -> skin.png (cavity has its own island in it), roughness 0.5 / 0.3
eyes    'eyes' -> eyes.png (eye_iris_texture.py), glossy (roughness 0.08, coat 0.6)
brows   'p2_brows' -> brows.png
teeth   'teeth_up' / 'teeth_lo' slots teeth + gums -> teeth.png (mouth_textures.py), tongue -> tongue.png
caruncle any object named *caruncle* -> flat pink sampled from the photo's inner eye corners (bake_qa caruncle_colour)
Images are referenced next to the .blend (relative paths, not packed). The old vertex colour 'ref_color' and
old 'ref_uv' are removed if present. Optional --atlas <atlas.json>: use the one-material atlas (atlas_pack.py)
instead (UV map 'uv_atlas', image atlas.png).
Usage: blender -b <uv.blend> -P tex_assign.py -- <tex_dir> <out.blend> [--atlas <atlas.json>]
"""
import bpy, sys, os, json

a = sys.argv[sys.argv.index('--') + 1:]
TEX, OUT = os.path.abspath(a[0]), os.path.abspath(a[1])
ATLAS = a[a.index('--atlas') + 1] if '--atlas' in a else None
UVN = 'uv_tex'


def image(fn):
    p = os.path.join(TEX, fn)
    if not os.path.exists(p): return None
    im = bpy.data.images.load(p, check_existing=True); im.colorspace_settings.name = 'sRGB'
    return im


def mat(name, img, uvmap, rough=0.5, coat=0.0, spec=0.5):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (400, 0)
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled'); bs.location = (100, 0)
    bs.inputs['Roughness'].default_value = rough
    if 'Coat Weight' in bs.inputs: bs.inputs['Coat Weight'].default_value = coat
    if 'Specular IOR Level' in bs.inputs: bs.inputs['Specular IOR Level'].default_value = spec
    nt.links.new(bs.outputs[0], out.inputs[0])
    if img:
        tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = img; tx.location = (-300, 0); tx.interpolation = 'Linear'
        um = nt.nodes.new('ShaderNodeUVMap'); um.uv_map = uvmap; um.location = (-500, 0)
        nt.links.new(um.outputs[0], tx.inputs[0]); nt.links.new(tx.outputs['Color'], bs.inputs['Base Color'])
    return m


def clean(o):
    me = o.data
    for c in list(me.color_attributes):
        if c.name == 'ref_color': me.color_attributes.remove(c)
    for u in list(me.uv_layers):
        if u.name == 'ref_uv': me.uv_layers.remove(u)
    if UVN in me.uv_layers:
        me.uv_layers.active = me.uv_layers[UVN]; me.uv_layers[UVN].active_render = True


rep = {}
if ATLAS:
    info = json.load(open(ATLAS)); im = image('atlas.png'); m = mat('tex_atlas', im, 'uv_atlas', rough=0.5)
    rp = os.path.join(TEX, 'atlas_rough.png')
    if os.path.exists(rp):                                   # roughness per part (glossy eyes / teeth in one material)
        ri = bpy.data.images.load(rp, check_existing=True); ri.colorspace_settings.name = 'Non-Color'
        nt = m.node_tree; bs = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'); um = next(n for n in nt.nodes if n.type == 'UVMAP')
        tr = nt.nodes.new('ShaderNodeTexImage'); tr.image = ri; tr.location = (-300, -300)
        nt.links.new(um.outputs[0], tr.inputs[0]); nt.links.new(tr.outputs['Color'], bs.inputs['Roughness'])
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.name not in info['objects']: continue
        r = info['rects'][info['objects'][o.name]]; clean(o); me = o.data
        if UVN not in me.uv_layers: continue
        src = me.uv_layers[UVN]; ua = me.uv_layers.get('uv_atlas') or me.uv_layers.new(name='uv_atlas')
        src = me.uv_layers[UVN]                                  # re-fetch after adding a layer
        n = len(me.loops); buf = [0.0] * (2 * n); src.data.foreach_get('uv', buf)
        for k in range(n):
            buf[2 * k] = r['u0'] + min(max(buf[2 * k], 0.0), 1.0) * r['su']
            buf[2 * k + 1] = r['v0'] + min(max(buf[2 * k + 1], 0.0), 1.0) * r['sv']
        me.uv_layers['uv_atlas'].data.foreach_set('uv', buf)
        me.uv_layers.active = me.uv_layers['uv_atlas']; me.uv_layers['uv_atlas'].active_render = True
        for i in range(len(me.materials)): me.materials[i] = m
        if not len(me.materials): me.materials.append(m)
        rep[o.name] = 'atlas ' + info['objects'][o.name]
else:
    f = bpy.data.objects.get('face')
    if f:
        clean(f); sk = image('skin.png')
        m_skin = mat('tex_skin', sk, UVN, rough=0.5, spec=0.45); m_in = mat('tex_mouth_inner', sk, UVN, rough=0.3, spec=0.5)
        for i, m in enumerate(f.data.materials):
            f.data.materials[i] = m_in if (m and m.name in ('mouth_inner', 'ref_mouth')) else m_skin
        rep['face'] = [m.name for m in f.data.materials]
    e = bpy.data.objects.get('eyes')
    if e:
        clean(e); e.data.materials.clear()                              # glossy cornea coat: catch-lights from the lights
        me_ = mat('tex_eye', image('eyes.png'), UVN, rough=0.12, coat=1.0, spec=0.6)
        bs_ = next(n for n in me_.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        if 'Coat Roughness' in bs_.inputs: bs_.inputs['Coat Roughness'].default_value = 0.02
        if 'Coat IOR' in bs_.inputs: bs_.inputs['Coat IOR'].default_value = 1.376
        e.data.materials.append(me_)
        rep['eyes'] = 'tex_eye'
    b = bpy.data.objects.get('p2_brows')
    if b and image('brows.png'):
        clean(b); b.data.materials.clear(); b.data.materials.append(mat('tex_brows', image('brows.png'), UVN, rough=0.7, spec=0.2))
        rep['p2_brows'] = 'tex_brows'
    for n in ('teeth_up', 'teeth_lo'):
        o = bpy.data.objects.get(n)
        if not o: continue
        clean(o); im = image('teeth.png')
        gi = [i for i, m in enumerate(o.data.materials) if m and m.name.startswith(('gums', 'ref_gums'))]
        mt = mat('tex_teeth', im, UVN, rough=0.25, spec=0.6); mg = mat('tex_gums', im, UVN, rough=0.35, spec=0.5)
        n_slots = len(o.data.materials)
        for i in range(n_slots): o.data.materials[i] = mg if i in gi else mt
        rep[n] = [m.name for m in o.data.materials]
    car = [o for o in bpy.data.objects if o.type == 'MESH' and 'caruncle' in o.name.lower()]
    if car:                                                           # inner-corner piece: flat pink from the photo
        q = os.path.join(TEX, 'bake_qa.json'); cc = (0.78, 0.47, 0.47)
        if os.path.exists(q): cc = tuple(json.load(open(q)).get('caruncle_colour', cc))
        lin = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in cc) + (1.0,)
        mc = mat('tex_caruncle', None, UVN, rough=0.25, spec=0.6); next(n for n in mc.node_tree.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Base Color'].default_value = lin
        for o in car: o.data.materials.clear(); o.data.materials.append(mc); rep[o.name] = 'tex_caruncle'
    t = bpy.data.objects.get('tongue')
    if t:
        clean(t); t.data.materials.clear(); t.data.materials.append(mat('tex_tongue', image('tongue.png'), UVN, rough=0.35, spec=0.5))
        rep['tongue'] = 'tex_tongue'
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=True)
bpy.ops.file.make_paths_relative(); bpy.ops.wm.save_mainfile(compress=True)
print('ASSIGNED', json.dumps(rep))
