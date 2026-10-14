"""Optimal-step non-rigid ICP (Amberg et al. 2007) for template -> scan fitting. Runs in art-venv (scipy).

Input npz: src (n,3) initial template positions, edges (m,2), tgt_v, tgt_f (target mesh), data_w (n,) data weight
(0 for eye-socket / mouth-bag vertices), lm_idx, lm_pos (hard landmarks: lid margins, lip seam, ...).
Output npz: X (n,3).
Usage: nricp.py in.npz out.npz [alphas]
"""
import sys, json
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

I = np.load(sys.argv[1]); out = sys.argv[2]
alphas = [float(a) for a in sys.argv[3].split(",")] if len(sys.argv) > 3 else [100, 50, 25, 12, 6, 3, 1.5]
src = I["src"].astype(float); E = I["edges"]; V = I["tgt_v"].astype(float); F = I["tgt_f"]
dw = I["data_w"].astype(float); li = I["lm_idx"]; lp = I["lm_pos"].astype(float)
n = len(src); m = len(E)

# dense target samples (vertices + barycentric samples per face) with face normals
fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]); area = np.linalg.norm(fn, axis=1); fn /= np.maximum(area, 1e-12)[:, None]
bary = np.array([[1/3, 1/3, 1/3], [0.6, 0.2, 0.2], [0.2, 0.6, 0.2], [0.2, 0.2, 0.6]])
S = np.concatenate([V[F[:, 0]] * b[0] + V[F[:, 1]] * b[1] + V[F[:, 2]] * b[2] for b in bary])
SN = np.concatenate([fn] * len(bary))
lab_s = np.concatenate([I["tgt_label"]] * len(bary)) if "tgt_label" in I else np.zeros(len(S), int)
lab_v = I["src_label"] if "src_label" in I else np.zeros(n, int)
trees = {k: (cKDTree(S[lab_s == k]), np.where(lab_s == k)[0]) for k in np.unique(lab_s)}

# stiffness: M (m x n) node-arc incidence, G = diag(1,1,1,gamma)
gamma = 1.0
EAR_K = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
ew = np.where((lab_v[E[:, 0]] > 0) | (lab_v[E[:, 1]] > 0), EAR_K, 1.0)
rows = np.repeat(np.arange(m), 2); cols = E.ravel(); vals = (np.tile([-1.0, 1.0], m) * np.repeat(ew, 2))
M = sp.csr_matrix((vals, (rows, cols)), shape=(m, n))
G = sp.diags([1, 1, 1, gamma])
MG = sp.kron(M, G).tocsr()                                     # (4m x 4n)

def D_of(P):
    """Sparse (n x 4n) with row i = [p_i 1] at block i."""
    r = np.repeat(np.arange(n), 4); c = (np.arange(n)[:, None] * 4 + np.arange(4)).ravel()
    v = np.c_[P, np.ones(n)].ravel()
    return sp.csr_matrix((v, (r, c)), shape=(n, 4 * n))

def normals(P):
    N = np.zeros_like(P)
    for a, b in ((0, 1), (1, 0)):
        pass
    return N

X = np.tile(np.r_[np.eye(3), np.zeros((1, 3))], (n, 1))        # (4n x 3) identity affines
D = D_of(src)
DL = D[li]
beta = float(I["beta"]) if "beta" in I else 10.0
log = []
cur = src.copy()
# vertex normals of the template (recomputed each step) from edge-adjacent faces is not available; use
# neighbour-plane normals via PCA of the 1-ring
nb = [[] for _ in range(n)]
for a, b in E:
    nb[a].append(b); nb[b].append(a)
def vnorm(P):
    N = np.zeros_like(P)
    for i in range(n):
        Q = P[nb[i]] - P[i]
        if len(Q) >= 2:
            w, v = np.linalg.eigh(Q.T @ Q); N[i] = v[:, 0]
    # orient away from the centroid of the head
    c = P.mean(0)
    flip = ((P - c) * N).sum(1) < 0
    N[flip] *= -1
    return N
for alpha in alphas:
    for it in range(3):
        Nn = vnorm(cur)
        j = np.zeros((n, 8), int)
        for k_, (tr, ids) in trees.items():
            sel = np.where(lab_v == k_)[0]
            if len(sel):
                _, jj = tr.query(cur[sel], k=8); j[sel] = ids[jj]
        best = np.full(n, -1)
        for i in range(n):
            for k in range(8):
                if np.dot(SN[j[i, k]], Nn[i]) > 0.5:
                    best[i] = j[i, k]; break
        U = np.where(best[:, None] >= 0, S[np.maximum(best, 0)], cur)
        dist = np.linalg.norm(U - cur, axis=1)
        thr = np.percentile(dist[dw > 0], 95) * 1.5 + 1e-4
        w = dw * (best >= 0) * (dist < thr)
        W = sp.diags(w)
        A = sp.vstack([alpha * MG, W @ D, beta * DL]).tocsr()
        Bm = np.vstack([np.zeros((4 * m, 3)), w[:, None] * U, beta * lp])
        AtA = (A.T @ A).tocsc(); AtB = A.T @ Bm
        X = np.column_stack([spsolve(AtA, AtB[:, k]) for k in range(3)])
        new = D @ X
        delta = float(np.linalg.norm(new - cur, axis=1).max()); cur = new
        log.append(dict(alpha=alpha, it=it, delta=delta, mean_dist=float(dist[w > 0].mean()), used=int((w > 0).sum())))
        print(log[-1], flush=True)
np.savez(out, X=cur)
json.dump(log, open(out.replace(".npz", "_log.json"), "w"))
