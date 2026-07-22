Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$taskName = "MyWave_AI_Team_LocalStack"
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if (-not $existing) {
    Write-Host "Задача '$taskName' не найдена." -ForegroundColor Yellow
    exit 0
}

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Host "Задача '$taskName' удалена." -ForegroundColor Green
