"""겹침생성 · skin weight pictures: which deform bone moves which part of the face.

All DEF-* vertex groups of 'face' are read into one weight matrix (one pass over the vertices). Region heat maps
(sum of the region's groups, dark blue 0 -> red 1) are drawn by lookup: the weight goes into a UV coordinate and
Workbench samples a ramp image (TEXTURE colour), so a face whose corners are 0 and 1 runs through the ramp instead of
blending blue and red into purple. The dominant-bone map colours each vertex by the region of its strongest bone
(hue), neighbouring bones of one region get different light/dark tones (greedy colouring of the bone adjacency), and
a dark line follows every edge where the strongest bone changes; magenta = no weight at all.
Mouth interior (only when the file has the cavity rings): the head is cut at x = 0 and seen from the character's
left, flat-lit so every colour is exactly the ramp colour; the lip skin next to the slit, the lip roll, the cavity
and its cap carry the jaw weight, the rest of the half head is neutral grey (shaded by its normal) for orientation.
A second picture from the same camera colours the parts (lip skin, roll, cavity, cap) with rig_viz_section colours.
Legend pictures for the doc: w_ramp.png (0 -> 1 strip, ticks at quarters) and w_regions.png (region swatches, with
the tones used under each); weights_palette.json holds the ramp stops, region colours, tones and every bone's colour.
QA: unweighted vertices, influences, weight sums, L/R mirror symmetry of weights (only on pairs that are true mirror
vertices), region counts, cavity jaw split (upper / lower half without the corner columns, corners separately).
Usage: blender -b <rigify_fit.blend | rigify_sym.blend> -P rig_viz_weights.py -- <out_dir> <landmarks.json>
"""
import bpy, sys, os, re, json
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

a = sys.argv[sys.argv.index('--') + 1:]; OUT = os.path.abspath(a[0]); LMJ = a[1]; os.makedirs(OUT, exist_ok=True)
face = bpy.data.objects['face']; me = face.data; N = len(me.vertices); eyes = bpy.data.objects.get('eyes')
X = np.empty(N * 3); me.vertices.foreach_get('co', X); X = X.reshape(-1, 3)
Nr = np.empty(N * 3); me.vertices.foreach_get('normal', Nr); Nr = Nr.reshape(-1, 3)
att = lambda n, d=0: np.array([v.value for v in me.attributes[n].data]) if n in me.attributes else np.full(N, d)
rg, mu, er = att('mouth_ring'), att('mouth_u', -1.0), att('eye_ring')

# --- weights: DEF groups only (organ groups like mouth_bag are selections, not deform) ---
gidx = {g.index: g.name for g in face.vertex_groups if g.name.startswith('DEF-')}
names = sorted(gidx.values()); col_of = {gi: names.index(n) for gi, n in gidx.items()}
W = np.zeros((N, len(names)), np.float32)
for v in me.vertices:
    for g in v.groups:
        c = col_of.get(g.group)
        if c is not None: W[v.index, c] = g.weight
S = W.sum(1); unw = S < 1e-4

REG = [('jaw', ('jaw', 'chin')), ('lips', ('lip',)), ('lids', ('lid',)), ('brows', ('brow',)), ('cheeks', ('cheek',)),
       ('nose', ('nose',)), ('ears', ('ear',)), ('tongue', ('tongue',)), ('teeth', ('teeth', 'tooth')), ('eye', ('eye',)),
       ('forehead', ('forehead', 'temple')), ('other', ())]
PAL = {'jaw': '#f08a1c', 'lips': '#d81e2c', 'lids': '#22c3d8', 'brows': '#f2d22a', 'cheeks': '#4cb84a', 'nose': '#3a5be6',
       'ears': '#8a5a32', 'tongue': '#c7788c', 'teeth': '#efeedd', 'eye': '#a4a4f2', 'forehead': '#7a4cb4',
       'other': '#8c8c8c', 'unweighted': '#ff00ff'}
breg = [next((r for r, ps in REG if n[4:].startswith(ps)), 'other') for n in names]   # startswith(()) is False
br = np.array(breg); REGS = [r for r, _ in REG if r in breg]                           # regions that have bones
RW = {r: W[:, br == r].sum(1) if r in REGS else np.zeros(N) for r, _ in REG}

