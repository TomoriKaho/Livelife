#!/usr/bin/env bash
# Run as root after inspecting this script and verifying the project's ports.
set -euo pipefail
test "$(id -u)" = 0
task_source="$(cd -- "$(dirname -- "$0")" && pwd)"
task_root=/opt/livelife
if ! id livelife >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /var/lib/livelife --shell /bin/bash livelife
fi
install -d -m 755 "$task_root" "$task_root/control" "$task_root/gateway" "$task_root/bin"
install -d -o livelife -g livelife -m 700 "$task_root/state" "$task_root/tunnels" "$task_root/credentials"
install -d -o livelife -g livelife -m 750 "$task_root/web"
install -d -o livelife -g livelife -m 750 "$task_root/gateway/config" "$task_root/gateway/run" \
  "$task_root/gateway/logs" "$task_root/gateway/data"
install -d -o root -g livelife -m 750 "$task_root/tls"
cp -R "$task_source/livelife" "$task_root/control/"
install -m 644 "$task_source/public-entry.py" "$task_root/control/"
install -m 755 "$task_source/renew-ip.sh" "$task_root/control/"
python3 -m venv "$task_root/control-venv"
"$task_root/control-venv/bin/python" -m pip install --disable-pip-version-check 'supervisor==4.3.0'
install -m 644 "$task_source/nginx.conf" "$task_root/gateway/nginx.conf"
install -m 644 "$task_source/livelife-logrotate" /etc/logrotate.d/livelife
if [[ ! -f "$task_root/config.json" ]]; then
  install -m 644 "$task_source/config.example.json" "$task_root/config.json"
fi
if [[ ! -f "$task_root/gateway/config/routes.conf" ]]; then
  install -o livelife -g livelife -m 644 /dev/null "$task_root/gateway/config/routes.conf"
fi
for task_unit in livelife-gateway.service livelife-recover.service livelife-recover.timer \
  livelife-renew-ip.service livelife-renew-ip.timer; do
  install -m 644 "$task_source/$task_unit" /etc/systemd/system/
done
systemctl daemon-reload
printf 'Installed. Configure SSH keys and IP certificate before enabling Livelife services.\n'
