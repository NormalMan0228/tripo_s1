"""Summarise loading measurements (tools/measure_loading.ps1 -> artifacts/loading/<label>-<n>.json).

    .tools/art-venv/Scripts/python.exe tools/summarize_loading.py base-gl base-fp [--json out.json]

For each label: per change of place the range (min-max) over the warm runs of seconds under the
veil, worst frame and frames over 50 ms; the cold run (if any) separately; the start's black screen;
the phase breakdown (median of the warm runs, ms); video/texture memory and peak working set.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "artifacts" / "loading"
ORDER = ["start -> title", "title -> home", "home -> village", "village -> resident's house",
         "resident's house -> village", "village -> expedition", "expedition -> village"]
PHASES = ["reading the game's scripts", "file read (main thread)", "waiting for file reads", "GPU upload + engine", "node assembly",
          "pad levelling", "collision", "render", "first render"]


def runs(label: str) -> tuple[list[dict], list[dict]]:
    warm, cold = [], []
    for path in sorted(DIR.glob(label + "-*.json")):
        rest = path.stem[len(label) + 1:]
        if not (rest.isdigit() or (rest.startswith("cold-") and rest[5:].isdigit())):
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        (cold if data.get("cold") else warm).append(data)
    return warm, cold


def span(values: list[float], digits: int = 2) -> str:
    if not values:
        return "-"
    low, high = min(values), max(values)
    return f"{low:.{digits}f}" if abs(high - low) < 10 ** -digits else f"{low:.{digits}f}-{high:.{digits}f}"


def summary(label: str) -> dict:
    warm, cold = runs(label)
    out = {"label": label, "warm_runs": len(warm), "cold_runs": len(cold), "changes": {}}
    for name in ORDER:
        rows = [r["changes"][name] for r in warm if name in r.get("changes", {})]
        cold_rows = [r["changes"][name] for r in cold if name in r.get("changes", {})]
        if not rows and not cold_rows:
            continue
        entry = {
            "seconds": [r["seconds"] for r in rows], "worst_ms": [r["worst_ms"] for r in rows],
            "over_50ms": [r["over_50ms"] for r in rows],
            "cold": cold_rows[0] if cold_rows else None,
            "phases": {p: statistics.median([r.get("phases", {}).get(p, 0.0) for r in rows]) for p in PHASES} if rows else {},
            "video_mb": statistics.median([r.get("video_mb", 0) for r in rows]) if rows else None,
            "texture_mb": statistics.median([r.get("texture_mb", 0) for r in rows]) if rows else None,
        }
        if name == "start -> title":
            entry["black_s"] = [r.get("black_until_card_s", 0) for r in rows]
            entry["cold_black_s"] = cold_rows[0].get("black_until_card_s") if cold_rows else None
        out["changes"][name] = entry
    out["peak_working_set_mb"] = [r.get("peak_working_set_mb") for r in warm]
    return out


def main() -> None:
    args = sys.argv[1:]
    skip = {args.index("--json") + 1} if "--json" in args else set()
    labels = [a for i, a in enumerate(args) if not a.startswith("--") and i not in skip]
    result = {}
    for label in labels:
        s = summary(label)
        result[label] = s
        print(f"== {label}: {s['warm_runs']} warm + {s['cold_runs']} cold run(s); peak working set {span(s['peak_working_set_mb'], 0)} MB")
        print(f"{'change':30s} {'under veil s':>12s} {'worst ms':>14s} {'>50ms':>7s} | cold: s / worst / >50")
        for name, e in s["changes"].items():
            c = e["cold"]
            cold = f"{c['seconds']:.2f} / {c['worst_ms']:.0f} / {c['over_50ms']}" if c else "-"
            print(f"{name:30s} {span(e['seconds']):>12s} {span(e['worst_ms'], 0):>14s} {span(e['over_50ms'], 0):>7s} | {cold}")
        st = s["changes"].get("start -> title")
        if st:
            print(f"black screen before the card: {span(st['black_s'])} s (cold {st['cold_black_s']})")
        for name in ("start -> title", "home -> village"):
            e = s["changes"].get(name)
            if e and e["phases"]:
                print(f"phases {name} (median ms): " + ", ".join(f"{p} {v:.0f}" for p, v in e["phases"].items() if v))
        if st:
            print(f"video memory after start: {st['video_mb']:.0f} MB (textures {st['texture_mb']:.0f} MB)")
    if "--json" in sys.argv:
        target = Path(sys.argv[sys.argv.index("--json") + 1])
        target.write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
