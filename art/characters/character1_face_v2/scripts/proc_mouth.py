"""Procedural, clean mouth components fitted inside the closed clean head (replaces Tripo's crude mouth interior).

Primary (child) dentition, 5 teeth per quadrant, upper + lower: superellipsoid crowns (incisors thin with a tapered
edge, canines pointed, molars broad), oriented along an elliptic arch; gums swept along the arch with the gum line
following the crown heights; parametric tongue inside the lower arch.  Placement guides come from the registered
Tripo open-mouth parts (incisor front y, incisal z, arch width).  The whole set is shifted back until every vertex is
inside the head with >= CLR clearance from the skin.  All meshes are closed, symmetric and separate objects.
Usage: blender --background head_seam.blend --python proc_mouth.py -- <out.blend>
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
E = lambda k, d: float(os.environ.get(k, d))
S_MM = E("S_MM", 0.0032)          # model units per real mm (fitted so the canine ends near x = 0.065, as in the guide)
Y_FRONT = E("Y_FRONT", -0.262)     # upper arch front (tooth centre line) at x = 0
Z_OCC = E("Z_OCC", 0.4485)         # upper incisal edge height (just under the lip line 0.453)
A_UP, B_UP = E("A_UP", 0.060), E("B_UP", 0.085)
A_LO, B_LO = E("A_LO", 0.055), E("B_LO", 0.080)
OVERJET, OVERBITE = E("OVERJET", 0.0065), E("OVERBITE", 0.005)
CLR = E("CLR", 0.002)
ROOT = E("ROOT", 1.35)          # crown mesh height / visible crown height (the rest sits in the gum)
rep = {}
for nm in ("TeethUpper", "TeethLower", "Tongue", "GumUpper", "GumLower"):
    o = bpy.data.objects.get(nm)
    if o: bpy.data.objects.remove(o)
head = bpy.data.objects["Head"]

# (name, width mm, height factor, thickness factor, kind)
UPPER = [("i1", 6.5, 1.15, 0.45, "inc"), ("i2", 5.2, 1.05, 0.45, "inc"), ("c", 6.8, 1.05, 0.75, "can"),
         ("m1", 7.3, 0.72, 0.90, "mol"), ("m2", 8.2, 0.68, 0.92, "mol")]
LOWER = [("i1", 4.0, 1.10, 0.50, "inc"), ("i2", 4.5, 1.05, 0.50, "inc"), ("c", 5.5, 1.00, 0.75, "can"),
         ("m1", 7.7, 0.70, 0.90, "mol"), ("m2", 9.9, 0.66, 0.92, "mol")]


class Arch:
    def __init__(s, a, b, yc):
        s.a, s.b, s.yc = a, b, yc
        th = np.linspace(0, math.radians(120), 4000)
        pts = np.c_[a * np.sin(th), yc + b * (1 - np.cos(th))]
        s.th = th; s.L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]

    def at(s, L):
        th = float(np.interp(L, s.L, s.th))
        p = Vector((s.a * math.sin(th), s.yc + s.b * (1 - math.cos(th)), 0))
        tan = Vector((s.a * math.cos(th), s.b * math.sin(th), 0)).normalized()
        nrm = Vector((tan.y, -tan.x, 0))            # labial (outward / toward -Y at the front)
        return p, tan, nrm, th


def superellipsoid(bm, w, t, h, kind, e=0.45):
    """crown in local coords: x along arch (w), y labial (t), z from 0 (edge) to h_tot (root side)"""
    geom = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=1.0)
    vs = [v for v in geom["verts"]]
    for v in vs:
        x, y, z = v.co
        sx = math.copysign(abs(x) ** e, x); sy = math.copysign(abs(y) ** e, y); sz = math.copysign(abs(z) ** 0.7, z)
        z01 = (sz + 1) / 2                                  # 0 at the edge, 1 at the root
        wx, ty = 1.0, 1.0
        if kind == "inc": ty = 0.30 + 0.70 * min(1, z01 * 1.6)
        if kind == "can": wx = 0.40 + 0.60 * min(1, z01 * 1.5); ty = 0.55 + 0.45 * min(1, z01 * 1.5)
        if kind == "mol" and z01 < 0.12: sz = -1 + (sz + 1) * 0.6   # flatter occlusal surface
        v.co = Vector((sx * w / 2 * wx, sy * t / 2 * ty, z01 * h))
    return vs


def build_teeth(name, spec, arch, z_edge_fn, upper):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    crowns = []
    for side in (1,):                       # right half built, then mirrored exactly
        L = 0.0
        for (tn, wmm, hf, tf, kind) in spec:
            w = wmm * S_MM; h_vis = w * hf; t = w * tf
            p, tan, nrm, th = arch.at(L + w / 2)
            L += w
            vs = superellipsoid(bm, w * 0.96, t, h_vis * ROOT, kind)
            ze = z_edge_fn(th, kind)
            # local frame: x = tangent, y = labial normal, z = up (upper teeth flipped: edge at bottom, root up)
            tx = Vector((side * tan.x, tan.y, 0)); ny = Vector((side * nrm.x, nrm.y, 0))
            zz = Vector((0, 0, 1 if upper else -1))
            tilt = Matrix.Rotation(math.radians(5 if kind == "inc" else 2) * (1 if upper else -1), 3, tx)   # labial inclination
            R = Matrix((tx, ny, zz)).transposed()
            base = Vector((side * p.x, p.y, ze))
            for v in vs:
                v.co = base + tilt @ (R @ v.co)
            crowns.append((tn, side, th, h_vis, t, w))
    dup = bmesh.ops.duplicate(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces))
    dv = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMVert)]
    for v in dv: v.co.x = -v.co.x
    bmesh.ops.reverse_faces(bm, faces=[g for g in dup["geom"] if isinstance(g, bmesh.types.BMFace)])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bm.normal_update()
    bm.to_mesh(me); bm.free()
    for f in me.polygons: f.use_smooth = True
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    return o, crowns, L


def build_gum(name, arch, crowns, upper, z_edge_fn, Lmax):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    th_c = np.array([c[2] for c in crowns if c[1] == 1]); hv = np.array([c[3] for c in crowns if c[1] == 1])
    tt = np.array([c[4] for c in crowns if c[1] == 1])
    rings = []; NS = 70; NP = 16
    Ls = np.linspace(-Lmax - 0.004, Lmax + 0.004, NS)
    for L in Ls:
        p, tan, nrm, th = arch.at(abs(L)); side = 1 if L >= 0 else -1
        hvis = float(np.interp(th, th_c, hv)); tk = float(np.interp(th, th_c, tt))
        ze = z_edge_fn(th, "mol" if th > th_c[2] else "inc")
        zg = ze + (hvis * 0.92 if upper else -hvis * 0.92)          # gum line just over the crown base
        gh = 0.013; gw = tk + 0.008
        zc = zg + (gh / 2 if upper else -gh / 2)
        c = Vector((side * p.x, p.y, zc)); ny = Vector((side * nrm.x, nrm.y, 0))
        ring = []
        for k in range(NP):
            ang = 2 * math.pi * k / NP
            ring.append(bm.verts.new(c + ny * (math.cos(ang) * gw / 2) + Vector((0, 0, math.sin(ang) * gh / 2))))
        rings.append(ring)
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for k in range(NP):
            bm.faces.new((r0[k], r0[(k + 1) % NP], r1[(k + 1) % NP], r1[k]))
    for r in (rings[0], rings[-1]):
        cen = bm.verts.new(sum((v.co for v in r), Vector()) / NP)
        for k in range(NP):
            bm.faces.new((r[k], r[(k + 1) % NP], cen) if r is rings[-1] else (r[(k + 1) % NP], r[k], cen))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    sub = o.modifiers.new("sub", 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
    bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier="sub")
    for f in me.polygons: f.use_smooth = True
    return o


up_arch = Arch(A_UP, B_UP, Y_FRONT)
lo_arch = Arch(A_LO, B_LO, Y_FRONT + OVERJET)
zu = lambda th, kind: Z_OCC if kind == "inc" else (Z_OCC + 0.0008 if kind == "can" else Z_OCC + 0.0015)
zl = lambda th, kind: Z_OCC + OVERBITE if kind == "inc" else (Z_OCC + 0.0030 if kind == "can" else Z_OCC + 0.0012)
TU, cu, Lu = build_teeth("TeethUpper", UPPER, up_arch, zu, True)
TL, cl, Ll = build_teeth("TeethLower", LOWER, lo_arch, zl, False)
GU = build_gum("GumUpper", up_arch, cu, True, zu, Lu)
GL = build_gum("GumLower", lo_arch, cl, False, zl, Ll)

# tongue: rounded slab inside the lower arch, top just under the occlusal plane, midline groove
bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=1.0)
mol_t = LOWER[3][1] * S_MM * LOWER[3][3]
TW = 2 * (A_LO - mol_t / 2 - 0.008); TLEN = E("TONGUE_LEN", 0.11); TH = E("TONGUE_TH", 0.032)
y_tip = Y_FRONT + OVERJET + 0.012
for v in bm.verts:
    x, y, z = v.co
    zt = z * (0.55 if z > 0 else 1.0)                              # flatter top
    zt -= 0.18 * math.exp(-(x / 0.18) ** 2) * max(0, z)            # midline groove
    wy = 1 - 0.25 * max(0, -y)                                     # narrower tip
    v.co = Vector((x * TW / 2 * wy, y_tip + (y + 1) / 2 * TLEN, Z_OCC + OVERBITE - 0.007 - TH * 0.55 + zt * TH / 2 + 0.006 * (y + 1) / 2))
bm.normal_update()
tme = bpy.data.meshes.new("Tongue"); bm.to_mesh(tme); bm.free()
for f in tme.polygons: f.use_smooth = True
TO = bpy.data.objects.new("Tongue", tme); bpy.context.scene.collection.objects.link(TO)
parts = [TU, TL, GU, GL, TO]

# fit inside the head: shift back (+Y) until every vertex is inside with >= CLR clearance
HX = np.array([v.co[:] for v in head.data.vertices])
HT = BVHTree.FromPolygons([tuple(p) for p in HX], [tuple(p.vertices) for p in head.data.polygons])


def inside(p):
    votes = 0
    for d in (Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((0.3, 0.2, 0.93)).normalized()):
        c = 0; o = Vector(p)
        while True:
            h = HT.ray_cast(o, d, 5)
            if h[0] is None: break
            c += 1; o = h[0] + d * 1e-6
        votes += c % 2
    return votes >= 2


def worst():
    bad, mind = 0, 9.0
    for o in parts:
        for v in o.data.vertices[::2] if False else list(o.data.vertices)[::2]:
            p = v.co
            d = (HT.find_nearest(p)[0] - p).length
            if not inside(p): bad += 1; mind = min(mind, -d)
            else: mind = min(mind, d)
    return bad, mind


shift = 0.0
for it in range(30):
    bad, mind = worst()
    if bad == 0 and mind >= CLR: break
    for o in parts:
        o.data.transform(Matrix.Translation((0, 0.001, 0)))
    shift += 0.001
rep.update(shift_back=shift, outside=bad, min_clearance_mm=mind * 1000)
for o in parts:
    rep[o.name] = {"faces": len(o.data.polygons)}
    bm = bmesh.new(); bm.from_mesh(o.data)
    rep[o.name]["boundary_edges"] = sum(1 for e in bm.edges if e.is_boundary)
    bm.free()
# pairwise intersections (teeth vs gum allowed: crowns are rooted in the gum)
def bvh(o):
    P = np.array([v.co[:] for v in o.data.vertices]); return BVHTree.FromPolygons([tuple(p) for p in P], [tuple(p.vertices) for p in o.data.polygons])
B = {o.name: bvh(o) for o in parts}
rep["overlap_upper_lower_teeth"] = len(B["TeethUpper"].overlap(B["TeethLower"]))
rep["overlap_tongue_teethlower"] = len(B["Tongue"].overlap(B["TeethLower"]))
rep["overlap_tongue_gumlower"] = len(B["Tongue"].overlap(B["GumLower"]))
rep["overlap_tongue_upper"] = len(B["Tongue"].overlap(B["TeethUpper"])) + len(B["Tongue"].overlap(B["GumUpper"]))
COL = {"TeethUpper": (1, 1, 0.93), "TeethLower": (0.97, 0.97, 0.9), "GumUpper": (0.85, 0.42, 0.45), "GumLower": (0.8, 0.38, 0.42), "Tongue": (0.85, 0.3, 0.36)}
for o in parts:
    m = bpy.data.materials.new(f"M_{o.name}"); m.diffuse_color = (*COL[o.name], 1); o.data.materials.append(m)
head["mouth_params"] = json.dumps({"S_MM": S_MM, "Y_FRONT": Y_FRONT + shift, "Z_OCC": Z_OCC, "A_UP": A_UP, "B_UP": B_UP, "A_LO": A_LO, "B_LO": B_LO})
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
json.dump(rep, open(OUT.replace(".blend", "_report.json"), "w"), indent=1)
print("MOUTH", json.dumps(rep))
