"""Generate the nine user-approved references as independent developer assets.

Uses the existing character budget and resumable Tripo task helper. Paid calls are
sequential; an ambiguous submission is never automatically submitted again.
No assembly, retopology, rigging, animation, or player-service publishing here.
"""
import argparse
import asyncio
import contextlib
import hashlib
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from detail_map_tripo import BASE, LEDGER, ProviderError, run, save

CHARACTER = ROOT / "art/characters/explorer_b_modular_v1"
PLAN = CHARACTER / "production-plan.json"
SELECTION = ROOT / "art/references/explorer_b_modular_v1/final_images_selection.json"
REFERENCES = SELECTION.parent / "final_images"
OUT = CHARACTER / "03_generated"
MANIFEST = OUT / "generation-manifest.json"
SETTINGS = {
    "head": ("head_skin", 30000),
    "body": ("body", 50000),
    "hand": ("hand_R", 30000),
    "hair": ("hair", 30000),
    "jacket": ("jacket", 30000),
    "shirt": ("shirt", 16000),
    "pants": ("pants", 30000),
    "boots": ("boot_R", 24000),
    "belt": ("belt", 16000),
}


@contextlib.contextmanager
def single_batch():
    """Fail closed if another copy is already paying against this budget."""
    OUT.mkdir(parents=True, exist_ok=True)
    lock_path = OUT / ".generation.lock"
    with lock_path.open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if sys.platform == "win32":
            import msvcrt
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError("another_modular_generation_batch_running") from None
        else:
            import fcntl
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ValueError("another_modular_generation_batch_running") from None
        try:
            yield
        finally:
            lock.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path):
    return path.relative_to(ROOT).as_posix()


async def generate(requested):
    plan = read(PLAN)
    stage = next(s for s in plan["stages"] if s["id"] == "references")
    if not stage["review"]["approved"]:
        raise ValueError("references_require_user_review")
    selection = read(SELECTION)
    manifest = read(MANIFEST) if MANIFEST.exists() else {
        "schema_version": 1,
        "character": "explorer_b",
        "reference_selection": relative(SELECTION),
        "date": "2026-10-04",
        "stage": "part_generation",
        "scope": "independent_component_generation_only",
        "state": "in_progress",
        "model": "P2-20260801",
        "texture": True,
        "pbr": True,
        "texture_quality": "detailed",
        "texture_model_default": "v3.0-20250812",
        "orientation": "align_image",
        "export_uv_default": True,
        "automatic_resubmit": False,
        "budget_bucket": "character_detail",
        "reservation_per_component": 150,
        "expected_credits_per_component": 120,
        "actual_credits_consumed": 0,
        "mirrored_components_created": False,
        "assembled": False,
        "rigged": False,
        "parts": {},
    }
    # Verify every approved reference before uploading or paying for any task.
    for asset in selection["assets"]:
        image = REFERENCES / asset["file"]
        if hashlib.sha256(image.read_bytes()).hexdigest() != asset["sha256"]:
            raise ValueError("approved_reference_changed")
    save(MANIFEST, manifest)
    for asset in selection["assets"]:
        key = asset["id"]
        if key not in requested:
            continue
        part_id, faces = SETTINGS[key]
        name = "explorer-modular-" + key + "-v1"
        image = REFERENCES / asset["file"]
        print(json.dumps({"part": key, "state": "start_or_resume"}), flush=True)
        await run(SimpleNamespace(bucket="character_detail", name=name,
                                  reserve=150, mode="generate", input_task=None,
                                  image=image, prompt=None, faces=faces))
        raw = BASE / "tripo/character_detail" / name
        result = read(raw / "result.json")
        if result["status"] != "success":
            raise ValueError("part_generation_failed")
        folder = OUT / key
        folder.mkdir(parents=True, exist_ok=True)
        model = folder / "model.glb"
        source = raw / "model.glb"
        shutil.copy2(source, model)
        manifest["parts"][key] = {
            "id": part_id,
            "label": asset["label"],
            "state": "generated_awaiting_review",
            "reference_image": relative(image),
            "reference_sha256": asset["sha256"],
            "model_file": relative(model),
            "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
            "bytes": model.stat().st_size,
            "requested_face_limit": faces,
            "task_id": result["task_id"],
            "credits_consumed": result["credits_consumed"],
            "request_record": relative(raw / "request.json"),
            "result_record": relative(raw / "result.json"),
            "chirality_verified": False if key in ("hand", "boots") else None,
            "fit_and_joint_topology_verified": False,
        }
        manifest["actual_credits_consumed"] = sum(
            p["credits_consumed"] for p in manifest["parts"].values()
            if isinstance(p["credits_consumed"], (int, float)))
        manifest["generated_count"] = len(manifest["parts"])
        save(MANIFEST, manifest)
        plan = read(PLAN)
        for part in plan["parts"]:
            if part["id"] == part_id:
                part["state"] = "generated_awaiting_review"
                part["mesh_path"] = relative(model)
                part["reference_images"] = [relative(image)]
        for s in plan["stages"]:
            if s["id"] == "part_generation":
                s["state"] = "in_progress"
                s["evidence"] = [relative(MANIFEST), relative(LEDGER)]
                s["outputs"] = [p["model_file"] for p in manifest["parts"].values()]
        plan["accounting"].update(new_tripo_calls=len(manifest["parts"]),
                                  new_scenario_calls=0,
                                  actual_tripo_credits=manifest["actual_credits_consumed"],
                                  current_part_generation_cost_is_measured=True)
        save(PLAN, plan)
        print(json.dumps({"part": key, "state": "saved",
                          "total_credits": manifest["actual_credits_consumed"]}), flush=True)
    if len(manifest["parts"]) == len(selection["assets"]):
        manifest["state"] = "awaiting_user_review"
        save(MANIFEST, manifest)
        plan = read(PLAN)
        plan["state"] = "independent_3d_parts_awaiting_user_review"
        plan["reference_coverage_note"] = (
            "Nine references independently generated. Hand/boot counterpart mirrors, "
            "assembly, fit, symmetry, topology, and rigging remain unverified and pending.")
        for s in plan["stages"]:
            if s["id"] == "part_generation":
                s["state"] = "awaiting_user_review"
        save(PLAN, plan)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts", nargs="+", choices=list(SETTINGS), default=list(SETTINGS))
    args = parser.parse_args()
    try:
        with single_batch():
            asyncio.run(generate(args.parts))
    except (ProviderError, ValueError) as exc:
        print(json.dumps({"error": exc.code if isinstance(exc, ProviderError)
                          else str(exc), "automatic_resubmit": False}), flush=True)
        sys.exit(1)
