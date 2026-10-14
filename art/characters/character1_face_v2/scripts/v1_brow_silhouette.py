import bpy, sys, os, json, numpy as np
sys.path.insert(0, r"C:\lsm26\triphthonS1\art\characters\character1_face_v1\scripts")
from face_common import EYE_C, EYE_R
out = {}
for side in ("L", "R"):
    ob = bpy.data.objects[f"Brow.{side}"]
    P = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    c = np.array(EYE_C[side]); sx = 1 if side == "L" else -1
    P = P[P[:, 1] < c[1]]
    u = sx * (P[:, 0] - c[0])
    U = np.linspace(np.percentile(u, 1), np.percentile(u, 99), 60); hw = (U[1] - U[0]) * 2
    lo = np.array([np.percentile(P[np.abs(u - g) < hw, 2], 4) for g in U]); hi = np.array([np.percentile(P[np.abs(u - g) < hw, 2], 96) for g in U])
    k = np.ones(5) / 5
    lo = np.convolve(np.pad(lo, 2, mode="edge"), k, "valid"); hi = np.convolve(np.pad(hi, 2, mode="edge"), k, "valid")
    mid, half = (lo + hi) / 2, (hi - lo) / 2 * 1.1
    out[side] = np.c_[U / EYE_R, (mid - half - c[2]) / EYE_R, (mid + half - c[2]) / EYE_R].tolist()
out["rgb"] = [0.325, 0.208, 0.149]
json.dump(out, open(os.path.abspath(sys.argv[sys.argv.index("--")+1]), "w"))
print("BROWS", len(out["L"]), np.round(np.array(out["L"])[[0, 30, -1]], 3).tolist())
