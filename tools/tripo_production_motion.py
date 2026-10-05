"""One resumable, bounded developer animation experiment. Never prints secrets/URLs."""
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
from server.provider import TripoProvider, ProviderError
from tools.generate_dev_character import save, quarantine_download


async def run(args):
    args.out.mkdir(parents=True, exist_ok=True)
    provider = TripoProvider(Settings(tripo_key=read_tripo_key(Path.home()/"Desktop/tripo_key.txt")))
    intent, task_file, result_file = [args.out / n for n in ("intent.json", "task.json", "result.json")]
    if result_file.exists():
        print(result_file.read_text(encoding="utf-8"))
        return
    if not task_file.exists():
        if intent.exists():
            raise ProviderError("ambiguous_intent_no_resubmit")
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,200}", args.source):
            raise ProviderError("invalid_source")
        before = await provider.balance()
        if before - 100 < args.baseline - args.max_spend:
            raise ProviderError("developer_credit_budget_exhausted")
        payload = {"input": args.source, "animations": ["preset:biped:"+n for n in args.clips],
                   "out_format": "glb", "bake_animation": True,
                   "export_with_geometry": True, "animate_in_place": True}
        save(args.out / "request.json", payload)
        with intent.open("x", encoding="utf-8") as f:
            json.dump({"time":time.time(), "balance_before":before, "automatic_resubmit":False}, f)
        result = await provider.request("POST", "/animations/retarget", payload)
        task_id = result.get("task_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,200}", task_id):
            raise ProviderError("upstream_schema")
        save(task_file, {"task_id":task_id})
        print(json.dumps({"submitted":True,"task_id":task_id}), flush=True)
    task_id = json.loads(task_file.read_text(encoding="utf-8"))["task_id"]
    for _ in range(240):
        task = await provider.task(task_id)
        if task.get("status") in ("success", "failed", "cancelled"):
            break
        await asyncio.sleep(5)
    else:
        raise ProviderError("task_still_running")
    after = await provider.balance()
    result = {"task_id":task_id, "status":task.get("status"), "credits_consumed":task.get("credits_consumed"),
              "balance_after":after, "total_spent":args.baseline-after, "clips":args.clips}
    if task.get("status") == "success":
        output = task.get("output", {})
        result["output_fields"] = list(output)
        url = output.get("model_url")
        if isinstance(url, str):
            result["bytes"] = await quarantine_download(url, args.out/"preset-original.glb")
        else:
            # Multiple clips can be returned as named downloadable models.
            candidates=[]
            for name,value in output.items():
                if isinstance(value,str) and name.endswith("model_url"):
                    candidates.append((name,value))
                elif isinstance(value,dict):
                    for key,link in value.items():
                        if isinstance(link,str) and link.startswith("https://"):
                            candidates.append((key,link))
            for n,(name,link) in enumerate(candidates):
                result.setdefault("downloads",[]).append({"name":name,"file":f"preset-{n}.glb",
                    "bytes":await quarantine_download(link,args.out/f"preset-{n}.glb")})
            if not candidates:
                raise ProviderError("missing_animation_output")
    save(result_file,result)
    print(json.dumps(result),flush=True)

if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--clips", nargs="+", choices=["idle","walk","run"], default=["idle","walk","run"])
    p.add_argument("--baseline", type=float, required=True)
    p.add_argument("--max-spend", type=float, default=3000)
    try:
        asyncio.run(run(p.parse_args()))
    except Exception as e:
        print(json.dumps({"error":e.code if isinstance(e,ProviderError) else type(e).__name__,"automatic_resubmit":False}))
        sys.exit(1)
