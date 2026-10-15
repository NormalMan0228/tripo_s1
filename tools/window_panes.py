"""Window panes found automatically on the facade renders (artifacts/outline_tool/renders), written as
outlines the door cutter reads (kind "window"), so every pane of every window is cut out of the building
whole and drawn by one glass material (item 9: all panes brighten and darken together).

    .tools/art-venv/Scripts/python.exe tools/window_panes.py [RENDERS] [OUT]

RENDERS defaults to artifacts/outline_tool/renders, OUT to artifacts/outline_tool/auto_windows. Per render
<model>__<face>: OUT/<render_id>.json ({render_id, polys: [{kind: "window", pts}]}, pixel coordinates)
and OUT/<render_id>_check.png (the render with the panes found outlined). A pane is a connected region
of glass colour (dark teal or blue; glints and thin glazing bars inside it filled), kept when its size
is a pane's (PANE_M2 square metres) and it fills enough of its bounding box; its outline is that box
(the convex hull of its texels: round and arched panes keep their shape). Regions over the door
(door_leaves.json's door projected into the render, or the user's door outline when there is one)
are dropped. Prints one WINDOW_PANES line per render.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import ConvexHull

ROOT = Path(__file__).resolve().parents[1]
PANE_M2 = (0.012, 2.5)
MIN_FILL = 0.42
MIN_SIDE_M = 0.07


def glass_mask(rgb: np.ndarray) -> np.ndarray:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    luma = r * 0.299 + g * 0.587 + b * 0.114
    tint = np.maximum(g, b) - r
    high = rgb.max(axis=2)
    sat = (high - rgb.min(axis=2)) / np.maximum(high, 0.01)
    seed = (tint > 0.08) & (b / np.maximum(g, 0.01) > 0.72) & (luma < 0.45)
    grow = ((tint > 0.03) & (b > r + 0.02) & (luma < 0.78) & (sat > 0.10)) | seed
    labels, count = ndimage.label(grow)
    if count == 0:
        return np.zeros(luma.shape, bool)
    index = np.arange(1, count + 1)
    seeds = ndimage.sum(seed, labels, index)
    area = ndimage.sum(np.ones_like(luma), labels, index)
    keep = np.zeros(count + 1, bool)
    keep[1:] = (seeds >= 6) & (seeds >= area * 0.15)
    glass = keep[labels]
    return ndimage.binary_fill_holes(ndimage.binary_closing(glass, iterations=2))


def door_box(meta: dict, outlines_dir: Path) -> list[tuple[float, float, float, float]]:
    """Pixel boxes over the door on this render: the user's door outlines, else door_leaves.json."""
    boxes = []
    user = outlines_dir / f"{meta['render_id']}.json"
    if user.exists():
        for poly in json.loads(user.read_text(encoding="utf-8")).get("polys", []):
            if poly.get("kind") == "door" and len(poly.get("pts", [])) >= 3:
                xs = [p[0] for p in poly["pts"]]
                ys = [p[1] for p in poly["pts"]]
                boxes.append((min(xs), min(ys), max(xs), max(ys)))
    if boxes:
        return boxes
    table = json.loads((ROOT / "game/maps/archipelago/door_leaves.json").read_text(encoding="utf-8"))
    o, u, v, mpp = np.array(meta["origin_tl"]), np.array(meta["u"]), np.array(meta["v"]), meta["mpp"]
    view = np.array(meta["view_dir"])
    for bid in meta.get("building_ids", []):
        rect = table.get(bid)
        if not rect:
            continue
        if "outline_px" in rect:
            if rect.get("render_id") == meta["render_id"]:
                xs = [p[0] for p in rect["outline_px"]]
                ys = [p[1] for p in rect["outline_px"]]
                boxes.append((min(xs) - 10, min(ys) - 10, max(xs) + 10, max(ys) + 10))
            continue
        if "out" not in rect:
            continue
        out, side, origin = np.array(rect["out"]), np.array(rect["side"]), np.array(rect["origin"])
        if float(out @ -view) < 0.7:
            continue  # the door is on another face
        corners = []
        for x in (rect["left"], rect["left"] + rect["width"]):
            for y in (rect["bottom"], rect["bottom"] + rect["height"]):
                p = origin + side * x + np.array([0, 1, 0]) * y + out * rect["front"]
                corners.append(((p - o) @ u / mpp, (p - o) @ v / mpp))
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        boxes.append((min(xs) - 10, min(ys) - 10, max(xs) + 10, max(ys) + 10))
    return boxes


