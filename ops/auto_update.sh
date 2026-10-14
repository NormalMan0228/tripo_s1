#!/usr/bin/env bash
# Pull-based auto-deploy for the school server, run every 5 minutes by villagen-autoupdate.timer
# (installed once with ops/install_auto_update.sh). Only the release branch deploys: pushes to dev
# alone never touch the server.
#   sudo bash ops/auto_update.sh             # what the timer runs
#   sudo bash ops/auto_update.sh --dry-run   # say what would happen, change nothing
# When origin/<branch> has moved since the last deploy:
#   1. ops/update_online_server.sh <branch> --announce <minutes>: the in-game maintenance notice and
#      countdown, a verified backup, the new code, the API rebuilt, /health (craft limits and sign-up
#      mode stay as ops/production.env has them).
#   2. ops/notice.sh release <config/version of game/project.godot>: the "new version" notice; the
#      download address already saved on the server stays.
#   Players are logged out when the maintenance starts. Installed games from 0.11.5 then update
#   themselves at their title: publish the patch first (tools/publish_school_build.py patch), or they
#   wait on "새 버전을 준비하고 있어요" until the patch list names the version.
# A failed deploy is remembered and not retried until the branch moves again.
# The wait before maintenance: ops/release.json on the release branch ({"announce_minutes": 5}, set per
# release by tools/deploy_school.py --announce N; 0 = right away), else the timer's default
# VILLAGEN_ANNOUNCE_MINUTES (10, changed with install_auto_update.sh --announce N).
# Other setting: VILLAGEN_RELEASE_BRANCH (school-release). Log: /var/log/villagen-autoupdate.log
set -euo pipefail
cd "$(dirname "$0")/.."
branch="${VILLAGEN_RELEASE_BRANCH:-school-release}"
announce="${VILLAGEN_ANNOUNCE_MINUTES:-10}"
state=/var/lib/villagen
mkdir -p "$state"
exec 9>"$state/autoupdate.lock"
flock -n 9 || exit 0
# Any update already running (a manual one counting down or rebuilding): no check until it is done.
if [ -e /var/lib/villagen/update.lock ] && ! flock -n /var/lib/villagen/update.lock true; then exit 0; fi
# A maintenance notice is up (scheduled or running, from any source, e.g. ops/notice.sh maintenance):
# no check while players are being told about it, so it is never replaced. A server that does not
# answer is checked as usual (an update may be what brings it back).
domain=$(sed -n 's/^TRIPOTHON_DOMAIN=//p' ops/production.env 2>/dev/null | head -n 1)
if [ -n "$domain" ] && health=$(curl -fsS --max-time 10 "https://$domain/health" 2>/dev/null); then
  case "$health" in *'"notice":null'*|*'"notice": null'*) ;; *'"notice":'*) exit 0 ;; esac
fi
stamp() { date '+%Y-%m-%d %H:%M:%S'; }
if ! git fetch --quiet origin "$branch" 2>/dev/null; then
  # No release branch yet, or GitHub unreachable: try again next time, quietly.
  exit 0
fi
target=$(git rev-parse "origin/$branch")
[ "$target" = "$(cat "$state/deployed" 2>/dev/null || true)" ] && exit 0
[ "$target" = "$(cat "$state/failed" 2>/dev/null || true)" ] && exit 0
# A manual update already brought this release (or newer code that contains it): count it as
# deployed instead of checking the release out again, which would roll the server back.
if git merge-base --is-ancestor "$target" HEAD 2>/dev/null; then
  echo "$target" > "$state/deployed"
  echo "$(stamp) ${target:0:7} is already on the server (manual update); nothing to do"
  exit 0
fi
version=$(git show "origin/$branch:game/project.godot" | sed -n 's/^config\/version="\([0-9.]*\)"$/\1/p')
wanted=$(git show "origin/$branch:ops/release.json" 2>/dev/null | sed -n 's/.*"announce_minutes"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' | head -n 1)
if [ -n "$wanted" ] && [ "$wanted" -le 1440 ]; then announce="$wanted"; fi
echo "$(stamp) new release on $branch: ${target:0:7} (version ${version:-?}), maintenance in $announce min"
if [ "${1:-}" = "--dry-run" ]; then echo "$(stamp) dry run: nothing changed"; exit 0; fi
result=0
VILLAGEN_AUTO=1 bash ops/update_online_server.sh "$branch" --announce "$announce" || result=$?
if [ "$result" -eq 0 ]; then
  echo "$target" > "$state/deployed"
  rm -f "$state/failed"
  if [ -n "$version" ]; then bash ops/notice.sh release "$version" || echo "$(stamp) release notice failed"; fi
  echo "$(stamp) deployed ${target:0:7}"
elif [ "$result" -eq 75 ] || [ "$result" -eq 3 ]; then
  # 75: a manual update took over during the countdown; 3: another update was running. Not a
  # failure: the next check decides again (and skips it if the manual update already brought it).
  echo "$(stamp) ${target:0:7} postponed: another update is in charge"
  exit 0
else
  echo "$target" > "$state/failed"
  echo "$(stamp) deploy FAILED for ${target:0:7}; the server keeps its backup. Next try when $branch moves."
  exit 1
fi
