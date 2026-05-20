# Local Production-Like Setup — ProspectIQ / LeadScope AI

This document describes how to run the full ProspectIQ stack on a developer
laptop with **real providers** (real SerpAPI, real OpenAI, optional Ollama) so
that every existing feature works exactly as it would in production — but
against a local database, against the local API, and against the local web app.

> Local production-like ≠ cloud deploy. We do **not** deploy to the cloud here.
> We just stop using any demo / stub mode silently and we wire the local stack
> against real third-party providers when the operator supplies real keys.

---

## 1. Laptop requirements

| Tool | Required version | Notes |
| --- | --- | --- |
| Windows | 10 or 11 | macOS / Linux also work; use the equivalent commands |
| PowerShell | 5.1+ (built-in) or PowerShell 7 | Used for the startup script |
| Python | **3.12.x** | Verify with `py -3.12 --version`. 3.10/3.11/3.14 will not work — the project pins 3.12 |
| Node.js | **20 LTS or later** | Verify with `node --version`. Node 20, 22, and 24 are verified working (build + tests pass). Node 18 is end-of-life and not supported. |
| npm | bundled with Node | |
| MySQL or MariaDB | **MariaDB 10.4+** or MySQL 8 | We test against XAMPP MariaDB 10.4.32. Docker MariaDB 11 (via `infra/docker-compose.yml`) is also supported |
| Docker Desktop | optional | Needed only if you prefer Docker MariaDB instead of XAMPP |
| Git | any modern version | |
| Ollama | optional | Only needed if you want local LLM streaming. OpenAI is automatically used as fallback when Ollama is unreachable |
| curl | any | Bundled with Git for Windows |

### Optional but recommended

- A free `8001/tcp` for the API and `5174/tcp` for the web dev server.
  Defaults are `8000` and `5173`. If those are already in use by another local
  project (very common on a dev box that also runs Laravel / Next / Vite),
  use the alternate ports documented below.

---

## 2. Environment variables (descriptions only — never paste real secrets)

All variables live in two files (both are **git-ignored**, never commit them):

- `apps/api/.env`
- `apps/web/.env`

### `apps/api/.env`

