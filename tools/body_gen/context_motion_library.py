"""Retarget Tripo motion to existing GLBs without re-exporting their mesh/skin.

Preserves original buffers, materials, skeleton names and existing animation.
World-space rest alignment handles Mixamo, game bones and the authored NPC rig.
"""
import argparse
import copy
import json
import math
import struct
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
NAMES = {"greet_01": "greet", "standing_relax": "relax", "box_01": "punch",
         "lift_heavy": "lift", "hit_to_body_01": "hurt"}
LOOPS = {"relax", "look_around", "fold_arms", "wait", "swagger", "warm_up"}
GAME = {"Hips": "Hip", "Spine": "Waist", "Spine1": "Spine01", "Spine2": "Spine02",
        "Neck": "NeckTwist01", "Head": "Head"}
CAST = {"Hips": "Hips", "Spine": "Spine", "Spine2": "Chest", "Neck": "Neck", "Head": "Head"}
NEXT = {}
for side, short, suffix in [("Left", "L", ".L"), ("Right", "R", ".R")]:
    for source, game, cast in [("Shoulder", "Clavicle", "Shoulder"), ("Arm", "Upperarm", "UpperArm"),
        ("ForeArm", "Forearm", "Forearm"), ("Hand", "Hand", "Hand"), ("UpLeg", "Thigh", "Thigh"),
        ("Leg", "Calf", "Calf"), ("Foot", "Foot", "Foot"), ("ToeBase", "ToeBase", "Toe")]:
        GAME[side + source] = short + "_" + game
        CAST[side + source] = cast + suffix
    for a, b in [("Shoulder", "Arm"), ("Arm", "ForeArm"), ("ForeArm", "Hand"),
                 ("UpLeg", "Leg"), ("Leg", "Foot"), ("Foot", "ToeBase")]:
        NEXT[side + a] = side + b


def read(path):
    raw = path.read_bytes()
    assert raw[:4] == b"glTF" and struct.unpack_from("<I", raw, 8)[0] == len(raw)
    count = struct.unpack_from("<I", raw, 12)[0]
    doc = json.loads(raw[20:20 + count])
    position = 20 + count
    blob = b""
    while position < len(raw):
        size, kind = struct.unpack_from("<I4s", raw, position)
        if kind == b"BIN\0":
            blob = raw[position + 8:position + 8 + size]
        position += 8 + size
    return doc, bytearray(blob)


def write(path, doc, blob):
    doc["buffers"][0]["byteLength"] = len(blob)
    body = json.dumps(doc, ensure_ascii=True, separators=(",", ":")).encode()
    body += b" " * (-len(body) % 4)
    blob += b"\0" * (-len(blob) % 4)
    data = struct.pack("<4sII", b"glTF", 2, 28 + len(body) + len(blob))
    data += struct.pack("<I4s", len(body), b"JSON") + body
    data += struct.pack("<I4s", len(blob), b"BIN\0") + blob
    temp = path.with_suffix(".glb.tmp")
    temp.write_bytes(data)
    temp.replace(path)


def values(doc, blob, index):
    accessor = doc["accessors"][index]
    assert "sparse" not in accessor
    view = doc["bufferViews"][accessor["bufferView"]]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[accessor["type"]]
    dtype = np.dtype({5126: "<f4", 5125: "<u4", 5123: "<u2", 5121: "u1"}[accessor["componentType"]])
    offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    stride = view.get("byteStride", width * dtype.itemsize)
    return np.ndarray((accessor["count"], width), dtype, blob, offset,
                      strides=(stride, dtype.itemsize)).astype(float).copy()


def add_values(doc, blob, data, kind):
    data = np.asarray(data, dtype="<f4")
    assert np.isfinite(data).all()
    blob += b"\0" * (-len(blob) % 4)
    offset = len(blob)
    blob += data.tobytes()
    views = doc.setdefault("bufferViews", [])
    index = len(views)
    views.append({"buffer": 0, "byteOffset": offset, "byteLength": data.nbytes})
    accessors = doc.setdefault("accessors", [])
    result = len(accessors)
    item = {"bufferView": index, "componentType": 5126, "count": len(data), "type": kind}
    if kind == "SCALAR":
        item.update(min=[float(data.min())], max=[float(data.max())])
    accessors.append(item)
    return result


def base_name(name):
    return name.split(":")[-1].replace("mixamorig_", "")


