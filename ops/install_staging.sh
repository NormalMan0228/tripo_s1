#!/usr/bin/env bash
# One-time setup of the development (staging) server on the school VM, next to production:
#   sudo bash ops/install_staging.sh            # install, or repair/refresh (safe to run again)
#   sudo bash ops/install_staging.sh --status   # same as: sudo bash ops/staging.sh status
#   sudo bash ops/install_staging.sh --remove   # stop it: timer, container and dev.<domain> site go,
#                                               # its checkout and data stay (install again to resume)
#   sudo bash ops/install_staging.sh --remove --purge   # also delete its data, image and checkout
# Run it from the school server checkout (~/tripo_s1, the one with ops/production.env). It:
#   1. clones the dev branch into /opt/villagen-staging (a separate checkout: production's working
#      copy and its school-release deploys are never touched);
#   2. writes ops/staging.env and a new invitation code there (not production's);
#   3. once, restarts the production proxy (Caddy) so it joins the villagen_staging_edge network and
#      reads ops/caddy-sites/ (2-5 seconds; asked first) - only if it does not already;
#   4. builds and starts the development API (fake crafting), then adds dev.<domain> to Caddy with a
#      graceful reload (production keeps its connections; a bad config leaves the old one running);
#   5. installs villagen-staging-update.timer: every 5 minutes, a new commit on origin/dev rebuilds
#      only the development container (no maintenance notice). Log: /var/log/villagen-staging-update.log
# Options: --yes (no questions), VILLAGEN_STAGING_DIR=/path (default /opt/villagen-staging).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "sudo bash ops/install_staging.sh 처럼 sudo 를 붙여 주세요." >&2; exit 1; }
prod=$(cd "$(dirname "$0")/.." && pwd -P)
stage="${VILLAGEN_STAGING_DIR:-/opt/villagen-staging}"
state="${VILLAGEN_STAGING_STATE:-/var/lib/villagen-staging}"
unit="${VILLAGEN_SYSTEMD_DIR:-/etc/systemd/system}/villagen-staging-update"
log="${VILLAGEN_STAGING_LOG:-/var/log/villagen-staging-update.log}"
site_file="$prod/ops/caddy-sites/staging.caddy"
action=install
yes=""
purge=""
for arg in "$@"; do
  case "$arg" in
    --status) action=status ;;
    --remove) action=remove ;;
    --purge) purge=yes ;;
    --yes|-y) yes=yes ;;
    *) echo "모르는 옵션: $arg" >&2; exit 2 ;;
  esac
done

if [ ! -f "$prod/ops/production.env" ]; then
  echo "학교 서버 폴더(ops/production.env 가 있는 곳, 보통 ~/tripo_s1)에서 실행해 주세요: cd ~/tripo_s1" >&2
  exit 1
fi
mkdir -p "$(dirname "$stage")"
if [ -e "$stage" ] && [ "$(cd "$stage" && pwd -P)" = "$prod" ]; then
  echo "개발 서버 폴더($stage)가 학교 서버 폴더와 같아요. VILLAGEN_STAGING_DIR 를 다른 곳으로 해 주세요." >&2
  exit 1
fi
# The production project exactly as ops/update_online_server.sh runs it (the proxy part is what we need).
pcompose=(docker compose --env-file "$prod/ops/production.env" -f "$prod/ops/compose.yaml" -f "$prod/ops/compose.gcp-free.yaml")
caddy_reload() {
  "${pcompose[@]}" exec -T proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
}
ask() {
  [ -n "$yes" ] && return 0
  local answer
  read -r -p "$1 [y/N] " answer
  [ "$answer" = "y" ] || [ "$answer" = "Y" ]
}

