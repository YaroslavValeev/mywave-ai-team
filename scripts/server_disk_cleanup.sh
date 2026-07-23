#!/usr/bin/env bash
# scripts/server_disk_cleanup.sh — безопасная очистка диска на RU AI-TEAM
# Usage on server:
#   cd /opt/mywave/ai-team && bash scripts/server_disk_cleanup.sh
set -euo pipefail
cd /opt/mywave/ai-team

echo "=== BEFORE ==="
df -h /
docker system df || true

echo "=== Docker prune (unused images/containers/networks, keep volumes) ==="
docker container prune -f || true
docker image prune -af || true
docker builder prune -af || true
docker network prune -f || true

echo "=== App logs truncate (keep last 2000 lines per container log if huge) ==="
journalctl --vacuum-size=200M 2>/dev/null || true

echo "=== apt cache ==="
apt-get clean || true

echo "=== AFTER ==="
df -h /
docker system df || true
echo "OK cleanup done. Reboot when ready: reboot"
