"""Sends the current commit to the school server, which updates itself (ops/auto_update.sh, every 5 min).

  python tools/deploy_school.py --announce 5    # maintenance notice 5 minutes ahead (0 = right away)
  python tools/deploy_school.py                 # the server's default wait (10 minutes unless changed
                                                # with ops/install_auto_update.sh --announce N)
  python tools/deploy_school.py --dry-run       # show what would be pushed
  python tools/deploy_school.py --message "0.11.9.1 업데이트: 옷장 새 화면"   # the patch message in the
                                                # maintenance notice (up to 120 characters)
  python tools/deploy_school.py --block-older   # also make this version the minimum: older games
                                                # cannot sign in and are sent to update (patch or
                                                # installer); --min-version X sets another minimum

Writes ops/release.json (version + wait, optional min_version), commits it, pushes the commit to dev
and to school-release. After deploying, the server's `notice.sh release <version>` also applies
min_version (ops/notice.sh).
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
    minimum = None
    if "--min-version" in args:
        minimum = args[args.index("--min-version") + 1]
        if not re.fullmatch(r"\d+(\.\d+){1,3}", minimum):
            raise SystemExit("--min-version needs a version like 0.11.6")
    dirty = git("status", "--porcelain", "--untracked-files=no", "--", ".", ":!*.import", capture=True)
    if dirty:
        raise SystemExit("commit or drop these changes first:\n" + dirty)
    version = re.search(r'config/version="([^"]+)"', (ROOT / "game" / "project.godot").read_text(encoding="utf-8")).group(1)
    release = {"version": version}
    if announce is not None: release["announce_minutes"] = announce
    if "--block-older" in args: minimum = version
    if minimum is not None: release["min_version"] = minimum
    # The patch message players read in the maintenance notice (ops/update_online_server.sh).
    if "--message" in args:
        message = " ".join(args[args.index("--message") + 1].split()).replace('"', "'").replace("\\", "/")
        if not 0 < len(message) <= 120:
            raise SystemExit("--message needs 1 to 120 characters")
        release["message"] = message
    old = RELEASE.read_text(encoding="utf-8") if RELEASE.exists() else ""
    new = json.dumps(release, indent=2, ensure_ascii=False) + "\n"
    wait = f"{announce} min" if announce is not None else "server default"
    if minimum is not None: wait += f", minimum game {minimum}"
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
