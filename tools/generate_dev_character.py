"""One bounded, resumable developer-owned Tripo image-to-model task.

The input is concept art, never a player's runtime request. Secrets and raw API
responses are not written or printed. An ambiguous submit is never repeated.
"""

import argparse
import asyncio
from datetime import datetime
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.config import Settings, read_tripo_key
from server.provider import ProviderError, TripoProvider


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


async def upload(provider: TripoProvider, image: Path) -> str:
    blob = image.read_bytes()
    if not blob or len(blob) > 20 * 1024 * 1024 or image.suffix.lower() not in (".png", ".jpg", ".jpeg"):
        raise ProviderError("invalid_developer_reference")
    mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
    try:
        async with httpx.AsyncClient(timeout=45, follow_redirects=False) as client:
            response = await client.post(
                provider.BASE + "/files",
                headers={"Authorization": "Bearer " + provider.settings.tripo_key},
                files={"file": (image.name, blob, mime)},
            )
        data = response.json() if response.status_code == 200 and len(response.content) < 1024 * 1024 else {}
        token = data.get("data", {}).get("file_token")
        if data.get("code") != 0 or not isinstance(token, str) or not token.startswith("file_"):
            raise ProviderError("reference_upload_failed")
        return token
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("reference_upload_failed") from None


async def reconcile(provider: TripoProvider, intent: Path) -> str:
    """Recover a submitted UUID task from billing; never submit a duplicate."""
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
            response = await client.get(
                provider.BASE + "/account/usage",
                headers={"Authorization": "Bearer " + provider.settings.tripo_key},
            )
        data = response.json() if response.status_code == 200 and len(response.content) < 1024 * 1024 else {}
        entries = data.get("data", [])
        if isinstance(entries, dict):
            entries = entries.get("items", [])
        cutoff = json.loads(intent.read_text(encoding="utf-8"))["time"] - 90
        candidates = []
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("type") != "image_to_model":
                continue
            created = datetime.fromisoformat(str(entry.get("created_at", "")).replace("Z", "+00:00")).timestamp()
            task_id = entry.get("task_id", "")
            if created >= cutoff and isinstance(task_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{8,200}", task_id):
                candidates.append(task_id)
        if len(candidates) == 1:
            return candidates[0]
    except Exception:
        pass
    raise ProviderError("ambiguous_generation_intent_no_resubmit")


async def quarantine_download(url: str, out: Path) -> int:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or parsed.port not in (None, 443) or not (
        host == "tripo3d.ai" or host.endswith(".tripo3d.ai") or host == "tripo-data.rg1.data.tripo3d.com"
    ):
        raise ProviderError("unsafe_asset_url")
    async with httpx.AsyncClient(timeout=90, follow_redirects=False) as client:
        response = await client.get(url)
    if response.status_code != 200 or not 12 < len(response.content) < 80 * 1024 * 1024:
        raise ProviderError("developer_asset_download_failed")
    if response.content[:4] != b"glTF":
        raise ProviderError("developer_asset_not_glb")
    out.write_bytes(response.content)
    return len(response.content)


async def run(args: argparse.Namespace) -> None:
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    provider = TripoProvider(Settings(tripo_key=read_tripo_key(args.key_file)))
    intent = out / "generation-intent.json"
    task_file = out / "generation-task.json"
    result_file = out / "generation-result.json"
    if result_file.exists():
        print("Existing result preserved; no new Tripo task submitted.")
        return
    if not task_file.exists():
        if intent.exists():
            task_id = await reconcile(provider, intent)
        else:
            balance = await provider.balance()
            if args.baseline - balance >= args.max_spend or balance < args.min_remaining:
                raise ProviderError("developer_credit_budget_exhausted")
            token = await upload(provider, args.image)
            payload = {
                "input": token,
                "model": args.model,
                "face_limit": args.face_limit,
                "texture": True,
                "pbr": True,
                "texture_quality": "detailed",
                "orientation": "align_image",
            }
            save(out / "generation-request.json", {k: v for k, v in payload.items() if k != "input"})
            save(intent, {"time": time.time(), "balance_before": balance, "automatic_resubmit": False})
            response = await provider.request("POST", "/generation/image-to-model", payload)
            task_id = response.get("task_id")
            if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,200}", task_id):
                raise ProviderError("upstream_schema")
        save(task_file, {"task_id": task_id})
    task_id = json.loads(task_file.read_text(encoding="utf-8"))["task_id"]
    for _ in range(240):
        task = await provider.task(task_id)
        status = task.get("status")
        if status in ("success", "failed", "cancelled"):
            break
        await asyncio.sleep(5)
    else:
        raise ProviderError("task_still_running")
    result = {
        "task_id": task_id,
        "status": status,
        "credits_consumed": task.get("credits_consumed"),
        "balance_before": json.loads(intent.read_text(encoding="utf-8"))["balance_before"],
        "balance_after": await provider.balance(),
    }
    result["balance_delta"] = result["balance_before"] - result["balance_after"]
    if status == "success":
        url = task.get("output", {}).get("model_url", "")
        try:
            blob = await provider.download(url, allow_textures=True)
            (out / "model.glb").write_bytes(blob)
            result["validated_glb_bytes"] = len(blob)
        except ProviderError as error:
            # The runtime validator intentionally rejects many large/rigged
            # meshes. Keep the trusted developer output outside the game until
            # Blender inspection and a compact export have succeeded.
            result["runtime_validation_error"] = error.code
            result["quarantined_glb_bytes"] = await quarantine_download(url, out / "model-quarantine.glb")
    save(result_file, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, default=Path.home() / "Desktop/tripo_key.txt")
    parser.add_argument("--model", default="P2-20260801")
    parser.add_argument("--face-limit", type=int, default=12000)
    parser.add_argument("--baseline", type=float, required=True)
    parser.add_argument("--max-spend", type=float, default=5000)
    parser.add_argument("--min-remaining", type=float, default=18595)
    try:
        asyncio.run(run(parser.parse_args()))
    except (ProviderError, ValueError) as error:
        print(json.dumps({"error": error.code if isinstance(error, ProviderError) else "invalid_key_file", "automatic_resubmit": False}))
        sys.exit(1)