| Variable | Description |
| --- | --- |
| `APP_NAME` | Display name of the API, e.g. `LeadScope AI API` |
| `APP_ENV` | `development` for local-prod-like. Set to `production` only when you actually deploy. |
| `API_V1_PREFIX` | API prefix, must remain `/api/v1` |
| `DATABASE_URL` | SQLAlchemy URL, e.g. `mysql+pymysql://prospectiq:<password>@127.0.0.1:3306/prospectiq` |
| `JWT_SECRET` | Long random string (≥32 chars). Used to sign access tokens |
| `JWT_EXPIRE_MINUTES` | Access token lifetime in minutes (default 120) |
| `WEB_ORIGIN` | Primary allowed browser origin, e.g. `http://localhost:5173` |
| `WEB_ORIGINS` | Comma-separated list of allowed origins. Must include the web dev server URL |
| `SQL_ECHO` | `false` in local-prod-like |
| `LOG_LEVEL` | `INFO` is the recommended baseline |
| `ENABLE_DB_HEALTHCHECK` | `true` exposes `/api/v1/health/db` |
| `ENABLE_REQUEST_LOGGING` | `true` to log method/path/status/duration |
| `ENABLE_API_DOCS` | Leave `false` unless you explicitly want `/docs` and `/openapi.json` |
| `DEFAULT_ADMIN_EMAIL` | First-time admin email |
| `DEFAULT_ADMIN_PASSWORD` | First-time admin password. **Rotate before sharing the env.** |
| `DEFAULT_ADMIN_NAME` | First-time admin display name |
| `DEFAULT_WORKSPACE_PUBLIC_ID` | Public ID of the bootstrap workspace |
| `DEFAULT_WORKSPACE_NAME` | Display name of the bootstrap workspace |
| `SERPAPI_RUNTIME_MODE` | `live` to use real SerpAPI (requires a real key). `demo` / `stub` / `blocked` skip the network |
| `SERPAPI_API_KEY` | Your SerpAPI key when `SERPAPI_RUNTIME_MODE=live` |
| `SERPAPI_BASE_URL` | `https://serpapi.com/search.json` |
| `DISCOVERY_KILL_SWITCH` | `false` to allow discovery; `true` downgrades to single-path |
| `DISCOVERY_MODE` | `multi_engine_multi_query` (recommended) or `multi_query_single_engine` or `single_path` |
| `DISCOVERY_MULTI_ENGINE_ENABLED` | `true` lets `multi_engine_multi_query` actually run |
| `DISCOVERY_ENGINE_LIST` | Comma-separated SerpAPI engines, default `google_maps_search,google_maps_place,google_web` |
| `DISCOVERY_MAX_CONCURRENCY` | Parallel SerpAPI calls per job |
| `DISCOVERY_MAX_CALLS_PER_JOB` | Upper bound on SerpAPI calls per job |
| `DISCOVERY_MAX_CANDIDATES_AFTER_MERGE` | Cap on candidates after cross-source dedupe |
| `DISCOVERY_MAX_ENRICHMENTS_PER_JOB` | Cap on Place enrichments per job |
| `DISCOVERY_GLOBAL_JOB_DEADLINE_SECONDS` | Hard timeout per job |
| `DISCOVERY_BILINGUAL_EXPANSION_ENABLED` | `true` enables Arabic ↔ English query expansion |
| `DISCOVERY_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Failures before the breaker opens |
| `DISCOVERY_CIRCUIT_BREAKER_COOLDOWN_SECONDS` | Cooldown before re-trying after the breaker opens |
| `AI_PROVIDER` | `ollama`, `openai`, `auto`, or `stub`. **Never use `stub` when you have real keys.** |
| `OPENAI_API_KEY` | Your OpenAI key. Used as primary if `AI_PROVIDER=openai`, or as fallback if `AI_PROVIDER=ollama` and Ollama is unreachable |
| `OPENAI_MODEL` | OpenAI model id, e.g. `gpt-4.1-mini` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` (override only if you proxy OpenAI) |
| `OLLAMA_BASE_URL` | URL of local Ollama, e.g. `http://localhost:11434`. Leave set even if Ollama is not running — the API will fall back to OpenAI |
| `OLLAMA_MODEL` | Local model name, e.g. `llama3.1` |
| `ENABLE_BILLING_SIMULATION` | `true` enables the billing simulation endpoints (`mark-paid`, `simulate-failure`). **Do not set in production.** Default: `false` (off). |

### `apps/web/.env`

| Variable | Description |
| --- | --- |
| `VITE_API_BASE_URL` | Browser-side URL of the API. For default ports: `http://localhost:8000`. For the alternate ports used by the startup script: `http://localhost:8001`. Leave **empty** only when nginx is fronting same-origin (Docker production-like) |
| `VITE_ENABLE_BILLING_SIMULATION` | `true` shows billing simulation buttons in the UI. Must match `ENABLE_BILLING_SIMULATION=true` in the backend. Default: `false` (hidden). |

> **Never paste real values into this document, into git, into screenshots,
> into commit messages, or into chat logs.** The startup script never echoes
> secrets either.

---

## 3. Setup from zero on a fresh laptop

### 3.1 Clone the repository

```powershell
cd C:\Users\<you>\Documents
git clone https://github.com/YusufJojeh/ProspectIQ.git
cd ProspectIQ
```

### 3.2 Provide the env files

You need to bring `apps/api/.env` and `apps/web/.env` to the new laptop
**out of band** (USB stick, password manager attachment, encrypted note, etc.).
Do **not** transfer them through git, Slack screenshots, or untrusted channels.

