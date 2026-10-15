"""Grip estimate for equipable models, outside Godot (same rule as EquipSockets.estimate_grip in
game/scripts/equip_sockets.gd): the longest bounding-box axis is the handle line. The handle end is
  1. the end nearer a part named like a handle (handle, grip, shaft, hilt, 손잡이, 자루) when named parts
     are given (crafted items are assembled from named parts);
  2. else the end holding the model's origin, when the origin lies in an end zone (modelled standing
     on the handle);
  3. else the end opposite a tip (one end narrowing to a point: its last 3 % spreads under TIP of its
     last 20 %: a spear point, a rod tip);
  4. else the end whose cross-section spreads less (first/last 20 % of the length).
The grip sits 12 % of the length in from the handle end. Prints a record in the equip_sockets.json format.

  python tools/equip_grip_estimate.py game/assets/authored_axe_v1.glb [more.glb ...]
  python tools/equip_grip_estimate.py --selftest
"""
import json
import struct
import sys

GRIP_IN = 0.12
END = 0.2
TIP_END = 0.03
TIP = 0.3
HANDLE_WORDS = ("handle", "grip", "shaft", "hilt", "stick", "pole", "손잡이", "자루")
COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def node_matrix(node):
    if "matrix" in node:
        m = node["matrix"]  # column-major
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    t = node.get("translation", [0, 0, 0])
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[r[0][0] * s[0], r[0][1] * s[1], r[0][2] * s[2], t[0]],
            [r[1][0] * s[0], r[1][1] * s[1], r[1][2] * s[2], t[1]],
            [r[2][0] * s[0], r[2][1] * s[1], r[2][2] * s[2], t[2]],
            [0, 0, 0, 1]]


def glb_points(path):
    data = open(path, "rb").read()
    length = struct.unpack("<I", data[12:16])[0]
    doc = json.loads(data[20:20 + length])
    blob_at = 20 + length
    blob = data[blob_at + 8:] if len(data) > blob_at else b""
    points = []

    def accessor(index):
        acc = doc["accessors"][index]
        view = doc["bufferViews"][acc["bufferView"]]
        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        n = COMPONENTS[acc["type"]]
        stride = view.get("byteStride", 4 * n)
        return [struct.unpack_from("<%df" % n, blob, start + i * stride) for i in range(acc["count"])]

    def walk(index, parent):
        node = doc["nodes"][index]
        world = mat_mul(parent, node_matrix(node))
        if "mesh" in node:
            for prim in doc["meshes"][node["mesh"]]["primitives"]:
                for v in accessor(prim["attributes"]["POSITION"]):
                    points.append(tuple(sum(world[r][c] * (v[c] if c < 3 else 1.0) for c in range(4)) for r in range(3)))
        for child in node.get("children", []):
            walk(child, world)

    identity = [[1 if i == j else 0 for j in range(4)] for i in range(4)]
    scene = doc["scenes"][doc.get("scene", 0)]
    for root in scene["nodes"]:
        walk(root, identity)
    return points


def spread_of(points, axis, low, length, lo, hi):
    group = [p for p in points if lo <= (p[axis] - low[axis]) / length <= hi]
    if not group:
        return 0.0, None
    c = [sum(p[i] for p in group) / len(group) for i in range(3)]
    return max((sum((p[i] - c[i]) ** 2 for i in range(3) if i != axis)) ** 0.5 for p in group), c


def estimate(points, handle_points=None, use_origin=True):
    """points: every vertex of the item; handle_points: vertices of parts named like a handle, if any."""
    if not points:
        return {}
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    size = [high[i] - low[i] for i in range(3)]
    axis = max(range(3), key=lambda i: size[i])
    length = size[axis]
    if length < 0.001:
        return {}
    ends = [[], []]
    for p in points:
        t = (p[axis] - low[axis]) / length
        if t < END:
            ends[0].append(p)
        elif t > 1 - END:
            ends[1].append(p)
    centre, spread = [], []
    for group in ends:
        c = [sum(p[i] for p in group) / max(1, len(group)) for i in range(3)]
        centre.append(c)
        spread.append(max((sum((p[i] - c[i]) ** 2 for i in range(3) if i != axis)) ** 0.5 for p in group) if group else 0.0)
    rule = "thinner"
    handle = 0 if spread[0] <= spread[1] else 1
    tips = [spread_of(points, axis, low, length, 0.0, TIP_END)[0] < TIP * spread[0],
            spread_of(points, axis, low, length, 1 - TIP_END, 1.0)[0] < TIP * spread[1]]
    if tips[0] != tips[1]:
        handle = 1 if tips[0] else 0
        rule = "tip"
    # The model's origin inside one end zone: that end is its base (tools are modelled standing on
    # their handle; a rod's butt below the reel).
    origin_t = (0.0 - low[axis]) / length
    if not use_origin:
        pass
    elif origin_t <= END:
        handle, rule = 0, "origin"
    elif origin_t >= 1 - END:
        handle, rule = 1, "origin"
    if handle_points:
        mid = sum(p[axis] for p in handle_points) / len(handle_points)
        handle = 0 if mid - low[axis] < length * 0.5 else 1
        rule = "named"
    grip = list(centre[handle])
    grip[axis] = low[axis] + length * (GRIP_IN if handle == 0 else 1 - GRIP_IN)
    return {"hold": "hand_r", "stow": "back", "grip": [round(g, 3) for g in grip], "axis": "xyz"[axis],
            "handle_end": "low" if handle == 0 else "high", "rule": rule, "length": round(length, 3), "radius": round(spread[handle], 3),
            "estimated": True}


