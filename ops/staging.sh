#!/usr/bin/env bash
# 개발 서버(dev 브랜치, https://dev.<학교 서버 주소>) 관리. 학교 서버 폴더에서 실행합니다(cd ~/tripo_s1).
# 처음 설치는 한 번만: sudo bash ops/install_staging.sh
# 개발 서버는 /opt/villagen-staging 의 별도 체크아웃, 별도 컨테이너(villagen-staging), 별도 데이터
# (villagen_staging_data), 별도 초대 코드를 씁니다. 학교 서버의 데이터와 컨테이너는 건드리지 않습니다.
set -euo pipefail

usage() {
  cat <<'HELP'
사용법 (cd ~/tripo_s1 다음에):

  sudo bash ops/staging.sh status
      주소, 제작 방식(fake/real), 배포된 커밋, 메모리, /health, 자동 업데이트 기록을 봅니다.

  sudo bash ops/staging.sh logs [줄 수 | -f | update]
      개발 서버 로그(기본 200줄). -f 는 계속 보기(Ctrl+C로 끝), update 는 자동 업데이트 기록.

  sudo bash ops/staging.sh fake
      가짜 제작(기본값): Tripo 대신 서버 안의 대역이 바로 샘플 모양을 돌려줍니다. 키를 넣지 않고 비용 0.

  sudo bash ops/staging.sh real --budget 300 [--max-credits 10] [--no-gemini]
      진짜 Tripo로 제작합니다(학교 서버의 키 파일을 읽기 전용으로 씀). --budget 은 개발 서버가 쓸 수 있는
      Tripo 크레딧 총량(1~2000, 필수), --max-credits 는 한 번 제작의 최대 크레딧(기본 10).
      Gemini 키가 있으면 설계에 Gemini도 씁니다(--no-gemini 로 끔).

  sudo bash ops/staging.sh reset [--yes]
      개발 서버 데이터(계정, 마을, 만든 물건, 제작 기록과 예산 사용량)를 모두 지우고 새로 시작합니다.

  sudo bash ops/staging.sh stop | start
      개발 서버를 잠시 끄거나(자동 업데이트도 멈춤) 다시 켭니다. 메모리가 부족할 때 씁니다.

  sudo bash ops/staging.sh update [--force]
      dev 브랜치가 바뀌었으면 개발 서버만 다시 만듭니다(자동 업데이트가 5분마다 실행하는 것).
      --force 는 바뀌지 않았어도, 실패했던 커밋도 다시 만듭니다.

  sudo bash ops/staging.sh admin <이름> [<이름> ...]
      개발 서버에만 있는 관리자 계정을 만들거나 비밀번호를 바꿉니다(비밀번호는 화면에서 입력).
HELP
}

command="${1:-help}"
[ $# -gt 0 ] && shift
case "$command" in
  status|logs|fake|real|reset|stop|start|update|admin) ;;
  help|-h|--help) usage; exit 0 ;;
  *) usage; exit 2 ;;
esac
[ "$(id -u)" -eq 0 ] || { echo "sudo bash ops/staging.sh $command 처럼 sudo 를 붙여 주세요." >&2; exit 1; }

stage="${VILLAGEN_STAGING_DIR:-/opt/villagen-staging}"
state="${VILLAGEN_STAGING_STATE:-/var/lib/villagen-staging}"
envfile="$stage/ops/staging.env"
updatelog="${VILLAGEN_STAGING_LOG:-/var/log/villagen-staging-update.log}"
project=villagen-staging
stamp() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "$(stamp) $*"; }
if [ ! -f "$envfile" ] || [ ! -f "$stage/ops/compose.staging.yaml" ]; then
  echo "개발 서버가 아직 설치되지 않았어요. 먼저: sudo bash ops/install_staging.sh" >&2
  exit 1
fi
mkdir -p "$state"

env_get() { sed -n "s/^$1=//p" "$envfile" | tail -n 1; }
env_set() {
  if grep -qE "^$1=" "$envfile"; then sed -i "s|^$1=.*|$1=$2|" "$envfile"; else echo "$1=$2" >> "$envfile"; fi
}

prod="$(env_get VILLAGEN_PROD_DIR)"
if [ -z "$prod" ] || [ ! -f "$prod/ops/production.env" ]; then
  echo "$envfile 의 VILLAGEN_PROD_DIR($prod)가 학교 서버 폴더가 아니에요. sudo bash ops/install_staging.sh 를 다시 실행해 주세요." >&2
  exit 1
fi
if [ "$(cd "$stage" && pwd -P)" = "$(cd "$prod" && pwd -P)" ]; then
  echo "개발 서버 폴더가 학교 서버 폴더와 같아요. 개발 서버는 따로 체크아웃해야 합니다." >&2
  exit 1
