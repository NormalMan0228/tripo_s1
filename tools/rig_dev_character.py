"""Resumable, budget-limited developer rigging. No credentials or signed URLs in artifacts."""
import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.config import Settings, read_tripo_key
from server.provider import ProviderError, TripoProvider
from tools.generate_dev_character import quarantine_download, save


async def run(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    provider = TripoProvider(Settings(tripo_key=read_tripo_key(args.key_file)))
    stage = args.operation
    task_file = out / (stage + "-task.json")
    intent_file = out / (stage + "-intent.json")
    result_file = out / (stage + "-result.json")
    if result_file.exists():
        print(json.dumps(json.loads(result_file.read_text(encoding="utf-8"))))
        return
    if not task_file.exists():
        if intent_file.exists():
            raise ProviderError("ambiguous_rig_intent_no_resubmit")
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,200}", args.source):
            raise ProviderError("invalid_source_task")
        if stage == "rig":
            check = out / "rigcheck-result.json"
            if not check.exists() or not json.loads(check.read_text(encoding="utf-8")).get("riggable"):
                raise ProviderError("rig_check_required")
        balance = await provider.balance()
        # Reserve 100 credits before each operation; do not approach the cap.
        floor = args.baseline - args.max_spend
        if balance - 100 < floor:
            raise ProviderError("developer_credit_budget_exhausted")
        payload = {"input": args.source}
        route = "/animations/rig-check"
        if stage == "rig":
            route = "/animations/rig"
            payload.update(model="v1.0-20240301", rig_type="biped", spec="tripo", out_format="glb")
        save(out / (stage + "-request.json"), payload)
        # Exclusive durable intent precedes the paid request. Never auto-resubmit.
        with intent_file.open("x", encoding="utf-8") as f:
            json.dump({"time": time.time(), "balance_before": balance, "automatic_resubmit": False}, f)
        data = await provider.request("POST", route, payload)
        task_id = data.get("task_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,200}", task_id):
            raise ProviderError("upstream_schema")
        save(task_file, {"task_id": task_id})
    task_id = json.loads(task_file.read_text(encoding="utf-8"))["task_id"]
    for _ in range(240):
        task = await provider.task(task_id)
        if task.get("status") in ("success", "failed", "cancelled"):
            break
        await asyncio.sleep(5)
    else:
        raise ProviderError("task_still_running")
    before = json.loads(intent_file.read_text(encoding="utf-8"))["balance_before"]
    after = await provider.balance()
    result = {"task_id": task_id, "status": task.get("status"), "credits_consumed": task.get("credits_consumed"),
              "balance_before": before, "balance_after": after, "balance_delta": before-after,
              "update_total_spent": args.baseline-after}
    output = task.get("output", {})
    if stage == "rigcheck":
        result.update(riggable=output.get("riggable", False), rig_type=output.get("rig_type"))
    elif task.get("status") == "success":
        result["glb_bytes"] = await quarantine_download(output.get("model_url", ""), out / "rig-original.glb")
    save(result_file, result)
    print(json.dumps(result))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=("rigcheck", "rig"))
    p.add_argument("--source", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--key-file", type=Path, default=Path.home()/"Desktop/tripo_key.txt")
    p.add_argument("--baseline", type=float, default=23595)
    p.add_argument("--max-spend", type=float, default=5000)
    try:
        asyncio.run(run(p.parse_args()))
    except Exception as e:
        print(json.dumps({"error": e.code if isinstance(e, ProviderError) else type(e).__name__, "automatic_resubmit": False}))
        sys.exit(1)
