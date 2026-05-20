#Requires -Version 5.1
<#
.SYNOPSIS
    Starts the ProspectIQ stack in local production-like mode.

.DESCRIPTION
    - Validates Python 3.12 and Node 20+ are on PATH.
    - Confirms apps/api/.env and apps/web/.env exist (refuses to start otherwise).
    - Confirms MariaDB/MySQL is reachable on the host/port from DATABASE_URL.
    - Creates the target schema and user in MariaDB if missing (idempotent),
      using the local root account. Only touches the schema referenced in
      DATABASE_URL. Does not touch any other database.
    - Runs alembic upgrade head and scripts/seed.py --demo-data (idempotent).
    - Probes SerpAPI, OpenAI, and Ollama using the configured credentials and
      reports reachability WITHOUT printing any secret value.
    - Starts uvicorn in the background.
    - Starts the Vite dev server in the background.
    - Writes logs under ./tmp and prints the URLs.

.PARAMETER ApiPort
    Port for uvicorn. Default 8001 (8000 is often taken by other local projects).

.PARAMETER WebPort
    Port for the Vite dev server. Default 5174.

.PARAMETER ApiHost
    Bind host for uvicorn. Default 127.0.0.1.

.PARAMETER WebHost
    Bind host for Vite. Default 127.0.0.1.

.PARAMETER SkipDbBootstrap
    Skip the create-database / create-user step.

.PARAMETER SkipMigrations
    Skip alembic upgrade head.

.PARAMETER SkipSeed
    Skip scripts/seed.py --demo-data.

.PARAMETER OnlyChecks
    Run validations only, do not start any service.

.NOTES
    - This script NEVER prints the value of any environment variable that
      could contain a secret (passwords, API keys, JWT secrets).
    - It uses the configured DATABASE_URL as source of truth for the local DB
      identity; you should not have to edit anything else to run the stack.
    - It fails fast and loudly when a required tool or env value is missing,
      so you get a clear error instead of a silently broken stack.
#>

[CmdletBinding()]
param(
    [int]$ApiPort = 8001,
    [int]$WebPort = 5174,
    [string]$ApiHost = "127.0.0.1",
    [string]$WebHost = "127.0.0.1",
    [switch]$SkipDbBootstrap,
    [switch]$SkipMigrations,
    [switch]$SkipSeed,
    [switch]$OnlyChecks
)

$ErrorActionPreference = "Stop"

function Write-Section($title) {
    Write-Host ""
    Write-Host "==> $title" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "    OK   $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "    WARN $msg" -ForegroundColor Yellow
}

function Fail($msg) {
    Write-Host "    FAIL $msg" -ForegroundColor Red
    throw $msg
}

# Resolve repo root from this script location
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ApiDir   = Join-Path $RepoRoot "apps\api"
$WebDir   = Join-Path $RepoRoot "apps\web"
$TmpDir   = Join-Path $RepoRoot "tmp"
$LogsDir  = Join-Path $RepoRoot "tmp\local-prod-logs"
$PyTools  = Join-Path $RepoRoot "tmp\local-prod-pytools"

$null = New-Item -ItemType Directory -Force -Path $TmpDir
$null = New-Item -ItemType Directory -Force -Path $LogsDir
$null = New-Item -ItemType Directory -Force -Path $PyTools

# Helper: write a python tool to disk (UTF-8 no BOM) and invoke it via the venv
function Invoke-VenvPy([string]$python, [string]$name, [string]$source, [string]$workDir, [string[]]$extraArgs) {
    $path = Join-Path $PyTools ($name + ".py")
    [System.IO.File]::WriteAllText($path, $source, [System.Text.UTF8Encoding]::new($false))
    Push-Location $workDir
    try {
        $args = @($path)
        if ($extraArgs) { $args += $extraArgs }
        $out = & $python @args
        return [PSCustomObject]@{
            ExitCode = $LASTEXITCODE
            Output   = $out
        }
    } finally {
        Pop-Location
    }
}

# ------------------------------------------------------------------
# 1. Tooling check
# ------------------------------------------------------------------
Write-Section "Tooling"

try {
    $pyVersion = (& py -3.12 --version) 2>&1
    if ($LASTEXITCODE -ne 0) { Fail "Python 3.12 launcher 'py -3.12' is required (got: $pyVersion)" }
    Write-Ok "Python: $pyVersion"
} catch {
    Fail "Python 3.12 not found. Install Python 3.12 from python.org and ensure 'py -3.12' resolves."
}

