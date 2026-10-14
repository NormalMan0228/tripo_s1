#!/usr/bin/env bash
# 점검 공지와 게임 버전 관리. 서버 창(EC2 Instance Connect)의 저장소 폴더에서 실행합니다.
# 서버를 다시 만들거나 끄지 않고, 몇 초 안에 게임에 반영됩니다.
# (server/client_policy.py 가 /data/client_policy.json 에 저장합니다.)
set -euo pipefail

usage() {
  cat <<'HELP'
사용법 (cd ~/tripo_s1 다음에):

  sudo bash ops/notice.sh show
      지금 설정을 봅니다.

  sudo bash ops/notice.sh maintenance <몇 분 뒤> <점검 분> ["안내 문구"] [--hold]
      점검을 예약합니다. 게임에는 30분 전부터 남은 시간이 뜨고,
      시작되면 접속이 잠시 막히고(/health 만 열림), 접속 중인 플레이어는 모두 로그아웃되어
      타이틀로 돌아갑니다(점검이 끝나면 다시 로그인).
      예) sudo bash ops/notice.sh maintenance 30 10 "새 버전 업데이트를 해요."
      --hold : 예상 시간이 지나도 cancel 할 때까지 점검을 계속합니다.

  sudo bash ops/notice.sh cancel
      점검 예약을 지우거나, 진행 중인 점검을 끝냅니다.

  sudo bash ops/notice.sh release <버전> [받는 주소]
      새 게임이 나왔다고 알립니다. 0.11.5 부터의 게임은 켤 때(타이틀) 바로 패치를 받고
      다시 시작합니다(패치가 없으면 설치 파일 안내). 플레이 중이면 위쪽 안내가 뜨고,
      타이틀로 돌아가면 업데이트합니다. 그 전 게임은 안내만 뜹니다.
      예) sudo bash ops/notice.sh release 0.11.5 https://example.com/villagen/index.html

  sudo bash ops/notice.sh min <버전>
      이 버전보다 오래된 게임은 접속을 막고 "업데이트 필요" 창을 띄웁니다.
      예) sudo bash ops/notice.sh min 0.11.4

  sudo bash ops/notice.sh min off | latest off | url off
      각각 끕니다. latest <버전>, url <주소> 로 하나씩 바꿀 수도 있습니다.

  sudo bash ops/notice.sh patches <패치 목록 주소> | auto | off
      게임이 읽는 패치 목록(patches.json)입니다. 기본(auto)은 받는 주소의 index.html 옆
      patches.json 이라 보통 바꿀 필요가 없습니다. off: 패치 없이 설치 파일로만 업데이트.

  sudo bash ops/notice.sh logout-all
      접속 중인 모든 플레이어를 로그아웃시킵니다(다시 로그인하면 이어서 플레이).
      점검이 시작될 때는 자동으로 모두 로그아웃되니, 점검 없이 서버를 바꿨을 때만 씁니다.
HELP
}

case "${1:-help}" in
  show|maintenance|cancel|release|min|latest|url|patches|logout-all) ;;
  *) usage; exit 0 ;;
esac
cd "$(dirname "$0")/.."
compose=(docker compose --env-file ops/production.env -f ops/compose.yaml -f ops/compose.gcp-free.yaml)
if [ -f ops/secrets/tripo-key ]; then
  compose+=(-f ops/compose.tripo.yaml)
  [ -f ops/secrets/gemini-key ] && compose+=(-f ops/compose.gemini.yaml)
fi
if [ -z "$("${compose[@]}" ps -q api 2>/dev/null)" ]; then
  echo "서버(api)가 꺼져 있어요. 먼저 sudo bash ops/update_online_server.sh 로 켜 주세요." >&2
  exit 1
fi
command="$1"; shift
args=()
case "$command" in
  maintenance)
    hold=()
    rest=()
    for value in "$@"; do
      if [ "$value" = "--hold" ]; then hold=(--hold); else rest+=("$value"); fi
    done
    if [ "${#rest[@]}" -lt 2 ] || ! [[ "${rest[0]}" =~ ^[0-9]+$ && "${rest[1]}" =~ ^[0-9]+$ ]]; then
      echo "몇 분 뒤에 시작해서 몇 분 걸리는지 숫자로 적어 주세요. 예) maintenance 30 10 \"안내 문구\"" >&2
      exit 2
    fi
    args=(--in "${rest[0]}" --minutes "${rest[1]}")
    [ "${#rest[@]}" -ge 3 ] && args+=(--message "${rest[2]}")
    args+=("${hold[@]}")
    ;;
  min|latest|url|patches)
    [ $# -ge 1 ] || { echo "값을 적어 주세요. 예) $command off" >&2; exit 2; }
    args=("$1")
    ;;
  release)
    [ $# -ge 1 ] || { echo "버전을 적어 주세요. 예) release 0.11.4 https://..." >&2; exit 2; }
    args=("$@")
    ;;
esac
"${compose[@]}" exec -T api python -m server.client_policy "$command" "${args[@]}"
