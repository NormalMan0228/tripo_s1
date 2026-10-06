"""Close the holes the village camera sees in the Tripo building GLBs.

The village camera is orthographic and never rotates (scripts/controller_profile.gd
CAMERA_OFFSET), and each building keeps the yaw in building_placements.json, so every
building is only ever seen from one direction. For that direction this tool:

1. rasterises the whole GLB (all primitives) into a depth buffer at PIX metres per
   pixel by dense point sampling;
2. finds the hole pixels: where the first surface hit is the *inside* of the shell
   (a back face lying INTERIOR metres or more behind the nearest outer surface: a
   crack between roof rows, a missing gable, an open dormer), and small pockets of
   background enclosed by the building (seen straight through);
3. covers them with a grid of small quads (CELL pixels) BEHIND metres behind the
   surrounding outer surface, facing the camera. Each quad samples one texel of the
   building's own atlas, picked from the surrounding outer surface (a darker one, so
   a filled crack reads as a shaded joint and a filled window as dark glass), and
   takes the nearest outer normal, so it lights like the wall or roof around it.

The quads are appended to the building's main textured primitive, so they share its
material and draw call. Back faces of thin open sheets (windmill sails, awnings)
are left alone; building_exterior.gdshader shades those two-sided.

The original file is kept inside the patched GLB (asset.extras.hole_patch holds the
original JSON chunk, BIN length and SHA-1; the original BIN bytes are unchanged at
the start of the new BIN), so --restore rewrites the exact original bytes.

  .tools/art-venv/Scripts/python.exe tools/patch_building_holes.py [--ids 01_cafe,09_town_hall]
      [--restore] [--debug-dir DIR] [--report artifacts/holes-patch-report.json]
Then reimport: Godot --headless --path game --import
"""
import argparse
import hashlib
import io
import json
import math
import re
import struct
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT/'game'
PLACEMENTS = GAME/'maps/archipelago/building_placements.json'
PROFILE = GAME/'scripts/controller_profile.gd'
KEY = 'hole_patch'

PIX = 0.015          # metres per depth-buffer pixel
CELL = 2             # patch quad size in pixels (3 cm)
INTERIOR = 0.10      # a back face this far behind the outer surface is the inside
BEHIND = 0.03        # patch distance behind the surrounding outer surface
PICK = 6             # texel candidates within this many pixels of the nearest outer pixel
PICK_PERCENTILE = 30 # darker-than-median texel of the surroundings
BLOCK = 3            # cells sharing one texel pick, so a fill reads as one surface
# Buildings whose wide holes are window openings (open dormers): those fill with the
# darkest texel around them, so they read as dark glass rather than as wall.
DARK_OPENINGS = {'01_cafe', '16_blue_cottage'}
OPENING_RADIUS = 4   # pixels: holes at least this thick inside count as openings
DARK_PERCENTILE = 3
THROUGH_MAX_M2 = 0.8 # see-through pockets larger than this are real openings
# Patch texcoords are shifted by whole tiles (the atlas repeats, so the texel is the
# same): building_layout.gd leaves triangles with u >= PATCH_U_MIN out of collision.
PATCH_U_SHIFT = 4.0
WALL_BAND = (0.15, 1.5)  # wall slice that decides what is inside the building
DOORWAY = 0.6            # closing radius for that slice (doorways and gaps)
LOW_POCKET = 0.6         # see-through pockets below this height are left open
# Pavilions and the sail lattice are meant to be seen through.
NO_THROUGH = {'04_windmill', '08_gazebo', '14_stage', '15_picnic_shelter'}

COMP = {5126: ('<f4', 4), 5125: ('<u4', 4), 5123: ('<u2', 2), 5121: ('u1', 1)}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}


def read_glb(data: bytes):
    magic, _version, _length = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67, 'not a GLB'
    jlen, _ = struct.unpack_from('<II', data, 12)
    jbytes = data[20:20+jlen]
    off = 20+jlen
    blen, _ = struct.unpack_from('<II', data, off)
    return json.loads(jbytes), jbytes, data[off+8:off+8+blen]