fi
domain="$(sed -n 's/^TRIPOTHON_DOMAIN=//p' "$prod/ops/production.env" | tail -n 1)"
site="dev.$domain"

# The staging project only: its own name, env file and compose files (never the production ones).
# "base" (status, logs, stop): only the service itself, whatever the craft mode.
compose=()
set_compose() {
  local files=(-f "$stage/ops/compose.staging.yaml")
  if [ "${1:-}" != "base" ] && [ "$(env_get STAGING_CRAFT)" = "real" ]; then
    if [ ! -f "$prod/ops/secrets/tripo-key" ]; then
      echo "학교 서버에 Tripo 키($prod/ops/secrets/tripo-key)가 없어서 real 로 켤 수 없어요. sudo bash ops/staging.sh fake" >&2
      return 1
    fi
    files+=(-f "$stage/ops/compose.staging-real.yaml")
    if [ "$(env_get STAGING_GEMINI)" != "off" ] && [ -f "$prod/ops/secrets/gemini-key" ]; then
      files+=(-f "$stage/ops/compose.staging-gemini.yaml")
    fi
  fi
  compose=(docker compose -p "$project" --project-directory "$stage/ops" --env-file "$envfile" "${files[@]}")
}

# The API answers at all (plain HTTP inside the container gets "https_required": that is alive too).
alive() {
  "${compose[@]}" exec -T staging-api python -c '
import urllib.request, urllib.error
try: urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=5)
except urllib.error.HTTPError: pass
' >/dev/null 2>&1
}

public_health() { curl -fsS --max-time 8 "https://$site/health"; }

running() {
  [ -n "$(docker ps -q --filter "label=com.docker.compose.project=$project" \
          --filter label=com.docker.compose.service=staging-api --filter status=running)" ]
}

# Recreates the staging container from the current checkout; "build" rebuilds the image first.
# Explicit returns: set -e does not apply inside a function called from an if.
deploy() {
  local commit
  commit="$(git -C "$stage" rev-parse --short HEAD)"
  "${compose[@]}" config --quiet || return 1
  if [ "${1:-}" = "build" ] || ! docker image inspect villagen-staging-api >/dev/null 2>&1; then
    # The build's own output goes to its own file; the update log keeps one line per deploy.
    if ! "${compose[@]}" build staging-api > "$state/last-build.log" 2>&1; then
      tail -n 25 "$state/last-build.log" >&2
      return 1
    fi
  fi
  VILLAGEN_SERVER_COMMIT="$commit" "${compose[@]}" up -d --no-build staging-api || return 1
  for _ in $(seq 1 45); do
    if alive; then return 0; fi
    sleep 2
  done
  echo "개발 서버가 90초 안에 켜지지 않았어요. 로그: sudo bash ops/staging.sh logs" >&2
  return 1
}

# Crafts still talking to Tripo (or its stand-in): switching the mode now would strand them.
busy_crafts() {
  running || { echo 0; return; }
  "${compose[@]}" exec -T staging-api python -c '
import sqlite3
db = sqlite3.connect("file:/data/world.sqlite3?mode=ro", uri=True)
print(db.execute("SELECT count(*) FROM studio_jobs WHERE state IN (?,?,?)", ("planning", "building", "submitting")).fetchone()[0])
' 2>/dev/null || echo 0
}

switch_mode() {
  local force="$1" count
  set_compose base
  count="$(busy_crafts)"
  if [ "${count:-0}" != "0" ] && [ -z "$force" ]; then
    echo "지금 만들고 있는 제작이 ${count}개 있어요. 끝난 뒤 다시 실행하거나, 그 제작을 포기하려면 --force 를 붙이세요." >&2
    exit 1
  fi
  set_compose
  deploy
}