case "$action" in
  status)
    exec bash "$prod/ops/staging.sh" status ;;
  remove)
    systemctl disable --now villagen-staging-update.timer 2>/dev/null || true
    rm -f "$unit.service" "$unit.timer"
    systemctl daemon-reload
    if [ -f "$site_file" ]; then
      rm -f "$site_file"
      caddy_reload >/dev/null 2>&1 && echo "dev 주소를 Caddy에서 뺐어요(학교 서버 연결은 그대로)." \
        || echo "Caddy 설정을 다시 읽지 못했어요. 학교 서버는 그대로 동작합니다." >&2
    fi
    if [ -f "$stage/ops/compose.staging.yaml" ]; then
      docker compose -p villagen-staging --project-directory "$stage/ops" -f "$stage/ops/compose.staging.yaml" \
        --env-file "$stage/ops/staging.env" down 2>/dev/null || true
    fi
    if [ -z "$purge" ]; then
      echo "개발 서버를 껐어요. 데이터와 체크아웃($stage)은 남겨 두었어요. 다시 켜기: sudo bash ops/install_staging.sh"
    else
      ask "개발 서버의 데이터(villagen_staging_data), 이미지, 체크아웃($stage)까지 지울까요? 학교 서버는 그대로입니다." \
        || { echo "데이터는 남겨 두었어요."; exit 0; }
      docker volume rm villagen_staging_data villagen_staging_backups >/dev/null 2>&1 || true
      docker image rm villagen-staging-api >/dev/null 2>&1 || true
      # Only a directory that really is the development checkout.
      if [ -f "$stage/ops/compose.staging.yaml" ] && [ -d "$stage/.git" ] && [ "$(cd "$stage" && pwd -P)" != "/" ]; then
        rm -rf "$stage"
      fi
      rm -rf "$state"
      echo "개발 서버의 데이터와 체크아웃을 지웠어요."
    fi
    exit 0 ;;
esac

# --- install / refresh -------------------------------------------------------------------------
domain="$(sed -n 's/^TRIPOTHON_DOMAIN=//p' "$prod/ops/production.env" | tail -n 1)"
[ -n "$domain" ] || { echo "ops/production.env 에 TRIPOTHON_DOMAIN 이 없어요." >&2; exit 1; }
# Production must already know about the development server (this commit or later on its branch).
if ! grep -q 'villagen_staging_edge' "$prod/ops/compose.yaml" || ! grep -q '^import /etc/caddy/sites/' "$prod/ops/Caddyfile"; then
  echo "학교 서버 폴더($prod)가 아직 개발 서버를 모르는 버전이에요." >&2
  echo "개발 서버 기능이 들어간 학교 서버 업데이트가 끝난 뒤 다시 실행해 주세요. 아무것도 바꾸지 않았어요." >&2
  exit 1
fi
proxy="$("${pcompose[@]}" ps -q proxy 2>/dev/null || true)"
[ -n "$proxy" ] || { echo "학교 서버의 Caddy(proxy)가 꺼져 있어요. 학교 서버를 먼저 켜 주세요." >&2; exit 1; }

# 1. The development checkout (dev branch only, shallow: it only ever moves forward to origin/dev).
if [ ! -d "$stage/.git" ]; then
  url="$(git -c safe.directory="$prod" -C "$prod" remote get-url origin)"
  echo "dev 브랜치를 $stage 에 받습니다 ($url)"
  git clone --quiet --depth 1 --branch dev --single-branch "$url" "$stage"
else
  git -C "$stage" fetch --quiet origin dev && git -C "$stage" reset --quiet --hard origin/dev
fi
for needed in ops/compose.staging.yaml ops/staging.env.example ops/staging.sh; do
  [ -f "$stage/$needed" ] || { echo "dev 브랜치에 $needed 가 아직 없어요. dev 에 개발 서버 파일이 올라간 뒤 다시 실행해 주세요." >&2; exit 1; }
done

# 2. Its own settings and invitation code (production's ops/secrets is only read in real mode).
if [ ! -f "$stage/ops/staging.env" ]; then
  cp "$stage/ops/staging.env.example" "$stage/ops/staging.env"
fi
if grep -qE '^VILLAGEN_PROD_DIR=' "$stage/ops/staging.env"; then
  sed -i "s|^VILLAGEN_PROD_DIR=.*|VILLAGEN_PROD_DIR=$prod|" "$stage/ops/staging.env"
else
  echo "VILLAGEN_PROD_DIR=$prod" >> "$stage/ops/staging.env"
fi
chmod 0644 "$stage/ops/staging.env"
install -d -m 0700 -o root -g root "$stage/ops/staging-secrets"
if [ ! -s "$stage/ops/staging-secrets/registration-code" ]; then
  (umask 077; python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "$stage/ops/staging-secrets/registration-code")
fi
chown root:10001 "$stage/ops/staging-secrets/registration-code"
chmod 0640 "$stage/ops/staging-secrets/registration-code"

