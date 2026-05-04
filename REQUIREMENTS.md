# Local development requirements (ProspectIQ)

Use this checklist when you clone or copy the project onto a new laptop so the stack runs the same way as on your main machine.

## Prerequisites

| Tool | Version | Notes |
|------|---------|--------|
| Python | **3.12.x** | Required for `apps/api` (`pyproject.toml`: `requires-python = ">=3.12"`). |
| Node.js | **22.x** | Used by CI and `apps/web` (`@types/node` tracks 22.x). LTS-aligned installs are fine. |
| npm | Bundled with Node | Run installs from `apps/web`. |
| Docker Desktop (or Docker Engine) | Current | Used to run MariaDB via `infra/docker-compose.yml`. Optional only if you already have MySQL/MariaDB and point `DATABASE_URL` at it. |
| Git | Any recent | Clone from your remote; do not rely on copying `node_modules` or `.venv`. |

**Windows:** PowerShell is assumed in repo scripts and examples. On macOS/Linux, use the same steps with `python3.12`, `source .venv/bin/activate`, and `cp` instead of `Copy-Item`.

## What travels in Git vs what you recreate locally

| In Git (clone/pull) | Not in Git — create on each machine |
|---------------------|--------------------------------------|
| Application source, `infra/`, `docs/`, workflows | `apps/api/.env` (copy from `apps/api/.env.example`) |
| `apps/api/.env.example`, `apps/web/.env.example` | `apps/web/.env` (copy from `apps/web/.env.example`) |
| Lockfiles (`package-lock.json`, etc.) | `apps/api/.venv/` Python virtual environment |
| | `apps/web/node_modules/` |
| | Local DB volume data (Docker named volumes) |

Never commit real secrets. `.env` files are listed in `.gitignore`. After copying a laptop backup, **delete or rotate** secrets if the folder ever touched a thumb drive or cloud sync used for non-repo files.

## New machine setup (minimal path)

### 1. Get the code

```powershell
git clone <your-remote-url> ProspectIQ
cd ProspectIQ
```

If you copy a folder instead of cloning, still run `git status` inside it and prefer `git pull` on the new machine so you stay aligned with the remote.

### 2. Database (MariaDB)

From the repo root:

```powershell
docker compose -f infra/docker-compose.yml up -d
```

Ensure the Docker engine is running (Windows: Docker Desktop).

### 3. Backend API

```powershell
cd apps/api
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -e .[dev]
Copy-Item .env.example .env
py -3.12 -m alembic upgrade head
py -3.12 scripts/seed.py
py -3.12 -m uvicorn app.main:app --reload
```

API: `http://localhost:8000`

Adjust `.env` if your DB host, port, user, or password differ from `DATABASE_URL` in `.env.example`.

### 4. Frontend

In a second terminal:

```powershell
cd apps/web
npm install
Copy-Item .env.example .env
npm run dev
```

App: `http://localhost:5173`

`VITE_API_BASE_URL` in `apps/web/.env` must match where the API listens (default `http://localhost:8000`). CORS is controlled by `WEB_ORIGIN` / `WEB_ORIGINS` in `apps/api/.env`.

### 5. Smoke check (optional, Windows)

From repo root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_local_environment.ps1
```

## Environment variables reference

- **API:** See `apps/api/.env.example` for all keys (JWT, database, SerpAPI, AI provider, demo vs live modes).
- **Web:** See `apps/web/.env.example` for `VITE_API_BASE_URL`.

For a safe offline or demo-style run, keep `SERPAPI_RUNTIME_MODE=demo` and `AI_PROVIDER=stub` as in the examples unless you intentionally enable live providers.

## Troubleshooting

- **Database connection errors:** Confirm Docker compose is up, then `DATABASE_URL` user/password/database match `infra/docker-compose.yml` (or your own MariaDB).
- **`py` / Python not 3.12:** Install Python 3.12 and use `py -3.12` explicitly on Windows.
- **Port in use:** Change uvicorn port or Vite port in the usual ways, and update `WEB_ORIGIN` / `VITE_API_BASE_URL` accordingly.
- **`npm install` failures:** Use the Node version above; delete `node_modules` and retry.

## Further reading

- Full local startup, demo mode, tests, and deployment: [`README.md`](README.md)
