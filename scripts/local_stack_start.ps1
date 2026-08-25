param(
    [switch]$Build,
    [switch]$NoCaddy,
    [switch]$FullAI,
    [switch]$EnableTelegramPolling,
    [string]$LocalModel = "qwen2.5:3b"
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

docker info | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker daemon недоступен. Запустите Docker Desktop и повторите."
}

$envText = Get-Content ".env" -Raw
$requiredVariables = @("OWNER_API_KEY", "POSTGRES_PASSWORD")
if ($EnableTelegramPolling) {
    $requiredVariables += @("TELEGRAM_BOT_TOKEN", "OWNER_CHAT_ID")
}
foreach ($required in $requiredVariables) {
    if ($envText -notmatch "(?m)^\s*$required\s*=\s*.+$") {
        throw "В .env отсутствует или пуста переменная: $required"
    }
}

$env:TELEGRAM_POLLING_ENABLED = if ($EnableTelegramPolling) { "true" } else { "false" }
$env:TELEGRAM_STAGE_NOTIFY = if ($EnableTelegramPolling) { "true" } else { "false" }
$env:APP_ENVIRONMENT = "local"
$env:APP_VERSION = "v1-local"
try {
    $env:APP_COMMIT_SHA = (& git rev-parse HEAD).Trim()
}
catch {
    $env:APP_COMMIT_SHA = "unknown"
}

if ($FullAI) {
    try {
        $ollama = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10
    }
    catch {
        throw "Ollama недоступен на http://127.0.0.1:11434. Запустите Ollama и повторите."
    }
    if ($LocalModel -notin @($ollama.models.name)) {
        $available = @($ollama.models.name) -join ", "
        throw "Модель '$LocalModel' не установлена. Доступны: $available"
    }

    $env:DOCKER_BUILD_TARGET = "full"
    $env:ORCHESTRATION_ENGINE = "crewai"
    $env:ORCHESTRATION_ALLOW_FALLBACK = "true"
    $env:LLM_TIER_DEFAULT = "local"
    $env:LLM_LOCAL_BASE_URL = "http://host.docker.internal:11434"
    $env:LLM_LOCAL_API_KEY = "ollama"
    $env:LLM_LOCAL_MODEL = $LocalModel
    $env:LLM_LOCAL_PROVIDER = "openai"
    $env:CREWAI_MODEL = $LocalModel
    $env:CREWAI_DEFAULT_MODEL = $LocalModel
    $env:CREWAI_PROVIDER = "openai"
    $env:CREWAI_TIMEOUT = "300"
    $env:CREWAI_MAX_TOKENS = "800"
    if (-not $Build) {
        $currentImage = docker compose images -q app
        if (-not $currentImage) {
            $Build = $true
        }
        else {
            docker run --rm $currentImage python -c "import crewai" 2>$null
            if ($LASTEXITCODE -ne 0) {
                $Build = $true
            }
        }
    }
    Write-Host ">> Full AI: Ollama / $LocalModel" -ForegroundColor Cyan
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

if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose не смог запустить локальный стек. Проверьте docker compose logs app postgres."
}

$healthUrl = "http://localhost:8080/health"
$health = $null
for ($attempt = 1; $attempt -le 60; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 5
        if ($health.status -eq "ok") {
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $health -or $health.status -ne "ok") {
    throw "Dashboard не прошёл healthcheck: $healthUrl"
}

Write-Host ""
Write-Host "Локальный стек запущен." -ForegroundColor Green
Write-Host "Проверка: docker compose ps"
Write-Host "Dashboard: http://localhost:8080/office"
Write-Host "Health: $healthUrl"
Write-Host "Telegram polling: $env:TELEGRAM_POLLING_ENABLED"
if ($FullAI) {
    Write-Host "Локальная AI-модель: $LocalModel"
}