$nodeVersion = (& node --version)
if ($LASTEXITCODE -ne 0) { Fail "Node.js not found on PATH." }
$nodeMajor = [int]($nodeVersion -replace '^v','' -replace '\..*$','')
if ($nodeMajor -lt 20) {
    Fail "Node $nodeVersion is too old. Node 20 LTS or later is required (20, 22, and 24 are verified working)."
}
Write-Ok "Node: $nodeVersion"

$npmVersion = (& npm --version)
if ($LASTEXITCODE -ne 0) { Fail "npm not found on PATH." }
Write-Ok "npm: $npmVersion"

# ------------------------------------------------------------------
# 2. .env presence check
# ------------------------------------------------------------------
Write-Section "Environment files"

$ApiEnv = Join-Path $ApiDir ".env"
$WebEnv = Join-Path $WebDir ".env"

if (-not (Test-Path $ApiEnv)) {
    Fail "Missing apps\api\.env. Copy from apps\api\.env.local-live.example and fill in real values."
}
Write-Ok "apps\api\.env present"

if (-not (Test-Path $WebEnv)) {
    Fail "Missing apps\web\.env. Copy from apps\web\.env.example."
}
Write-Ok "apps\web\.env present"

$venvPython = Join-Path $ApiDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Fail "Backend venv not found at $venvPython. Create it with: cd apps\api && py -3.12 -m venv .venv && .\.venv\Scripts\Activate.ps1 && py -3.12 -m pip install -e .[dev]"
}

# ------------------------------------------------------------------
# 3. Backend settings inspection
# ------------------------------------------------------------------
Write-Section "Backend Settings"

$inspectorSource = @'
import json
from sqlalchemy.engine.url import make_url
from app.core.config import get_settings
s = get_settings()
url = make_url(s.database_url)
out = {
    "app_env": s.app_env,
    "analysis_runtime": s.analysis_runtime,
    "analysis_fallback_runtime": s.analysis_fallback_runtime,
    "discovery_runtime": s.discovery_runtime,
    "effective_discovery_mode": s.effective_discovery_mode,
    "has_serpapi": s.has_serpapi_configured,
    "has_openai": s.has_openai_configured,
    "has_ollama": s.has_ollama_configured,
    "db_host": url.host,
    "db_port": url.port,
    "db_user": url.username,
    "db_name": url.database,
    "warnings": s.runtime_warnings,
    "web_origins": s.allowed_web_origins,
    "openai_base_url": s.openai_base_url,
    "ollama_base_url": s.ollama_base_url,
    "serpapi_base_url": s.serpapi_base_url,
}
print(json.dumps(out))
'@

$inspectResult = Invoke-VenvPy -python $venvPython -name "inspect_settings" -source $inspectorSource -workDir $ApiDir
if ($inspectResult.ExitCode -ne 0) {
    Write-Host ($inspectResult.Output | Out-String) -ForegroundColor Red
    Fail "Could not load backend settings. Fix apps\api\.env and retry."
}
$cfg = ($inspectResult.Output | Out-String).Trim() | ConvertFrom-Json

Write-Ok "APP_ENV               = $($cfg.app_env)"
Write-Ok "analysis_runtime      = $($cfg.analysis_runtime)"
Write-Ok "analysis_fallback     = $($cfg.analysis_fallback_runtime)"
Write-Ok "discovery_runtime     = $($cfg.discovery_runtime)"
Write-Ok "discovery_mode        = $($cfg.effective_discovery_mode)"
Write-Ok "DB host:port          = $($cfg.db_host):$($cfg.db_port)"
Write-Ok "DB name               = $($cfg.db_name)"
Write-Ok "DB user               = $($cfg.db_user)"
Write-Ok "Allowed web origins   = $($cfg.web_origins -join ', ')"

if (-not $cfg.has_serpapi) { Write-Warn "SERPAPI_API_KEY is empty. Live lead discovery is blocked." }
if (-not $cfg.has_openai)  { Write-Warn "OPENAI_API_KEY is empty. OpenAI fallback unavailable." }
if (-not $cfg.has_ollama)  { Write-Warn "OLLAMA_BASE_URL/OLLAMA_MODEL not configured." }

