"""Texture size caps for the archipelago map that players cannot see (re-runnable on a fresh copy).

    .tools/art-venv/Scripts/python.exe tools/lighten_archipelago_map.py [--dry-run]
    .tools/godot/Godot_v4.7.2-stable_win64_console.exe --headless --path game --import

The map assets (game/maps/archipelago/assets, git-ignored) are copied from labs/terrain_lab by
tools/port_archipelago_map.py, which runs this at its end; run it by hand after any other copy.
It only edits `process/size_limit` in the textures' .import files (the source PNGs stay as they are;
Godot downsizes on import, mipmaps are made from the smaller image).

Which caps (the rule, not a list, so a re-ported map gets the same treatment):
  * Prop textures (environment_layout.json models): the camera is at its closest (orthographic size
    6.5 m) on a 1080-pixel-tall screen, a metre of surface covers at most 1080/6.5 = 166 pixels.
    A texture keeps at least MIN_TEXELS_PER_M (300, 1.8 texels per pixel) on 90 % of the model's
    surface (area-weighted 10th percentile of the per-triangle density, from the GLB's UVs, at the
    placed scale): the GPU samples a smaller mipmap than the full image there anyway, so dropping
    the top level does not change what is drawn. Never below 1024 px. Normal and ORM maps get the
    same cap (never above their own size).
  * Buildings keep their full textures: at 70-170 texels per metre they are close to one texel per
    pixel at the closest zoom, so a cap there would show.
  * Textures no frame draws: the terrain GLB's own ocean and pond materials (the map replaces them
    with its water shaders, archipelago.gd) and v3/*_surface_color.png (the water shaders never
    sample it) are capped to DEAD_LIMIT.
Writes docs/performance/data/texture_caps.json (what changed, sizes before and after).
"""
from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "game" / "maps" / "archipelago"
ASSETS = MAP / "assets"
REPORT = ROOT / "docs" / "performance" / "data" / "texture_caps.json"
MIN_TEXELS_PER_M = 300.0
MIN_LIMIT = 1024
DEAD_LIMIT = 256
# The terrain GLB's ocean/pond materials: replaced by material_override (water shaders) on every mesh.
# The water shaders declare surface_color but never sample it (archipelago.gd no longer loads these).
DEAD = ["archipelago_terrain_environment_v1_ocean_surface_color.png", "archipelago_terrain_environment_v1_ocean_surface_normal.png",
        "archipelago_terrain_environment_v1_pond_surface_color.png", "archipelago_terrain_environment_v1_pond_surface_normal.png",
        "v3/ocean_surface_color.png", "v3/pond_surface_color.png"]

_COMPONENT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_glb(path: Path):
    data = path.read_bytes()
    json_length = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + json_length])
    bin_length = struct.unpack_from("<I", data, 20 + json_length)[0]
    blob = data[28 + json_length:28 + json_length + bin_length]

    def accessor(index: int) -> np.ndarray:
        acc = doc["accessors"][index]
        view = doc["bufferViews"][acc["bufferView"]]
        offset = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        width = _WIDTH[acc["type"]]
        kind = np.dtype(_COMPONENT[acc["componentType"]])
        item = kind.itemsize * width
        stride = view.get("byteStride", 0)
        if stride and stride != item:
            raw = np.frombuffer(blob, np.uint8, count=stride * (acc["count"] - 1) + item, offset=offset)
            array = np.lib.stride_tricks.as_strided(raw, (acc["count"], item), (stride, 1)).copy().view(kind)
        else:
            array = np.frombuffer(blob, kind, count=acc["count"] * width, offset=offset)
        return array.reshape(acc["count"], width) if width > 1 else array
    return doc, accessor


def _matrix(node: dict) -> np.ndarray:
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    rotation = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    out = np.eye(4)
    out[:3, :3] = rotation * np.array(node.get("scale", [1, 1, 1]))
    out[:3, 3] = node.get("translation", [0, 0, 0])
    return out


def texel_density_p10(path: Path, scale: float) -> float:
    """Area-weighted 10th percentile of texels per metre for a 1-pixel texture (multiply by size)."""
    doc, accessor = read_glb(path)
    meshes: list[tuple[int, np.ndarray]] = []

    def walk(index: int, parent: np.ndarray) -> None:
        node = doc["nodes"][index]
        world = parent @ _matrix(node)
        if "mesh" in node:
            meshes.append((node["mesh"], world))
        for child in node.get("children", []):
            walk(child, world)
    for top in doc["scenes"][doc.get("scene", 0)]["nodes"]:
        walk(top, np.eye(4))
    densities, weights = [], []
    for mesh, world in meshes:
        for primitive in doc["meshes"][mesh]["primitives"]:
            if "TEXCOORD_0" not in primitive["attributes"]:
                continue
            points = (world[:3, :3] @ accessor(primitive["attributes"]["POSITION"]).astype(np.float64).T).T * scale
            uv = accessor(primitive["attributes"]["TEXCOORD_0"]).astype(np.float64)
            index = (accessor(primitive["indices"]).astype(np.int64) if "indices" in primitive else np.arange(len(points))).reshape(-1, 3)
            a, b, c = points[index[:, 0]], points[index[:, 1]], points[index[:, 2]]
            area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
            ua, ub, uc = uv[index[:, 0]], uv[index[:, 1]], uv[index[:, 2]]
            uv_area = 0.5 * np.abs((ub[:, 0] - ua[:, 0]) * (uc[:, 1] - ua[:, 1]) - (uc[:, 0] - ua[:, 0]) * (ub[:, 1] - ua[:, 1]))
            # Patch quads (tools/patch_building_holes.py) sit in shifted atlas tiles; skip them and slivers.
            inside = (np.max(np.stack([ua[:, 0], ub[:, 0], uc[:, 0]]), axis=0) <= 1.001) & (area > 1e-8) & (uv_area > 0)
            densities.append(np.sqrt(uv_area[inside] / area[inside]))
            weights.append(area[inside])
    density = np.concatenate(densities)
    weight = np.concatenate(weights)
    order = np.argsort(density)
    cumulative = np.cumsum(weight[order]) / weight.sum()
    return float(density[order][np.searchsorted(cumulative, 0.10)])


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        head = handle.read(24)
    return struct.unpack(">II", head[16:24])