# 3. The proxy: on the staging network and reading ops/caddy-sites/ (a container made from an older
#    compose.yaml/Caddyfile needs one restart; certificates stay in its caddy_data volume).
proxy_ready() {
  local id="$1"
  docker inspect -f '{{range $name, $net := .NetworkSettings.Networks}}{{$name}} {{end}}' "$id" | grep -qw villagen_staging_edge &&
    docker exec "$id" test -d /etc/caddy/sites &&
    docker exec "$id" grep -q '^import /etc/caddy/sites/' /etc/caddy/Caddyfile
}
mkdir -p "$prod/ops/caddy-sites"
if ! proxy_ready "$proxy"; then
  echo "학교 서버의 HTTPS 입구(Caddy)를 한 번 다시 켜야 개발 서버 주소를 붙일 수 있어요."
  echo "그동안 2~5초 학교 서버 접속이 끊길 수 있어요(게임은 스스로 다시 연결합니다). 플레이어가 적을 때 하세요."
  ask "지금 Caddy를 다시 켤까요?" || { echo "취소했어요. 아무것도 켜지 않았어요(체크아웃만 받아 두었어요)."; exit 1; }
  (cd "$prod" && "${pcompose[@]}" up -d --no-deps --no-build --force-recreate proxy)
  proxy="$("${pcompose[@]}" ps -q proxy)"
  proxy_ready "$proxy" || { echo "Caddy가 개발 서버 네트워크에 붙지 않았어요. 학교 서버는 동작합니다. 저에게 알려 주세요." >&2; exit 1; }
  healthy=""
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 5 "https://$domain/health" >/dev/null 2>&1; then healthy=yes; break; fi
    sleep 2
  done
  if [ -n "$healthy" ]; then echo "Caddy를 다시 켰어요. 학교 서버 /health 정상."
  else echo "Caddy를 다시 켰지만 학교 서버 /health 가 아직 응답하지 않아요. 확인: curl https://$domain/health" >&2; fi
fi

# 4. The development API (first build: a few minutes), then its site with a graceful reload.
export VILLAGEN_STAGING_DIR="$stage"
rm -f "$state/failed"
bash "$prod/ops/staging.sh" update --force
cat > "$site_file.tmp" <<'EOF'
# The development server (ops/install_staging.sh). Remove with: sudo bash ops/install_staging.sh --remove
dev.{$TRIPOTHON_DOMAIN} {
    header Strict-Transport-Security "max-age=31536000"
    reverse_proxy staging-api:8765
}
EOF
mv "$site_file.tmp" "$site_file"
if ! caddy_reload; then
  rm -f "$site_file"
  caddy_reload >/dev/null 2>&1 || true
  echo "Caddy가 dev 주소 설정을 받아들이지 않아 되돌렸어요. 학교 서버는 그대로입니다. 저에게 알려 주세요." >&2
  exit 1
fi

# 5. Follow origin/dev every 5 minutes (production's own timer and checkout stay as they are).
cat > "$unit.service" <<EOF
[Unit]
Description=Villagen development server: rebuild from the dev branch
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
Environment=VILLAGEN_STAGING_DIR=$stage
ExecStart=/bin/bash $prod/ops/staging.sh update
StandardOutput=append:$log
StandardError=append:$log
TimeoutStartSec=3600
Nice=10
EOF
cat > "$unit.timer" <<EOF
[Unit]
Description=Check the dev branch for the development server every 5 minutes

[Timer]
OnBootSec=4min
OnUnitActiveSec=5min
Unit=villagen-staging-update.service

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now villagen-staging-update.timer >/dev/null

echo "개발 서버 주소: https://dev.$domain  (처음에는 인증서를 받느라 1~2분 걸릴 수 있어요)"
for _ in $(seq 1 40); do
  if curl -fsS --max-time 5 "https://dev.$domain/health"; then echo; break; fi
  sleep 3
done
echo "제작은 가짜(fake, 비용 0)로 시작해요. 진짜 Tripo: sudo bash ops/staging.sh real --budget 300"
echo "dev 브랜치에 push 하면 5분 안에 개발 서버만 다시 만들어집니다(공지 없음)."
echo "상태 보기: sudo bash ops/staging.sh status"
