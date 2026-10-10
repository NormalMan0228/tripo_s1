#!/usr/bin/env bash
# Updates the Google Cloud demo server in place. Run on the VM from the repository
# checkout:
#   sudo bash ops/update_online_server.sh [branch] [--per-account N] [--per-day N]
#        [--craft-day-limit N] [--welcome-stars N] [--open-signup | --invite-only] [--signups-per-ip N]
#        [--max-credits N]   (Tripo credits one craft may spend; 10 = cheapest craft only)
#        [--budget N]        (Tripo credits this server may spend in total; 0 = no budget)
#        [--announce N]      (warn players first: maintenance starts in N minutes, the terminal
#                             counts down, then the update runs and the notice is cleared once
#                             /health answers again; Ctrl+C during the countdown cancels both)
#        [--downtime N]      (minutes the announcement says the update takes; default 5)
# 1. Optionally writes the craft limits, welcome stars and sign-up mode into ops/production.env
#    (--per-day sets the server-wide and per-account daily limits; --craft-day-limit only the
#    server-wide one, which caps Tripo spending per day when sign-up is open).
# 2. With --announce, schedules the maintenance notice (ops/notice.sh) and waits for it.
# 3. Backs up /data (SQLite + private GLBs) and verifies the snapshot.
# 4. Checks out the branch and rebuilds only the API container.
# 5. Turns on crafting if ops/secrets/tripo-key exists (simple one-mesh craft), and the
#    LLM design step (server -> Gemini -> Tripo) if ops/secrets/gemini-key exists too, and the
#    cost monitor's read-only usage route if ops/secrets/usage-key exists (ops/usage_key.sh).
#    Then prints /health.
# Secrets and Docker volumes are never printed or touched beyond their permissions.
set -euo pipefail
branch="main"
announce=""
downtime="5"
declare -A limits=()
while [ $# -gt 0 ]; do
  case "$1" in
    --per-account) limits[TRIPO_USER_TOTAL_REQUEST_LIMIT]="$2"; shift 2 ;;
    --per-day) limits[TRIPO_DAILY_REQUEST_LIMIT]="$2"; limits[TRIPO_USER_DAILY_REQUEST_LIMIT]="$2"; shift 2 ;;
    --welcome-stars) limits[TRIPOTHON_WELCOME_STARS]="$2"; shift 2 ;;
    --craft-day-limit) limits[TRIPO_DAILY_REQUEST_LIMIT]="$2"; shift 2 ;;
    --open-signup) limits[TRIPOTHON_OPEN_REGISTRATION]="true"; shift ;;
    --invite-only) limits[TRIPOTHON_OPEN_REGISTRATION]="false"; shift ;;
    --signups-per-ip) limits[TRIPOTHON_SIGNUPS_PER_IP_DAY]="$2"; shift 2 ;;
    --max-credits) limits[TRIPOTHON_MAX_CREDITS_PER_CRAFT]="$2"; shift 2 ;;
    --budget) limits[TRIPOTHON_TRIPO_CREDIT_BUDGET]="$2"; shift 2 ;;
    --announce) announce="$2"; shift 2 ;;
    --downtime) downtime="$2"; shift 2 ;;
    -*) echo "Unknown option $1" >&2; exit 2 ;;
    *) branch="$1"; shift ;;
  esac
done
if [ -n "$announce" ] && ! [[ "$announce" =~ ^[0-9]+$ && "$announce" -le 1440 ]]; then
  echo "--announce 뒤에는 0~1440 사이의 분을 적어 주세요. 예) --announce 10" >&2; exit 2
fi
[[ "$downtime" =~ ^[0-9]+$ && "$downtime" -ge 1 && "$downtime" -le 1440 ]] || { echo "--downtime 은 1~1440 분이에요." >&2; exit 2; }
cd "$(dirname "$0")/.."
for key in "${!limits[@]}"; do
  value="${limits[$key]}"
  [[ "$value" =~ ^([0-9]+|true|false)$ ]] || { echo "$key must be a whole number" >&2; exit 2; }
  if grep -qE "^$key=" ops/production.env; then sed -i "s/^$key=.*/$key=$value/" ops/production.env
  else echo "$key=$value" >> ops/production.env; fi
  echo "Set $key=$value"
done
compose=(docker compose --env-file ops/production.env -f ops/compose.yaml -f ops/compose.gcp-free.yaml)
if [ -f ops/secrets/tripo-key ]; then
  chown root:10001 ops/secrets/tripo-key && chmod 0640 ops/secrets/tripo-key
  compose+=(-f ops/compose.tripo.yaml)
  echo "Tripo key found: crafting will be enabled."
  if [ -f ops/secrets/gemini-key ]; then
    chown root:10001 ops/secrets/gemini-key && chmod 0640 ops/secrets/gemini-key
    compose+=(-f ops/compose.gemini.yaml)
    echo "Gemini key found: crafting designs each object with Gemini before Tripo."
  fi