def pack_glb(jbytes: bytes, bin_: bytes) -> bytes:
    j = jbytes+b' '*((4-len(jbytes) % 4) % 4)
    b = bin_+b'\0'*((4-len(bin_) % 4) % 4)
    total = 12+8+len(j)+8+len(b)
    return (struct.pack('<III', 0x46546C67, 2, total)+struct.pack('<II', len(j), 0x4E4F534A)+j
            + struct.pack('<II', len(b), 0x004E4942)+b)


def original_bytes(data: bytes) -> bytes:
    """The unpatched file: itself, or the exact original kept in a patched one."""
    g, _, bin_ = read_glb(data)
    info = g.get('asset', {}).get('extras', {}).get(KEY)
    if not info:
        return data
    out = pack_glb(info['original_json'].encode('utf-8'), bin_[:info['original_bin_length']])
    assert hashlib.sha1(out).hexdigest() == info['original_sha1'], 'restore does not match the original'
    return out


def accessor(g, bin_, i):
    a = g['accessors'][i]
    assert 'sparse' not in a
    v = g['bufferViews'][a['bufferView']]
    dt, size = COMP[a['componentType']]
    n = NCOMP[a['type']]
    assert v.get('byteStride', size*n) == size*n, 'interleaved buffers are not supported'
    start = v.get('byteOffset', 0)+a.get('byteOffset', 0)
    return np.frombuffer(bin_, dtype=dt, count=a['count']*n, offset=start).reshape(a['count'], n)


