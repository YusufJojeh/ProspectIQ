# Local development requirements (ProspectIQ)

Use this checklist when you **clone from Git**, **copy from a USB flash drive**, or otherwise move the project onto a new laptop so the stack runs the same way as on your main machine.

## Copying via USB flash drive

Flash copy is fine; treat the stick as **untrusted storage** if it ever held a real `apps/api/.env` with production or personal API keys (rotate those secrets after setup if you are unsure).

**On the source PC (before ejecting the drive)**

1. Copy the **entire** `ProspectIQ` project folder to the stick, or zip it and copy the archive (often faster and fewer “path too long” issues on Windows).
2. Optional but recommended: include the **`.git`** folder so the other laptop can run `git pull` later. In File Explorer, turn on **View → Hidden items** so `.git` is visible; some drag-and-drop UIs skip hidden folders unless you zip the parent folder.
3. To save space and avoid broken installs, you can **delete before copying** (they are recreated on the new machine):
   - `apps/web/node_modules`
   - `apps/api/.venv`
   - `apps/web/dist`, `apps/web/.vite`
   - `tmp/`, `output/`, `apps/web/test-artifacts/` if present
4. Do **not** assume you need `apps/api/.env` or `apps/web/.env` on the stick for the app to work elsewhere: on the new PC, create them from `.env.example` (see below). If you do copy `.env` for convenience, handle the stick like a secret.

**On the destination PC**

1. Copy the folder off the stick to a normal path (for example `Desktop\ProspectIQ`), or extract the zip there.
2. Install **Python 3.12**, **Node 22**, **Docker Desktop** (if you use the compose database), and **Git** (optional but useful if `.git` was included).
3. Follow **First-time run** from step **2** (database) onward. Always run `pip install` and `npm install` on the new machine; do not reuse `node_modules` or `.venv` from another OS or CPU unless you know it is the same environment.
4. If the repo **has no `.git`** folder, you still run the app the same way; to sync with GitHub later, clone fresh into a new folder or `git init` + add remote (advanced)—simplest is to clone from GitHub on that laptop and copy over only files you changed, or use a new zip after pushing from the first PC.

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

## First-time run (all commands)

Run these **once per machine** (or after wiping Docker volumes / the database). Replace `<REPO_ROOT>` mentally with wherever you put the project (for example `C:\Users\You\Desktop\ProspectIQ`).

### 1. Get the code (if you do not have the folder yet)

```powershell
git clone https://github.com/YusufJojeh/ProspectIQ.git
cd ProspectIQ
```

If you copied the project from USB or another disk, `cd` into that folder instead and skip `git clone`.

### 2. Database: option A — Docker (recommended; **creates DB and user automatically**)

`infra/docker-compose.yml` sets `MARIADB_DATABASE`, `MARIADB_USER`, and `MARIADB_PASSWORD` so the first container start creates database **`prospectiq`** and user **`prospectiq`** (password **`prospectiq`**) to match `apps/api/.env.example`. You do **not** need to run `CREATE DATABASE` by hand.

From **repository root**:

```powershell
docker compose -f infra/docker-compose.yml up -d
```

Wait until MariaDB is healthy (first start can take ~30–60 seconds). Then continue with **step 4** (backend).

### 3. Database: option B — MariaDB / MySQL already installed (no Docker)

Create the database and user yourself (matches default `DATABASE_URL` in `apps/api/.env.example`). Connect as root (or another admin) and run:

```sql
CREATE DATABASE IF NOT EXISTS prospectiq
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'prospectiq'@'127.0.0.1' IDENTIFIED BY 'prospectiq';
GRANT ALL PRIVILEGES ON prospectiq.* TO 'prospectiq'@'127.0.0.1';

CREATE USER IF NOT EXISTS 'prospectiq'@'localhost' IDENTIFIED BY 'prospectiq';
GRANT ALL PRIVILEGES ON prospectiq.* TO 'prospectiq'@'localhost';

FLUSH PRIVILEGES;
```

Paste the SQL block into any MariaDB/MySQL admin tool, or run `mysql -u root -p`, paste the block, and press Enter. If you use a **different** database name, user, password, or host, set `DATABASE_URL` in `apps/api/.env` to match.

### 4. Backend API (first time)

From **repository root**:

```powershell
cd apps\api
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -e .[dev]
Copy-Item .env.example .env
py -3.12 -m alembic upgrade head
py -3.12 scripts\seed.py
py -3.12 -m uvicorn app.main:app --reload
```

- API: `http://localhost:8000`
- If `alembic` or `seed` cannot connect: confirm step **2** or **3** is done and `DATABASE_URL` in `.env` matches your running MariaDB.

### 5. Frontend (first time, second terminal)

From **repository root** in a **new** terminal:

```powershell
cd apps\web
npm install
Copy-Item .env.example .env
npm run dev
```

- App: `http://localhost:5173`
- `VITE_API_BASE_URL` in `apps/web/.env` must point at the API (default `http://localhost:8000`). CORS uses `WEB_ORIGIN` / `WEB_ORIGINS` in `apps/api/.env`.

### 6. Smoke check (optional, Windows)

From **repository root**:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_local_environment.ps1
```

### macOS / Linux (same flow, different shell)

```bash
cd /path/to/ProspectIQ
docker compose -f infra/docker-compose.yml up -d

cd apps/api
python3.12 -m venv .venv
source .venv/bin/activate
python3.12 -m pip install --upgrade pip
python3.12 -m pip install -e .[dev]
cp .env.example .env
python3.12 -m alembic upgrade head
python3.12 scripts/seed.py
python3.12 -m uvicorn app.main:app --reload
```

Second terminal:

```bash
cd /path/to/ProspectIQ/apps/web
npm install
cp .env.example .env
npm run dev
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