else
  echo "No ops/secrets/tripo-key: the server stays without paid crafting."
fi
# Read-only usage totals for the PC cost monitor (made by: sudo bash ops/usage_key.sh).
if [ -f ops/secrets/usage-key ]; then
  chown root:10001 ops/secrets/usage-key && chmod 0640 ops/secrets/usage-key
  compose+=(-f ops/compose.usage.yaml)
  echo "Usage key found: the cost monitor can read usage totals."
fi
policy() { "${compose[@]}" exec -T api python -m server.client_policy "$@"; }
running="$("${compose[@]}" ps -q api 2>/dev/null || true)"
announced=""
replaced=""
# A stop before the new server runs leaves the old one serving: end the maintenance again.
leave() {
  local status=$?
  if [ "$status" -ne 0 ] && [ -n "$announced" ] && [ -z "$replaced" ]; then
    echo "업데이트가 중간에 멈췄어요. 서버는 그대로이니 점검 공지를 지웁니다." >&2
    policy cancel >/dev/null || echo "공지를 지우지 못했어요. sudo bash ops/notice.sh cancel 을 실행해 주세요." >&2
  fi
}
trap leave EXIT
if [ -n "$announce" ]; then
  if [ -z "$running" ]; then
    echo "서버가 꺼져 있어서 공지 없이 바로 업데이트합니다."
  elif ! policy maintenance --in "$announce" --minutes "$downtime" --hold --message "서버 업데이트가 있어요." >/dev/null; then
    echo "지금 서버는 공지 기능이 없는 옛 버전이에요. 이번 한 번은 --announce 없이 업데이트해 주세요." >&2
    exit 2
  else
    announced="yes"
    trap 'echo; echo "취소했어요. 점검 공지를 지웁니다."; announced=""; policy cancel >/dev/null || true; exit 130' INT TERM
    if [ "$announce" -eq 0 ]; then echo "지금 바로 점검을 시작해요(약 ${downtime}분)."
    else echo "플레이어에게 ${announce}분 뒤 점검(약 ${downtime}분)을 알렸어요. 게임에는 30분 전부터 남은 시간이 떠요."; fi
    finish=$(( $(date +%s) + announce * 60 ))
    while :; do
      left=$(( finish - $(date +%s) ))
      [ "$left" -le 0 ] && break
      printf '\r점검 시작까지 %d분 %02d초  (Ctrl+C: 업데이트와 공지 취소)   ' $(( left / 60 )) $(( left % 60 ))
      sleep 1
    done
    # A moment past the start, so every reply is already "점검 중" before the backup.
    sleep 2
    trap - INT TERM
    echo
    echo "점검을 시작했어요. 업데이트하는 동안 플레이어 접속을 막아 둡니다."
  fi
fi
stamp="$(date +%Y%m%d-%H%M%S)"
if [ -n "$running" ]; then
  "${compose[@]}" exec -T api python /app/tools/backup_server.py create --data-dir /data --destination "/backups/before-update-$stamp"
  "${compose[@]}" exec -T api python /app/tools/backup_server.py verify --snapshot "/backups/before-update-$stamp"
fi
git fetch origin
git checkout "$branch"
git pull --ff-only origin "$branch"
"${compose[@]}" config --quiet
# /health shows this commit next to the release version (config/version of game/project.godot).
VILLAGEN_SERVER_COMMIT="$(git rev-parse --short HEAD)" "${compose[@]}" up -d --build api
replaced="yes"
if grep -qE '^TRIPOTHON_OPEN_REGISTRATION=false' ops/production.env; then
  echo "WARNING: sign-up needs the invitation code, but the trial game has no code field." >&2
  echo "         Run again with --open-signup so players can create accounts." >&2
fi
domain="$(grep -E '^TRIPOTHON_DOMAIN=' ops/production.env | cut -d= -f2-)"
for attempt in $(seq 1 45); do
  if curl -fsS "https://$domain/health"; then
    echo
    if [ -n "$announced" ]; then
      if policy cancel >/dev/null; then echo "점검을 끝냈어요. 플레이어가 다시 들어올 수 있어요."
      else echo "점검 공지를 지우지 못했어요. sudo bash ops/notice.sh cancel 을 실행해 주세요." >&2; fi
    fi
    exit 0
  fi
  sleep 2
done
echo "The API did not answer on https://$domain/health; check: ${compose[*]} logs api" >&2
if [ -n "$announced" ]; then
  echo "점검 공지는 그대로 두었어요(플레이어 접속 막힘). 서버를 확인한 뒤 sudo bash ops/notice.sh cancel 로 끝내 주세요." >&2
fi
exit 1
