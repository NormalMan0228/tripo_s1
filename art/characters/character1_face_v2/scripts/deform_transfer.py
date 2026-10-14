"""Deformation transfer (Sumner & Popovic 2004, Poisson form) between meshes with identical topology.

For every source triangle j: S_j = V~_j V_j^-1 (3x3, with the normal as 4th vertex). Target deformed edges are
asked to equal S_j applied to the target rest edges; least squares over all triangles + anchors (vertices the
source key does not move stay fixed). One sparse factorisation is reused for every key and coordinate.
Usage: deform_transfer.py in.npz out.npz
"""
import sys
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

d = np.load(sys.argv[1], allow_pickle=True)
T = d["tris"]; S0 = d["src_base"]; SK = d["src_keys"]; X0 = d["tgt_base"]; names = d["names"]
n = len(X0); m = len(T)


def frames(P):
    v1, v2, v3 = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    e1, e2 = v2 - v1, v3 - v1
    nrm = np.cross(e1, e2); nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-12)[:, None] ** 0.5 * np.maximum(np.linalg.norm(nrm, axis=1), 1e-12)[:, None] ** 0.5
    nrm = np.cross(e1, e2); ln = np.linalg.norm(nrm, axis=1); nrm = nrm / np.sqrt(np.maximum(ln, 1e-18))[:, None]
    return np.stack([e1, e2, nrm], axis=2)        # (m,3,3) columns e1, e2, n/sqrt|n|


Vs = frames(S0); Vs_inv = np.linalg.inv(Vs)
Wt = frames(X0)
area = 0.5 * np.linalg.norm(np.cross(X0[T[:, 1]] - X0[T[:, 0]], X0[T[:, 2]] - X0[T[:, 0]]), axis=1)
wa = np.sqrt(area / area.mean())
# edge operator: rows (e1, e2) per triangle
r = np.repeat(np.arange(2 * m), 2)
c = np.stack([T[:, 1], T[:, 0], T[:, 2], T[:, 0]], 1).ravel()
v = np.tile([1.0, -1.0], 2 * m) * np.repeat(np.repeat(wa, 2), 2)
A = sp.csr_matrix((v, (r, c)), shape=(2 * m, n))
out = np.zeros_like(SK)
ANCH_W = 50.0
for k in range(len(SK)):
    disp_src = np.linalg.norm(SK[k] - S0, axis=1)
    anchor = disp_src < max(1e-7, disp_src.max() * 1e-4)
    Vd = frames(SK[k])
    S = Vd @ Vs_inv                                # (m,3,3)
    tgt_e = S @ Wt[:, :, :2]                       # desired deformed target edges (m,3,2)
    b = np.zeros((2 * m, 3))
    b[0::2] = tgt_e[:, :, 0] * wa[:, None]; b[1::2] = tgt_e[:, :, 1] * wa[:, None]
    ai = np.where(anchor)[0]
    Aa = sp.csr_matrix((np.full(len(ai), ANCH_W), (np.arange(len(ai)), ai)), shape=(len(ai), n))
    M = sp.vstack([A, Aa]).tocsc()
    lu = splu((M.T @ M + 1e-9 * sp.identity(n)).tocsc())
    rhs = M.T @ np.vstack([b, ANCH_W * X0[ai]])
    out[k] = np.column_stack([lu.solve(rhs[:, j]) for j in range(3)])
    if k % 10 == 0:
        print(k, str(names[k]), "anchors", int(anchor.sum()), "max disp", round(float(np.linalg.norm(out[k] - X0, axis=1).max()), 4), flush=True)
np.savez(sys.argv[2], keys=out, names=names)
print("DONE", len(SK))