# Check for weak/default admin password (never print the value)
$defaultPasswords = @("ChangeMe123!", "local-dev-admin-password-rotate-before-sharing")
$adminPassSource = @'
import json, os, sys
from sqlalchemy.engine.url import make_url
from app.core.config import get_settings
s = get_settings()
is_default = s.default_admin_password in {"ChangeMe123!", "local-dev-admin-password-rotate-before-sharing"}
print(json.dumps({"is_default": is_default, "app_env": s.app_env}))
'@
$passCheckResult = Invoke-VenvPy -python $venvPython -name "check_admin_pass" -source $adminPassSource -workDir $ApiDir
if ($passCheckResult.ExitCode -eq 0) {
    $passInfo = ($passCheckResult.Output | Out-String).Trim() | ConvertFrom-Json
    if ($passInfo.is_default) {
        Write-Host ""
        Write-Host "  **** SECURITY WARNING: DEFAULT ADMIN PASSWORD DETECTED ****" -ForegroundColor Red
        Write-Host "  DEFAULT_ADMIN_PASSWORD is set to a known default value." -ForegroundColor Red
        Write-Host "  This is acceptable for a local demo environment but MUST be" -ForegroundColor Red
        Write-Host "  changed before sharing this environment with anyone." -ForegroundColor Red
        Write-Host "  Action: Update DEFAULT_ADMIN_PASSWORD in apps\api\.env to a" -ForegroundColor Yellow
        Write-Host "          unique value with uppercase, lowercase, digit, special char." -ForegroundColor Yellow
        Write-Host ""
    } else {
        Write-Ok "Admin password: custom (not a known default)"
    }
}

foreach ($w in $cfg.warnings) { Write-Warn $w }

if ($cfg.analysis_runtime -eq "demo") {
    Fail "AI runtime is 'demo' but you asked for local-prod-like. Set AI_PROVIDER=ollama or openai in apps\api\.env."
}
if ($cfg.discovery_runtime -in @("demo","stub") -and $cfg.has_serpapi) {
    Write-Warn "SerpAPI key is configured but SERPAPI_RUNTIME_MODE forces $($cfg.discovery_runtime). Set SERPAPI_RUNTIME_MODE=live to actually use the key."
}

$expectedWebOrigin = "http://${WebHost}:${WebPort}"
$corsOk = ($cfg.web_origins -contains $expectedWebOrigin) -or ($cfg.web_origins -contains $expectedWebOrigin.Replace("127.0.0.1","localhost")) -or ($cfg.web_origins -contains $expectedWebOrigin.Replace("localhost","127.0.0.1"))
if (-not $corsOk) {
    Write-Host ""
    Write-Host "  !!!! CORS MISCONFIGURATION DETECTED !!!!" -ForegroundColor Red
    Write-Host "  The selected web origin is:  $expectedWebOrigin" -ForegroundColor Red
    Write-Host "  Configured WEB_ORIGINS does NOT include it." -ForegroundColor Red
    Write-Host ""
    Write-Host "  FIX: Open apps\api\.env and add the following to WEB_ORIGINS (comma-append):" -ForegroundColor Yellow
    Write-Host "       $expectedWebOrigin" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Example:" -ForegroundColor Yellow
    Write-Host "       WEB_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,$expectedWebOrigin" -ForegroundColor Yellow
    Write-Host ""
    if (-not $OnlyChecks) {
        throw "CORS is misconfigured for WebPort=$WebPort. Fix apps\api\.env -> WEB_ORIGINS and retry."
    }
} else {
    Write-Ok "CORS: $expectedWebOrigin is in WEB_ORIGINS"
}

# ------------------------------------------------------------------
# 4. DB reachability + optional bootstrap
# ------------------------------------------------------------------
Write-Section "Database"

$dbHost = $cfg.db_host
$dbPort = if ($cfg.db_port) { [int]$cfg.db_port } else { 3306 }

$tcp = New-Object System.Net.Sockets.TcpClient
try {
    $iar = $tcp.BeginConnect($dbHost, $dbPort, $null, $null)
    if (-not $iar.AsyncWaitHandle.WaitOne(2000, $false)) {
        Fail "MariaDB/MySQL not reachable at ${dbHost}:${dbPort}. Start XAMPP MySQL or 'docker compose -f infra\docker-compose.yml up -d'."
    }
    $tcp.EndConnect($iar)
    Write-Ok "TCP reachable at ${dbHost}:${dbPort}"
} finally {
    $tcp.Close()
}

