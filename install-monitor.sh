#!/usr/bin/env bash
# Author: 数萌AI服务器 (winintel) | winintel.com
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${1:-/opt/winintel-server-doctor}"
[[ $EUID == 0 ]] || { echo "Run with sudo" >&2; exit 1; }
[[ "$PREFIX" =~ ^/[a-zA-Z0-9_./-]+$ && "$PREFIX" != / ]] || exit 2
install -d -m 755 "$PREFIX" /etc/winintel-server-doctor
install -d -m 700 /var/lib/winintel-server-doctor
if [[ "$ROOT" != "$PREFIX" ]]; then
    cp "$ROOT/doctor.py" "$ROOT/hardware.py" "$ROOT/monitor.py" "$ROOT/install-runtime.sh" "$PREFIX/"
fi
bash "$PREFIX/install-runtime.sh" "$PREFIX"
if [[ ! -e /etc/winintel-server-doctor/monitor.json ]]; then
    printf '{"webhook_url": null, "send_heartbeat": true}\n' > /etc/winintel-server-doctor/monitor.json
    chmod 600 /etc/winintel-server-doctor/monitor.json
fi
cat > /etc/systemd/system/winintel-server-monitor.service <<EOF
[Unit]
Description=winintel AI server hardware health snapshot
After=multi-user.target
[Service]
Type=oneshot
ExecStart=$PREFIX/uv run --offline --no-project --python $PREFIX/.venv/bin/python $PREFIX/monitor.py
UMask=0077
Nice=10
TimeoutStartSec=10min
EOF
cat > /etc/systemd/system/winintel-server-monitor.timer <<'EOF'
[Unit]
Description=winintel AI hardware monitor every 30 minutes
[Timer]
OnCalendar=*:0/30
Persistent=true
RandomizedDelaySec=0
Unit=winintel-server-monitor.service
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now winintel-server-monitor.timer
systemctl start winintel-server-monitor.service
systemctl list-timers winintel-server-monitor.timer --no-pager
echo "Monitoring active. Local alerts: /var/lib/winintel-server-doctor/alerts.jsonl"
echo "External alerts require your HTTPS JSON receiver in /etc/winintel-server-doctor/monitor.json"
