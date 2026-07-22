param(
    [switch]$All
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Команда 'docker' не найдена."
}

if ($All) {
    Write-Host ">> docker compose down" -ForegroundColor Yellow
    docker compose down
}
else {
    Write-Host ">> docker compose stop app caddy" -ForegroundColor Yellow
    docker compose stop app caddy
}

Write-Host "Готово." -ForegroundColor Green