class Rig:
    def __init__(self, doc):
        self.doc = doc
        self.nodes = doc["nodes"]
        self.parent = {c: i for i, n in enumerate(self.nodes) for c in n.get("children", [])}
        self.by_name = {n.get("name", ""): i for i, n in enumerate(self.nodes)}
        self.base = {base_name(n.get("name", "")): i for i, n in enumerate(self.nodes)}
        self.order = []
        def walk(index):
            self.order.append(index)
            for child in self.nodes[index].get("children", []):
                walk(child)
        for i in range(len(self.nodes)):
            if i not in self.parent:
                walk(i)
        self.trs = []
        self.local = []
        for n in self.nodes:
            if "matrix" in n:
                m = np.array(n["matrix"]).reshape(4, 4).T
                scale = np.linalg.norm(m[:3, :3], axis=0)
                q = Rotation.from_matrix(m[:3, :3] / scale).as_quat()
                translation = m[:3, 3]
            else:
                translation = np.array(n.get("translation", [0, 0, 0]), dtype=float)
                q = np.array(n.get("rotation", [0, 0, 0, 1]), dtype=float)
                scale = np.array(n.get("scale", [1, 1, 1]), dtype=float)
                m = np.eye(4)
                m[:3, :3] = Rotation.from_quat(q).as_matrix() * scale
                m[:3, 3] = translation
            self.trs.append((translation, q, scale))
            self.local.append(m)
        self.world = {}
        for i in self.order:
            self.world[i] = self.world[self.parent[i]] @ self.local[i] if i in self.parent else self.local[i]
        self.rotation = {i: Rotation.from_matrix(m[:3, :3] / np.linalg.norm(m[:3, :3], axis=0))
                         for i, m in self.world.items()}

    def mapped(self):
        if "Hip" in self.by_name:
            return {k: self.by_name[v] for k, v in GAME.items() if v in self.by_name}
        if "Chest" in self.by_name and "UpperArm.L" in self.by_name:
            return {k: self.by_name[v] for k, v in CAST.items() if v in self.by_name}
        return {k: self.base[k] for k in GAME if k in self.base}


def interpolate(times, data, samples, rotation=False, mode="LINEAR"):
    if len(times) == 1:
        value = data[1] if mode == "CUBICSPLINE" else data[0]
        return np.repeat(value[None], len(samples), axis=0)
    ids = np.searchsorted(times, samples, side="right") - 1
    ids = np.clip(ids, 0, len(times) - 2)
    span = times[ids + 1] - times[ids]
    t = np.clip((samples - times[ids]) / np.maximum(span, 1e-8), 0, 1)
    if mode == "CUBICSPLINE":
        data = data.reshape(len(times), 3, -1)
        a, b = data[ids, 1], data[ids + 1, 1]
        out = ((2*t**3-3*t**2+1)[:, None]*a + (t**3-2*t**2+t)[:, None]*span[:, None]*data[ids, 2]
               + (-2*t**3+3*t**2)[:, None]*b + (t**3-t**2)[:, None]*span[:, None]*data[ids+1, 0])
    else:
        a, b = data[ids].copy(), data[ids+1].copy()
        if rotation:
            negative = np.sum(a*b, axis=1) < 0
            b[negative] *= -1
        if mode == "STEP":
            t[:] = 0
        if rotation:
            dot = np.clip(np.sum(a*b, axis=1), -1, 1)
            angle = np.arccos(dot)
            sine = np.sin(angle)
            small = np.abs(sine) < 1e-5
            sine[small] = 1
            out = (np.sin((1-t)*angle)[:, None]*a + np.sin(t*angle)[:, None]*b)/sine[:, None]
            out[small] = a[small]*(1-t[small, None]) + b[small]*t[small, None]
        else:
            out = a*(1-t[:, None]) + b*t[:, None]
    if rotation:
        out /= np.linalg.norm(out, axis=1)[:, None]
    return out


def source_motion(path, fps, animation_name=None):
    doc, blob = read(path)
    rig = Rig(doc)
    animation = next(a for a in doc["animations"] if a.get("name")==animation_name) if animation_name else doc["animations"][0]
    tracks = []
    end = 0
    for channel in animation["channels"]:
        sampler = animation["samplers"][channel["sampler"]]
        times = values(doc, blob, sampler["input"])[:, 0]
        end = max(end, float(times[-1]))
        tracks.append((channel["target"], times, values(doc, blob, sampler["output"]), sampler.get("interpolation", "LINEAR")))
    times = np.linspace(0, end, int(math.ceil(end*fps)) + 1)
    local = {i: np.repeat(rig.local[i][None], len(times), axis=0) for i in rig.order}
    for i in rig.order:
        t, q, scale = rig.trs[i]
        translation = np.repeat(t[None], len(times), axis=0)
        rotations = np.repeat(q[None], len(times), axis=0)
        scales = np.repeat(scale[None], len(times), axis=0)
        for target, clock, data, mode in tracks:
            if target.get("node") != i:
                continue
            kind = target["path"]
            interpolated = interpolate(clock, data, times, kind == "rotation", mode)
            if kind == "translation": translation = interpolated
            if kind == "rotation": rotations = interpolated
            if kind == "scale": scales = interpolated
        local[i][:, :3, :3] = Rotation.from_quat(rotations).as_matrix()*scales[:, None, :]
        local[i][:, :3, 3] = translation
    world = {}
    for i in rig.order:
        world[i] = world[rig.parent[i]] @ local[i] if i in rig.parent else local[i]
    return rig, world, times


