"""Build four low-poly hand tools (pickaxe, broom, umbrella, lantern) as GLB files.

  blender -b --factory-startup -P tools/body_gen/build_hand_tools.py -- \
      [--out game/assets/tools] [--preview DIR] [--only pickaxe,broom,umbrella,lantern]

Conventions (must match equip_sockets.json from the animation-check session N6):
  * units are metres; the object origin is the point the hand grips;
  * the handle runs along glTF +Y toward the tool head. The model is built along
    Blender +Z, and the exporter's Y-up conversion (x, y, z) -> (x, z, -y) turns that
    into +Y in the GLB;
  * within +-4 cm of the origin along the handle there is nothing but the handle
    (handle radius 1.5-2.5 cm); the handles have vertex rings at -4, 0 and +4 cm so that
    vertex-based grip checks find surface there;
  * lantern: origin = centre of the top ring, the body hangs toward -Y;
  * umbrella: the main node is the closed umbrella's stick (handle, shaft, tip). Two
    child nodes hold the fabric: 'Canopy' (open, radius 0.5 m) and 'Furled' (closed wrap
    around the shaft). Show one of them at a time.

Everything is made from swept rings (loft), so there are no textures or UVs: flat
Principled BSDF colours, 2-3 materials per tool, <= 1,500 triangles per GLB.
After export the GLB is read back with a tiny pure-Python reader and the triangle
count, material count, node names and POSITION bounds are printed.
With --preview DIR the GLBs are re-imported and rendered (Workbench) into
DIR/hand_tools_2x2.png; red/orange rings mark the origin and the +-4 cm grip zone.
"""
import json
import math
import os
import struct
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

TAU = 2.0 * math.pi
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ----------------------------------------------------------------------------- args
def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {"out": os.path.join(REPO, "game", "assets", "tools"), "preview": None,
            "only": "pickaxe,broom,umbrella,lantern"}
    i = 0
    while i < len(argv):
        key = argv[i].lstrip("-")
        if key in opts and i + 1 < len(argv):
            opts[key] = argv[i + 1]
            i += 2
        else:
            raise SystemExit("unknown argument: %s" % argv[i])
    opts["only"] = [s.strip() for s in opts["only"].split(",") if s.strip()]
    return opts