If you don't have a copy of `.env` yet, start from the examples:

```powershell
Copy-Item apps\api\.env.local-live.example apps\api\.env
Copy-Item apps\web\.env.example            apps\web\.env
```

Then edit each `.env` and fill in real values for:

- `JWT_SECRET` — generate a long random secret (≥32 chars)
- `DATABASE_URL` — point to your local MariaDB/MySQL
- `SERPAPI_API_KEY` — real SerpAPI key (or leave empty + set `SERPAPI_RUNTIME_MODE=blocked`)
- `OPENAI_API_KEY` — real OpenAI key (or leave empty if you only use Ollama)
- `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD`

### 3.3 Database

You can use **either** XAMPP MariaDB **or** Docker MariaDB. Pick one.

#### Option A — XAMPP MariaDB (no Docker)

1. Start XAMPP Control Panel → start MySQL (it listens on `127.0.0.1:3306`).
2. The startup script `scripts/setup_local_prod_like.ps1` will read
   `DATABASE_URL` from `apps/api/.env`, log in as `root` (no password — the
   XAMPP default) and create the database and user **only** for the schema
   referenced in `DATABASE_URL`. It does not touch any other database on the
   same MariaDB instance.

#### Option B — Docker MariaDB

```powershell
docker compose -f infra\docker-compose.yml up -d
```

This spins up MariaDB 11 with database `prospectiq`, user `prospectiq`,
password `prospectiq`. Make sure your `DATABASE_URL` matches those values.

### 3.4 Backend dependencies

```powershell
cd apps\api
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -e .[dev]
```

### 3.5 Migrations + seed

```powershell
py -3.12 -m alembic upgrade head
py -3.12 scripts\seed.py --demo-data
deactivate
cd ..\..
```

This brings the schema to `0008_db_hardening_integrity` and seeds the demo
workspace and four roles.

### 3.6 Frontend dependencies

```powershell
cd apps\web
npm ci
cd ..\..
```

### 3.7 Run everything via the startup script

```powershell
.\scripts\setup_local_prod_like.ps1
```

The script will:

1. Validate that Python 3.12, Node 22, and the MariaDB instance are reachable.
2. Ensure the `apps/api/.env` and `apps/web/.env` files exist (refusing to
   start if they are missing).
3. Ensure the database/user from `DATABASE_URL` exist (creates them via the
   local `root` account when missing).
4. Run `alembic upgrade head` (idempotent).
5. Run `scripts/seed.py --demo-data` (idempotent).
6. Probe SerpAPI, OpenAI, and Ollama with the credentials from `.env` and
   **report which ones are reachable** without printing any secret value.
7. Start the API on the requested port (default 8001) in the background.
8. Start the web dev server on the requested port (default 5174) in the
   background.
9. Print the URLs and the log file paths.

Defaults are `-ApiPort 8001 -WebPort 5174` so the script does **not** collide
with other local projects that already occupy `8000` and `5173`. If you want
to use the original ports, pass `-ApiPort 8000 -WebPort 5173`, but first stop
any other process holding those ports.

---

## 4. How to run individual components

When you don't want the startup script (for example, you want hot reload on
each side in its own terminal):

### Backend API

```powershell
cd apps\api
.\.venv\Scripts\Activate.ps1
py -3.12 -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

### Frontend web

```powershell
cd apps\web
npm run dev -- --host 127.0.0.1 --port 5174
```

Make sure `apps/web/.env` has `VITE_API_BASE_URL=http://localhost:8001` (or
whatever port your API uses) so the SPA hits the right backend, **and** that
`WEB_ORIGINS` in `apps/api/.env` includes the web dev URL.

### Background tasks

The current backend uses FastAPI `BackgroundTasks` for lead discovery and
lead refresh. They run in the same uvicorn process. There is **no separate
worker, queue, or scheduler**, and there is no WebSocket server. The frontend
polls via React Query.

