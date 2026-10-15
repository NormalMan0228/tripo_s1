"""Clean a Tripo P2 monster mesh before rigging (no reshaping of the body).

  blender -b -P tools/body_gen/mesh_cleanup.py -- in.fbx out.fbx [options] [--report out.json]

Options (sizes are fractions of the model height H):
  --weld 0.0006       weld cracks: merge only open-boundary vertices closer than this
  --fill 8            fill holes whose rim has at most this many edges (bigger openings
                      such as mouths, sleeves and rivet domes are left alone)
  --drop 9            delete loose islands with at most this many vertices (debris sheets)
  --split-nm 40       cut edges shared by 3+ faces and delete the small pieces (<= N verts)
                      that come loose (finger spurs, fins); the cut rims are then welded/filled
  --drop-island V:F   delete islands with exactly V verts and F faces (e.g. a bad box shell)
  --box x0,y0,z0,x1,y1,z1[,bevel]
                      add a closed bevelled box (coordinates as fractions of H from the
                      bounding-box minimum), used to replace a broken shell
New faces get the winding of their neighbours. Writes a JSON report with before/after
counts (vertices, faces, islands, open edges, edges with 3+ faces).

clean_bmesh() is also used by build_game_monster.py to repeat the same cleanup on the
textured, rigged mesh (same vertices as the P2 mesh; skin weights are kept).
"""
import json
import shlex
import sys

import bmesh
import bpy
from mathutils import Vector


def parse(args):
    """Option list (CLI style) -> dict."""
    if isinstance(args, str):
        args = shlex.split(args)

    def opt(name, default=None, cast=float):
        if name in args:
            return cast(args[args.index(name) + 1])
        return default

    return {
        'drop_exact': [tuple(int(x) for x in args[i + 1].split(':')) for i, a in enumerate(args) if a == '--drop-island'],
        'drop': opt('--drop', 0, int),
        'weld': opt('--weld', 0.0),
        'split_nm': opt('--split-nm', 0, int),
        'fill': opt('--fill', 0, int),
        'box': opt('--box', None, str),
    }


def islands(bm):
    seen, out = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, comp = [v], []
        seen.add(v.index)
        while stack:
            a = stack.pop()
            comp.append(a)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index)
                    stack.append(b)
        out.append(comp)
    return out


def stats(bm):
    bm.verts.index_update()
    return {
        "vertices": len(bm.verts),
        "faces": len(bm.faces),
        "islands": len(islands(bm)),
        "open_edges": sum(1 for e in bm.edges if len(e.link_faces) == 1),
        "nonmanifold_edges": sum(1 for e in bm.edges if len(e.link_faces) > 2),
        "loose_edges": sum(1 for e in bm.edges if not e.link_faces),
    }


def match_winding(bm, faces):
    """Flip new faces whose winding disagrees with the neighbour across a shared edge."""
    flip = []
    for f in faces:
        if not f.is_valid:
            continue
        agree = disagree = 0
        for l in f.loops:
            for g in l.edge.link_faces:
                if g is f or g in faces:
                    continue
                gl = next(x for x in g.loops if x.edge is l.edge)
                if gl.vert is l.vert:
                    disagree += 1
                else:
                    agree += 1
        if disagree > agree:
            flip.append(f)
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
    return len(flip)


