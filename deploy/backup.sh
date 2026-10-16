#!/usr/bin/env bash
# Download all server data (parks, logins, friends) from the VM into one file:
#   bash deploy/backup.sh            -> backups/themepark-data-<date>.tar.gz
# Only reads from the VM. Settings: deploy/deploy.env (see deploy.env.example).
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f deploy/deploy.env ] && . deploy/deploy.env
HOST="${TP_HOST:?set TP_HOST, e.g. ubuntu@1.2.3.4 (see deploy/deploy.env.example)}"
KEY="${TP_KEY:-$HOME/.ssh/id_ed25519}"

mkdir -p backups
OUT="backups/themepark-data-$(date +%Y%m%d-%H%M).tar.gz"
/usr/bin/ssh -i "$KEY" "$HOST" 'tar czf - -C ~/themepark-server --exclude="data/requests.log*" data' > "$OUT.part"
mv "$OUT.part" "$OUT"
echo "saved $OUT"
python3 tools/data.py info "$OUT"
