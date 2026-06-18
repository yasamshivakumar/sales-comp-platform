# One-time local setup for Incentra (Windows)
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "=== Incentra local setup ===" -ForegroundColor Cyan

if (-not (Test-Path "$Root\backend\.env")) {
    Copy-Item "$Root\backend\.env.example" "$Root\backend\.env"
    Write-Host "Created backend\.env — edit DB_PASSWORD before migrate." -ForegroundColor Yellow
} else {
    Write-Host "backend\.env already exists"
}

if (-not (Test-Path "$Root\frontend\.env")) {
    Copy-Item "$Root\frontend\.env.example" "$Root\frontend\.env"
    Write-Host "Created frontend\.env"
} else {
    Write-Host "frontend\.env already exists"
}

$venvPython = "$Root\backend\myenv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -m pip install -r "$Root\backend\requirements.txt" -q
    Push-Location "$Root\backend"
    & $venvPython manage.py migrate --noinput
    Pop-Location
    Write-Host "Migrations applied." -ForegroundColor Green
} else {
    Write-Host "No backend\myenv — create venv and pip install -r requirements.txt" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "  Terminal 1: cd backend; .\myenv\Scripts\activate; python manage.py runserver"
Write-Host "  Terminal 2: cd frontend; npm install; npm start"
Write-Host "  Browser:    http://localhost:3000/login"
Write-Host "  API check:  http://127.0.0.1:8000/api/health/"