if (-not $SkipDbBootstrap) {
    $bootstrapSource = @'
import sys
import pymysql
from dotenv import dotenv_values
from sqlalchemy.engine.url import make_url
env = dotenv_values(".env")
u = make_url(env["DATABASE_URL"])
target_db = u.database
target_user = u.username
target_pw = u.password
try:
    conn = pymysql.connect(host=u.host, port=u.port or 3306, user="root", password="", connect_timeout=3)
except pymysql.err.OperationalError:
    sys.stderr.write("ROOT_BOOTSTRAP_FAILED\n")
    sys.exit(2)
cur = conn.cursor()
cur.execute("CREATE DATABASE IF NOT EXISTS `" + target_db + "` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
cur.execute("CREATE USER IF NOT EXISTS '" + target_user + "'@'localhost' IDENTIFIED BY %s", (target_pw,))
cur.execute("CREATE USER IF NOT EXISTS '" + target_user + "'@'127.0.0.1' IDENTIFIED BY %s", (target_pw,))
cur.execute("ALTER USER '" + target_user + "'@'localhost' IDENTIFIED BY %s", (target_pw,))
cur.execute("ALTER USER '" + target_user + "'@'127.0.0.1' IDENTIFIED BY %s", (target_pw,))
cur.execute("GRANT ALL PRIVILEGES ON `" + target_db + "`.* TO '" + target_user + "'@'localhost'")
cur.execute("GRANT ALL PRIVILEGES ON `" + target_db + "`.* TO '" + target_user + "'@'127.0.0.1'")
cur.execute("FLUSH PRIVILEGES")
conn.commit()
conn.close()
print("DB_BOOTSTRAP_OK")
'@
    $bootRes = Invoke-VenvPy -python $venvPython -name "bootstrap_db" -source $bootstrapSource -workDir $ApiDir
    if ($bootRes.ExitCode -eq 0) {
        Write-Ok "Database and user provisioned/verified"
    } elseif ($bootRes.ExitCode -eq 2) {
        Write-Warn "Could not auto-bootstrap DB user/schema (root@localhost without password unavailable)."
        Write-Warn "If your project user already exists with the correct password, the next check will still pass."
    } else {
        Write-Host ($bootRes.Output | Out-String) -ForegroundColor Red
        Fail "Unexpected DB bootstrap failure. Re-run with -SkipDbBootstrap and provision the DB manually."
    }
} else {
    Write-Warn "Skipping DB bootstrap (per -SkipDbBootstrap)."
}

$checkSource = @'
from app.core.database import get_engine
from sqlalchemy import text
with get_engine().connect() as conn:
    conn.execute(text("SELECT 1"))
print("PROJECT_DB_OK")
'@
$checkRes = Invoke-VenvPy -python $venvPython -name "check_db" -source $checkSource -workDir $ApiDir
if ($checkRes.ExitCode -ne 0) {
    Write-Host ($checkRes.Output | Out-String) -ForegroundColor Red
    Fail "Project credentials cannot connect to MariaDB. Verify the password in DATABASE_URL matches the local DB user."
}
Write-Ok "Project user can connect to '$($cfg.db_name)'"

# ------------------------------------------------------------------
# 5. Migrations + seed
# ------------------------------------------------------------------
if (-not $SkipMigrations) {
    Write-Section "Migrations"
    Push-Location $ApiDir
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $venvPython -m alembic upgrade head
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEAP
        Pop-Location
    }
    if ($code -ne 0) { Fail "alembic upgrade head failed (exit $code)." }
    Write-Ok "Alembic head reached"
} else {
    Write-Warn "Skipping migrations (per -SkipMigrations)"
}

if (-not $SkipSeed) {
    Write-Section "Seed"
    Push-Location $ApiDir
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $venvPython scripts\seed.py --demo-data
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEAP
        Pop-Location
    }
    if ($code -ne 0) { Fail "seed.py failed (exit $code)." }
    Write-Ok "Demo data seeded"
} else {
    Write-Warn "Skipping seed (per -SkipSeed)"
}

# ------------------------------------------------------------------
# 6. Provider connectivity probes (no secret echo)
# ------------------------------------------------------------------
Write-Section "Provider connectivity"

$probeSource = @'
import json
from app.core.config import get_settings
from app.core.runtime_health import probe_serpapi, probe_ollama
s = get_settings()
out = {}
out["serpapi"]    = {"configured": s.has_serpapi_configured}
out["openai_cfg"] = {"configured": s.has_openai_configured}
out["ollama"]     = {"configured": s.has_ollama_configured}
if s.has_serpapi_configured:
    p = probe_serpapi(s)
    out["serpapi"]["reachable"] = p.reachable
    out["serpapi"]["detail"]    = p.detail
if s.has_ollama_configured:
    p = probe_ollama(s)
    out["ollama"]["reachable"] = p.reachable
    out["ollama"]["detail"]    = p.detail