def direction_rotation(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    cross = np.cross(a, b)
    dot = float(np.clip(np.dot(a, b), -1, 1))
    if dot < -0.999999:
        axis = np.cross(a, [0, 1, 0])
        if np.linalg.norm(axis) < 1e-5: axis = np.cross(a, [1, 0, 0])
        return Rotation.from_rotvec(axis / np.linalg.norm(axis)*np.pi)
    q = np.r_[cross, 1+dot]
    return Rotation.from_quat(q / np.linalg.norm(q))


def reduce_keys(times, data, rotation):
    """Keep interpolation within 0.23 degrees / 0.0001 local units at every source key."""
    tolerance = .004 if rotation else .0001
    keep = {0, len(times)-1}
    pending = [(0, len(times)-1)]
    while pending:
        left, right = pending.pop()
        if right-left < 2: continue
        mid = np.arange(left+1, right)
        alpha = ((times[mid]-times[left])/(times[right]-times[left]))[:, None]
        a, b = data[left], data[right]
        if rotation and np.dot(a, b)<0: b=-b
        estimate = a*(1-alpha) + b*alpha
        if rotation:
            estimate /= np.linalg.norm(estimate, axis=1)[:, None]
            error = 2*np.arccos(np.clip(np.abs(np.sum(estimate*data[mid], axis=1)), 0, 1))
        else:
            error = np.linalg.norm(estimate-data[mid], axis=1)
        peak = int(np.argmax(error))
        if error[peak] > tolerance:
            index = int(mid[peak]);keep.add(index)
            pending.extend([(left,index),(index,right)])
    indices = np.array(sorted(keep))
    # Independently reconstruct every original key after simplification.
    rebuilt = interpolate(times[indices],data[indices],times,rotation)
    error = 2*np.arccos(np.clip(np.abs(np.sum(rebuilt*data,axis=1)),0,1)) if rotation else np.linalg.norm(rebuilt-data,axis=1)
    # glTF quaternion LINEAR is spherical interpolation. Verify that too and keep
    # extra keys when its error differs from the normalized-linear fitting bound.
    if float(error.max()) > tolerance*1.001:
        return np.arange(len(times)), 0.0
    return indices, float(error.max())


def retarget(doc, blob, target, motion, name, reduce=True):
    source, world, times = motion
    sm, tm = source.mapped(), target.mapped()
    left, right = "LeftUpLeg", "RightUpLeg"
    ss = source.world[sm[left]][:3, 3] - source.world[sm[right]][:3, 3]
    ts = target.world[tm[left]][:3, 3] - target.world[tm[right]][:3, 3]
    ss[1] = ts[1] = 0
    yaw = Rotation.from_rotvec([0, math.atan2(np.cross(ss, ts)[1], np.dot(ss, ts)), 0])
    aligned_rest = {key: yaw * source.rotation[index] for key, index in sm.items()}
    desired = {}
    for key, ti in tm.items():
        if key not in sm: continue
        si = sm[key]
        matrices = world[si][:, :3, :3]
        posed = yaw * Rotation.from_matrix(matrices / np.linalg.norm(matrices, axis=1)[:, None, :])
        delta = posed * aligned_rest[key].inv()
        align = Rotation.identity()
        # Limb alignment rotates the target rest direction onto the donor's before
        # applying motion; aligning body yaw first prevents the old m2 shoulder collapse.
        child = NEXT.get(key)
        if child in sm and child in tm and "Foot" not in key:
            td = target.world[tm[child]][:3, 3] - target.world[ti][:3, 3]
            sd = yaw.apply(source.world[sm[child]][:3, 3] - source.world[si][:3, 3])
            if min(np.linalg.norm(td), np.linalg.norm(sd)) > 1e-6:
                align = direction_rotation(td, sd)
        desired[ti] = delta * align * target.rotation[ti]
    parents = {}
    tracks = []
    saved_keys = 0
    full_keys = 0
    maximum_rotation_error = 0.0
    def track(index, path, data):
        nonlocal saved_keys, full_keys, maximum_rotation_error
        indices, error = reduce_keys(times,data,path=="rotation") if reduce else (np.arange(len(times)),0.0)
        full_keys+=len(times);saved_keys+=len(indices)
        if path=="rotation": maximum_rotation_error=max(maximum_rotation_error,error)
        time_index = add_values(doc,blob,times[indices,None],"SCALAR")
        value_index = add_values(doc,blob,data[indices],"VEC4" if path=="rotation" else "VEC3")
        tracks.append((index,path,time_index,value_index))
    for index in target.order:
        parent = target.parent.get(index)
        parent_rot = parents[parent] if parent is not None else Rotation.identity()
        local = Rotation.from_quat(target.trs[index][1])
        final = desired.get(index, parent_rot * local)
        parents[index] = final
        if index in desired:
            quats = (parent_rot.inv() * final).as_quat()
            for frame in range(1, len(quats)):
                if np.dot(quats[frame], quats[frame-1]) < 0: quats[frame] *= -1
            track(index,"rotation",quats)
    hip = tm["Hips"]
    src_hip = sm["Hips"]
    source_height = source.world[src_hip][1, 3] - min(m[1, 3] for m in source.world.values())
    target_height = target.world[hip][1, 3] - min(m[1, 3] for m in target.world.values())
    ratio = target_height / max(source_height, 1e-5)
    displacement = world[src_hip][:, :3, 3] - source.world[src_hip][:3, 3]
    displacement[:, [0, 2]] = 0  # Bodies/network own position; clips never move the collider.
    parent_matrix = target.world[target.parent[hip]] if hip in target.parent else np.eye(4)
    local_displacement = displacement @ np.linalg.inv(parent_matrix[:3, :3]).T * ratio
    track(hip,"translation",target.trs[hip][0]+local_displacement)
    result = {"name": name, "samplers": [], "channels": []}
    for index, path, time_index, accessor in tracks:
        sampler = len(result["samplers"])
        result["samplers"].append({"input": time_index, "output": accessor, "interpolation": "LINEAR"})
        result["channels"].append({"sampler": sampler, "target": {"node": index, "path": path}})
        node = doc["nodes"][index]
        if "matrix" in node:
            t, q, scale = target.trs[index]
            node.pop("matrix")
            node.update(translation=t.tolist(), rotation=q.tolist(), scale=scale.tolist())
    doc.setdefault("animations", []).append(result)
    return {"name": name, "seconds": float(times[-1]), "keys": len(times), "bones": len(desired),
            "full_keys":full_keys,"stored_keys":saved_keys,"max_rotation_error_degrees":math.degrees(maximum_rotation_error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=ROOT / "artifacts/context-motions-20261021")
    parser.add_argument("--targets", nargs="+", default=[f"game/assets/{s}.glb" for s in ["m1", "m2", "m3", "m4", "f1", "f2", "f3", "f4"]])
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--no-reduce", action="store_true")
    args = parser.parse_args()
    motions = {NAMES.get(p.parent.name, p.parent.name): source_motion(p, args.fps)
               for p in sorted(args.sources.glob("*/motion.glb")) if p.parent.name not in ("rig", "rig-check", "hurt")}
    donor = args.sources / "original-assets/m1.glb"
    if not donor.exists(): donor=ROOT / "game/assets/m1.glb"
    for name in ["walk","run"]:
        motions[name]=source_motion(donor,args.fps,name)
    assert len(motions) >= 1
    reports = []
    backup_dir = args.sources / "original-assets"
    for filename in args.targets:
        path = ROOT / filename
        backup = backup_dir / path.relative_to(ROOT / "game/assets")
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists(): backup.write_bytes(path.read_bytes())
        original, blob = read(backup)
        doc = copy.deepcopy(original)
        target = Rig(doc)
        names = {a.get("name") for a in doc.get("animations", [])}
        clips = []
        for name, motion in motions.items():
            if name in names: continue
            clips.append(retarget(doc, blob, target, motion, name,not args.no_reduce))
        assert doc["meshes"] == original["meshes"] and doc["skins"] == original["skins"]
        write(path, doc, blob)
        reports.append({"path": filename, "bytes": path.stat().st_size, "clips": clips,
                        "geometry_preserved": True})
        print(json.dumps(reports[-1]), flush=True)
    (args.sources / "retarget-report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
