"""The survival maps' baked static data (game/maps/survival/generated/, git-ignored): bake it, check it.

    .tools/art-venv/Scripts/python.exe tools/bake_survival.py           # bake when stale (else nothing)
    .tools/art-venv/Scripts/python.exe tools/bake_survival.py --check   # exit 3 when stale or missing
    .tools/art-venv/Scripts/python.exe tools/bake_survival.py --force   # bake again anyway
    .tools/art-venv/Scripts/python.exe tools/bake_survival.py --pack builds/windows/Villagen.pck
                                                                        # the pack carries this bake?

What it holds and when it counts: game/maps/survival/survival_bake.gd. The bake itself is
tools/bake_survival.gd (Godot, headless): per map the ground mesh, the water sheets and the rim
block of the scatter. Fresh means: same layouts.json, survival_map.gd, survival_bake.gd, engine and
set of prop models present as when it was made.

The export steps keep it fresh: tools/build_game.ps1 bakes before exporting, tools/game_patch.py
before exporting a patch, and tools/package_release.py refuses a pack whose bake is stale or older
than the one on disk. A game without fresh baked data still runs: it builds the maps at runtime as
before (slower entry), so a stale bake is never used.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / ".tools" / "godot" / "Godot_v4.7.2-stable_win64_console.exe"
GENERATED = ROOT / "game" / "maps" / "survival" / "generated"
FILES = ["survival_forest.res", "survival_quarry.res", "survival_frost.res"]
PACK_PREFIX = "maps/survival/generated/"


def _godot(*args: str) -> subprocess.CompletedProcess:
    command = [str(GODOT), "--headless", "--path", str(ROOT / "game"), "--script", "res://../tools/bake_survival.gd", "--", *args]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _line(result: subprocess.CompletedProcess, prefix: str) -> str:
    lines = [l for l in result.stdout.splitlines() if l.startswith(prefix)]
    return lines[-1] if lines else ""


def check() -> tuple[bool, str]:
    """(fresh, what Godot said) for the baked data on disk."""
    result = _godot("--check")
    return result.returncode == 0, _line(result, "BAKE_SURVIVAL_CHECK") or f"check failed ({result.returncode})"


def bake() -> None:
    result = _godot()
    for line in result.stdout.splitlines():
        if line.startswith(("BAKE_SURVIVAL", "BAKE_DONE")):
            print(line)
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-15:])
        raise SystemExit(f"survival bake failed ({result.returncode}):\n{tail}")


def ensure(force: bool = False) -> None:
    """Bakes when the baked data is missing or stale; fails if it is still not fresh after."""
    fresh, said = check()
    if fresh and not force:
        print("survival bake:", said)
        return
    print("survival bake:", said, "-> baking", flush=True)
    bake()
    fresh, said = check()
    if not fresh:
        raise SystemExit(f"survival bake still not fresh after baking: {said}")
    print("survival bake:", said)


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_pack(pck: Path) -> None:
    """Refuses (SystemExit) a pack whose baked data is missing, stale or not the bake on disk."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import game_patch
    fresh, said = check()
    if not fresh:
        raise SystemExit(f"the survival bake is stale ({said}): run tools/build_game.ps1 (it re-bakes) and package again")
    files = game_patch.read_pck(pck)["files"]
    for name in FILES:
        entry = files.get(PACK_PREFIX + name)
        if entry is None:
            raise SystemExit(f"{pck.name} has no {PACK_PREFIX + name}: export again after tools/bake_survival.py")
        if entry["md5"] != _md5(GENERATED / name):
            raise SystemExit(f"{pck.name} carries an older {name} than the bake on disk: export again")
    print(f"{pck.name}: survival bake present and fresh ({', '.join(FILES)})")


def main() -> None:
    args = sys.argv[1:]
    if "--check" in args:
        fresh, said = check()
        print(said)
        sys.exit(0 if fresh else 3)
    if "--pack" in args:
        verify_pack(Path(args[args.index("--pack") + 1]))
        return
    ensure(force="--force" in args)


if __name__ == "__main__":
    main()
