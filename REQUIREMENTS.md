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
2. Install **Python 3.12**, **Node 22**, and either **MariaDB/MySQL locally** or **Docker Desktop** (only if you use `infra/docker-compose.yml` for the database). **Git** is optional but useful if `.git` was included.
3. Follow **New machine setup** from step 2 (Database) onward. Always run `pip install` and `npm install` on the new machine; do not reuse `node_modules` or `.venv` from another OS or CPU unless you know it is the same environment.
4. If the repo **has no `.git`** folder, you still run the app the same way; to sync with GitHub later, clone fresh into a new folder or `git init` + add remote (advanced)—simplest is to clone from GitHub on that laptop and copy over only files you changed, or use a new zip after pushing from the first PC.

## Prerequisites

| Tool                              | Version           | Notes                                                                                                                         |
| --------------------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Python                            | **3.12.x**  | Required for`apps/api` (`pyproject.toml`: `requires-python = ">=3.12"`).                                                |
| Node.js                           | **22.x**    | Used by CI and`apps/web` (`@types/node` tracks 22.x). LTS-aligned installs are fine.                                      |
| npm                               | Bundled with Node | Run installs from`apps/web`.                                                                                                |
| MariaDB or MySQL (local install)  | Current           | Optional alternative to Docker: server listening on`127.0.0.1:3306`. Matches `DATABASE_URL` in `apps/api/.env.example`. |
| Docker Desktop (or Docker Engine) | Current           | Optional: run MariaDB via`infra/docker-compose.yml` if you prefer not to install a database server on the host.             |
| Git                               | Any recent        | Clone from your remote; do not rely on copying`node_modules` or `.venv`.                                                  |

**Windows:** PowerShell is assumed in repo scripts and examples. On macOS/Linux, use the same steps with `python3.12`, `source .venv/bin/activate`, and `cp` instead of `Copy-Item`.

## What travels in Git vs what you recreate locally

| In Git (clone/pull)                                  | Not in Git — create on each machine                    |
| ---------------------------------------------------- | ------------------------------------------------------- |
| Application source,`infra/`, `docs/`, workflows  | `apps/api/.env` (copy from `apps/api/.env.example`) |
| `apps/api/.env.example`, `apps/web/.env.example` | `apps/web/.env` (copy from `apps/web/.env.example`) |
| Lockfiles (`package-lock.json`, etc.)              | `apps/api/.venv/` Python virtual environment          |
|                                                      | `apps/web/node_modules/`                              |
|                                                      | Local DB volume data (Docker named volumes)             |

Never commit real secrets. `.env` files are listed in `.gitignore`. After copying a laptop backup, **delete or rotate** secrets if the folder ever touched a thumb drive or cloud sync used for non-repo files.

## First-time run without Docker (local database)

Use this when you have **MariaDB or MySQL installed on the machine** (no Docker). The defaults below match `apps/api/.env.example`: database `prospectiq`, user `prospectiq`, password `prospectiq`, host `127.0.0.1`, port `3306`.

### 1. Install and start the database server

- Install **MariaDB** or **MySQL** from the official installer for your OS.
- Start the service so something is listening on **3306** (default). Use your vendor docs if the port differs; if it does, change `DATABASE_URL` in `apps/api/.env` accordingly.

### 2. Create database and user (SQL)

Open a client as a privileged user (examples):

- **Windows (typical MariaDB path):**`"C:\Program Files\MariaDB 11.4\bin\mysql.exe" -u root -p`(adjust folder if your version/path differs.)
- **macOS/Linux:**
  `sudo mysql -u root`
  or `mysql -u root -p`

Then run:

```sql
CREATE DATABASE IF NOT EXISTS prospectiq CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'prospectiq'@'127.0.0.1' IDENTIFIED BY 'prospectiq';
CREATE USER IF NOT EXISTS 'prospectiq'@'localhost' IDENTIFIED BY 'prospectiq';

GRANT ALL PRIVILEGES ON prospectiq.* TO 'prospectiq'@'127.0.0.1';
GRANT ALL PRIVILEGES ON prospectiq.* TO 'prospectiq'@'localhost';

FLUSH PRIVILEGES;
```

If your SQL server rejects `CREATE USER IF NOT EXISTS` (some older MySQL builds), create the two users once without `IF NOT EXISTS`, or drop existing dev users first, then re-run the `GRANT` lines.

Confirm `DATABASE_URL` in `.env` after you copy the example (next step). It should be:

`mysql+pymysql://prospectiq:prospectiq@127.0.0.1:3306/prospectiq`

### 3. Backend (first terminal)

From the **repository root** (adjust `cd` if your folder name differs):

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

### 4. Frontend (second terminal)

```powershell
cd apps/web
npm install
Copy-Item .env.example .env
npm run dev
```

App: `http://localhost:5173`

On macOS/Linux, use `python3.12`, `source .venv/bin/activate`, and `cp .env.example .env` inside `apps/api` and `apps/web`.

## New machine setup (minimal path)

### 1. Get the code

```powershell
git clone <your-remote-url> ProspectIQ
cd ProspectIQ
```

If you copy a folder instead of cloning, still run `git status` inside it and prefer `git pull` on the new machine so you stay aligned with the remote.

### 2. Database (MariaDB via Docker)

If you use a **local MariaDB/MySQL install without Docker**, skip this step and follow **[First-time run without Docker (local database)](#first-time-run-without-docker-local-database)** for creating the database and users first.

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

- **API:** See `apps/api/.env.local-live.example` for the recommended local-live profile and `apps/api/.env.example` for the generic template.
- **Web:** See `apps/web/.env.example` for `VITE_API_BASE_URL`.

Recommended defaults for a safe first run:

- `SERPAPI_RUNTIME_MODE=demo`
- `AI_PROVIDER=stub`

For real-provider validation, switch to `apps/api/.env.local-live.example` values (`SERPAPI_RUNTIME_MODE=live`, real `SERPAPI_API_KEY`, and `AI_PROVIDER=ollama|openai|auto`).

## Troubleshooting

- **Database connection errors:** Confirm Docker compose is up, then `DATABASE_URL` user/password/database match `infra/docker-compose.yml` (or your own MariaDB).
- **`py` / Python not 3.12:** Install Python 3.12 and use `py -3.12` explicitly on Windows.
- **Port in use:** Change uvicorn port or Vite port in the usual ways, and update `WEB_ORIGIN` / `VITE_API_BASE_URL` accordingly.
- **`npm install` failures:** Use the Node version above; delete `node_modules` and retry.

## Further reading

- Full local startup, demo mode, tests, and deployment: [`README.md`](README.md)
