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
# Settings (environment of the timer's service): VILLAGEN_RELEASE_BRANCH (school-release),
# VILLAGEN_ANNOUNCE_MINUTES (10). Log: /var/log/villagen-autoupdate.log
set -euo pipefail
cd "$(dirname "$0")/.."
branch="${VILLAGEN_RELEASE_BRANCH:-school-release}"
announce="${VILLAGEN_ANNOUNCE_MINUTES:-10}"
state=/var/lib/villagen
mkdir -p "$state"
exec 9>"$state/autoupdate.lock"
flock -n 9 || exit 0
stamp() { date '+%Y-%m-%d %H:%M:%S'; }
if ! git fetch --quiet origin "$branch" 2>/dev/null; then
  # No release branch yet, or GitHub unreachable: try again next time, quietly.
  exit 0
fi
target=$(git rev-parse "origin/$branch")
[ "$target" = "$(cat "$state/deployed" 2>/dev/null || true)" ] && exit 0
[ "$target" = "$(cat "$state/failed" 2>/dev/null || true)" ] && exit 0
version=$(git show "origin/$branch:game/project.godot" | sed -n 's/^config\/version="\([0-9.]*\)"$/\1/p')
echo "$(stamp) new release on $branch: ${target:0:7} (version ${version:-?}), maintenance in $announce min"
if [ "${1:-}" = "--dry-run" ]; then echo "$(stamp) dry run: nothing changed"; exit 0; fi
if bash ops/update_online_server.sh "$branch" --announce "$announce"; then
  echo "$target" > "$state/deployed"
  rm -f "$state/failed"
  if [ -n "$version" ]; then bash ops/notice.sh release "$version" || echo "$(stamp) release notice failed"; fi
  echo "$(stamp) deployed ${target:0:7}"
else
  echo "$target" > "$state/failed"
  echo "$(stamp) deploy FAILED for ${target:0:7}; the server keeps its backup. Next try when $branch moves."
  exit 1
fi
