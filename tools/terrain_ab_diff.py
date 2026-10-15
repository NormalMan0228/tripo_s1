"""Compares the village ground captures of game/tests/terrain_ab_capture.gd.

    .tools/art-venv/Scripts/python.exe tools/terrain_ab_diff.py --ab artifacts/terrain_p2/ab [--level 1a|1b]
    .tools/art-venv/Scripts/python.exe tools/terrain_ab_diff.py --pairs DIR PREFIX_A PREFIX_B      # e.g. before default
    .tools/art-venv/Scripts/python.exe tools/terrain_ab_diff.py --two-up A.png B.png OUT.png "label A" "label B"

--ab: every "ab_h<hour>_<spot>_z<zoom>_A.png" (the ground as drawn before the chunks) against its
"_B.png" (the chunks), taken in one process with time held still. The pairs with every omni light
hidden are checked against the thresholds of the level (1a: the chunks are the same triangles, so
>= 99.99 % of the pixels the same and a mean difference <= 0.01/255; 1b: simplified ground, mean
<= 0.06/255 at zoom 6.5 and <= 0.08/255 at 10 and 22, 99.9th percentile <= 4/255, no pixel over
32/255); the "_lit" pairs are reported only. Then the crack test (crack_A/B, crack_close_A/B: the
grounds white on magenta from above, nothing below the line the chunks leave out): magenta in B
where A is white is a hole between chunks (white only in B is a kept triangle reaching below it).
A difference image (x8, red) is written next to each pair that fails. Prints TERRAIN_AB_DIFF {...}
and exits 1 on a failure.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

LEVELS = {
    "1a": {"identical": 0.9999, "mean": {6.5: 0.01, 10.0: 0.01, 22.0: 0.01}, "p999": None, "max": None},
    "1b": {"identical": None, "mean": {6.5: 0.06, 10.0: 0.08, 22.0: 0.08}, "p999": 4, "max": 32},
}


def load(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def stats(a: np.ndarray, b: np.ndarray) -> dict:
    diff = np.abs(a - b)
    per_pixel = diff.max(axis=2)
    return {
        "identical": float((per_pixel == 0).mean()),
        "mean": float(diff.mean()),
        "p999": float(np.percentile(per_pixel, 99.9)),
        "max": int(per_pixel.max()),
        "changed_pixels": int((per_pixel > 0).sum()),
    }


def diff_image(a: np.ndarray, b: np.ndarray, out: Path) -> None:
    per_pixel = np.abs(a - b).max(axis=2)
    base = (a.mean(axis=2) * 0.35).astype(np.uint8)
    rgb = np.stack([base, base, base], axis=2)
    hot = per_pixel > 0
    rgb[hot, 0] = np.clip(per_pixel[hot] * 8 + 80, 0, 255).astype(np.uint8)
    rgb[hot, 1] = 0
    rgb[hot, 2] = 0
    Image.fromarray(rgb).save(out)


def check(level: str, zoom: float, s: dict) -> list[str]:
    rule = LEVELS[level]
    problems = []
    if rule["identical"] is not None and s["identical"] < rule["identical"]:
        problems.append(f"identical {s['identical']*100:.4f} % < {rule['identical']*100:.2f} %")
    if s["mean"] > rule["mean"].get(zoom, 0.08):
        problems.append(f"mean {s['mean']:.4f}/255 > {rule['mean'].get(zoom, 0.08)}")
    if rule["p999"] is not None and s["p999"] > rule["p999"]:
        problems.append(f"p99.9 {s['p999']:.1f} > {rule['p999']}")
    if rule["max"] is not None and s["max"] > rule["max"]:
        problems.append(f"max {s['max']} > {rule['max']}")
    return problems


def crack(directory: Path) -> dict:
    out = {}
    for name in ["crack", "crack_close"]:
        a_path, b_path = directory / f"{name}_A.png", directory / f"{name}_B.png"
        if not a_path.exists() or not b_path.exists():
            continue
        a, b = load(a_path), load(b_path)
        white_a = (a > 200).all(axis=2)
        white_b = (b > 200).all(axis=2)
        magenta_b = (b[:, :, 0] > 200) & (b[:, :, 1] < 60) & (b[:, :, 2] > 200)
        holes = white_a & magenta_b
        out[name] = {"ground_pixels_a": int(white_a.sum()), "ground_pixels_b": int(white_b.sum()), "holes": int(holes.sum()),
                     "only_in_b": int((white_b & ~white_a).sum())}
        if holes.any():
            diff_image(a, b, directory / f"{name}_holes.png")
    return out


def ab(directory: Path, level: str) -> int:
    pattern = re.compile(r"ab_h(\d+)_(.+)_z([\d.]+)_A(_lit)?\.png$")
    rows = []
    failures = []
    for a_path in sorted(directory.glob("ab_h*_A*.png")):
        m = pattern.match(a_path.name)
        if not m:
            continue
        b_path = a_path.with_name(a_path.name.replace("_A", "_B", 1) if not m.group(4) else a_path.name.replace("_A_lit", "_B_lit"))
        if not b_path.exists():
            failures.append(f"{b_path.name} missing")
            continue
        hour, spot, zoom, lit = int(m.group(1)), m.group(2), float(m.group(3)), bool(m.group(4))
        a, b = load(a_path), load(b_path)
        s = stats(a, b)
        problems = [] if lit else check(level, zoom, s)
        if problems:
            failures.append(f"h{hour} {spot} z{zoom}: " + ", ".join(problems))
            diff_image(a, b, a_path.with_name(a_path.name.replace("_A", "_diff", 1)))
        rows.append({"hour": hour, "spot": spot, "zoom": zoom, "lit": lit, **{k: round(v, 6) if isinstance(v, float) else v for k, v in s.items()}, "ok": not problems})
    strict = [r for r in rows if not r["lit"]]
    lit = [r for r in rows if r["lit"]]
    summary = {
        "level": level, "pairs": len(rows), "strict_pairs": len(strict),
        "strict_worst_mean": max((r["mean"] for r in strict), default=0.0),
        "strict_lowest_identical": min((r["identical"] for r in strict), default=1.0),
        "strict_worst_max": max((r["max"] for r in strict), default=0),
        "lit_worst_mean": max((r["mean"] for r in lit), default=0.0),
        "lit_lowest_identical": min((r["identical"] for r in lit), default=1.0),
        "crack": crack(directory),
        "failures": failures, "rows": rows,
    }
    for name, c in summary["crack"].items():
        if c["holes"] > 0:
            failures.append(f"{name}: {c['holes']} magenta pixels inside the ground")
    summary["ok"] = not failures
    print("TERRAIN_AB_DIFF " + json.dumps(summary))
    return 0 if not failures else 1


def pairs(directory: Path, first: str, second: str) -> int:
    rows = []
    for a_path in sorted(directory.glob(f"{first}_*.png")):
        b_path = a_path.with_name(second + a_path.name[len(first):])
        if not b_path.exists():
            continue
        s = stats(load(a_path), load(b_path))
        rows.append({"file": a_path.name[len(first) + 1:], **{k: round(v, 6) if isinstance(v, float) else v for k, v in s.items()}})
    print("TERRAIN_PAIRS " + json.dumps({"first": first, "second": second, "rows": rows}))
    return 0


def two_up(a: Path, b: Path, out: Path, label_a: str, label_b: str) -> int:
    images = [Image.open(a).convert("RGB"), Image.open(b).convert("RGB")]
    width, height = images[0].size
    band = 44
    canvas = Image.new("RGB", (width * 2 + 12, height + band), (24, 26, 30))
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 26)
    except OSError:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)
    for index, (image, label) in enumerate(zip(images, [label_a, label_b])):
        x = index * (width + 12)
        canvas.paste(image, (x, band))
        draw.text((x + 12, 8), label, fill=(240, 240, 240), font=font)
    canvas.save(out)
    print(f"TWO_UP {out}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--ab"]:
        level = args[args.index("--level") + 1] if "--level" in args else "1a"
        return ab(Path(args[1]), level)
    if args[:1] == ["--pairs"]:
        return pairs(Path(args[1]), args[2], args[3])
    if args[:1] == ["--two-up"]:
        return two_up(Path(args[1]), Path(args[2]), Path(args[3]), args[4], args[5])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