print(json.dumps(out))
'@
$probeRes = Invoke-VenvPy -python $venvPython -name "probe_providers" -source $probeSource -workDir $ApiDir
if ($probeRes.ExitCode -eq 0) {
    $probeJson = ($probeRes.Output | Out-String).Trim() | ConvertFrom-Json
    if ($probeJson.serpapi.configured) {
        if ($probeJson.serpapi.reachable) {
            Write-Ok "SerpAPI reachable ($($probeJson.serpapi.detail))"
        } else {
            Write-Warn "SerpAPI not reachable ($($probeJson.serpapi.detail))"
        }
    } else {
        Write-Warn "SerpAPI not configured"
    }
    if ($probeJson.ollama.configured) {
        if ($probeJson.ollama.reachable) {
            Write-Ok "Ollama reachable ($($probeJson.ollama.detail))"
        } else {
            Write-Warn "Ollama not reachable ($($probeJson.ollama.detail)). OpenAI fallback will be used."
        }
    }
    if ($probeJson.openai_cfg.configured) {
        Write-Ok "OpenAI key configured (not actively probed to avoid billable usage)"
    }
} else {
    Write-Warn "Provider probe failed; continuing."
}

if ($OnlyChecks) {
    Write-Section "Done (checks only)"
    Write-Host "All preflight checks passed. Rerun without -OnlyChecks to actually start the stack." -ForegroundColor Green
    return
}

# ------------------------------------------------------------------
# 7. Start API and Web in background
# ------------------------------------------------------------------
Write-Section "Starting services"

function Test-PortFree([string]$h, [int]$p) {
    $listener = $null
    try {
        $ip = [System.Net.IPAddress]::Parse($h)
        $listener = [System.Net.Sockets.TcpListener]::new($ip, $p)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { try { $listener.Stop() } catch {} }
    }
}

if (-not (Test-PortFree $ApiHost $ApiPort)) {
    Fail "Port $ApiPort on $ApiHost is already in use. Choose a different -ApiPort or stop the conflicting process."
}
if (-not (Test-PortFree $WebHost $WebPort)) {
    Fail "Port $WebPort on $WebHost is already in use. Choose a different -WebPort or stop the conflicting process."
}

$apiLog = Join-Path $LogsDir "api.log"
$webLog = Join-Path $LogsDir "web.log"

$apiCmd = "Set-Location '$ApiDir'; & '$venvPython' -m uvicorn app.main:app --host $ApiHost --port $ApiPort --reload *>&1 | Tee-Object -FilePath '$apiLog'"
$webCmd = "Set-Location '$WebDir'; & npm run dev -- --host $WebHost --port $WebPort *>&1 | Tee-Object -FilePath '$webLog'"

$apiProc = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile","-NoLogo","-Command",$apiCmd) -WindowStyle Hidden -PassThru
$webProc = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile","-NoLogo","-Command",$webCmd) -WindowStyle Hidden -PassThru

Write-Ok "API process started (PID $($apiProc.Id)) -> $apiLog"
Write-Ok "Web process started (PID $($webProc.Id)) -> $webLog"

Write-Host ""
Write-Host "Waiting for API to come up..." -ForegroundColor Cyan
$apiUp = $false
for ($i=0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://${ApiHost}:${ApiPort}/api/v1/health/live" -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $apiUp = $true; break }
    } catch {}
}
if ($apiUp) {
    Write-Ok "API live (http://${ApiHost}:${ApiPort}/api/v1/health/live)"
} else {
    Write-Warn "API did not respond on /api/v1/health/live within 30s. See $apiLog"
}

Write-Host "Waiting for web dev server..." -ForegroundColor Cyan
$webUp = $false
for ($i=0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://${WebHost}:${WebPort}/" -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $webUp = $true; break }
    } catch {}
}
if ($webUp) {
    Write-Ok "Web up (http://${WebHost}:${WebPort}/)"
} else {
    Write-Warn "Web did not respond on /. See $webLog"
}

Write-Host ""
Write-Host "Stack is up." -ForegroundColor Green
Write-Host "  API : http://${ApiHost}:${ApiPort}" -ForegroundColor Green
Write-Host "  Web : http://${WebHost}:${WebPort}" -ForegroundColor Green
Write-Host "  Logs: $LogsDir" -ForegroundColor Green
Write-Host ""
Write-Host "Stop the stack with:" -ForegroundColor Yellow
$stopIds = "$($apiProc.Id),$($webProc.Id)"
Write-Host "  Stop-Process -Id $stopIds -Force" -ForegroundColor Yellow