lin = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)        # attribute colours are linear
hexrgb = lambda h: np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)])
tohex = lambda c: '#%02x%02x%02x' % tuple(int(round(255 * float(x))) for x in np.clip(c, 0, 1))
RAMP = np.array([[0.09, 0.11, 0.38], [0.10, 0.32, 0.78], [0.12, 0.70, 0.62], [0.96, 0.86, 0.18], [0.90, 0.16, 0.06]])
def heat(t):
    t = np.clip(t, 0, 1) * (len(RAMP) - 1); i = np.minimum(t.astype(int), len(RAMP) - 2); f = (t - i)[:, None]
    return RAMP[i] * (1 - f) + RAMP[i + 1] * f

# --- dominant map: neighbouring bones of one region never share a tone; dark line where the strongest bone changes ---
TONE = [0.0, -0.45, 0.48, -0.22, 0.72, 0.24]                     # >0 toward white, <0 toward black
tint = lambda c, t: c + (1 - c) * t if t > 0 else c * (1 + t)
dom = W.argmax(1)
ed = np.empty(len(me.edges) * 2, int); me.edges.foreach_get('vertices', ed); ed = ed.reshape(-1, 2)
da, db = dom[ed[:, 0]], dom[ed[:, 1]]; cross = (da != db) & ~unw[ed[:, 0]] & ~unw[ed[:, 1]]
nb = {i: set() for i in range(len(names))}
for p, q in set(zip(da[cross & (br[da] == br[db])].tolist(), db[cross & (br[da] == br[db])].tolist())): nb[p].add(q); nb[q].add(p)
tone = {}
for i in sorted(range(len(names)), key=lambda i: -len(nb[i])):    # greedy, most-connected bones first
    used = {tone[j] for j in nb[i] if j in tone}; tone[i] = next(k for k in range(99) if k not in used)
bone_col = np.array([tint(hexrgb(PAL[breg[i]]), TONE[tone[i] % len(TONE)]) for i in range(len(names))])
DOM = bone_col[dom].copy(); DOM[unw] = hexrgb(PAL['unweighted'])
DOM[np.where(da < db, ed[:, 0], ed[:, 1])[cross]] *= 0.3          # one side of each border edge: a thin line, not a band
json.dump({'ramp': {'positions': np.linspace(0, 1, len(RAMP)).round(3).tolist(), 'stops_srgb': RAMP.tolist(),
                    'stops_hex': [tohex(c) for c in RAMP], 'meaning': 'summed skin weight of the region, 0 -> 1'},
           'regions': {r: PAL[r] for r in REGS + ['unweighted']}, 'region_order': REGS,
           'tones': TONE, 'tone_rule': 'tint toward white (>0) or black (<0); bones of one region that touch get different tones',
           'border_line': 'vertex colour x0.3 on one side of every edge where the dominant bone changes',
           'bones': {n: {'region': breg[i], 'tone': tone[i], 'hex': tohex(bone_col[i])} for i, n in enumerate(names)}},
          open(os.path.join(OUT, 'weights_palette.json'), 'w'), indent=1)

# --- QA ---
qa = {'verts': N, 'def_groups': len(names)}
qa['unweighted'] = int(unw.sum())
qa['unweighted_where'] = {'mouth_rings': int((unw & (rg > 0)).sum()), 'eye_rings': int((unw & (er != 0)).sum()),
                          'other_skin': int((unw & (rg <= 0) & (er == 0)).sum())}
inf = (W > 0).sum(1); qa['max_influences'] = int(inf.max()); i01 = (W >= 0.01).sum(1)   # heat weights leave many tiny ones
qa['max_influences_ge_0.01'] = int(i01.max()); qa['share_over_4'] = round(float((inf > 4).mean()), 4)
qa['share_over_8'] = round(float((inf > 8).mean()), 4); qa['share_over_4_ge_0.01'] = round(float((i01 > 4).mean()), 4)
qa['influence_hist'] = {int(k): int((inf == k).sum()) for k in np.unique(inf)}
off = (~unw) & (np.abs(S - 1) > 0.01)
qa['sum_not_1_share'] = round(float(off.mean()), 5); qa['sum_not_1'] = int(off.sum())
qa['sum_range_weighted'] = [round(float(S[~unw].min()), 4), round(float(S[~unw].max()), 4)] if (~unw).any() else None
swap = lambda n: re.sub(r'\.([LR])(?=\.|$)', lambda m: '.' + 'RL'[m.group(1) == 'R'], n)
perm = np.array([names.index(swap(n)) if swap(n) in names else i for i, n in enumerate(names)])
kd = KDTree(N)
for i, p in enumerate(X): kd.insert(p, i)
kd.balance()
mir = np.empty(N, int); md = np.empty(N)
for i, p in enumerate(X):                                         # coincident lip/lid edge verts: the mirrored normal decides
    hits = kd.find_n((-p[0], p[1], p[2]), 4); d0 = hits[0][2]; nm = Nr[i] * [-1, 1, 1]
    j = max((h for h in hits if h[2] < d0 + 1e-6), key=lambda h: Nr[h[1]] @ nm)[1]; mir[i] = j; md[i] = d0
