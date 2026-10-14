"""Symmetry plane of a head point cloud by reflective ICP (art-venv python, scipy).
Finds rigid (R,t) with R S p + t ~ p (S = reflection x->-x); R S is a reflection about the plane n.x = d.
Writes a 4x4 alignment matrix that maps the plane to x = 0 (and keeps the face toward -Y, up +Z).
Usage: python sym_plane.py <points.npy> <out.json>"""
import sys, json, numpy as np
from scipy.spatial import cKDTree
P = np.load(sys.argv[1]).astype(float)
rng = np.random.default_rng(0)
Q = P[rng.choice(len(P), min(60000, len(P)), replace=False)]
tree = cKDTree(Q)
S = np.diag([-1.0, 1, 1])
R, t = np.eye(3), np.zeros(3)
for it in range(60):
    X = (Q @ S.T) @ R.T + t
    d, j = tree.query(X)
    keep = d < np.percentile(d, 90)
    A, B = (Q @ S.T)[keep], Q[j[keep]]
    ca, cb = A.mean(0), B.mean(0)
    U, s, Vt = np.linalg.svd((A - ca).T @ (B - cb))
    D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ D @ U.T; t = cb - R @ ca
G = R @ S
w, V = np.linalg.eig(G)
n = np.real(V[:, np.argmin(np.real(w))]); n /= np.linalg.norm(n)
if n[0] < 0: n = -n
dd = float(n @ t) / 2.0
# rotation taking n to +X with minimal twist
x = np.array([1.0, 0, 0]); v = np.cross(n, x); s_ = np.linalg.norm(v); c_ = n @ x
K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
Rot = np.eye(3) + K + K @ K * ((1 - c_) / (s_ ** 2)) if s_ > 1e-9 else np.eye(3)
T = np.eye(4); T[:3, :3] = Rot; T[:3, 3] = -Rot @ (n * dd)
Pa = P @ Rot.T + T[:3, 3]
dm, _ = cKDTree(Pa).query(Pa[rng.choice(len(Pa), 30000, replace=False)] * [-1, 1, 1])
out = {"normal": n.tolist(), "offset": dd, "angle_deg": float(np.degrees(np.arccos(min(1, c_)))), "matrix": T.tolist(),
       "mirror_residual_mm": {"median": float(np.median(dm) * 1000), "p95": float(np.percentile(dm, 95) * 1000), "max": float(dm.max() * 1000)}}
json.dump(out, open(sys.argv[2], "w"), indent=1)
print("SYM", json.dumps({k: out[k] for k in ("normal", "offset", "angle_deg", "mirror_residual_mm")}))
