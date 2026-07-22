param(
    [int]$Tail = 60
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Команда 'docker' не найдена."
}

Write-Host "== docker compose ps ==" -ForegroundColor Cyan
docker compose ps

Write-Host ""
Write-Host "== app logs (tail $Tail) ==" -ForegroundColor Cyan
docker compose logs --tail $Tail app