### Realtime

Not implemented. The assistant uses SSE streaming over the same FastAPI
process — no extra service is needed.

---

## 5. How to verify everything works

### 5.1 Quick health checks

```powershell
curl http://127.0.0.1:8001/api/v1/health
curl http://127.0.0.1:8001/api/v1/health/db
curl http://127.0.0.1:8001/api/v1/health/ready
curl -I http://127.0.0.1:5174/
```

Expected: `200` for all four.

### 5.2 Smoke login

Open `http://localhost:5174/login` and sign in with one of the seeded demo
accounts (see section 6). The session is stored in `localStorage` under
`prospectiq-auth-session`.

### 5.3 Backend test suite

```powershell
cd apps\api
.\.venv\Scripts\Activate.ps1
py -3.12 -m pytest --basetemp ..\..\tmp\pytest-bt -q
```

The `--basetemp` flag works around a Windows-specific permission quirk on
`C:\Users\<you>\AppData\Local\Temp\pytest-of-*`. Without it the
`tmp_path` fixture may fail with `PermissionError [WinError 5]` even when the
code is correct.

### 5.4 Frontend checks

```powershell
cd apps\web
npm run lint
npm run test:unit
npm run build
```

### 5.5 Live provider verification

The startup script prints which providers are reachable. To re-check at any
time without restarting:

```powershell
cd apps\api
.\.venv\Scripts\Activate.ps1
py -3.12 -c "from app.core.config import get_settings; s=get_settings(); print('AI:', s.analysis_runtime, '| fallback:', s.analysis_fallback_runtime); print('Discovery:', s.discovery_runtime)"
```

You should see something like:

```
AI: ollama | fallback: openai
Discovery: live
```

If the analysis runtime is ever `demo` you have a configuration drift — fix
your `.env` so that real keys are picked up.

---

## 6. Demo / admin accounts

The `scripts/seed.py --demo-data` script creates four accounts in the
default workspace. The passwords are intentionally simple because this is a
local-only fixture.

| Email | Role | Password |
| --- | --- | --- |
| `admin@example.test` | `account_owner` | `password` |
| `manager@example.test` | `manager` | `password` |
| `user1@example.test` | `member` | `password` |
| value of `DEFAULT_ADMIN_EMAIL` | `account_owner` | value of `DEFAULT_ADMIN_PASSWORD` |

> Rotate the bootstrap admin credentials before sharing this environment with
> anyone else. The runtime emits a warning whenever
> `DEFAULT_ADMIN_PASSWORD` is left at one of the well-known dev defaults.

---

## 7. Common errors and fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `pymysql.err.OperationalError (1045, "Access denied for user 'prospectiq'@'localhost'")` | The DB user/database in `DATABASE_URL` does not exist on the local MariaDB | Run `scripts/setup_local_prod_like.ps1` or create them manually as `root` |
| `PermissionError [WinError 5] ... pytest-of-Yusuf` during pytest | Windows ACL on the default pytest tmp dir | Add `--basetemp ..\..\tmp\pytest-bt` to the pytest command |
| API starts but the SPA can't talk to it | `VITE_API_BASE_URL` does not match the actual API port, or the API port is not in `WEB_ORIGINS` | Align `apps/web/.env` and `apps/api/.env` so the URLs match |
| 404 HTML response on `http://localhost:8000/api/v1/health` from a completely different (Laravel-style) app | Another local project is bound to port 8000 | Use the alternate ports (`-ApiPort 8001`) or stop the other project |
| `analysis_runtime: demo` even though `OPENAI_API_KEY` is set | `AI_PROVIDER=stub` in `.env` | Set `AI_PROVIDER=ollama` or `openai` |
| `Discovery: blocked` even though `SERPAPI_API_KEY` is set | `SERPAPI_RUNTIME_MODE` is set to `blocked` / `demo` / `stub` | Set `SERPAPI_RUNTIME_MODE=live` |
| Assistant chat fails with `503 Service Unavailable` | Ollama isn't running **and** OpenAI fallback is unreachable / wrong key | Start Ollama, or correct `OPENAI_API_KEY` |

