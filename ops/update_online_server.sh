#!/usr/bin/env bash
# Updates the Google Cloud demo server in place. Run on the VM from the repository
# checkout:
#   sudo bash ops/update_online_server.sh [branch] [--per-account N] [--per-day N]
#        [--craft-day-limit N] [--welcome-stars N] [--open-signup | --invite-only] [--signups-per-ip N]
#        [--max-credits N]   (Tripo credits one craft may spend; 10 = cheapest craft only)
# 1. Optionally writes the craft limits, welcome stars and sign-up mode into ops/production.env
#    (--per-day sets the server-wide and per-account daily limits; --craft-day-limit only the
#    server-wide one, which caps Tripo spending per day when sign-up is open).
# 2. Backs up /data (SQLite + private GLBs) and verifies the snapshot.
# 3. Checks out the branch and rebuilds only the API container.
# 4. Turns on crafting if ops/secrets/tripo-key exists (simple one-mesh craft), and the
#    LLM design step (server -> Gemini -> Tripo) if ops/secrets/gemini-key exists too.
#    Then prints /health.
# Secrets and Docker volumes are never printed or touched beyond their permissions.
set -euo pipefail
branch="main"
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
    -*) echo "Unknown option $1" >&2; exit 2 ;;
    *) branch="$1"; shift ;;
  esac
done
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
stamp="$(date +%Y%m%d-%H%M%S)"
if [ -n "$("${compose[@]}" ps -q api 2>/dev/null)" ]; then
  "${compose[@]}" exec -T api python /app/tools/backup_server.py create --data-dir /data --destination "/backups/before-update-$stamp"
  "${compose[@]}" exec -T api python /app/tools/backup_server.py verify --snapshot "/backups/before-update-$stamp"
fi
git fetch origin
git checkout "$branch"
git pull --ff-only origin "$branch"
"${compose[@]}" config --quiet
"${compose[@]}" up -d --build api
if grep -qE '^TRIPOTHON_OPEN_REGISTRATION=false' ops/production.env; then
  echo "WARNING: sign-up needs the invitation code, but the trial game has no code field." >&2
  echo "         Run again with --open-signup so players can create accounts." >&2
fi
domain="$(grep -E '^TRIPOTHON_DOMAIN=' ops/production.env | cut -d= -f2-)"
for attempt in $(seq 1 45); do
  if curl -fsS "https://$domain/health"; then echo; exit 0; fi
  sleep 2
done
echo "The API did not answer on https://$domain/health; check: ${compose[*]} logs api" >&2
exit 1