# ------------------------------------------------------------------------ materials
def srgb(c):
    """sRGB 0-1 -> linear (Blender colour inputs are linear)."""
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def material(name, rgb, rough=0.7, metal=0.0, emit=None, emit_strength=1.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    lin = srgb(rgb)
    p.inputs["Base Color"].default_value = (*lin, 1.0)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit:
        p.inputs["Emission Color"].default_value = (*srgb(emit), 1.0)
        p.inputs["Emission Strength"].default_value = emit_strength
    m.use_backface_culling = True  # closed meshes: glTF doubleSided = false (cheaper in Godot)
    m.diffuse_color = (*lin, 1.0)  # viewport / Workbench colour
    m.roughness = rough
    m.metallic = metal
    return m


def mats():
    return {
        "wood": material("tool_wood", (0.62, 0.40, 0.24), rough=0.75),
        "wood_dark": material("tool_wood_dark", (0.48, 0.29, 0.16), rough=0.7),
        "steel": material("tool_steel", (0.66, 0.68, 0.72), rough=0.42, metal=0.6),
        "straw": material("tool_straw", (0.93, 0.78, 0.40), rough=0.9),
        "binding": material("tool_red_binding", (0.80, 0.19, 0.16), rough=0.8),
        "canopy": material("tool_canopy_coral", (0.93, 0.44, 0.32), rough=0.8),
        "metal": material("tool_metal_grey", (0.58, 0.58, 0.61), rough=0.45, metal=0.5),
        "iron": material("tool_iron_dark", (0.21, 0.21, 0.23), rough=0.55, metal=0.45),
        "glass": material("tool_glass_glow", (1.0, 0.80, 0.46), rough=0.3,
                          emit=(1.0, 0.70, 0.34), emit_strength=2.0),
    }


# ------------------------------------------------------------------------- geometry
def _frames(pts, hint):
    """Tangent T, normal N, binormal B (= T x N) per path point, parallel-transported."""
    n = len(pts)
    T = []
    for i in range(n):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        T.append((b - a).normalized())
    h = Vector(hint)
    nv = (h - T[0] * h.dot(T[0])).normalized()
    N = []
    for i in range(n):
        if i:
            nv = (nv - T[i] * nv.dot(T[i])).normalized()
        N.append(nv.copy())
    return T, N, [T[i].cross(N[i]) for i in range(n)]


def loft(bm, rings, segs, mat, hint=(1, 0, 0), phase=0.0, mod=None):
    """Sweep rings along a path. rings = [(centre, rx[, ry[, angle_offset]])].

    rx (along N) / ry (along B); a ring with radius 0 becomes a pole (closed, rounded
    end). mod(i, j, angle) -> (radial scale, offset along T) for per-vertex shaping.
    Winding is outward: quads (A[j], A[j+1], B[j+1], B[j]), start pole (P, B[j+1], B[j]),
    end pole (A[j], A[j+1], P). Returns the new faces.
    """
    pts = [Vector(r[0]) for r in rings]
    T, N, B = _frames(pts, hint)
    rows = []
    for i, ring in enumerate(rings):
        rx = ring[1]
        ry = ring[2] if len(ring) > 2 else rx
        off = ring[3] if len(ring) > 3 else 0.0
        if rx <= 1e-7 and ry <= 1e-7:
            rows.append([bm.verts.new(pts[i])])
            continue
        row = []
        for j in range(segs):
            a = TAU * j / segs + phase + off
            s, dt = mod(i, j, a) if mod else (1.0, 0.0)
            p = pts[i] + N[i] * (math.cos(a) * rx * s) + B[i] * (math.sin(a) * ry * s) + T[i] * dt
            row.append(bm.verts.new(p))
        rows.append(row)
    faces = []
    for i in range(len(rows) - 1):
        A, C = rows[i], rows[i + 1]
        if len(A) == 1 and len(C) == 1:
            continue
        for j in range(segs):
            k = (j + 1) % segs
            if len(A) == 1:
                f = bm.faces.new((A[0], C[k], C[j]))
            elif len(C) == 1:
                f = bm.faces.new((A[j], A[k], C[0]))
            else:
                f = bm.faces.new((A[j], A[k], C[k], C[j]))
            f.material_index = mat
            faces.append(f)
    return faces


def zrings(spec, x=0.0, y=0.0):
    """[(z, rx[, ry])] -> rings on a vertical axis through (x, y)."""
    return [((x, y, s[0]),) + tuple(s[1:]) for s in spec]


def torus(bm, centre, R, r, seg_major, seg_minor, mat, axis="Z"):
    """Torus around `axis` ('Z' = ring lies in XY, 'Y' = ring lies in XZ)."""
    rot = Matrix.Identity(3) if axis == "Z" else Matrix.Rotation(math.pi / 2, 3, "X")
    c = Vector(centre)
    rows = []
    for i in range(seg_major):
        u = TAU * i / seg_major
        d = Vector((math.cos(u), math.sin(u), 0.0))
        row = []
        for j in range(seg_minor):
            v = TAU * j / seg_minor
            p = d * (R + r * math.cos(v)) + Vector((0, 0, r * math.sin(v)))
            row.append(bm.verts.new(c + rot @ p))
        rows.append(row)
    faces = []
    for i in range(seg_major):
        A, C = rows[i], rows[(i + 1) % seg_major]
        for j in range(seg_minor):
            k = (j + 1) % seg_minor
            # u grows along +phi, v grows outward->up: (A[j], C[j], C[k], A[k]) is outward
            f = bm.faces.new((A[j], C[j], C[k], A[k]))
            f.material_index = mat
            faces.append(f)
    return faces


def signed_volume(faces):
    vol = 0.0
    for f in faces:
        vs = [v.co for v in f.verts]
        for t in range(1, len(vs) - 1):
            vol += vs[0].dot(vs[t].cross(vs[t + 1])) / 6.0
    return vol


def check_closed(label, faces):
    v = signed_volume(faces)
    if v <= 0:
        print("  !! %s: negative volume %.6f (normals inward?)" % (label, v))
    return v


def finish_object(name, bm, materials, smooth_deg=50.0, parent=None):
    """bmesh -> mesh object; smooth shading with sharp edges above smooth_deg."""
    bm.normal_update()
    lim = math.radians(smooth_deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim:
            e.smooth = False
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in materials:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if parent:
        ob.parent = parent
    return ob


# ---------------------------------------------------------------------------- tools
def build_pickaxe(M):
    """0.90 m long (Y -0.27..+0.63), head 0.45 m wide (pick point +X, chisel -X)."""
    bm = bmesh.new()
    WOOD, STEEL = 0, 1
    handle = [(-0.270, 0), (-0.266, 0.012), (-0.258, 0.021), (-0.246, 0.025), (-0.232, 0.025),
              (-0.220, 0.0215), (-0.205, 0.019), (-0.100, 0.019), (-0.040, 0.019), (0.000, 0.019),
              (0.040, 0.0192), (0.100, 0.0195),
              (0.300, 0.0205), (0.500, 0.022), (0.600, 0.022), (0.616, 0.0205),
              (0.626, 0.014), (0.630, 0)]
    f = loft(bm, [((0, 0, z), r, r * 0.88) for z, r in handle], 14, WOOD)
    check_closed("pickaxe handle", f)
    collar = [(0.519, 0), (0.521, 0.024, 0.026), (0.528, 0.031, 0.034), (0.614, 0.031, 0.034),
              (0.622, 0.026, 0.028), (0.625, 0)]
    f = loft(bm, zrings(collar), 12, STEEL)
    check_closed("pickaxe collar", f)
    zc, droop = 0.578, 0.9

    def arm(sign, prof):
        rings = []
        for x, rz, ry in prof:
            rings.append(((sign * x, 0.0, zc - droop * x * x), rz, ry))
        return loft(bm, rings, 8, STEEL, hint=(0, 0, 1))

    # pick point (+X): tapers to a point
    f = arm(1, [(0.0, 0, 0), (0.004, 0.031, 0.026), (0.04, 0.029, 0.024), (0.09, 0.023, 0.019),
                (0.14, 0.016, 0.0135), (0.18, 0.010, 0.0085), (0.208, 0.0045, 0.004),
                (0.225, 0, 0)])
    check_closed("pick arm", f)
    # chisel (-X): thin vertically, stays wide in depth -> flat blade edge
    f = arm(-1, [(0.0, 0, 0), (0.004, 0.031, 0.026), (0.04, 0.028, 0.025), (0.09, 0.021, 0.024),
                 (0.14, 0.014, 0.024), (0.185, 0.008, 0.024), (0.214, 0.004, 0.021),
                 (0.225, 0, 0)])
    check_closed("chisel arm", f)
    return {"Pickaxe": finish_object("Pickaxe", bm, [M["wood"], M["steel"]])}


BROOM_PROFILE = [(0.500, 0, 0), (0.506, 0.022, 0.022), (0.520, 0.034, 0.030), (0.560, 0.042, 0.034),
                 (0.620, 0.055, 0.037), (0.700, 0.090, 0.042), (0.780, 0.128, 0.046),
                 (0.840, 0.150, 0.047), (0.866, 0.157, 0.046), (0.874, 0.140, 0.036),
                 (0.877, 0, 0)]


def _broom_radius(z):
    pr = BROOM_PROFILE
    for a, b in zip(pr[1:], pr[2:]):
        if a[0] <= z <= b[0]:
            t = (z - a[0]) / (b[0] - a[0])
            return a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t
    raise ValueError(z)


def build_broom(M):
    """1.20 m long (Y -0.32..+0.88); corn broom, bristles toward +Y."""
    bm = bmesh.new()
    WOOD, STRAW, RED = 0, 1, 2
    handle = [(-0.320, 0), (-0.316, 0.011), (-0.308, 0.018), (-0.296, 0.0215), (-0.284, 0.0215),
              (-0.274, 0.018), (-0.262, 0.0172), (-0.040, 0.0175), (0.000, 0.0175), (0.040, 0.0175),
              (0.300, 0.018),
              (0.540, 0.0185), (0.600, 0.0185), (0.606, 0)]
    f = loft(bm, zrings(handle), 12, WOOD)
    check_closed("broom handle", f)
    jag = len(BROOM_PROFILE) - 3  # ring index of the straw tips

    def straw(i, j, a):
        z = BROOM_PROFILE[i][0]
        s = 1.0 + (0.035 * math.sin(j * 2.7 + i * 1.3) if z >= 0.66 else 0.0)
        dt = 0.0
        if i == jag:
            dt = 0.014 if j % 2 == 0 else 0.0
        elif i == jag - 1:
            dt = 0.004 if j % 2 == 0 else -0.004
        return s, dt

    f = loft(bm, [((0, 0, z), rx, ry) for z, rx, ry in BROOM_PROFILE], 20, STRAW, mod=straw)
    check_closed("bristles", f)
    for zc in (0.545, 0.590, 0.640):
        rings = []
        for dz, grow in ((-0.011, -0.003), (-0.008, 0.005), (0.008, 0.005), (0.011, -0.003)):
            rx, ry = _broom_radius(zc + dz)
            rings.append(((0, 0, zc + dz), rx + grow, ry + grow))
        loft(bm, rings, 20, RED)  # open band, both rims tucked under the straw
    return {"Broom": finish_object("Broom", bm, [M["wood"], M["straw"], M["binding"]])}


def build_umbrella(M):
    """0.90 m closed (Y -0.15..+0.75), crook handle at the bottom, tip at +Y.

    Children: 'Canopy' (open, radius 0.5 m) and 'Furled' (closed wrap).
    """
    WOOD, CANOPY, METAL = 0, 1, 2
    mlist = [M["wood_dark"], M["canopy"], M["metal"]]
    bm = bmesh.new()
    # straight grip from +0.095 down to -0.08, then a J crook bending toward +X
    rings = [((0, 0, 0.100), 0), ((0, 0, 0.097), 0.013), ((0, 0, 0.089), 0.0195),
             ((0, 0, 0.075), 0.0205), ((0, 0, 0.040), 0.0205), ((0, 0, 0.0), 0.0205),
             ((0, 0, -0.040), 0.0205), ((0, 0, -0.080), 0.0205)]
    cx, cz, rc = 0.0495, -0.080, 0.0495
    n_arc = 9  # 22.5 deg steps, so the lowest point (270 deg) is a ring
    th_end = TAU + math.pi / 8
    for k in range(1, n_arc + 1):
        th = math.pi + (th_end - math.pi) * k / n_arc
        rings.append(((cx + rc * math.cos(th), 0, cz + rc * math.sin(th)), 0.0205))
    tan = Vector((-math.sin(th_end), 0, math.cos(th_end)))
    end = Vector(rings[-1][0])
    rings.append((tuple(end + tan * 0.009), 0.017))
    rings.append((tuple(end + tan * 0.016), 0))
    f = loft(bm, rings, 10, WOOD, hint=(0, 1, 0), phase=TAU / 20)  # a vertex at the very bottom
    check_closed("crook handle", f)
    f = loft(bm, zrings([(0.086, 0), (0.088, 0.013), (0.094, 0.0165), (0.106, 0.0165),
                         (0.112, 0.011), (0.114, 0)]), 10, METAL)
    check_closed("handle collar", f)
    f = loft(bm, zrings([(0.105, 0), (0.106, 0.0085), (0.705, 0.0085), (0.706, 0)]), 8, METAL)
    check_closed("shaft", f)
    f = loft(bm, zrings([(0.698, 0), (0.700, 0.012), (0.712, 0.013), (0.722, 0.0095),
                         (0.738, 0.005), (0.750, 0)]), 8, METAL)
    check_closed("ferrule", f)
    stick = finish_object("Umbrella", bm, mlist)

    # closed canopy: spindle with 8 folds that twist a little toward the tip
    bm = bmesh.new()
    fur = [(0.262, 0), (0.266, 0.012), (0.285, 0.034), (0.320, 0.050), (0.400, 0.056),
           (0.500, 0.050), (0.600, 0.034), (0.660, 0.020), (0.690, 0.012), (0.694, 0)]
    rings = [((0, 0, z), r, r, 0.05 * i) for i, (z, r) in enumerate(fur)]

    def folds(i, j, a):
        return (1.0 if j % 2 == 0 or i in (1, len(fur) - 2) else 0.74), 0.0

    f = loft(bm, rings, 16, CANOPY, mod=folds)
    check_closed("furled", f)
    furled = finish_object("Furled", bm, mlist, parent=stick)

    # open canopy: 8 panels with a scalloped rim, 8 mm thick shell
    bm = bmesh.new()
    segs, R, apex, drop, thick = 32, 0.5, 0.705, 0.17, 0.008
    us = (0.07, 0.34, 0.64, 1.0)

    def pos(u, j):
        th = TAU * j / segs
        s = math.sin(math.pi * ((th / (TAU / 8)) % 1.0))  # 0 on a rib, 1 mid-panel
        r = R * u * (1.0 - 0.055 * s * u)
        z = apex - drop * u ** 1.7 + 0.032 * s * u ** 3
        return Vector((r * math.cos(th), r * math.sin(th), z))

    down = Vector((0, 0, thick))
    top = [[bm.verts.new(pos(u, j)) for j in range(segs)] for u in us]
    bot = [[bm.verts.new(pos(u, j) - down) for j in range(segs)] for u in us]
    pt = bm.verts.new((0, 0, apex))
    pb = bm.verts.new((0, 0, apex - thick))
    faces = []
    for j in range(segs):
        k = (j + 1) % segs
        faces.append(bm.faces.new((pt, top[0][j], top[0][k])))
        faces.append(bm.faces.new((pb, bot[0][k], bot[0][j])))
        for i in range(len(us) - 1):
            faces.append(bm.faces.new((top[i][j], top[i + 1][j], top[i + 1][k], top[i][k])))
            faces.append(bm.faces.new((bot[i][k], bot[i + 1][k], bot[i + 1][j], bot[i][j])))
        faces.append(bm.faces.new((top[-1][j], bot[-1][j], bot[-1][k], top[-1][k])))
    for f in faces:
        f.material_index = CANOPY
    check_closed("canopy", faces)
    canopy = finish_object("Canopy", bm, mlist, smooth_deg=60.0, parent=stick)
    return {"Umbrella": stick, "Furled": furled, "Canopy": canopy}


def build_lantern(M):
    """Origin = centre of the top ring; 0.35 m from the ring top (Y +0.06) to the base (Y -0.29)."""
    IRON, GLASS = 0, 1
    bm = bmesh.new()
    f = torus(bm, (0, 0, 0), 0.045, 0.015, 20, 10, IRON, axis="Y")  # 20: a vertex at the top
    check_closed("ring", f)
    f = loft(bm, zrings([(-0.050, 0), (-0.052, 0.010), (-0.058, 0.0155), (-0.068, 0.017),
                         (-0.078, 0.021), (-0.082, 0)]), 10, IRON)
    check_closed("ring knob", f)
    hexs = 6
    f = loft(bm, zrings([(-0.074, 0), (-0.076, 0.024), (-0.084, 0.032), (-0.116, 0.084),
                         (-0.122, 0.092), (-0.130, 0.092), (-0.135, 0.080), (-0.137, 0)]),
             hexs, IRON)
    check_closed("roof", f)
    f = loft(bm, zrings([(-0.130, 0), (-0.132, 0.066), (-0.190, 0.071), (-0.246, 0.066),
                         (-0.248, 0)]), hexs, GLASS)
    check_closed("glass", f)
    for k in range(hexs):
        a = TAU * k / hexs
        x, y = 0.071 * math.cos(a), 0.071 * math.sin(a)
        f = loft(bm, zrings([(-0.128, 0), (-0.130, 0.0065), (-0.248, 0.0065), (-0.250, 0)], x, y),
                 6, IRON)
        check_closed("bar", f)
    f = loft(bm, zrings([(-0.240, 0), (-0.242, 0.072), (-0.250, 0.080), (-0.261, 0.087),
                         (-0.277, 0.087), (-0.286, 0.080), (-0.290, 0)]), hexs, IRON)
    check_closed("base", f)
    return {"Lantern": finish_object("Lantern", bm, [M["iron"], M["glass"]], smooth_deg=40.0)}


BUILDERS = {"pickaxe": build_pickaxe, "broom": build_broom,
            "umbrella": build_umbrella, "lantern": build_lantern}


# --------------------------------------------------------------------------- export
def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)


def export_glb(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs.values():
        ob.select_set(True)
    bpy.context.view_layer.objects.active = next(iter(objs.values()))
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_materials="EXPORT",
                              export_animations=False)


# ----------------------------------------------------------------------- glb reader
def read_glb_json(path):
    with open(path, "rb") as fh:
        data = fh.read()
    magic, _ver, length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67:
        raise ValueError("not a GLB: %s" % path)
    off = 12
    while off < length:
        clen, ctype = struct.unpack_from("<II", data, off)
        off += 8
        if ctype == 0x4E4F534A:
            return json.loads(data[off:off + clen].decode("utf-8"))
        off += clen
    raise ValueError("no JSON chunk")


def glb_stats(path):
    js = read_glb_json(path)
    acc = js["accessors"]
    out = {"file": path, "bytes": os.path.getsize(path), "materials": len(js.get("materials", [])),
           "material_names": [m.get("name") for m in js.get("materials", [])],
           "nodes": [], "tris": 0, "min": [math.inf] * 3, "max": [-math.inf] * 3, "meshes": {}}
    for n in js["nodes"]:
        xf = {k: n[k] for k in ("translation", "rotation", "scale", "matrix") if k in n}
        out["nodes"].append({"name": n.get("name"), "mesh": n.get("mesh"),
                             "children": n.get("children", []), "transform": xf})
    for mi, mesh in enumerate(js["meshes"]):
        mt, mn, mx = 0, [math.inf] * 3, [-math.inf] * 3
        for prim in mesh["primitives"]:
            pa = acc[prim["attributes"]["POSITION"]]
            mn = [min(a, b) for a, b in zip(mn, pa["min"])]
            mx = [max(a, b) for a, b in zip(mx, pa["max"])]
            cnt = acc[prim["indices"]]["count"] if "indices" in prim else pa["count"]
            if prim.get("mode", 4) == 4:
                mt += cnt // 3
        node = next((n["name"] for n in out["nodes"] if n["mesh"] == mi), mesh.get("name"))
        out["meshes"][node] = {"tris": mt, "min": mn, "max": mx}
        out["tris"] += mt
        out["min"] = [min(a, b) for a, b in zip(out["min"], mn)]
        out["max"] = [max(a, b) for a, b in zip(out["max"], mx)]
    return out


def print_stats(st):
    fmt = lambda v: "(" + ", ".join("%+.4f" % x for x in v) + ")"
    print("  %s  %.1f KB" % (st["file"], st["bytes"] / 1024.0))
    print("    triangles %d, materials %d %s" % (st["tris"], st["materials"], st["material_names"]))
    print("    bounds min %s max %s" % (fmt(st["min"]), fmt(st["max"])))
    for axis, i in (("X", 0), ("Y", 1), ("Z", 2)):
        print("      %s: %+.4f .. %+.4f  (%.4f m)" % (axis, st["min"][i], st["max"][i],
                                                    st["max"][i] - st["min"][i]))
    for name, m in st["meshes"].items():
        print("    mesh node %-10s tris %4d  Y %+.4f .. %+.4f" % (name, m["tris"], m["min"][1], m["max"][1]))
    for n in st["nodes"]:
        print("    node %-10s children %s transform %s" % (n["name"], n["children"], n["transform"] or "identity"))


# -------------------------------------------------------------------------- preview
def preview(paths, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    import numpy as np

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = True
    sh.show_object_outline = True
    sh.show_backface_culling = True  # flipped normals would show up as holes
    scene.display.render_aa = "8"
    scene.view_settings.view_transform = "Standard"
    scene.render.resolution_x = scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    if not scene.world:
        scene.world = bpy.data.worlds.new("preview_world")
    scene.world.color = (0.80, 0.80, 0.82)
    marker_red = material("preview_marker_red", (0.95, 0.10, 0.10))
    marker_org = material("preview_marker_orange", (1.0, 0.6, 0.1))

    def add_markers(offset):
        bm = bmesh.new()
        torus(bm, Vector(offset), 0.032, 0.0025, 24, 4, 0)
        torus(bm, Vector(offset) + Vector((0, 0, 0.04)), 0.030, 0.002, 24, 4, 1)
        torus(bm, Vector(offset) + Vector((0, 0, -0.04)), 0.030, 0.002, 24, 4, 1)
        return finish_object("marker", bm, [marker_red, marker_org])

    def import_glb(path, offset=(0, 0, 0)):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            if o.parent is None:
                o.location = Vector(offset)
            for slot in o.material_slots:
                m = slot.material
                p = m.node_tree.nodes.get("Principled BSDF") if m and m.node_tree else None
                if p:
                    m.diffuse_color = p.inputs["Base Color"].default_value[:]
        return new

    def render_panel(name, png):
        bpy.context.view_layer.update()
        obs = [o for o in scene.objects if o.type == "MESH" and not o.hide_render]
        pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        c = (lo + hi) / 2
        d = Vector((0.55, -1.0, 0.32)).normalized()
        cam_data = bpy.data.cameras.new("cam")
        cam_data.type = "ORTHO"
        cam = bpy.data.objects.new("cam", cam_data)
        scene.collection.objects.link(cam)
        cam.location = c + d * 4.0
        rot = (-d).to_track_quat("-Z", "Y")
        cam.rotation_euler = rot.to_euler()
        right, up = rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0))
        sx = max(p.dot(right) for p in pts) - min(p.dot(right) for p in pts)
        sy = max(p.dot(up) for p in pts) - min(p.dot(up) for p in pts)
        cam_data.ortho_scale = max(sx, sy) * 1.12
        cam_data.clip_end = 20.0
        scene.camera = cam
        scene.render.filepath = png
        bpy.ops.render.render(write_still=True)
        print("  rendered %s -> %s" % (name, png))

    panels = []
    for name in ("pickaxe", "broom", "umbrella", "lantern"):
        if name not in paths:
            continue
        clear_scene()
        if name == "umbrella":
            closed = import_glb(paths[name], (0, 0, 0))
            opened = import_glb(paths[name], (0.75, 0, 0))
            for o in closed:
                if o.name.startswith("Canopy"):
                    o.hide_render = True
            for o in opened:
                if o.name.startswith("Furled"):
                    o.hide_render = True
            add_markers((0, 0, 0))
            add_markers((0.75, 0, 0))
        else:
            import_glb(paths[name])
            add_markers((0, 0, 0))
        png = os.path.join(out_dir, "panel_%s.png" % name)
        render_panel(name, png)
        panels.append(png)

    size = 640
    grid = np.ones((size * 2, size * 2, 4), dtype=np.float32)
    for idx, png in enumerate(panels):
        img = bpy.data.images.load(png)
        px = np.empty(size * size * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(size, size, 4)
        row, col = divmod(idx, 2)
        y0 = (1 - row) * size  # image rows start at the bottom
        grid[y0:y0 + size, col * size:(col + 1) * size] = px
    out = bpy.data.images.new("hand_tools_2x2", size * 2, size * 2, alpha=True)
    out.pixels.foreach_set(grid.ravel())
    path = os.path.join(out_dir, "hand_tools_2x2.png")
    out.filepath_raw = path
    out.file_format = "PNG"
    out.save()
    print("PREVIEW", path)


# ----------------------------------------------------------------------------- main
def main():
    opts = parse_args()
    M = mats()
    paths, summary = {}, {}
    for name in opts["only"]:
        print("== %s" % name)
        clear_scene()
        objs = BUILDERS[name](M)
        path = os.path.join(opts["out"], name + ".glb")
        export_glb(objs, path)
        st = glb_stats(path)
        print_stats(st)
        paths[name] = path
        summary[name] = {"tris": st["tris"], "materials": st["materials"],
                         "y": [round(st["min"][1], 4), round(st["max"][1], 4)],
                         "nodes": [n["name"] for n in st["nodes"]]}
    print("SUMMARY " + json.dumps(summary))
    if opts["preview"]:
        preview(paths, opts["preview"])


if __name__ == "__main__":
    main()