def box(points, centre, half, steps=3):
    for i in range(steps + 1):
        for j in range(steps + 1):
            for k in range(steps + 1):
                points.append((centre[0] + half[0] * (2 * i / steps - 1), centre[1] + half[1] * (2 * j / steps - 1), centre[2] + half[2] * (2 * k / steps - 1)))


def selftest():
    failures = 0
    # A hammer standing on +Y: thin handle 0..0.8, a wide head at the top.
    hammer = []
    box(hammer, (0, 0.4, 0), (0.02, 0.4, 0.02))
    box(hammer, (0, 0.85, 0), (0.15, 0.06, 0.05))
    r = estimate(hammer, use_origin=False)
    ok = r["axis"] == "y" and r["handle_end"] == "low" and abs(r["grip"][1] - 0.12 * 0.91) < 0.03 and r["radius"] < 0.04
    print(("PASS" if ok else "FAIL"), "hammer up +Y:", r)
    failures += not ok
    # The same hammer lying along -X (head at low x): the handle is the high end.
    flipped = [(-p[1], p[0], p[2]) for p in hammer]
    r = estimate(flipped, use_origin=False)
    ok = r["axis"] == "x" and r["handle_end"] == "high" and r["grip"][0] > -0.2
    print(("PASS" if ok else "FAIL"), "hammer along -X:", r)
    failures += not ok
    # A plain rod: either end is fine, the radius stays small.
    rod = []
    box(rod, (0, 0, 0.75), (0.015, 0.015, 0.75))
    r = estimate(rod, use_origin=False)
    ok = r["axis"] == "z" and r["radius"] < 0.03
    print(("PASS" if ok else "FAIL"), "rod along Z:", r)
    failures += not ok
    # A spear: a thin shaft, a point at the top that is wider below its tip (the tip rule picks the butt).
    spear = []
    box(spear, (0, 0.6, 0), (0.02, 0.6, 0.02))
    for k in range(6):
        w = 0.06 * (1 - k / 6)
        box(spear, (0, 1.22 + k * 0.03, 0), (w, 0.015, 0.01), 2)
    box(spear, (0, 1.42, 0), (0.002, 0.005, 0.002), 1)
    r = estimate(spear, use_origin=False)
    ok = r["handle_end"] == "low"
    print(("PASS" if ok else "FAIL"), "spear point up:", r)
    failures += not ok
    # Named parts win over shape: the 'handle' part at the top.
    named = [p for p in hammer if p[1] > 0.75]
    r = estimate(hammer, named)
    ok = r["handle_end"] == "high" and r["rule"] == "named"
    print(("PASS" if ok else "FAIL"), "named handle part:", r)
    failures += not ok
    # A rod with a reel near the butt, modelled standing on the butt: the origin cue picks the butt.
    reel_rod = []
    box(reel_rod, (0, 0.9, 0), (0.012, 0.9, 0.012))
    box(reel_rod, (0.06, 0.15, 0), (0.05, 0.04, 0.03))
    r = estimate(reel_rod)
    ok = r["handle_end"] == "low" and r["rule"] == "origin"
    print(("PASS" if ok else "FAIL"), "rod with a reel, origin at the butt:", r)
    failures += not ok
    print("GRIP_ESTIMATE_SELFTEST", "FAIL" if failures else "PASS")
    return failures


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(1 if selftest() else 0)
    for path in sys.argv[1:]:
        print(path, json.dumps(estimate(glb_points(path))))
