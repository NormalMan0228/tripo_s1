"""Sends the current commit to the school server, which updates itself (ops/auto_update.sh, every 5 min).

  python tools/deploy_school.py --announce 5    # maintenance notice 5 minutes ahead (0 = right away)
  python tools/deploy_school.py                 # the server's default wait (10 minutes unless changed
                                                # with ops/install_auto_update.sh --announce N)
  python tools/deploy_school.py --dry-run       # show what would be pushed

Writes ops/release.json (version + wait), commits it, pushes the commit to dev and to school-release.
Uncommitted changes to tracked files (other than Godot's .import files) stop it, so only committed
work is deployed. Follow the update on /health, or on the VM: sudo bash ops/install_auto_update.sh --status
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "ops" / "release.json"


def git(*args: str, capture: bool = False) -> str:
    out = subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, encoding="utf-8",
                         stdout=subprocess.PIPE if capture else None)
    return out.stdout.strip() if capture else ""


def main() -> None:
    args = sys.argv[1:]
    dry = "--dry-run" in args
    announce = None
    if "--announce" in args:
        value = args[args.index("--announce") + 1]
        if not value.isdigit() or int(value) > 1440:
            raise SystemExit("--announce needs whole minutes from 0 to 1440")
        announce = int(value)
    dirty = git("status", "--porcelain", "--untracked-files=no", "--", ".", ":!*.import", capture=True)
    if dirty:
        raise SystemExit("commit or drop these changes first:\n" + dirty)
    version = re.search(r'config/version="([^"]+)"', (ROOT / "game" / "project.godot").read_text(encoding="utf-8")).group(1)
    release = {"version": version}
    if announce is not None: release["announce_minutes"] = announce
    old = RELEASE.read_text(encoding="utf-8") if RELEASE.exists() else ""
    new = json.dumps(release, indent=2) + "\n"
    wait = f"{announce} min" if announce is not None else "server default"
    if dry:
        print(f"would deploy {version} ({git('rev-parse', '--short', 'HEAD', capture=True)}), maintenance in {wait}")
        return
    if new != old:
        RELEASE.write_text(new, encoding="utf-8")
        git("add", str(RELEASE))
        git("commit", "-q", "-m", f"Deploy school server {version} (maintenance in {wait})",
            "-m", "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    head = git("rev-parse", "HEAD", capture=True)
    git("push", "-q", "origin", "HEAD:dev")
    # school-release only ever moves forward with dev, so this never rewrites history.
    git("push", "-q", "origin", "HEAD:refs/heads/school-release")
    print(f"school-release -> {head[:7]} ({version}); the server picks it up within 5 minutes, "
          f"then maintenance starts after {wait}.")


if __name__ == "__main__":
    main()