---

## 8. Fastest setup path (5 commands)

Assuming Python 3.12, Node 22, MariaDB and the two `.env` files are already
in place:

```powershell
cd C:\Users\<you>\<wherever>\ProspectIQ
cd apps\api ; py -3.12 -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; py -3.12 -m pip install -e .[dev] ; py -3.12 -m alembic upgrade head ; py -3.12 scripts\seed.py --demo-data ; deactivate ; cd ..\..
cd apps\web ; npm ci ; cd ..\..
.\scripts\setup_local_prod_like.ps1
```

---

## 9. Missing Local Requirements

These items are needed for **specific features** to work in real (non-stub)
mode. The rest of the app still works without them.

| Feature | Requires | What breaks if missing |
| --- | --- | --- |
| Real lead discovery (search jobs) | `SERPAPI_RUNTIME_MODE=live` + a valid `SERPAPI_API_KEY` | Search jobs return no real candidates. The backend exposes `Discovery: blocked` in `get_settings()` |
| Local LLM streaming (Ollama) | Local Ollama daemon on `OLLAMA_BASE_URL`, model `OLLAMA_MODEL` pulled (`ollama pull llama3.1`) | The first attempt to hit the LLM falls back to OpenAI. No user-visible failure if OpenAI is reachable. If both are unreachable the assistant raises `503 ServiceUnavailable` |
| Cloud LLM (OpenAI) | Valid `OPENAI_API_KEY` + `OPENAI_MODEL` | Same as above — only matters when Ollama is also down |
| Outreach email delivery | **Not implemented** in this codebase. Outreach generates the message but does not send it | The frontend exposes a "copy to clipboard" button only |
| Real payment processing | **Not implemented**. Billing is stub-only with `mark-paid` and `simulate-failure` endpoints | No production payment flow |
| Avatar / file uploads | **Not implemented** — backend has no upload endpoint | The `avatar_url` field stays whatever the seed sets |
| Forgot password flow | **Backend endpoint not implemented**. Only the frontend route exists | Submitting the forgot-password form has no real backend effect |
| Refresh tokens | **Not implemented**. Sessions expire hard after `JWT_EXPIRE_MINUTES` | User has to re-login after the access token expires |
| Rate limiting on `/auth/*` | **Not implemented** | Brute-force protection relies on the operating environment |

If you add the missing services later (real Ollama, real SMTP, etc.), no
code change is needed for the providers that already have stable adapters —
just edit `.env`. The frontend reads everything through the same API base
URL, so nothing else moves.

---

## 10. Key Rotation Policy

If any API key (OpenAI, SerpAPI, or any future provider) is ever exposed in
a chat log, commit message, screenshot, or any channel outside the `.env`
file itself:

1. **Treat the key as compromised immediately.**
2. Rotate it at the provider's dashboard (OpenAI Platform, SerpAPI account).
3. Paste the new key into `apps/api/.env` only.
4. Verify the new key works:
   ```powershell
   cd apps\api
   .\.venv\Scripts\Activate.ps1
   py -3.12 -c "from app.core.config import get_settings; s=get_settings(); print('AI:', s.analysis_runtime, '| fallback:', s.analysis_fallback_runtime); print('Discovery:', s.discovery_runtime)"
   ```
5. Never reuse a key that was exposed, even if the exposure was brief.

The `.env` placeholder `ROTATED-KEY-REQUIRED-paste-your-new-*-key-here`
is used when a key needs rotation before the provider will function.

---

## 11. Related Documentation

- [I18N Translation Audit](I18N_TRANSLATION_AUDIT.md) — full audit of
  EN/AR locale parity, bugs fixed, and Arabic translation quality.