def clean_bmesh(bm, o, H, lo, mw):
    """Run the cleanup steps on bm (object-space mesh with world matrix mw). o: parse() dict."""
    steps = []
    # 1. delete named bad islands (exact vert/face counts) and small debris islands
    gone = []
    for comp in islands(bm):
        faces = {f for v in comp for f in v.link_faces}
        if (len(comp), len(faces)) in o['drop_exact'] or len(comp) <= o['drop']:
            gone.append((len(comp), len(faces)))
            bmesh.ops.delete(bm, geom=comp, context="VERTS")
    steps.append({"dropped_islands": gone})

    # 2. weld cracks: merge open-boundary vertices only (a global weld creates new fins)
    if o['weld']:
        bd = list({v for e in bm.edges if len(e.link_faces) == 1 for v in e.verts})
        n0 = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bd, dist=o['weld'] * H)
        steps.append({"weld_dist": o['weld'] * H, "verts_merged": n0 - len(bm.verts)})

    # 3. cut non-manifold edges (after the weld, so the cut rims stay open) and delete the small pieces that come loose
    if o['split_nm']:
        nm = [e for e in bm.edges if len(e.link_faces) > 2]
        # the split duplicates vertices, so track the cut by position, not by vertex
        key = lambda c: (round(c.x / H, 5), round(c.y / H, 5), round(c.z / H, 5))
        touched = {key(v.co) for e in nm for v in e.verts}
        if nm:
            bmesh.ops.split_edges(bm, edges=nm)
        bm.verts.index_update()
        loose = []
        for comp in islands(bm):
            if len(comp) <= o['split_nm'] and any(key(v.co) in touched for v in comp):
                loose.append(len(comp))
                bmesh.ops.delete(bm, geom=comp, context="VERTS")
        # re-join the cut where both sides are big pieces (e.g. a leg cut at the knee); only the
        # small loose fins are meant to go
        bm.verts.index_update()
        island_of = {}
        for i, comp in enumerate(islands(bm)):
            for v in comp:
                island_of[v] = i
        groups = {}
        for v in bm.verts:
            k = key(v.co)
            if k in touched:
                groups.setdefault(k, []).append(v)
        rim = [v for g in groups.values() if len({island_of[v] for v in g}) > 1 for v in g]
        n0 = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=rim, dist=1e-6 * H)
        steps.append({"nm_edges_cut": len(nm), "loose_pieces_deleted": loose,
                      "cut_rejoined_verts": n0 - len(bm.verts)})

    # 4. fill small holes, then give the new faces their neighbours' winding
    if o['fill']:
        bd = [e for e in bm.edges if len(e.link_faces) == 1]
        res = bmesh.ops.holes_fill(bm, edges=bd, sides=o['fill'])
        new = res["faces"]
        flipped = match_winding(bm, set(new))
        steps.append({"holes_filled": len(new), "flipped": flipped})

    # 5. replacement box
    if o['box']:
        vals = [float(x) for x in o['box'].split(",")]
        x0, y0, z0, x1, y1, z1 = vals[:6]
        bev = vals[6] if len(vals) > 6 else 0.0
        a = lo + Vector((x0, y0, z0)) * H
        b = lo + Vector((x1, y1, z1)) * H
        inv = mw.inverted()
        res = bmesh.ops.create_cube(bm, size=1.0)
        vs = res["verts"]
        for v in vs:
            w = Vector((a.x if v.co.x < 0 else b.x, a.y if v.co.y < 0 else b.y, a.z if v.co.z < 0 else b.z))
            v.co = inv @ w
        # corners keep the cube's order (min side -> a, max side -> b), so its outward winding stays valid
        if bev:
            edges = list({e for v in vs for e in v.link_edges})
            bmesh.ops.bevel(bm, geom=vs + edges, offset=bev * H, segments=2, affect="EDGES", profile=0.5)
        steps.append({"box": [round(x, 4) for x in vals]})
    return steps


def clean_object(obj, o):
    """Clean a mesh object in place; returns the report dict (before, steps, after)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    mw = obj.matrix_world.copy()
    co = [mw @ v.co for v in bm.verts]
    lo = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
    hi = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
    H = max(hi - lo)  # Tripo exports fit the largest side to ~1
    report = {"before": stats(bm)}
    report["steps"] = clean_bmesh(bm, o, H, lo, mw)
    report["after"] = stats(bm)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return report


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:]
    src, dst = argv[0], argv[1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if len(meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for o in meshes:
            o.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.join()
    obj = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
    report = {"source": src}
    report.update(clean_object(obj, parse(argv[2:])))
    bpy.ops.export_scene.fbx(filepath=dst, use_selection=False, add_leaf_bones=False, bake_anim=False)
    if "--report" in argv:
        json.dump(report, open(argv[argv.index("--report") + 1], "w", encoding="utf-8"), indent=1)
    print("CLEAN", json.dumps({"before": report["before"], "after": report["after"], "steps": report["steps"]}))