# a vertex without a true mirror partner pairs with whatever is nearest, so its "error" is mesh asymmetry: weights
# are only compared on pairs closer than 0.5 mm
E = np.abs(W - W[mir][:, perm]); ev = E.max(1); close = md < 5e-4; p95 = float(np.percentile(md, 95)) * 1000
qa['sym'] = {'pair_dist_p95_mm': round(p95, 3), 'pair_dist_max_mm': round(float(md.max()) * 1000, 3),
             'mesh_mirror_exact': bool(p95 < 1.0), 'pairs_lt_0.5mm': int(close.sum()), 'pairs_lt_0.5mm_share': round(float(close.mean()), 4)}
if close.any():
    ec = np.where(close, ev, -1); wv = int(ec.argmax())
    qa['sym'].update({'err_p95': round(float(np.percentile(ev[close], 95)), 4), 'err_max': round(float(ev[close].max()), 4),
                      'err_mean': round(float(ev[close].mean()), 5), 'verts_err_gt_0.05': int((ev[close] > 0.05).sum()),
                      'worst_group': names[int(E[wv].argmax())] if ev[wv] > 1e-4 else None,
                      'worst_pos': [round(float(c), 4) for c in X[wv]] if ev[wv] > 1e-4 else None})
if p95 >= 1.0: qa['sym']['note'] = 'mesh is not mirror-exact; errors cover only the true mirror pairs (< 0.5 mm)'
qa['regions'] = {r: {'weighted': int((RW[r] > 1e-3).sum()), 'dominant': int(((~unw) & (br[dom] == r)).sum())} for r in REGS}
jaw_def = W[:, names.index('DEF-jaw')] if 'DEF-jaw' in names else np.zeros(N)
CAV = rg.max() >= 15                                              # rings: 1..K skin->slit, K+1..K+2 roll, K+3..K+6 cavity, K+7 cap
if CAV:
    K = int(rg.max()) - 7; cav = (rg >= K + 3) & (rg <= K + 6); roll = (rg == K + 1) | (rg == K + 2)
    cor = np.isclose(mu, 0, atol=1e-3) | np.isclose(mu, 0.5, atol=1e-3) | np.isclose(mu, 1, atol=1e-3)   # mouth-corner columns
    lo, up = (mu > 0.5) & (mu < 1) & ~cor, (mu > 0) & (mu < 0.5) & ~cor
    m = lambda w, s: round(float(w[s].mean()), 4) if s.any() else None
    qa['mouth_interior'] = {'slit_ring': K, 'cavity_verts': int(cav.sum()), 'roll_verts': int(roll.sum()),
                            'cavity_split_verts': {'lower': int((cav & lo).sum()), 'upper': int((cav & up).sum()), 'corner': int((cav & cor).sum())},
                            'cavity_lower_def_jaw_mean': m(jaw_def, cav & lo), 'cavity_upper_def_jaw_mean': m(jaw_def, cav & up),
                            'cavity_corner_def_jaw_mean': m(jaw_def, cav & cor),
                            'cavity_lower_jaw_region_mean': m(RW['jaw'], cav & lo), 'cavity_upper_jaw_region_mean': m(RW['jaw'], cav & up),
                            'roll_lower_jaw_region_mean': m(RW['jaw'], roll & lo), 'roll_upper_jaw_region_mean': m(RW['jaw'], roll & up),
                            'roll_corner_jaw_region_mean': m(RW['jaw'], roll & cor), 'cap_def_jaw_mean': m(jaw_def, rg == K + 7)}
else: qa['mouth_interior'] = {'note': 'no cavity rings in this file (mouth view skipped)', 'mouth_ring_max': int(rg.max()),
                              'inner_ring_def_jaw_mean': round(float(jaw_def[rg == rg.max()].mean()), 4) if rg.max() > 0 else None}
json.dump(qa, open(os.path.join(OUT, 'weights_qa.json'), 'w'), indent=1)

