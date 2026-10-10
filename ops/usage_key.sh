#!/usr/bin/env bash
# The read-only usage key for the PC cost monitor (tools/cost_monitor). Run on the VM from the
# repository checkout, after the server runs code that has GET /v1/ops/usage:
#   sudo bash ops/usage_key.sh            make the key if missing (printed once) and restart the API
#   sudo bash ops/usage_key.sh --show     print the existing key again
#   sudo bash ops/usage_key.sh --rotate   replace the key (the old one stops working) and restart
#   sudo bash ops/usage_key.sh --remove   delete the key, which turns the usage route off
# The key only reads aggregate totals (counts, Tripo credits, LLM tokens); it is not a player or
# admin login. It lives in ops/secrets/usage-key (git-ignored) and reaches the API as a Docker
# secret through ops/compose.usage.yaml. Restarting recreates only the API container: no code
# update, no rebuild, and the data volume stays as it is.
set -euo pipefail
action="${1:-create}"
case "$action" in
  create|--show|--rotate|--remove) ;;
  *) echo "Usage: sudo bash ops/usage_key.sh [--show | --rotate | --remove]" >&2; exit 2 ;;
esac
cd "$(dirname "$0")/.."
[ "$(id -u)" -eq 0 ] || { echo "Run it with sudo: sudo bash ops/usage_key.sh" >&2; exit 1; }
[ -f ops/production.env ] || { echo "ops/production.env is missing: set the server up first." >&2; exit 1; }
file=ops/secrets/usage-key

print_key() {
  echo
  echo "===== Cost monitor usage key: copy the next line ====="
  tr -d '\r\n' < "$file"; echo
  echo "======================================================"
  echo "Paste it into the cost monitor settings on your PC (Settings > server > usage key)."
  echo "Do not post it in chats, Git or screenshots."
}

if [ "$action" = "--show" ]; then
  [ -s "$file" ] || { echo "No usage key yet. Make one with: sudo bash ops/usage_key.sh" >&2; exit 1; }
  print_key
  exit 0
fi

created=false
if [ "$action" = "--remove" ]; then
  rm -f "$file"
  echo "Usage key removed: the cost monitor route is off after the restart."
elif [ "$action" = "--rotate" ] || [ ! -s "$file" ]; then
  umask 077
  mkdir -p ops/secrets
  tmp="$(mktemp ops/secrets/.usage-key.XXXXXX)"
  printf 'vgu_%s\n' "$(od -An -tx1 -N24 /dev/urandom | tr -d ' \n')" > "$tmp"
  mv -f "$tmp" "$file"
  created=true
  echo "Made a new usage key."
else
  echo "A usage key already exists (not printed again; --show prints it, --rotate replaces it)."
fi
if [ -f "$file" ]; then chown root:10001 "$file" && chmod 0640 "$file"; fi

# The same compose files ops/update_online_server.sh uses; only the API is recreated.
compose=(docker compose --env-file ops/production.env -f ops/compose.yaml -f ops/compose.gcp-free.yaml)
if [ -f ops/secrets/tripo-key ]; then
  compose+=(-f ops/compose.tripo.yaml)
  if [ -f ops/secrets/gemini-key ]; then compose+=(-f ops/compose.gemini.yaml); fi
fi
if [ -f "$file" ]; then compose+=(-f ops/compose.usage.yaml); fi
"${compose[@]}" config --quiet
"${compose[@]}" up -d api

domain="$(grep -E '^TRIPOTHON_DOMAIN=' ops/production.env | cut -d= -f2-)"
healthy=false
for attempt in $(seq 1 45); do
  if curl -fsS -o /dev/null "https://$domain/health"; then healthy=true; break; fi
  sleep 2
done
if [ "$healthy" != true ]; then
  echo "The API did not answer on https://$domain/health; check: ${compose[*]} logs api" >&2
  exit 1
fi
if [ -f "$file" ]; then
  # The key goes to curl on stdin, never on the command line.
  code="$(printf 'Authorization: Bearer %s\n' "$(tr -d '\r\n' < "$file")" | curl -s -o /dev/null -w '%{http_code}' -H @- "https://$domain/v1/ops/usage" || true)"
  case "$code" in
    200) echo "Usage route OK: https://$domain/v1/ops/usage" ;;
    404) echo "The server code has no usage route yet. Update it first (ops/update_online_server.sh with your usual options), then run this again." >&2 ;;
    *) echo "The usage route answered $code; check: ${compose[*]} logs api" >&2 ;;
  esac
fi
if [ "$created" = true ]; then print_key; fi
