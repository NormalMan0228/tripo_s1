#!/usr/bin/env bash
# Updates the Google Cloud demo server in place. Run on the VM from the repository
# checkout:   sudo bash ops/update_online_server.sh [branch]
# 1. Backs up /data (SQLite + private GLBs) and verifies the snapshot.
# 2. Checks out the branch and rebuilds only the API container.
# 3. Turns on crafting if ops/secrets/tripo-key exists (simple one-mesh craft;
#    no OpenAI key needed), then prints /health.
# Secrets, ops/production.env and Docker volumes are never touched.
set -euo pipefail
branch="${1:-main}"
cd "$(dirname "$0")/.."
compose=(docker compose --env-file ops/production.env -f ops/compose.yaml -f ops/compose.gcp-free.yaml)
if [ -f ops/secrets/tripo-key ]; then
  chown root:10001 ops/secrets/tripo-key && chmod 0640 ops/secrets/tripo-key
  compose+=(-f ops/compose.tripo.yaml)
  echo "Tripo key found: crafting will be enabled."
else
  echo "No ops/secrets/tripo-key: the server stays without paid crafting."
fi
stamp="$(date +%Y%m%d-%H%M%S)"
"${compose[@]}" exec -T api python /app/tools/backup_server.py create --data-dir /data --destination "/backups/before-update-$stamp"
"${compose[@]}" exec -T api python /app/tools/backup_server.py verify --snapshot "/backups/before-update-$stamp"
git fetch origin
git checkout "$branch"
git pull --ff-only origin "$branch"
"${compose[@]}" config --quiet
"${compose[@]}" up -d --build api
domain="$(grep -E '^TRIPOTHON_DOMAIN=' ops/production.env | cut -d= -f2-)"
for attempt in $(seq 1 30); do
  if curl -fsS "https://$domain/health"; then echo; exit 0; fi
  sleep 2
done
echo "The API did not answer on https://$domain/health; check: ${compose[*]} logs api" >&2
exit 1
