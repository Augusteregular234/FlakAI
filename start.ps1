# FlakAI v2 - Start all services
Write-Host "Starting FlakAI v2..." -ForegroundColor Green

$backendDir  = Join-Path $PSScriptRoot "backend"
$frontendDir = Join-Path $PSScriptRoot "frontend"

# Ensure admin user exists
Write-Host "Seeding admin user..." -ForegroundColor Yellow
& "$backendDir\venv\Scripts\python.exe" "$backendDir\seed_admin.py" 2>$null

# Backend
Write-Host "Starting backend..." -ForegroundColor Yellow
Start-Process powershell `
    -ArgumentList "-ExecutionPolicy", "Bypass", "-NoExit", "-Command", ".\venv\Scripts\python run.py" `
    -WorkingDirectory $backendDir `
    -WindowStyle Normal

# Wait for backend to be ready (poll /health)
Write-Host "Waiting for backend..." -ForegroundColor Yellow
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep 1
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}
if ($ready) {
    Write-Host "Backend ready." -ForegroundColor Green
} else {
    Write-Host "Backend did not respond in 20s — check the backend window for errors." -ForegroundColor Red
}

# Frontend
Write-Host "Starting frontend..." -ForegroundColor Yellow
Start-Process powershell `
    -ArgumentList "-ExecutionPolicy", "Bypass", "-NoExit", "-Command", "npm.cmd run dev" `
    -WorkingDirectory $frontendDir `
    -WindowStyle Normal

Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Login: admin / admin" -ForegroundColor Green
