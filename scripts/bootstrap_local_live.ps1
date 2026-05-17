$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "== ProspectIQ local-live bootstrap ==" -ForegroundColor Cyan

$apiEnv = Join-Path $Root "apps\api\.env"
$apiEnvExample = Join-Path $Root "apps\api\.env.local-live.example"
$webEnv = Join-Path $Root "apps\web\.env"
$webEnvExample = Join-Path $Root "apps\web\.env.local-live.example"

if (-not (Test-Path $apiEnv)) {
    Copy-Item $apiEnvExample $apiEnv
}
if (-not (Test-Path $webEnv)) {
    Copy-Item $webEnvExample $webEnv
}

docker compose -f infra/docker-compose.yml up -d

Set-Location "$Root\apps\api"
if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -e .[dev]
& ".\.venv\Scripts\python.exe" -m alembic upgrade head
& ".\.venv\Scripts\python.exe" scripts/seed.py

Set-Location "$Root\apps\web"
if (-not (Test-Path "node_modules")) {
    npm install
}

New-Item -ItemType Directory -Force "$Root\tmp" | Out-Null

Start-Process powershell.exe -WindowStyle Hidden -WorkingDirectory "$Root\apps\api" -ArgumentList @(
    "-NoProfile",
    "-Command",
    "& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload *> '$Root\tmp\local-api.log'"
)

Start-Process powershell.exe -WindowStyle Hidden -WorkingDirectory "$Root\apps\web" -ArgumentList @(
    "-NoProfile",
    "-Command",
    "npm run dev *> '$Root\tmp\local-web.log'"
)

Write-Host "`nLocal-live services started." -ForegroundColor Green
Write-Host "API: http://localhost:8000" -ForegroundColor Green
Write-Host "Web: http://localhost:5173" -ForegroundColor Green
Write-Host "Logs: tmp/local-api.log and tmp/local-web.log" -ForegroundColor Green