def panes(render: Path, outlines_dir: Path) -> tuple[dict, Image.Image, dict]:
    meta = json.loads(render.with_suffix(".json").read_text(encoding="utf-8"))
    meta.setdefault("render_id", render.stem)
    image = Image.open(render).convert("RGB")
    # Half size is plenty to find panes (memory stays low); pixel coordinates are scaled back.
    scale = 2
    small = image.resize((image.width // scale, image.height // scale), Image.BILINEAR)
    rgb = np.asarray(small, dtype=np.float32) / 255.0
    mpp = float(meta["mpp"]) * scale
    glass = glass_mask(rgb)
    labels, count = ndimage.label(glass)
    found = []
    doors = door_box(meta, outlines_dir)
    stats = {"regions": int(count), "panes": 0, "dropped_door": 0, "dropped_shape": 0}
    for index, sl in enumerate(ndimage.find_objects(labels), start=1):
        if sl is None:
            continue
        ys, xs = sl
        w, h = xs.stop - xs.start, ys.stop - ys.start
        area_px = float((labels[sl] == index).sum())
        area_m2 = area_px * mpp * mpp
        if not (PANE_M2[0] <= area_m2 <= PANE_M2[1]) or min(w, h) * mpp < MIN_SIDE_M or area_px < MIN_FILL * w * h:
            stats["dropped_shape"] += 1
            continue
        cx, cy = (xs.start + w / 2) * scale, (ys.start + h / 2) * scale
        if any(b[0] <= cx <= b[2] and b[1] <= cy <= b[3] for b in doors):
            stats["dropped_door"] += 1
            continue
        # The pane's own outline: the convex hull of its texels (round and arched panes keep their shape),
        # grown by a texel so the frame's antialiased edge comes with it.
        yy, xx = np.nonzero(labels[sl] == index)
        corners = np.concatenate([np.stack([xx + dx, yy + dy], axis=1) for dx in (0, 1) for dy in (0, 1)])
        hull = ConvexHull(corners)
        ring = corners[hull.vertices].astype(float)
        centre = ring.mean(axis=0)
        ring = centre + (ring - centre) * (1.0 + 1.5 / max(1.0, float(np.abs(ring - centre).max())))
        pts = [[round(float((x + xs.start) * scale), 1), round(float((y + ys.start) * scale), 1)] for x, y in ring]
        found.append({"kind": "window", "hinge": None, "closed": True, "pts": pts})
    stats["panes"] = len(found)
    del rgb, glass, labels
    check = image
    draw = ImageDraw.Draw(check)
    for b in doors:
        draw.rectangle(b, outline=(255, 0, 0), width=4)
    for poly in found:
        draw.polygon([tuple(p) for p in poly["pts"]], outline=(0, 255, 0), width=3)
    return {"render_id": meta["render_id"], "polys": found, "auto": True}, check, stats


def main() -> None:
    renders = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/outline_tool/renders"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "artifacts/outline_tool/auto_windows"
    out.mkdir(parents=True, exist_ok=True)
    outlines = ROOT / "artifacts/outline_tool/outlines"
    for render in sorted(renders.glob("*.png")):
        if not render.with_suffix(".json").exists():
            continue
        result, check, stats = panes(render, outlines)
        (out / f"{render.stem}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
        # The cutter's input for this render: the user's doors and windows where drawn, else these panes.
        merged = {"render_id": render.stem, "polys": []}
        user_file = outlines / f"{render.stem}.json"
        if user_file.exists():
            user = json.loads(user_file.read_text(encoding="utf-8"))
            merged["polys"] = [p for p in user.get("polys", []) if len(p.get("pts", [])) >= 3]
        if not any(p.get("kind") == "window" for p in merged["polys"]):
            merged["polys"] += result["polys"]
        (out.parent / "merged").mkdir(parents=True, exist_ok=True)
        (out.parent / "merged" / f"{render.stem}.json").write_text(json.dumps(merged, indent=1), encoding="utf-8")
        check.thumbnail((1024, 1024))
        check.save(out / f"{render.stem}_check.png")
        print("WINDOW_PANES", render.stem, json.dumps(stats))


if __name__ == "__main__":
    main()
