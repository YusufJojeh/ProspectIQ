$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "== ProspectIQ local prod-like verification ==" -ForegroundColor Cyan

$envFile = Join-Path $Root "infra\.env.local-prod-like"
$envExample = Join-Path $Root "infra\local-prod-like.env.example"
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host "[Infra] Created infra/local-prod-like.env from example." -ForegroundColor Yellow
}

docker compose --env-file $envFile -f infra/docker-compose.deploy.yml up -d
Start-Sleep -Seconds 10

$webResponse = Invoke-WebRequest -Uri "http://localhost:8080" -UseBasicParsing -TimeoutSec 10
$apiResponse = Invoke-WebRequest -Uri "http://localhost:8080/api/v1/health/live" -UseBasicParsing -TimeoutSec 10

Write-Host "Web status: $($webResponse.StatusCode)" -ForegroundColor Green
Write-Host "API live status: $($apiResponse.StatusCode)" -ForegroundColor Green
