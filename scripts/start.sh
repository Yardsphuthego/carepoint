#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
command -v docker >/dev/null 2>&1 || { echo 'Install and start Docker Desktop first: https://www.docker.com/products/docker-desktop/'; exit 1; }
docker info >/dev/null 2>&1 || { echo 'Docker is not running. Start Docker Desktop and try again.'; exit 1; }
docker compose version >/dev/null
if ! docker compose -f compose.local.yml up --build --detach --wait --wait-timeout 900; then
  echo 'Startup failed. Inspect: docker compose -f compose.local.yml logs --tail=100'
  exit 1
fi
printf '\nCarepoint is ready: http://localhost:%s\n\n' "${CAREPOINT_FRONTEND_PORT:-3100}"
docker compose -f compose.local.yml exec -T web cat /data/local-logins.txt
