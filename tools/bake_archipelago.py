"""The archipelago's generated data (game/maps/archipelago/generated/, git-ignored): bake it, check it.

    .tools/art-venv/Scripts/python.exe tools/bake_archipelago.py           # bake when stale (else nothing)
    .tools/art-venv/Scripts/python.exe tools/bake_archipelago.py --check   # exit 3 when stale or missing
    .tools/art-venv/Scripts/python.exe tools/bake_archipelago.py --force   # bake again anyway
    .tools/art-venv/Scripts/python.exe tools/bake_archipelago.py --pack builds/windows/Villagen.pck
                                                                           # the pack carries this bake?

What it holds and when it counts: game/maps/archipelago/island_bake.gd. The bake itself is
tools/bake_archipelago.gd (Godot, headless): simplified collision for every render-mesh collider and
the baked island. Fresh means: same layouts, build scripts, engine and map assets (MD5 of every GLB,
PNG and .import) as when it was made.

The export steps keep it fresh: tools/build_game.ps1 bakes before exporting, tools/game_patch.py
before exporting a patch, and tools/package_release.py refuses a pack whose bake is stale or older
than the one on disk. A game without fresh generated data still runs: it builds the map at runtime
as before (slower), so a stale bake is never used.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / ".tools" / "godot" / "Godot_v4.7.2-stable_win64_console.exe"
GENERATED = ROOT / "game" / "maps" / "archipelago" / "generated"
FILES = ["manifest.json", "collision.res", "island.scn"]
PACK_PREFIX = "maps/archipelago/generated/"


def _godot(*args: str) -> subprocess.CompletedProcess:
    command = [str(GODOT), "--headless", "--path", str(ROOT / "game"), "--script", "res://../tools/bake_archipelago.gd", "--", *args]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _line(result: subprocess.CompletedProcess, prefix: str) -> str:
    lines = [l for l in result.stdout.splitlines() if l.startswith(prefix)]
    return lines[-1] if lines else ""


def check() -> tuple[bool, str]:
    """(fresh, what Godot said) for the generated data on disk."""
    result = _godot("--check")
    return result.returncode == 0, _line(result, "BAKE_CHECK") or f"check failed ({result.returncode})"


def bake() -> None:
    result = _godot()
    for line in result.stdout.splitlines():
        if line.startswith(("BAKE_COLLISION", "BAKE_ISLAND", "BAKE_DONE")):
            print(line)
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-15:])
        raise SystemExit(f"bake failed ({result.returncode}):\n{tail}")


def ensure(force: bool = False) -> None:
    """Bakes when the generated data is missing or stale; fails if it is still not fresh after."""
    fresh, said = check()
    if fresh and not force:
        print("archipelago bake:", said)
        return
    print("archipelago bake:", said, "-> baking", flush=True)
    bake()
    fresh, said = check()
    if not fresh:
        raise SystemExit(f"archipelago bake still not fresh after baking: {said}")
    print("archipelago bake:", said)


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_pack(pck: Path) -> None:
    """Refuses (SystemExit) a pack whose generated data is missing, stale or not the bake on disk."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import game_patch
    fresh, said = check()
    if not fresh:
        raise SystemExit(f"the archipelago bake is stale ({said}): run tools/build_game.ps1 (it re-bakes) and package again")
    files = game_patch.read_pck(pck)["files"]
    for name in FILES:
        entry = files.get(PACK_PREFIX + name)
        if entry is None:
            raise SystemExit(f"{pck.name} has no {PACK_PREFIX + name}: export again after tools/bake_archipelago.py")
        if entry["md5"] != _md5(GENERATED / name):
            raise SystemExit(f"{pck.name} carries an older {name} than the bake on disk: export again")
    print(f"{pck.name}: archipelago bake present and fresh ({', '.join(FILES)})")


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
