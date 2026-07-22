param(
    [switch]$Build,
    [switch]$NoCaddy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Команда '$Name' не найдена. Установите ее и повторите."
    }
}

Assert-Command "docker"

if (-not (Test-Path ".env")) {
    throw "Файл .env не найден в корне репозитория ($repoRoot)."
}

try {
    docker info | Out-Null
}
catch {
    throw "Docker daemon недоступен. Запустите Docker Desktop и повторите."
}

$envText = Get-Content ".env" -Raw
foreach ($required in @("TELEGRAM_BOT_TOKEN", "OWNER_CHAT_ID", "OWNER_API_KEY", "POSTGRES_PASSWORD")) {
    if ($envText -notmatch "(?m)^\s*$required\s*=\s*.+$") {
        throw "В .env отсутствует или пуста переменная: $required"
    }
}

$services = @("postgres", "app")
if (-not $NoCaddy) {
    $services += "caddy"
}

if ($Build) {
    Write-Host ">> docker compose up -d --build $($services -join ' ')" -ForegroundColor Cyan
    docker compose up -d --build @services
}
else {
    Write-Host ">> docker compose up -d $($services -join ' ')" -ForegroundColor Cyan
    docker compose up -d @services
}

Write-Host ""
Write-Host "Локальный стек запущен." -ForegroundColor Green
Write-Host "Проверка: docker compose ps"
Write-Host "Dashboard: http://localhost:8080/health"
