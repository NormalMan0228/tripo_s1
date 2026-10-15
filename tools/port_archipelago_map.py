"""Copy the reviewed archipelago map from labs/terrain_lab into the game project.

The lab stays the art source. This copies only what the map loads at runtime into
game/maps/archipelago and rewrites res:// paths for the new location. Imported
texture settings (.import) travel with each asset so Godot keeps the lab's
compression choices; then tools/lighten_archipelago_map.py caps the textures players
cannot see at full size. Re-run after the lab map changes, let Godot reimport
(--headless --path game --import), then re-bake the generated data
(tools/bake_archipelago.py).

The game's building_layout.gd and environment_layout.gd have grown past the lab's
(paced loading, generated collision): they are only copied with --scripts, which
overwrites those changes.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labs" / "terrain_lab"
DEST = ROOT / "game" / "maps" / "archipelago"
PREFIX = "res://maps/archipelago/"
SCRIPTS = ["building_layout.gd", "environment_layout.gd"]
SHADERS = ["water_surface", "waterfall", "waterfall_body", "waterfall_splash", "ground_surface",
           "rock_surface", "bridge_timber", "campfire"]
LAYOUTS = ["building_placements.json", "environment_layout.json"]


def rewrite(text: str, scripts: bool = False) -> str:
    text = text.replace("res://assets/", PREFIX + "assets/")
    # Lab review outputs live under the repository art folder, one level higher here.
    text = text.replace("res://../../", "res://../")
    for name in (SCRIPTS if scripts else []) + LAYOUTS + [s + ".gdshader" for s in SHADERS]:
        text = text.replace('"res://' + name, '"' + PREFIX + name)
    return text


def asset_files() -> list[Path]:
    assets = LAB / "assets"
    wanted: list[Path] = sorted(assets.glob("archipelago_terrain_environment_v1*"))
    buildings = json.loads((LAB / "building_placements.json").read_text(encoding="utf-8"))
    environment = json.loads((LAB / "environment_layout.json").read_text(encoding="utf-8"))
    fitted = {b["id"] for b in environment["bridges"] if b.get("fitted_model")}
    models = [b["model"] for b in buildings["buildings"]]
    models += [m["model"] for m in environment["models"] if m["id"] not in fitted]
    models += [b["fitted_model"] for b in environment["bridges"] if b.get("fitted_model")]
    for model in models:
        source = assets / model.removeprefix("res://assets/")
        stem = source.name.removesuffix(".glb")
        # A Tripo GLB keeps its extracted textures beside it with the model's stem.
        wanted += [p for p in source.parent.glob(stem + "*") if p.name == source.name + ".import"
                   or p.name == source.name or re.match(re.escape(stem) + r"_(Color|NormalGL|ORM|Roughness|Metallic)", p.name)]
    wanted += sorted((assets / "prop_lods").glob("*"))
    wanted += sorted((assets / "v3").glob("*"))
    wanted += sorted(p for p in (assets / "v5").glob("*") if p.is_file())
    return sorted(set(wanted))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--scripts", action="store_true", help="also overwrite the layout scripts with the lab's")
    args = parser.parse_args()
    files = asset_files()
    total = sum(p.stat().st_size for p in files)
    print(f"assets: {len(files)} files, {total / 1e9:.2f} GB")
    if args.dry_run:
        return
    for source in files:
        target = DEST / source.relative_to(LAB)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix == ".import":
            target.write_text(rewrite(source.read_text(encoding="utf-8"), args.scripts), encoding="utf-8", newline="\n")
        elif not target.exists() or target.stat().st_size != source.stat().st_size or target.stat().st_mtime < source.stat().st_mtime:
            shutil.copy2(source, target)
    for name in (SCRIPTS if args.scripts else []) + LAYOUTS + [s + ".gdshader" for s in SHADERS]:
        text = (LAB / name).read_text(encoding="utf-8")
        (DEST / name).write_text(rewrite(text, args.scripts), encoding="utf-8", newline="\n")
    print("ported to", DEST.relative_to(ROOT))
    import lighten_archipelago_map
    lighten_archipelago_map.apply()
    print("next: Godot --headless --path game --import, then tools/bake_archipelago.py")


if __name__ == "__main__":
    main()
