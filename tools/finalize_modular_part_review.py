"""Verify and collect actual 3D part outputs for the user's next review gate."""
import hashlib
import json
import shutil
import struct
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
CHARACTER = ROOT / "art/characters/explorer_b_modular_v1"
OUT = CHARACTER / "03_generated"
MANIFEST = OUT / "generation-manifest.json"
LEDGER = ROOT / "artifacts/detail-map-20261003/budget.json"
ORDER = ["head", "body", "hand", "hair", "jacket", "shirt", "pants", "boots", "belt"]
VIEWS = ["front", "angle", "side", "back", "clay"]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


manifest = read(MANIFEST)
assert set(manifest["parts"]) == set(ORDER), "nine_parts_required"
ledger = read(LEDGER)["buckets"]["character_detail"]
review = {"stage": "part_generation", "state": "awaiting_user_review",
          "parts": [], "actual_tripo_credits": 0,
          "assembly_completed": False, "retopology_completed": False,
          "final_materials_completed": False, "rigging_completed": False,
          "user_approved": False}
images = OUT / "review_images"
images.mkdir(exist_ok=True)
for index, key in enumerate(ORDER, 1):
    part = manifest["parts"][key]
    folder = OUT / key
    blob = (folder / "model.glb").read_bytes()
    assert hashlib.sha256(blob).hexdigest() == part["model_sha256"], "model_changed"
    magic, version, total = struct.unpack_from("<4sII", blob)
    assert magic == b"glTF" and version == 2 and total == len(blob), "invalid_glb_container"
    length, tag = struct.unpack_from("<I4s", blob, 12)
    assert tag == b"JSON" and 20 + length <= len(blob), "invalid_glb_json"
    gltf = json.loads(blob[20:20 + length])
    assert not any("uri" in b for b in gltf.get("buffers", [])), "external_glb_buffer"
    assert not any("uri" in i for i in gltf.get("images", [])), "external_glb_image"
    assert not gltf.get("skins") and not gltf.get("animations"), "unexpected_rig_or_animation"
    assert (folder / "review.blend").is_file(), "blender_review_scene_missing"
    for view in VIEWS:
        assert (folder / ("preview-" + view + ".png")).stat().st_size > 1000, "preview_missing"
    inspection = read(folder / "mesh-inspection.json")
    assert inspection["has_uvs"] and inspection["triangles"] > 0 and inspection["textures"], "empty_inspection"
    entry = ledger["tasks"]["explorer-modular-" + key + "-v1"]
    assert entry["state"] == "success" and entry["task_id"] == part["task_id"], "task_mismatch"
    assert entry["credits_consumed"] == part["credits_consumed"], "credits_mismatch"
    reference = ROOT / part["reference_image"]
    assert hashlib.sha256(reference.read_bytes()).hexdigest() == part["reference_sha256"], "reference_changed"
    review["actual_tripo_credits"] += part["credits_consumed"]
    summary = {"part": key, "label": part["label"], "id": part["id"],
               "mesh_objects": len(inspection["mesh_objects"]), "triangles": inspection["triangles"],
               "vertices": inspection["vertices"], "credits_consumed": part["credits_consumed"],
               "preview": f"review_images/{index:02d}_{key}.png",
               "has_uvs": inspection["has_uvs"], "texture_sizes": [t["size"] for t in inspection["textures"]],
               "source_geometry_unchanged": True, "assembly_and_deformation_tested": False}
    review["parts"].append(summary)
    shutil.copy2(folder / "preview-angle.png", images / f"{index:02d}_{key}.png")
    part["mesh_inspection"] = (folder / "mesh-inspection.json").relative_to(ROOT).as_posix()
    part["review_blend"] = (folder / "review.blend").relative_to(ROOT).as_posix()
    part["previews"] = [(folder / ("preview-" + v + ".png")).relative_to(ROOT).as_posix() for v in VIEWS]
spent = sum(t.get("credits_consumed", t["reservation"]) for t in ledger["tasks"].values())
assert spent <= ledger["tripo_cap"], "character_budget_exceeded"
review["character_budget_cap"] = ledger["tripo_cap"]
review["character_budget_spent_including_prior_experiments"] = spent
review["character_budget_remaining"] = ledger["tripo_cap"] - spent
manifest["state"] = "awaiting_user_review"
manifest["actual_credits_consumed"] = review["actual_tripo_credits"]
manifest["preview_images_folder"] = images.relative_to(ROOT).as_posix()
save(MANIFEST, manifest)
save(OUT / "review-summary.json", review)
archive = CHARACTER / "Tripothon_B_3D_Parts_20261004.zip"
with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=6) as package:
    for key in ORDER:
        folder = OUT / key
        files = [folder / "model.glb", folder / "review.blend", folder / "mesh-inspection.json"]
        files += [folder / ("preview-" + view + ".png") for view in VIEWS]
        if (folder / "quality-notes.json").exists():
            files.append(folder / "quality-notes.json")
        for path in files:
            package.write(path, path.relative_to(OUT).as_posix())
    for path in [MANIFEST, OUT / "review-summary.json", *images.glob("*.png")]:
        package.write(path, path.relative_to(OUT).as_posix())
print(json.dumps({"verified_parts": len(review["parts"]), "actual_tripo_credits": review["actual_tripo_credits"],
                  "budget_remaining": review["character_budget_remaining"], "archive": str(archive),
                  "archive_bytes": archive.stat().st_size, "stage": "awaiting_user_review"}))
