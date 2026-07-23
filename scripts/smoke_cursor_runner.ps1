# Minimal Cursor runner smoke — no git merge, no PR.
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File .\scripts\smoke_cursor_runner.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$py = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "=== cursor CLI on PATH ==="
$cursor = Get-Command cursor -ErrorAction SilentlyContinue
if ($cursor) {
    Write-Host "cursor -> $($cursor.Source)"
    & cursor --version
} else {
    Write-Host "WARN: cursor not on PATH (set CURSOR_CLI if needed)"
}

Write-Host "`n=== runner resolve + --version via app.runners.cursor_runner ==="
& $py -c @"
import asyncio
from app.runners.cursor_runner import resolve_cursor_binary, build_cursor_argv, get_runner_config, run_cursor_cli

cfg = get_runner_config()
print('binary=', resolve_cursor_binary())
print('exists=', cfg.get('cursor_binary_exists'))
print('argv=', build_cursor_argv(''))
code, out, err = asyncio.run(run_cursor_cli('.', '', timeout_sec=30))
print('exit=', code)
print('stdout=', (out or '')[:300])
if err:
    print('stderr=', err[:300])
raise SystemExit(0 if code == 0 else 1)
"@

if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: cursor_runner smoke"
    exit 1
}
Write-Host "OK: cursor_runner smoke (no merge)"
