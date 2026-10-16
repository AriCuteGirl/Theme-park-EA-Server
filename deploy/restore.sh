#!/usr/bin/env bash
# Upload a backup made by backup.sh (or tools/data.py export) to the VM:
#   bash deploy/restore.sh backups/themepark-data-<date>.tar.gz
# The VM's current data is kept as ~/themepark-server/data.before-restore-<date>.
# On a new VM, run deploy_oracle.sh first. Settings: deploy/deploy.env.
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f deploy/deploy.env ] && . deploy/deploy.env
HOST="${TP_HOST:?set TP_HOST, e.g. ubuntu@1.2.3.4 (see deploy/deploy.env.example)}"
KEY="${TP_KEY:-$HOME/.ssh/id_ed25519}"
FILE="${1:?usage: bash deploy/restore.sh <backup.tar.gz>}"

python3 tools/data.py info "$FILE"
read -r -p "Replace the server's data on $HOST with this backup? [y/N] " ok
case "$ok" in y|Y) ;; *) echo "cancelled"; exit 1 ;; esac

/usr/bin/scp -i "$KEY" "$FILE" "$HOST":/tmp/themepark-restore.tar.gz
/usr/bin/ssh -i "$KEY" "$HOST" 'set -e
mkdir -p ~/themepark-server && cd ~/themepark-server
sudo systemctl stop themepark 2>/dev/null || true
if [ -d data ]; then mv data "data.before-restore-$(date +%Y%m%d-%H%M%S)"; fi
tar xzf /tmp/themepark-restore.tar.gz && rm /tmp/themepark-restore.tar.gz
sudo systemctl start themepark 2>/dev/null || true
echo "restored $(ls data/parks | grep -c "\.json$") park file(s)"'
