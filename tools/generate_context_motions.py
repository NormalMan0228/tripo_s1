"""Resumable developer Tripo motion library; keeps task ids and exact credit usage.

Uses the account's existing credits only. A recorded POST intent without a task id
is never resubmitted automatically. Keys and signed output URLs are not logged.
"""
import argparse
import asyncio
import json
import struct
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.config import Settings, read_tripo_key
from server.provider import TripoProvider, ProviderError
from tools.generate_dev_character import quarantine_download

CLIPS = ["greet_01", "agree", "bow", "look_around", "standing_relax", "fold_arms",
         "wait", "swagger", "chop", "dig", "box_01", "hurt", "clap", "cheer",
         "warm_up", "lift_heavy", "hit_to_body_01"]


def save(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def static_donor(source, output):
    raw = source.read_bytes()
    size = struct.unpack_from("<I", raw, 12)[0]
    doc = json.loads(raw[20:20 + size])
    doc.pop("animations", None)
    doc.pop("skins", None)
    for node in doc["nodes"]:
        node.pop("skin", None)
    for mesh in doc["meshes"]:
        for primitive in mesh["primitives"]:
            for key in list(primitive["attributes"]):
                if key.startswith(("JOINTS_", "WEIGHTS_")):
                    primitive["attributes"].pop(key)
    body = json.dumps(doc, separators=(",", ":")).encode()
    body += b" " * (-len(body) % 4)
    tail = raw[20 + size:]
    output.write_bytes(struct.pack("<4sII", b"glTF", 2, 20 + len(body) + len(tail))
                       + struct.pack("<I4s", len(body), b"JSON") + body + tail)


async def job(provider, folder, route, payload):
    folder.mkdir(parents=True, exist_ok=True)
    task_file = folder / "task.json"
    result_file = folder / "result.json"
    if result_file.exists():
        result = json.loads(result_file.read_text(encoding="utf-8"))
        if result["status"] != "success":
            raise ProviderError("recorded_task_failed")
        return result
    if not task_file.exists():
        intent = folder / "intent.json"
        if intent.exists():
            raise ProviderError("ambiguous_intent_no_resubmit")
        save(folder / "request.json", payload)
        with intent.open("x", encoding="utf-8") as file:
            json.dump({"time": time.time(), "automatic_resubmit": False}, file)
        task = await provider.request("POST", route, payload)
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or "/" in task_id:
            raise ProviderError("upstream_schema")
        save(task_file, {"task_id": task_id})
        print(json.dumps({"job": folder.name, "submitted": task_id}), flush=True)
    task_id = json.loads(task_file.read_text(encoding="utf-8"))["task_id"]
    last = None
    for _ in range(240):
        task = await provider.task(task_id)
        status = task.get("status")
        if status != last:
            print(json.dumps({"job": folder.name, "status": status}), flush=True)
            last = status
        if status in ("success", "failed", "cancelled", "canceled"):
            break
        await asyncio.sleep(5)
    else:
        raise ProviderError("task_still_running")
    result = {k: task.get(k) for k in ("task_id", "status", "credits_consumed", "error_code")}
    output = task.get("output", {})
    result["output_fields"] = list(output)
    if "riggable" in output:
        result["riggable"] = output["riggable"]
        result["rig_type"] = output.get("rig_type")
    url = output.get("model_url") or output.get("model")
    if status == "success" and isinstance(url, str):
        result["bytes"] = await quarantine_download(url, folder / "motion.glb")
    save(result_file, result)
    if status != "success":
        raise ProviderError("generation_failed")
    print(json.dumps({"job": folder.name, **result}), flush=True)
    return result


async def run(args):
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    provider = TripoProvider(Settings(tripo_key=read_tripo_key(args.key_file)))
    balance_file = out / "balance-before.json"
    if not balance_file.exists():
        save(balance_file, {"balance": await provider.balance(), "time": time.time()})
    token_file = out / "upload.json"
    if not token_file.exists():
        donor = out / "donor.glb"
        static_donor(ROOT / "game/assets/m1.glb", donor)
        async with httpx.AsyncClient(timeout=90, follow_redirects=False) as client:
            response = await client.post(provider.BASE + "/files",
                headers={"Authorization": "Bearer " + provider.key},
                files={"file": ("donor.glb", donor.read_bytes(), "model/gltf-binary")})
        if response.status_code != 200:
            raise ProviderError("donor_upload_failed")
        value = response.json()
        token = value.get("data", {}).get("file_token")
        if value.get("code") != 0 or not isinstance(token, str):
            raise ProviderError("donor_upload_failed")
        save(token_file, {"file_token": token})
    token = json.loads(token_file.read_text(encoding="utf-8"))["file_token"]
    check = await job(provider, out / "rig-check", "/animations/rig-check", {"input": token})
    if not check.get("riggable"):
        raise ProviderError("donor_not_riggable")
    rig = await job(provider, out / "rig", "/animations/rig", {
        "input": token, "model": "v1.0-20240301", "rig_type": "biped",
        "spec": "mixamo", "out_format": "glb"})
    # v1 is intentional: its everyday and social presets are unavailable on v2.5/v3 rigs.
    semaphore = asyncio.Semaphore(2)
    async def motion(name):
        async with semaphore:
            if await provider.balance() < 10:
                raise ProviderError("insufficient_existing_credits")
            return await job(provider, out / name, "/animations/retarget", {
                "input": rig["task_id"], "animation": "preset:biped:" + name,
                "out_format": "glb", "export_with_geometry": True, "animate_in_place": True})
    results = await asyncio.gather(*(motion(name) for name in args.clips))
    before = json.loads(balance_file.read_text(encoding="utf-8"))["balance"]
    after = await provider.balance()
    all_clips = {p.parent.name: json.loads(p.read_text(encoding="utf-8"))
                 for p in out.glob("*/result.json") if p.parent.name not in ("rig", "rig-check")}
    save(out / "ledger.json", {"approval": "2026-10-21 user authorized available credits for contextual character/NPC animations",
        "balance_before": before, "balance_after": after, "balance_difference": before - after,
        "reported_credits": sum(float(x.get("credits_consumed") or 0) for x in [check, rig, *all_clips.values()]),
        "clips": all_clips, "rig": rig})
    print(json.dumps({"complete": len(results), "balance_before": before, "balance_after": after,
                      "balance_difference": before - after}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/context-motions-20261021")
    parser.add_argument("--key-file", type=Path, default=Path.home() / "Desktop/tripo_key.txt")
    parser.add_argument("--clips", nargs="+", choices=CLIPS, default=CLIPS)
    try:
        asyncio.run(run(parser.parse_args()))
    except Exception as error:
        print(json.dumps({"error": error.code if isinstance(error, ProviderError) else type(error).__name__,
                          "automatic_resubmit": False}), flush=True)
        sys.exit(1)
