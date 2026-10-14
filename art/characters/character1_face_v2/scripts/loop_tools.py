"""Quad edge-loop helpers (bmesh)."""
import bmesh
import numpy as np


def next_edge_in_loop(e, v):
    """Continue an edge loop through vertex v (valence 4): the edge sharing no face with e."""
    if len(v.link_edges) != 4:
        return None
    fe = set(f for f in e.link_faces)
    for e2 in v.link_edges:
        if e2 is e:
            continue
        if not (set(e2.link_faces) & fe):
            return e2
    return None


def walk_loop(bm, e0):
    """Closed edge loop through edge e0, as ordered vertex indices (None if it does not close)."""
    verts = [e0.verts[0].index]
    e, v = e0, e0.verts[1]
    for _ in range(5000):
        if v.index == verts[0]:
            return verts
        verts.append(v.index)
        e2 = next_edge_in_loop(e, v)
        if e2 is None:
            return None
        v = e2.other_vert(v); e = e2
    return None


def ring_around(bm, co, center, axis_idx=(0, 2), max_r=0.05, min_n=8):
    """All closed edge loops that encircle `center` in the given projection plane, sorted by mean radius."""
    c2 = np.array(center)[list(axis_idx)]
    found, seen = [], set()
    for e in bm.edges:
        m = (co[e.verts[0].index] + co[e.verts[1].index]) / 2
        if np.linalg.norm(m[list(axis_idx)] - c2) > max_r:
            continue
        key = frozenset((e.verts[0].index, e.verts[1].index))
        if key in seen:
            continue
        lp = walk_loop(bm, e)
        if not lp or len(lp) < min_n:
            continue
        for a, b in zip(lp, lp[1:] + lp[:1]):
            seen.add(frozenset((a, b)))
        P = co[lp][:, list(axis_idx)] - c2
        ang = np.unwrap(np.arctan2(P[:, 1], P[:, 0]))
        winding = abs(ang[-1] - ang[0] + (np.arctan2(P[0, 1], P[0, 0]) - np.arctan2(P[-1, 1], P[-1, 0]) + np.pi) % (2 * np.pi) - np.pi)
        if winding > 5.5:          # encircles the centre (~2*pi)
            found.append((float(np.linalg.norm(P, axis=1).mean()), lp))
    found.sort(key=lambda t: t[0])
    return found
