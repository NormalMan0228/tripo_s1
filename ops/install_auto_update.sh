#!/usr/bin/env bash
# One-time setup on the school VM: a systemd timer runs ops/auto_update.sh every 5 minutes, so a
# push to the release branch (school-release) updates the server by itself, with the 10-minute
# maintenance notice first and the "new version" notice after.
#   sudo bash ops/install_auto_update.sh            # install, or refresh after an update
#   sudo bash ops/install_auto_update.sh --status   # timer state and the last log lines
#   sudo bash ops/install_auto_update.sh --announce 5   # default wait before maintenance (minutes, 0 = none)
#   sudo bash ops/install_auto_update.sh --remove   # stop and remove the timer
# A release can still choose its own wait (ops/release.json, tools/deploy_school.py --announce N).
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
unit=/etc/systemd/system/villagen-autoupdate
log=/var/log/villagen-autoupdate.log
minutes=10
[ -f "$unit.service" ] && minutes=$(sed -n 's/^Environment=VILLAGEN_ANNOUNCE_MINUTES=\([0-9]*\)$/\1/p' "$unit.service" | head -n 1)
case "${1:-}" in
  --announce)
    [[ "${2:-}" =~ ^[0-9]+$ && "$2" -le 1440 ]] || { echo "--announce 뒤에 0~1440 사이의 분을 적어 주세요. 예) --announce 5" >&2; exit 2; }
    minutes="$2" ;;
  --status)
    systemctl --no-pager status villagen-autoupdate.timer | head -n 6 || true
    echo "--- deployed: $(cat /var/lib/villagen/deployed 2>/dev/null || echo none)"
    tail -n 15 "$log" 2>/dev/null || echo "(no log yet)"
    exit 0 ;;
  --remove)
    systemctl disable --now villagen-autoupdate.timer 2>/dev/null || true
    rm -f "$unit.service" "$unit.timer"
    systemctl daemon-reload
    echo "자동 업데이트를 껐어요."
    exit 0 ;;
esac
cat > "$unit.service" <<EOF
[Unit]
Description=Villagen school server auto-update (release branch)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo
Environment=VILLAGEN_RELEASE_BRANCH=school-release
Environment=VILLAGEN_ANNOUNCE_MINUTES=${minutes:-10}
ExecStart=/bin/bash $repo/ops/auto_update.sh
StandardOutput=append:$log
StandardError=append:$log
TimeoutStartSec=3600
EOF
cat > "$unit.timer" <<EOF
[Unit]
Description=Check for a new Villagen school release every 5 minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=5min
Unit=villagen-autoupdate.service

[Install]
WantedBy=timers.target
EOF
mkdir -p /var/lib/villagen
# What runs now counts as deployed, so installing never redeploys it.
[ -f /var/lib/villagen/deployed ] || git -C "$repo" rev-parse HEAD > /var/lib/villagen/deployed
systemctl daemon-reload
systemctl enable --now villagen-autoupdate.timer
echo "자동 업데이트를 켰어요. school-release 브랜치가 바뀌면 5분 안에 점검 공지(기본 ${minutes:-10}분 뒤 시작)가 나가고 업데이트됩니다."
echo "상태 보기: sudo bash ops/install_auto_update.sh --status"
