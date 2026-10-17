#!/usr/bin/env bash
# Deploy the Theme Park server to an Ubuntu VM (e.g. Oracle Cloud free tier) and
# run it as a systemd service:  bash deploy/deploy_oracle.sh
# Re-running it updates the code; saved parks in ~/themepark-server/data are kept.
#
# Settings come from deploy/deploy.env (not in git, see deploy.env.example) or
# the environment: TP_HOST (user@ip), TP_KEY (ssh key), TP_PUBLIC (http://ip:8086).
set -euo pipefail

ENV_FILE="$(dirname "$0")/deploy.env"
[ -f "$ENV_FILE" ] && . "$ENV_FILE"
HOST="${TP_HOST:?set TP_HOST, e.g. ubuntu@1.2.3.4 (see deploy/deploy.env.example)}"
KEY="${TP_KEY:-$HOME/.ssh/id_ed25519}"
PUBLIC_URL="${TP_PUBLIC:-http://${HOST#*@}:8086}"
SSH=(/usr/bin/ssh -i "$KEY" -o StrictHostKeyChecking=accept-new)

cd "$(dirname "$0")/.."

echo "== copying server code"
"${SSH[@]}" "$HOST" 'mkdir -p ~/themepark-server/data'
/usr/bin/scp -i "$KEY" server/server.py server/game.py server/catalog.json server/settings.json server/manage.py "$HOST":themepark-server/

echo "== installing service + opening port 8086"
"${SSH[@]}" "$HOST" "PUBLIC_URL='$PUBLIC_URL' bash -s" <<'REMOTE'
set -euo pipefail
sudo tee /etc/systemd/system/themepark.service >/dev/null <<UNIT
[Unit]
Description=Theme Park revival server
After=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/themepark-server
Environment=TP_PORT=8086
Environment=TP_PUBLIC=${PUBLIC_URL}
ExecStart=/usr/bin/python3 -u /home/ubuntu/themepark-server/server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
# Oracle's Ubuntu images REJECT everything not explicitly allowed in iptables.
if ! sudo iptables -C INPUT -p tcp --dport 8086 -j ACCEPT 2>/dev/null; then
  sudo iptables -I INPUT 5 -p tcp --dport 8086 -m state --state NEW -j ACCEPT
  sudo netfilter-persistent save >/dev/null 2>&1 || sudo sh -c 'iptables-save > /etc/iptables/rules.v4'
fi
sudo systemctl daemon-reload
sudo systemctl enable --now themepark.service
sudo systemctl restart themepark.service
sleep 2
systemctl --no-pager --lines=3 status themepark.service | head -5
curl -s -o /dev/null -w 'local check: HTTP %{http_code}\n' http://127.0.0.1:8086/director/api/android/getDirectionByPackage
REMOTE

echo
echo "== checking from here"
curl -s -m 8 -o /dev/null -w 'public check: HTTP %{http_code}\n' "$PUBLIC_URL/director/api/android/getDirectionByPackage" \
  || echo "public check FAILED: add an Ingress rule for TCP port 8086 (source 0.0.0.0/0) to the VM's subnet Security List in the Oracle console"