def set_limit(import_file: Path, limit: int, dry: bool) -> int:
    text = import_file.read_text(encoding="utf-8")
    current = re.search(r"(?m)^process/size_limit=(\d+)", text)
    previous = int(current.group(1)) if current else 0
    if previous == limit:
        return previous
    edited = re.sub(r"(?m)^process/size_limit=\d+", f"process/size_limit={limit}", text) if current else text.rstrip("\n") + f"\nprocess/size_limit={limit}\n"
    if not dry:
        import_file.write_text(edited, encoding="utf-8", newline="\n")
    return previous


def model_textures(model: Path) -> list[Path]:
    stem = model.name.removesuffix(".glb")
    return sorted(p for p in model.parent.glob(stem + "_*.png") if re.match(re.escape(stem) + r"_(Color|NormalGL|ORM|Roughness|Metallic)_", p.name))


def plan() -> list[dict]:
    layout = json.loads((MAP / "environment_layout.json").read_text(encoding="utf-8"))
    scales: dict[str, list[float]] = {}
    for instance in layout["instances"]:
        scales.setdefault(instance["id"], []).append(float(instance.get("scale", 1.0)))
    rows = []
    for spec in layout["models"]:
        model = ASSETS / spec["model"].split("/assets/", 1)[1]
        if not model.exists() or spec["id"] not in scales:
            continue
        p10 = texel_density_p10(model, float(np.median(scales[spec["id"]])))
        for texture in model_textures(model):
            size = max(png_size(texture))
            limit = size
            # Halve while the halved image still keeps MIN_TEXELS_PER_M on 90 % of the surface.
            while limit // 2 >= MIN_LIMIT and p10 * (limit // 2) >= MIN_TEXELS_PER_M:
                limit //= 2
            # Normal and ORM maps: the same rule at their own size.
            rows.append({"texture": texture.relative_to(ASSETS).as_posix(), "model": spec["id"], "size": size,
                         "p10_texels_per_m_at_size": round(p10 * size), "limit": limit if limit < size else 0,
                         "p10_texels_per_m_after": round(p10 * min(limit, size))})
    for name in DEAD:
        texture = ASSETS / name
        if texture.exists():
            rows.append({"texture": name, "model": "never drawn (terrain water material replaced, or unsampled)", "size": max(png_size(texture)),
                         "p10_texels_per_m_at_size": None, "limit": DEAD_LIMIT, "p10_texels_per_m_after": None})
    return rows


def ctex_mb(size: int) -> float:
    # BPTC: 1 byte per texel, mipmaps add a third.
    return size * size * 4 / 3 / 1e6


def apply(dry: bool = False) -> dict:
    rows = plan()
    changed = 0
    for row in rows:
        target = row["limit"] or 0
        previous = set_limit(ASSETS / (row["texture"] + ".import"), target, dry)
        row["previous_limit"] = previous
        changed += previous != target
    before = sum(ctex_mb(r["size"]) for r in rows)
    after = sum(ctex_mb(min(r["size"], r["limit"] or r["size"])) for r in rows)
    report = {"rule": f"props: >= {MIN_TEXELS_PER_M:.0f} texels/m on 90% of the surface, never below {MIN_LIMIT} px; "
                      f"buildings unchanged; terrain ocean/pond materials (never drawn) {DEAD_LIMIT} px",
              "textures": rows, "capped": sum(1 for r in rows if r["limit"]), "estimated_mb_before": round(before),
              "estimated_mb_after": round(after)}
    if not dry:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"texture caps: {report['capped']} of {len(rows)} prop/terrain textures capped ({changed} .import files changed); "
          f"~{report['estimated_mb_before']} MB -> ~{report['estimated_mb_after']} MB imported")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = apply(args.dry_run)
    if args.dry_run:
        for row in report["textures"]:
            if row["limit"]:
                print(f"  {row['texture']}: {row['size']} -> {row['limit']} ({row['p10_texels_per_m_after']} texels/m)")


if __name__ == "__main__":
    main()