# --- legend pictures (no text): ramp strip with quarter ticks; per region its base colour (big) and other tones below ---
def png(name, rgb):                                               # rgb: H x W x 3 sRGB, row 0 = top
    h, w = rgb.shape[:2]; im = bpy.data.images.new(name, w, h)
    im.pixels.foreach_set(np.c_[rgb[::-1].reshape(-1, 3), np.ones(h * w)].ravel().astype(np.float32))
    im.filepath_raw = os.path.join(OUT, name + '.png'); im.file_format = 'PNG'; im.save()
BGL = np.array([0.96, 0.96, 0.96]); strip = np.tile(BGL, (72, 1024, 1)); strip[:48, 12:1012] = heat(np.linspace(0, 1, 1000))[None]
for k in range(5): c = 12 + int(round(k * 999 / 4)); strip[48:66, max(c - 2, 0):c + 2] = 0.15
png('w_ramp', strip)
nt = [1 + max(tone[i] for i in range(len(names)) if breg[i] == r) for r in REGS] + [1]; Z, G = 80, 12
sw = np.tile(BGL, (G + Z + (max(nt) - 1) * (Z // 2 + 4) + G, G + (len(REGS) + 1) * (Z + G), 1))
for k, r in enumerate(REGS + ['unweighted']):
    x0 = G + k * (Z + G); sw[G:G + Z, x0:x0 + Z] = hexrgb(PAL[r])
    for t in range(1, nt[k]):
        y0 = G + Z + 4 + (t - 1) * (Z // 2 + 4); sw[y0:y0 + Z // 2, x0:x0 + Z] = tint(hexrgb(PAL[r]), TONE[t % len(TONE)])
png('w_regions', sw)

# --- render setup: Workbench; heat by ramp lookup image (bands: 0 heat, 1 grey context by shade row, 2 mouth parts) ---
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_percentage = 100
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'; sc.render.film_transparent = False
if not sc.world: sc.world = bpy.data.worlds.new('w')
sh = sc.display.shading; sh.show_specular_highlight = False
sh.show_xray = False; sh.show_backface_culling = False; sh.show_shadows = False; sh.show_cavity = False; sh.show_object_outline = False
for o in bpy.data.objects:
    if o.type == 'MESH': o.hide_render = o.name not in ('face', 'eyes')
HB, GB, PB, LW = 16, 64, 16, 256; LH = HB + GB + PB
PARTS = np.array([[0.93, 0.82, 0.73], [0.96, 0.66, 0.66], [0.74, 0.42, 0.52], [0.45, 0.20, 0.32]])   # lip skin, roll, cavity, cap
lut = np.zeros((LH, LW, 3)); lut[:HB] = heat(np.linspace(0, 1, LW))[None]
lut[HB:HB + GB] = np.linspace(0.28, 0.76, GB)[:, None, None]; lut[HB + GB:] = PARTS[np.arange(LW) * len(PARTS) // LW][None]
img = bpy.data.images.new('wviz_lut', LW, LH)                     # byte image, sRGB: the lookup returns these values exactly
img.pixels.foreach_set(np.c_[lut.reshape(-1, 3), np.ones(LW * LH)].ravel().astype(np.float32))   # row 0 = v 0 (bottom)
wm = bpy.data.materials.new('wviz'); wm.use_nodes = True; tx = wm.node_tree.nodes.new('ShaderNodeTexImage')
tx.image = img; tx.interpolation = 'Closest'; wm.node_tree.nodes.active = tx
hu = lambda w: (np.clip(w, 0, 1) * (LW - 1) + 0.5) / LW; VH = HB / 2 / LH; VP = (HB + GB + PB / 2) / LH
vgrey = lambda s: (HB + 0.5 + np.clip(s, 0, 1) * (GB - 1)) / LH
def uvset(ob, u, v):
    m = ob.data
    if not m.materials: m.materials.append(wm)
    for s in ob.material_slots: s.material = wm
    ul = m.uv_layers.get('wviz') or m.uv_layers.new(name='wviz'); m.uv_layers.active = ul; ul.active_render = True
    li = np.empty(len(m.loops), int); m.loops.foreach_get('vertex_index', li)
    ul.data.foreach_set('uv', np.c_[np.broadcast_to(u, (len(m.vertices),))[li], np.broadcast_to(v, (len(m.vertices),))[li]].ravel().astype(np.float32)); m.update()
def paint(ob, rgb):
    m = ob.data; ca = m.color_attributes.get('wviz') or m.color_attributes.new('wviz', 'FLOAT_COLOR', 'POINT')
    m.color_attributes.active_color = ca; m.color_attributes.render_color_index = m.color_attributes.find('wviz')
    ca.data.foreach_set('color', np.c_[lin(np.asarray(rgb, float)), np.ones(len(rgb))].ravel().astype(np.float32)); m.update()
if eyes: paint(eyes, np.full((len(eyes.data.vertices), 3), 0.30)); uvset(eyes, 0.5, vgrey(0.05))
def look(light, ctype, bg=0.62): sh.light = light; sh.color_type = ctype; sc.world.color = (bg, bg, bg)

LT = {int(k): np.array(v) for k, v in json.load(open(LMJ)).items() if not k.startswith('_')}
top = (LT[2][2] + LT[5][2]) / 2; fh = top - LT[24][2]; cz = (top + LT[24][2]) / 2 - 0.02 * fh
ec = (LT[8] + LT[12]) / 2; ew = abs(LT[12][0] - LT[8][0])
cam = bpy.data.cameras.new('wcam'); cam.type = 'ORTHO'; co = bpy.data.objects.new('wcam', cam); sc.collection.objects.link(co); sc.camera = co
def shot(name, d, size, tgt, fit=None, res=(1024, 1024)):
    sc.render.resolution_x, sc.render.resolution_y = res
    d = Vector(d).normalized(); rot = (-d).to_track_quat('-Z', 'Y')
    if fit is not None:                                           # frame these points exactly (camera-plane bbox)
        R = np.array(rot.to_matrix())[:, :2]; q = (fit - np.array(tgt)) @ R; lo_, hi_ = q.min(0), q.max(0)
        tgt = np.array(tgt) + R @ ((lo_ + hi_) / 2); size = 1.12 * float(max(hi_[0] - lo_[0], (hi_[1] - lo_[1]) * res[0] / res[1]))
    co.location = Vector(tuple(tgt)) + d * 2; cam.ortho_scale = size; co.rotation_euler = rot.to_euler(); cam.clip_start = 0.01
    sc.render.filepath = os.path.join(OUT, name + '.png'); bpy.ops.render.render(write_still=True)
FRONT, Q34 = ((0, -1, 0), 1.75 * fh, (0, 0, cz)), ((0.7, -0.7, 0), 1.9 * fh, (0, 0, cz))
EYES = ((0, -1, 0), 1.9 * ew, (0, ec[1], ec[2] + 0.05 * ew)); ERES = (1024, 512)
look('STUDIO', 'TEXTURE')
for r in ('jaw', 'lips', 'lids', 'brows', 'cheeks', 'nose'):
    uvset(face, hu(RW[r]), VH); shot('w_' + r, *FRONT)
    if r == 'jaw': shot('w_jaw_34', *Q34)
    if r == 'lids': shot('w_lids_eyes', *EYES, res=ERES)        # the lid rings are a few pixels wide in the full-face view
look('STUDIO', 'VERTEX'); paint(face, DOM)
shot('w_dominant_front', *FRONT); shot('w_dominant_34', *Q34); shot('w_dominant_eyes', *EYES, res=ERES)

# mouth interior (cavity files only): half head (x <= 0) seen from the character's left; flat light so the colours
# are the ramp; lip skin near the slit + roll + cavity + cap coloured, the rest grey, shaded by how much it faces x
if CAV:
    keep = X[:, 0] <= 2e-4; colv = rg >= K - 3
    vg = face.vertex_groups.new(name='wviz_keep'); vg.add([int(i) for i in np.where(keep)[0]], 1.0, 'REPLACE')
    mk = face.modifiers.new('wviz_mask', 'MASK'); mk.vertex_group = vg.name
    if eyes: eyes.hide_render = True
    fit = np.vstack([X[keep & colv], LT[16][None], LT[24][None]]); vctx = vgrey(0.15 + 0.85 * np.abs(Nr[:, 0]))
    part = np.select([rg == K + 7, rg >= K + 3, rg >= K + 1], [3, 2, 1], 0)
    look('FLAT', 'TEXTURE', 0.86)
    uvset(face, hu(RW['jaw']), np.where(colv, VH, vctx)); shot('w_jaw_mouth', (1, 0, 0), 0, (0.0, *LT[34][1:]), fit=fit)
    uvset(face, (part + 0.5) / len(PARTS), np.where(colv, VP, vctx)); shot('w_mouth_parts', (1, 0, 0), 0, (0.0, *LT[34][1:]), fit=fit)
print('WEIGHTS', json.dumps({k: qa[k] for k in ('unweighted', 'max_influences', 'sum_not_1_share')}), json.dumps(qa['sym']))
print('MOUTHQA', json.dumps(qa['mouth_interior']))
