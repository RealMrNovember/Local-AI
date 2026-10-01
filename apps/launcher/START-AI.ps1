# CiciByte AI — Windows portable launcher (Phase 1 stub)
#
# Phase 1 scope: set up the backend venv if missing, install deps, run the
# API, and tell the user where the (not-yet-built) frontend will live.
# Phase 9a replaces this with a fully bundled, drive-letter-independent
# launcher (no system Python/Node dependency).

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BackendDir = Join-Path $RepoRoot "apps\backend"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "CiciByte AI — starting (Phase 1 foundation)" -ForegroundColor Cyan

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Yellow
    python -m venv $VenvDir
}

Write-Host "Installing backend dependencies..." -ForegroundColor Yellow
& $VenvPython -m pip install --quiet --upgrade pip
& $VenvPython -m pip install --quiet -r (Join-Path $BackendDir "requirements.txt")

Write-Host "Starting backend on http://127.0.0.1:8765 ..." -ForegroundColor Green
Push-Location $BackendDir
try {
    & $VenvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8765
}
finally {
    Pop-Location
}
