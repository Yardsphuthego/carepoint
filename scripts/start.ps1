$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install and start Docker Desktop first: https://www.docker.com/products/docker-desktop/' }
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker is not running. Start Docker Desktop and try again.' }
docker compose version
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 is required.' }
docker compose -f compose.local.yml up --build --detach --wait --wait-timeout 900
if ($LASTEXITCODE -ne 0) { throw 'Startup failed. Inspect: docker compose -f compose.local.yml logs --tail=100' }
$carepointPort = if ($env:CAREPOINT_FRONTEND_PORT) { $env:CAREPOINT_FRONTEND_PORT } else { '3100' }
Write-Host "`nCarepoint is ready: http://localhost:$carepointPort`n"
docker compose -f compose.local.yml exec -T web cat /data/local-logins.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not read the local login details.' }