def node_matrices(g):
    mats = {}

    def local(n):
        if 'matrix' in n:
            return np.array(n['matrix'], dtype=np.float64).reshape(4, 4).T
        x, y, z, w = n.get('rotation', [0, 0, 0, 1])
        r = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                      [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                      [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        m = np.eye(4)
        m[:3, :3] = r*np.array(n.get('scale', [1, 1, 1]))
        m[:3, 3] = n.get('translation', [0, 0, 0])
        return m

    def walk(i, parent):
        m = parent@local(g['nodes'][i])
        mats[i] = m
        for c in g['nodes'][i].get('children', []):
            walk(c, m)
    for i in g['scenes'][g.get('scene', 0)]['nodes']:
        walk(i, np.eye(4))
    return mats


def camera_offset():
    text = PROFILE.read_text(encoding='utf-8')
    m = re.search(r'const CAMERA_OFFSET\s*:?=\s*Vector3\(([^)]*)\)', text)
    return np.array([float(v) for v in m.group(1).split(',')]) if m else np.array([0, 8.8, 16.5])


def albedo_luma(g, bin_, material):
    tex = g['textures'][material['pbrMetallicRoughness']['baseColorTexture']['index']]
    img = g['images'][tex['source']]
    view = g['bufferViews'][img['bufferView']]
    raw = bin_[view.get('byteOffset', 0):view.get('byteOffset', 0)+view['byteLength']]
    image = Image.open(io.BytesIO(raw)).convert('RGB')
    image = image.reduce(max(1, image.width//2048))
    a = np.asarray(image, dtype=np.float32)/255.0
    return a@np.array([.299, .587, .114], dtype=np.float32)


def gather(g, bin_):
    """All triangles in scene space plus the main textured primitive."""
    mats = node_matrices(g)
    tris, normals, uvs, kinds = [], [], [], []
    target = None
    best = -1
    for ni, m in mats.items():
        node = g['nodes'][ni]
        if 'mesh' not in node:
            continue
        for pi, prim in enumerate(g['meshes'][node['mesh']]['primitives']):
            assert prim.get('mode', 4) == 4
            material = g['materials'][prim['material']] if 'material' in prim else {}
            textured = 'baseColorTexture' in material.get('pbrMetallicRoughness', {})
            pos = accessor(g, bin_, prim['attributes']['POSITION']).astype(np.float64)
            nrm = accessor(g, bin_, prim['attributes']['NORMAL']).astype(np.float64)
            idx = accessor(g, bin_, prim['indices']).reshape(-1, 3).astype(np.int64)
            world = pos@m[:3, :3].T+m[:3, 3]
            nworld = nrm@np.linalg.inv(m[:3, :3])
            nworld /= np.linalg.norm(nworld, axis=1, keepdims=True)+1e-12
            tris.append(world[idx])
            normals.append(nworld[idx])
            if textured:
                uv = accessor(g, bin_, prim['attributes']['TEXCOORD_0']).astype(np.float64)
                uvs.append(uv[idx])
                if len(idx) > best:
                    best = len(idx)
                    target = {'node': ni, 'mesh': node['mesh'], 'primitive': pi, 'matrix': m, 'material': material,
                              'tri_start': sum(len(t) for t in tris[:-1]), 'tri_count': len(idx)}
            else:
                uvs.append(np.zeros((len(idx), 3, 2)))
            # 0: textured (one-sided look), 1: flat-colour double-sided panel (covers both ways)
            kinds.append(np.full(len(idx), 0 if textured else 1, dtype=np.int8))
    return np.concatenate(tris), np.concatenate(normals), np.concatenate(uvs), np.concatenate(kinds), target


def rasterise(tris, f, r, u):
    """Nearest hit per pixel: depth, triangle id and barycentrics."""
    x = tris@r
    y = tris@u
    z = tris@f
    x0, x1 = x.min()-4*PIX, x.max()+4*PIX
    y0, y1 = y.min()-4*PIX, y.max()+4*PIX
    w = int(math.ceil((x1-x0)/PIX))
    h = int(math.ceil((y1-y0)/PIX))
    zbuf = np.full(h*w, np.inf, dtype=np.float64)
    ztri = np.full(h*w, -1, dtype=np.int64)
    zbar = np.zeros((h*w, 2), dtype=np.float32)
    edges = np.stack([np.hypot(x[:, 1]-x[:, 0], y[:, 1]-y[:, 0]), np.hypot(x[:, 2]-x[:, 1], y[:, 2]-y[:, 1]),
                      np.hypot(x[:, 0]-x[:, 2], y[:, 0]-y[:, 2])], 1).max(1)
    steps = np.clip(np.ceil(edges/(.45*PIX)), 1, 600).astype(np.int64)
    for k in np.unique(steps):
        sel = np.nonzero(steps == k)[0]
        i, j = np.meshgrid(np.arange(k+1), np.arange(k+1), indexing='ij')
        keep = i+j <= k
        b1 = (i[keep]/k).astype(np.float64)
        b2 = (j[keep]/k).astype(np.float64)
        per = max(1, 3_000_000//len(b1))
        for c in range(0, len(sel), per):
            t = sel[c:c+per]
            px = x[t, 0:1]+(x[t, 1:2]-x[t, 0:1])*b1+(x[t, 2:3]-x[t, 0:1])*b2
            py = y[t, 0:1]+(y[t, 1:2]-y[t, 0:1])*b1+(y[t, 2:3]-y[t, 0:1])*b2
            pz = z[t, 0:1]+(z[t, 1:2]-z[t, 0:1])*b1+(z[t, 2:3]-z[t, 0:1])*b2
            ix = ((px-x0)/PIX).astype(np.int64)
            iy = ((y1-py)/PIX).astype(np.int64)
            pid = (iy*w+ix).ravel()
            depth = pz.ravel()
            tid = np.repeat(t, len(b1))
            bb1 = np.tile(b1, len(t))
            bb2 = np.tile(b2, len(t))
            order = np.lexsort((depth, pid))
            pid, depth, tid, bb1, bb2 = pid[order], depth[order], tid[order], bb1[order], bb2[order]
            first = np.ones(len(pid), dtype=bool)
            first[1:] = pid[1:] != pid[:-1]
            pid, depth, tid, bb1, bb2 = pid[first], depth[first], tid[first], bb1[first], bb2[first]
            better = depth < zbuf[pid]
            p = pid[better]
            zbuf[p] = depth[better]
            ztri[p] = tid[better]
            zbar[p, 0] = bb1[better]
            zbar[p, 1] = bb2[better]
    return zbuf.reshape(h, w), ztri.reshape(h, w), zbar.reshape(h, w, 2), (x0, y1, w, h)


_FOOTPRINT = {}


def inside_footprint(tris, points):
    """Which points (scene x, z) lie inside the building's walls: a slice of the
    walls between WALL_BAND heights, gaps up to 2*DOORWAY closed, enclosed area filled."""
    step = .03
    key = id(tris)
    if key not in _FOOTPRINT:
        _FOOTPRINT.clear()
        _FOOTPRINT[key] = _footprint(tris, step)
    inside, lo, w, d = _FOOTPRINT[key]
    ix = np.clip(((points[:, 0]-lo[0])/step).astype(int), 0, w-1)
    iz = np.clip(((points[:, 2]-lo[2])/step).astype(int), 0, d-1)
    return inside[iz, ix]


def _footprint(tris, step):
    lo = tris.reshape(-1, 3).min(0)-1.0
    hi = tris.reshape(-1, 3).max(0)+1.0
    w = int((hi[0]-lo[0])/step)+1
    d = int((hi[2]-lo[2])/step)+1
    wall = np.zeros((d, w), dtype=bool)
    ymin, ymax = tris[..., 1].min(1), tris[..., 1].max(1)
    sel = np.nonzero((ymax > WALL_BAND[0]) & (ymin < WALL_BAND[1]))[0]
    rng = np.random.default_rng(1)
    for c in range(0, len(sel), 20000):
        t = tris[sel[c:c+20000]]
        size = np.linalg.norm(t[:, 1]-t[:, 0], axis=1)+np.linalg.norm(t[:, 2]-t[:, 0], axis=1)
        n = np.clip((size/step*2).astype(int), 3, 200)
        rep = np.repeat(np.arange(len(t)), n)
        a = rng.random(len(rep))
        b = rng.random(len(rep))
        flip = a+b > 1
        a[flip], b[flip] = 1-a[flip], 1-b[flip]
        p = t[rep, 0]+(t[rep, 1]-t[rep, 0])*a[:, None]+(t[rep, 2]-t[rep, 0])*b[:, None]
        keep = (p[:, 1] > WALL_BAND[0]) & (p[:, 1] < WALL_BAND[1])
        p = p[keep]
        wall[((p[:, 2]-lo[2])/step).astype(int), ((p[:, 0]-lo[0])/step).astype(int)] = True
    grown = ndimage.distance_transform_edt(~wall)*step <= DOORWAY
    closed = ndimage.distance_transform_edt(grown)*step > DOORWAY
    closed |= wall
    inside = ndimage.binary_fill_holes(closed) & ~closed
    inside = ndimage.binary_erosion(inside, iterations=3)
    return inside, lo, w, d


def patch_building(spec, data, debug_dir=None):
    g, _jbytes, bin_ = read_glb(data)
    tris, tnorm, tuv, kinds, target = gather(g, bin_)
    assert target is not None, 'no textured primitive'
    yaw = math.radians(float(spec['yaw_degrees']))
    view = -camera_offset()
    view /= np.linalg.norm(view)
    # Building local = R_y(-yaw) * world (Godot Basis(Vector3.UP, yaw)).
    c, s = math.cos(yaw), math.sin(yaw)
    rot = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    f = rot.T@view
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    zbuf, ztri, zbar, (x0, y1, w, h) = rasterise(tris, f, r, u)
    covered = ztri >= 0
    tid = np.where(covered, ztri, 0)
    geo = np.cross(tris[:, 1]-tris[:, 0], tris[:, 2]-tris[:, 0])
    facing = (geo@f) < 0
    front = covered & (facing[tid] | (kinds[tid] == 1))
    back = covered & ~front
    t0, t1 = target['tri_start'], target['tri_start']+target['tri_count']
    tfront = front & (tid >= t0) & (tid < t1)
    _, near = ndimage.distance_transform_edt(~front, return_indices=True)
    near_depth = zbuf[near[0], near[1]]
    interior = back & (zbuf-near_depth > INTERIOR)
    through = np.zeros_like(covered)
    if spec['id'] not in NO_THROUGH:
        pocket = ndimage.binary_fill_holes(covered) & ~covered
        labels, count = ndimage.label(pocket)
        if count:
            area = ndimage.sum(pocket, labels, np.arange(1, count+1))*PIX*PIX
            small = np.concatenate([[False], area <= THROUGH_MAX_M2])
            through = small[labels]
            # Only gaps that look into the building (the ray crosses the space inside
            # the walls on its way down); a porch or the space between columns stays open.
            py, px = np.nonzero(through)
            if len(py):
                origin = (x0+(px+.5)*PIX)[:, None]*r+(y1-(py+.5)*PIX)[:, None]*u
                start = near_depth[py, px]
                end = -origin[:, 1]/f[1]
                hits = np.zeros(len(py), dtype=bool)
                for k in np.linspace(0, 1, 12):
                    t = start+(end-start)*k
                    hits |= inside_footprint(tris, origin+t[:, None]*f)
                # Near the ground a pocket is the floor between columns and steps.
                hits &= (origin+start[:, None]*f)[:, 1] > LOW_POCKET
                through[py, px] = hits
    holes = interior | through
    region = ndimage.binary_dilation(holes, iterations=1)
    # Coarse cells: any hole pixel inside marks the cell.
    gh, gw = (h+CELL-1)//CELL, (w+CELL-1)//CELL
    pad = np.zeros((gh*CELL, gw*CELL), dtype=bool)
    pad[:h, :w] = region
    cells = pad.reshape(gh, CELL, gw, CELL).any(axis=(1, 3))
    ci, cj = np.nonzero(cells)
    report = {'id': spec['id'], 'interior_px': int(interior.sum()), 'through_px': int(through.sum()),
              'hole_m2': round(float(holes.sum())*PIX*PIX, 4), 'cells': int(len(ci))}
    if debug_dir:
        dbg = np.zeros((h, w, 3), dtype=np.uint8)
        dbg[front] = (150, 150, 150)
        dbg[tfront] = (200, 200, 200)
        dbg[back] = (90, 0, 90)
        dbg[interior] = (255, 0, 255)
        dbg[through] = (255, 255, 0)
        dbg[~covered & ~through] = (0, 120, 0)
        Image.fromarray(dbg).save(Path(debug_dir)/f'holes-map-{spec["id"]}.png')
    if len(ci) == 0:
        return None, report
    # Corner depth: deepest nearby outer surface, then a little behind it.
    deep = ndimage.maximum_filter(near_depth, size=2*CELL+1)
    ca = np.clip(np.arange(gh+1)*CELL, 0, h-1)
    cb = np.clip(np.arange(gw+1)*CELL, 0, w-1)
    corner_depth = deep[np.ix_(ca, cb)]+BEHIND
    # Texel and normal per cell from the target's outer surface around it.
    _, tnear = ndimage.distance_transform_edt(~tfront, return_indices=True)
    by = np.clip((ci//BLOCK*BLOCK+BLOCK//2)*CELL+CELL//2, 0, h-1)
    bx = np.clip((cj//BLOCK*BLOCK+BLOCK//2)*CELL+CELL//2, 0, w-1)
    ny, nx = tnear[0][by, bx], tnear[1][by, bx]
    percentile = np.full(len(ci), float(PICK_PERCENTILE))
    if spec['id'] in DARK_OPENINGS:
        labels, count = ndimage.label(holes)
        if count:
            thick = ndimage.maximum(ndimage.distance_transform_edt(holes), labels, np.arange(1, count+1))
            wide = np.concatenate([[False], np.asarray(thick) >= OPENING_RADIUS])[labels]
            wide = ndimage.binary_dilation(wide, iterations=CELL*2)
            cy = np.clip(ci*CELL+CELL//2, 0, h-1)
            cx = np.clip(cj*CELL+CELL//2, 0, w-1)
            percentile[wide[cy, cx]] = DARK_PERCENTILE
    bar = zbar
    t_all = np.where(tfront, ztri, t0)
    b1, b2 = bar[..., 0], bar[..., 1]
    b0 = 1-b1-b2

    def uv_at(yy, xx):
        t = t_all[yy, xx]
        return tuv[t, 0]*b0[yy, xx][..., None]+tuv[t, 1]*b1[yy, xx][..., None]+tuv[t, 2]*b2[yy, xx][..., None]
    luma_img = albedo_luma(g, bin_, target['material'])
    lh, lw = luma_img.shape
    off = np.arange(-PICK, PICK+1)
    dy, dx = np.meshgrid(off, off, indexing='ij')
    dy, dx = dy.ravel(), dx.ravel()
    qy = np.clip(ny[:, None]+dy[None], 0, h-1)
    qx = np.clip(nx[:, None]+dx[None], 0, w-1)
    valid = tfront[qy, qx]
    quv = uv_at(qy, qx)
    lu = np.mod(quv[..., 0], 1.0)
    lv = np.mod(quv[..., 1], 1.0)
    luma = luma_img[np.clip((lv*lh).astype(int), 0, lh-1), np.clip((lu*lw).astype(int), 0, lw-1)]
    luma = np.where(valid, luma, np.nan)
    order = np.sort(np.where(np.isnan(luma), np.inf, luma), axis=1)
    valid_n = np.maximum(valid.sum(1), 1)
    goal = order[np.arange(len(ci)), np.clip((percentile/100*(valid_n-1)).astype(int), 0, luma.shape[1]-1)]
    pick = np.nanargmin(np.abs(luma-goal[:, None]), axis=1)
    uv = quv[np.arange(len(ci)), pick]
    t = t_all[ny, nx]
    nrm = (tnorm[t, 0]*b0[ny, nx][:, None]+tnorm[t, 1]*b1[ny, nx][:, None]+tnorm[t, 2]*b2[ny, nx][:, None])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)+1e-12
    # Quad corners (top-left, top-right, bottom-left, bottom-right) in scene space.
    texel = 1.0/2048

    def corner(a, b):
        d = corner_depth[a, b]
        return (x0+b*CELL*PIX)[:, None]*r+(y1-a*CELL*PIX)[:, None]*u+d[:, None]*f
    quad = [corner(ci, cj), corner(ci, cj+1), corner(ci+1, cj), corner(ci+1, cj+1)]
    uv = np.clip(np.mod(uv, 1.0), 0, 1-2*texel)+[PATCH_U_SHIFT, 0]
    quv4 = [uv, uv+[texel, 0], uv+[0, texel], uv+[texel, texel]]
    pos = np.stack(quad, 1).reshape(-1, 3)
    uvs = np.stack(quv4, 1).reshape(-1, 2)
    nrms = np.repeat(nrm, 4, axis=0)
    base = np.arange(len(ci))*4
    idx = np.stack([base, base+2, base+1, base+1, base+2, base+3], 1).reshape(-1, 3)
    tri_n = np.cross(pos[idx[:, 1]]-pos[idx[:, 0]], pos[idx[:, 2]]-pos[idx[:, 0]])
    assert ((tri_n@f) < 0).mean() > .99, 'patch quads must face the camera'
    # Into the target primitive's node space.
    m = target['matrix']
    inv = np.linalg.inv(m)
    lpos = pos@inv[:3, :3].T+inv[:3, 3]
    lnrm = nrms@m[:3, :3]
    lnrm /= np.linalg.norm(lnrm, axis=1, keepdims=True)
    report['triangles'] = int(len(idx))
    return {'target': target, 'pos': lpos, 'nrm': lnrm, 'uv': uvs, 'idx': idx}, report


def write_patched(data: bytes, patch) -> bytes:
    g, jbytes, bin_ = read_glb(data)
    target = patch['target']
    prim = g['meshes'][target['mesh']]['primitives'][target['primitive']]
    assert set(prim['attributes']) <= {'POSITION', 'NORMAL', 'TEXCOORD_0'}, prim['attributes']
    old = {k: accessor(g, bin_, prim['attributes'][k]) for k in ('POSITION', 'NORMAL', 'TEXCOORD_0')}
    old_idx = accessor(g, bin_, prim['indices']).ravel()
    n0 = len(old['POSITION'])
    pos = np.concatenate([old['POSITION'], patch['pos']]).astype('<f4')
    nrm = np.concatenate([old['NORMAL'], patch['nrm']]).astype('<f4')
    uv = np.concatenate([old['TEXCOORD_0'], patch['uv']]).astype('<f4')
    idx = np.concatenate([old_idx.astype(np.int64), patch['idx'].ravel()+n0])
    idx_type = 5123 if len(pos) < 65535 else 5125
    idx = idx.astype('<u2' if idx_type == 5123 else '<u4')
    new = dict(g)
    new['accessors'] = list(g['accessors'])
    new['bufferViews'] = list(g['bufferViews'])
    blob = bytearray(bin_)
    blob += b'\0'*((4-len(blob) % 4) % 4)

    def add(array, comp, kind, target_kind, minmax=False):
        start = len(blob)
        raw = array.tobytes()
        blob.extend(raw)
        blob.extend(b'\0'*((4-len(blob) % 4) % 4))
        new['bufferViews'].append({'buffer': 0, 'byteOffset': start, 'byteLength': len(raw), 'target': target_kind})
        acc = {'bufferView': len(new['bufferViews'])-1, 'componentType': comp, 'count': len(array), 'type': kind}
        if minmax:
            acc['min'] = [float(v) for v in array.min(0)]
            acc['max'] = [float(v) for v in array.max(0)]
        new['accessors'].append(acc)
        return len(new['accessors'])-1
    attributes = dict(prim['attributes'])
    attributes['POSITION'] = add(pos, 5126, 'VEC3', 34962, True)
    attributes['NORMAL'] = add(nrm, 5126, 'VEC3', 34962)
    attributes['TEXCOORD_0'] = add(uv, 5126, 'VEC2', 34962)
    indices = add(idx, idx_type, 'SCALAR', 34963)
    meshes = json.loads(json.dumps(g['meshes']))
    meshes[target['mesh']]['primitives'][target['primitive']]['attributes'] = attributes
    meshes[target['mesh']]['primitives'][target['primitive']]['indices'] = indices
    new['meshes'] = meshes
    new['buffers'] = [dict(g['buffers'][0], byteLength=len(blob))]
    asset = dict(g.get('asset', {}))
    extras = dict(asset.get('extras', {}))
    extras[KEY] = {'tool': 'tools/patch_building_holes.py', 'original_json': jbytes.decode('utf-8'),
                   'original_bin_length': len(bin_), 'original_sha1': hashlib.sha1(data).hexdigest(),
                   'patch_vertices': int(len(patch['pos'])), 'patch_triangles': int(len(patch['idx']))}
    asset['extras'] = extras
    new['asset'] = asset
    out = pack_glb(json.dumps(new, separators=(',', ':'), ensure_ascii=False).encode('utf-8'), bytes(blob))
    assert original_bytes(out) == data
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', default='')
    ap.add_argument('--restore', action='store_true')
    ap.add_argument('--debug-dir', default='')
    ap.add_argument('--report', default='')
    args = ap.parse_args()
    manifest = json.loads(PLACEMENTS.read_text(encoding='utf-8'))
    wanted = set(filter(None, args.ids.split(',')))
    reports = []
    for spec in manifest['buildings']:
        if wanted and spec['id'] not in wanted:
            continue
        path = GAME/spec['model'].replace('res://', '')
        current = path.read_bytes()
        source = original_bytes(current)
        if args.restore:
            if source != current:
                path.write_bytes(source)
            print(f'{spec["id"]}: restored {len(source)/1e6:.2f} MB')
            continue
        patch, report = patch_building(spec, source, args.debug_dir or None)
        out = write_patched(source, patch) if patch else source
        if out != current:
            path.write_bytes(out)
        report['size_mb'] = [round(len(source)/1e6, 2), round(len(out)/1e6, 2)]
        reports.append(report)
        print(json.dumps(report))
    if args.report:
        Path(args.report).write_text(json.dumps(reports, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
