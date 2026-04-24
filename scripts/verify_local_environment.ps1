# LeadScope / ProspectIQ local environment smoke checks (Windows PowerShell).
# Run from repository root:  powershell -ExecutionPolicy Bypass -File scripts/verify_local_environment.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "== ProspectIQ local verification ==" -ForegroundColor Cyan

# 1) Optional: MariaDB via Docker
if (Get-Command docker -ErrorAction SilentlyContinue) {
    try {
        docker info 2>$null | Out-Null
        Write-Host "`n[Docker] Starting MariaDB (infra/docker-compose.yml)..." -ForegroundColor Yellow
        docker compose -f infra/docker-compose.yml up -d
        Start-Sleep -Seconds 3
    } catch {
        Write-Host "[Docker] Skipped or failed (start Docker Desktop if you use compose DB)." -ForegroundColor DarkYellow
    }
} else {
    Write-Host "`n[Docker] Not in PATH; ensure MySQL/MariaDB listens on DATABASE_URL." -ForegroundColor DarkYellow
}

# 2) Backend import
Write-Host "`n[API] Python import..." -ForegroundColor Yellow
Set-Location "$Root\apps\api"
py -3.12 -c "from app.main import app; print('  app import OK:', app.title)"

# 3) Database connectivity
Write-Host "`n[API] Database probe..." -ForegroundColor Yellow
py -3.12 scripts/check_database_connection.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Fix: start DB, then: alembic upgrade head && py -3.12 scripts/seed.py --migrate" -ForegroundColor Red
    Set-Location $Root
    exit 1
}

# 4) Migrations
Write-Host "`n[API] Alembic upgrade head..." -ForegroundColor Yellow
py -3.12 -m alembic upgrade head

# 5) Frontend build
Write-Host "`n[Web] npm ci + build..." -ForegroundColor Yellow
Set-Location "$Root\apps\web"
if (-not (Test-Path "node_modules")) {
    npm ci
}
npm run build

Write-Host "`nAll checks passed." -ForegroundColor Green
Set-Location $Root
