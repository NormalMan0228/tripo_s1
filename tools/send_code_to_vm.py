"""Hands the newest dev code to the school VM through a private S3 object while GitHub cannot serve it.

Bundles the commits the VM is missing (dev since BASE), uploads them to s3://<bucket>/private/ (not public), and
prints the VM commands (a short URL only the school server's IP may read). Run it yourself:
  .tools\\art-venv\\Scripts\\python.exe tools/send_code_to_vm.py [base-commit]
BASE defaults to 5498320 (2026-10-09), which the VM already has; if the VM says it lacks prerequisite commits, run
again with an older base or `--full`.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "tools" / "download_host.json").read_text(encoding="utf-8"))
KEY = "private/villagen-dev.bundle"
PAGE = f"https://{CFG['bucket']}.s3.{CFG['region']}.amazonaws.com/{CFG['prefix'].strip('/')}/index.html"


def git(*args, cwd=ROOT):
    subprocess.run(["git", *args], cwd=cwd, check=True)


def main() -> None:
    import boto3
    args = sys.argv[1:]
    base = None if "--full" in args else (args[0] if args else "5498320")
    with tempfile.TemporaryDirectory() as tmp:
        bare, bundle = Path(tmp) / "b.git", Path(tmp) / "villagen-dev.bundle"
        git("init", "-q", "--bare", str(bare))
        git("fetch", "-q", "origin", "dev")
        git("push", "-q", str(bare), "FETCH_HEAD:refs/heads/dev")
        git("bundle", "create", str(bundle), "dev", *([f"^{base}"] if base else []), cwd=bare)
        c = boto3.Session(profile_name=CFG["profile"], region_name=CFG["region"]).client("s3")
        c.upload_file(str(bundle), CFG["bucket"], KEY, ExtraArgs={"ContentType": "application/octet-stream"})
        size = bundle.stat().st_size
    # The bucket policy lets only the school server's IP read private/ (statement SchoolServerPrivateRead), so the
    # VM needs no signed link; nobody else can fetch it.
    url = f"https://{CFG['bucket']}.s3.{CFG['region']}.amazonaws.com/{KEY}"
    print(f"\nuploaded {size / 1024 ** 2:.1f}MB (private; only the school server IP can read it)\n")
    print("=== VM (EC2 Instance Connect) ===")
    print("cd ~/tripo_s1")
    print(f"curl -fL -o /tmp/villagen-dev.bundle '{url}'")
    print("sudo git bundle verify /tmp/villagen-dev.bundle")
    print("sudo git remote set-url origin /tmp/villagen-dev.bundle")
    print("sudo bash ops/update_online_server.sh dev --open-signup --per-account 0 --per-day 3 "
          "--craft-day-limit 105 --max-credits 35 --budget 4000 --welcome-stars 70")
    print("sudo git remote set-url origin https://github.com/NormalMan0228/tripo_s1.git")
    print(f"sudo bash ops/notice.sh release 0.11.3 {PAGE}")
    print("sudo bash ops/usage_key.sh")


if __name__ == "__main__":
    main()
