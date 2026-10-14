import bpy, json, numpy as np
w = bpy.data.objects["WrapHead"]; me = w.data; kb = me.shape_keys.key_blocks
F = json.load(open(bpy.path.abspath("//target_features.json"))); C = json.loads(w["vertex_classes"]); sock = set(C["socket"])
for key in ("Basis", "eyeBlinkLeft_50", "eyeBlinkLeft"):
    X = np.array([v.co[:] for v in kb[key].data]); c = np.array(F["eye_L"]["center"]); R = F["eye_L"]["radius"]
    inv = tot = inv_s = 0
    for p in me.polygons:
        vs = list(p.vertices); P = X[vs]; cen = P.mean(0)
        if np.linalg.norm(cen - c) > R * 1.5 or cen[1] > c[1]: continue
        nrm = np.cross(P[1] - P[0], P[2] - P[0])
        out = np.dot(nrm, cen - c) > 0
        if all(v in sock for v in vs):
            inv_s += (not out)
            continue
        tot += 1; inv += (not out)
    print(key, "outer-skin faces near eye", tot, "inverted", inv, "| socket faces facing outward", inv_s)
