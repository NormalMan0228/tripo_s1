"""Similarity ICP (rotation, translation, uniform scale) of a source cloud onto a target cloud, point-to-plane-free robust
point-to-point with trimmed correspondences.  Usage: python icp_similarity.py <src.npy> <dst.npy> <out.json>"""
import sys, json, numpy as np
from scipy.spatial import cKDTree
S = np.load(sys.argv[1]).astype(float); D = np.load(sys.argv[2]).astype(float)
rng = np.random.default_rng(0)
S = S[rng.choice(len(S), min(40000, len(S)), replace=False)]
tree = cKDTree(D)
R, t, s = np.eye(3), np.zeros(3), 1.0
for it in range(80):
    X = s * S @ R.T + t
    d, j = tree.query(X); keep = d < np.percentile(d, 85)
    A, B = S[keep], D[j[keep]]
    ca, cb = A.mean(0), B.mean(0); A0, B0 = A - ca, B - cb
    U, sig, Vt = np.linalg.svd(A0.T @ B0); Dg = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ Dg @ U.T; s = float((sig * np.diag(Dg)).sum() / (A0 ** 2).sum()); t = cb - s * R @ ca
X = s * S @ R.T + t; d, _ = tree.query(X)
M = np.eye(4); M[:3, :3] = s * R; M[:3, 3] = t
out = {"matrix": M.tolist(), "scale": s, "rot_deg": float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))),
       "translation": t.tolist(), "residual_mm": {"median": float(np.median(d) * 1000), "p90": float(np.percentile(d, 90) * 1000)}}
json.dump(out, open(sys.argv[3], "w"), indent=1); print("ICP", json.dumps({k: out[k] for k in out if k != "matrix"}))