case "$command" in
  status)
    set_compose base
    echo "개발 서버 주소: https://$site"
    if [ "$(env_get STAGING_CRAFT)" = "real" ]; then
      gemini="Tripo만"
      [ "$(env_get STAGING_GEMINI)" != "off" ] && [ -f "$prod/ops/secrets/gemini-key" ] && gemini="Gemini 설계 + Tripo"
      echo "제작 방식: real ($gemini, 예산 $(env_get STAGING_TRIPO_BUDGET) 크레딧, 한 번 최대 $(env_get STAGING_MAX_CREDITS_PER_CRAFT))"
    else
      echo "제작 방식: fake (Tripo 대역, 비용 0)"
    fi
    deployed="$(cut -c1-7 "$state/deployed" 2>/dev/null || echo 없음)"
    echo "배포된 커밋: $deployed / dev 최신(마지막 확인): $(git -C "$stage" rev-parse --short origin/dev 2>/dev/null || echo ?)"
    [ -f "$state/failed" ] && echo "실패한 커밋: $(cut -c1-7 "$state/failed") (dev 에 새 커밋이 오면 다시 시도)"
    [ -f "$state/stopped" ] && echo "멈춘 상태입니다. 다시 켜기: sudo bash ops/staging.sh start"
    "${compose[@]}" ps staging-api || true
    echo "--- 메모리 (학교 서버 포함)"
    docker stats --no-stream --format '{{.Name}}  {{.MemUsage}}  CPU {{.CPUPerc}}' 2>/dev/null || true
    free -m | sed -n '1,3p'
    echo "--- https://$site/health"
    public_health || echo "(응답 없음: 서버가 꺼졌거나, 처음이라 인증서를 받는 중일 수 있어요)"
    echo
    echo "--- 자동 업데이트"
    systemctl --no-pager status villagen-staging-update.timer 2>/dev/null | sed -n '1,3p' || true
    tail -n 8 "$updatelog" 2>/dev/null || echo "(기록 없음)"
    ;;

  logs)
    set_compose base
    case "${1:-200}" in
      update) tail -n 60 "$updatelog" 2>/dev/null || echo "(기록 없음)" ;;
      -f) "${compose[@]}" logs -f --tail 50 staging-api ;;
      *) [[ "${1:-200}" =~ ^[0-9]+$ ]] || { echo "줄 수는 숫자로 적어 주세요." >&2; exit 2; }
         "${compose[@]}" logs --tail "${1:-200}" staging-api ;;
    esac
    ;;

  fake)
    force=""
    [ "${1:-}" = "--force" ] && force=yes
    env_set STAGING_CRAFT fake
    switch_mode "$force"
    echo "개발 서버를 가짜 제작(fake)으로 바꿨어요. Tripo 키는 컨테이너에서 빠졌고 비용은 0입니다."
    ;;

  real)
    budget="$(env_get STAGING_TRIPO_BUDGET)"
    cap="$(env_get STAGING_MAX_CREDITS_PER_CRAFT)"
    gemini="$(env_get STAGING_GEMINI)"
    force=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --budget) budget="${2:-}"; shift 2 ;;
        --max-credits) cap="${2:-}"; shift 2 ;;
        --no-gemini) gemini=off; shift ;;
        --gemini) gemini=on; shift ;;
        --force) force=yes; shift ;;
        *) echo "모르는 옵션: $1" >&2; exit 2 ;;
      esac
    done
    if ! [[ "$budget" =~ ^[0-9]+$ ]] || [ "$budget" -lt 1 ] || [ "$budget" -gt 2000 ]; then
      echo "--budget 뒤에 개발 서버가 쓸 Tripo 크레딧 총량(1~2000)을 적어 주세요. 예) real --budget 300" >&2; exit 2
    fi
    if ! [[ "${cap:-10}" =~ ^[0-9]+$ ]] || [ "${cap:-10}" -lt 10 ] || [ "${cap:-10}" -gt "$budget" ]; then
      echo "--max-credits 는 10 이상, 예산 이하로 적어 주세요(10 = 가장 싼 제작만)." >&2; exit 2
    fi
    [ -f "$prod/ops/secrets/tripo-key" ] || { echo "학교 서버에 Tripo 키가 없어요($prod/ops/secrets/tripo-key)." >&2; exit 1; }
    env_set STAGING_CRAFT real
    env_set STAGING_TRIPO_BUDGET "$budget"
    env_set STAGING_MAX_CREDITS_PER_CRAFT "${cap:-10}"
    env_set STAGING_GEMINI "${gemini:-on}"
    switch_mode "$force"
    echo "개발 서버를 진짜 Tripo(real)로 바꿨어요: 예산 $budget 크레딧, 한 번 최대 ${cap:-10} 크레딧."
    echo "예산 사용량은 개발 서버 데이터에만 기록됩니다(가짜 제작은 0). 확인: sudo bash ops/staging.sh status"
    echo "다 쓰면 가짜로 되돌리기: sudo bash ops/staging.sh fake"
    ;;

  reset)
    set_compose
    echo "개발 서버의 계정, 마을, 만든 물건, 제작 기록(예산 사용량 포함)을 모두 지웁니다."
    echo "학교 서버(~/tripo_s1, 플레이어 데이터)는 그대로입니다."
    if [ "${1:-}" != "--yes" ]; then
      read -r -p "정말 지우려면 reset 이라고 입력하세요: " answer
      [ "$answer" = "reset" ] || { echo "취소했어요."; exit 1; }
    fi
    "${compose[@]}" rm --stop --force staging-api
    # Only the development volumes, by their fixed names (production's are ops_game_data and ops_backups).
    for volume in villagen_staging_data villagen_staging_backups; do
      docker volume rm "$volume" >/dev/null 2>&1 || true
    done
    deploy
    echo "개발 서버를 빈 데이터로 새로 시작했어요."
    ;;

  stop)
    set_compose base
    mkdir -p "$state"
    touch "$state/stopped"
    "${compose[@]}" stop staging-api
    echo "개발 서버를 껐어요(자동 업데이트도 멈춤). 다시 켜기: sudo bash ops/staging.sh start"
    ;;

  start)
    set_compose
    rm -f "$state/stopped"
    deploy
    echo "개발 서버를 켰어요: https://$site"
    ;;

  update)
    force=""
    [ "${1:-}" = "--force" ] && force=yes
    prodlock="${VILLAGEN_PROD_LOCK:-/var/lib/villagen/autoupdate.lock}"
    mkdir -p "$state" "$(dirname "$prodlock")"
    exec 8>"$state/update.lock"
    flock -n 8 || exit 0
    # Never build while the school server deploys (ops/auto_update.sh holds this lock): next round.
    exec 7>"$prodlock"
    if ! flock -n 7; then
      [ -n "$force" ] && echo "학교 서버가 업데이트 중이에요. 몇 분 뒤 다시 실행해 주세요." >&2
      exit 0
    fi
    if [ -f "$state/stopped" ] && [ -z "$force" ]; then exit 0; fi
    if ! git -C "$stage" fetch --quiet origin dev 2>/dev/null; then
      # GitHub unreachable: try again next round, quietly.
      [ -n "$force" ] && { echo "GitHub에서 dev 브랜치를 받지 못했어요." >&2; exit 1; }
      exit 0
    fi
    target="$(git -C "$stage" rev-parse origin/dev)"
    if [ -z "$force" ]; then
      [ "$target" = "$(cat "$state/failed" 2>/dev/null || true)" ] && exit 0
      if [ "$target" = "$(cat "$state/deployed" 2>/dev/null || true)" ]; then
        set_compose
        if ! running; then
          log "development server was not running: starting ${target:0:7} again"
          deploy || log "start FAILED"
        fi
        exit 0
      fi
    fi
    log "dev ${target:0:7}: rebuilding the development server"
    git -C "$stage" reset --quiet --hard "$target"
    rm -f "$state/stopped"
    if set_compose && deploy build; then
      echo "$target" > "$state/deployed"
      rm -f "$state/failed"
      # The image this build replaced (only development images carry this label).
      docker image prune --force --filter label=villagen.staging=1 >/dev/null 2>&1 || true
      log "deployed ${target:0:7}"
      public_health >/dev/null 2>&1 || log "note: https://$site/health does not answer yet (certificate or proxy); the server itself is up"
    else
      echo "$target" > "$state/failed"
      log "deploy FAILED for ${target:0:7}; next try when dev moves (or: sudo bash ops/staging.sh update --force)"
      exit 1
    fi
    ;;

  admin)
    [ $# -ge 1 ] || { echo "관리자 이름을 적어 주세요. 예) admin devadmin" >&2; exit 2; }
    for name in "$@"; do
      [[ "$name" =~ ^[A-Za-z0-9_]{3,24}$ ]] || { echo "이름은 영문, 숫자, _ 로 3~24자: $name" >&2; exit 2; }
    done
    set_compose
    running || { echo "개발 서버가 꺼져 있어요: sudo bash ops/staging.sh start" >&2; exit 1; }
    read -r -s -p "개발 서버 관리자 비밀번호(학교 서버와 다르게): " password; echo
    read -r -s -p "한 번 더: " again; echo
    [ "$password" = "$again" ] || { echo "두 비밀번호가 달라요." >&2; exit 1; }
    [ "${#password}" -ge 10 ] || { echo "비밀번호는 10자 이상으로 해 주세요." >&2; exit 1; }
    # The tool is not in the image: copy it to the container's /tmp, give the password on stdin.
    "${compose[@]}" exec -T staging-api sh -c 'cat > /tmp/admin_accounts.py' < "$stage/tools/admin_accounts.py"
    printf '%s\n' "$password" | "${compose[@]}" exec -T -e PYTHONPATH=/app staging-api sh -c \
      'IFS= read -r TRIPOTHON_ADMIN_PASSWORD; export TRIPOTHON_ADMIN_PASSWORD; python /tmp/admin_accounts.py --data-dir /data --mode live "$@"; status=$?; rm -f /tmp/admin_accounts.py; exit $status' \
      admin "$@"
    ;;
esac
