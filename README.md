# LeadScope AI

LeadScope AI is the product. `ProspectIQ` is the repository slug and internal package prefix used in local paths, container names, and environment defaults.

## Repository Layout

```text
ProspectIQ/
|-- apps/
|   |-- api/
|   `-- web/
|-- docs/
|-- infra/
|-- .editorconfig
|-- .gitignore
|-- .pre-commit-config.yaml
`-- README.md
```

## Foundation Snapshot

- `apps/api`: FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic backend.
- `apps/web`: React + TypeScript + Vite + Tailwind frontend.
- `docs`: implementation and delivery references.
- `infra`: local MariaDB development assets.

## Local Startup

Validated against CI:

- Python `3.12`
- Node.js `22`
- PowerShell examples are shown below; on macOS/Linux use the shell-equivalent commands such as `python3.12`, `cp`, and `source .venv/bin/activate`.

### 1. Start MariaDB

```powershell
docker compose -f infra/docker-compose.yml up -d
```

If Docker Desktop is installed on Windows, make sure the Docker engine is actually running before continuing.

### 2. Run the backend

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

Backend URL: `http://localhost:8000`

### 3. Run the frontend

```powershell
cd apps/web
npm install
Copy-Item .env.example .env
npm run dev
```

Frontend URL: `http://localhost:5173`

For local development, the backend accepts both `http://localhost:5173` and `http://127.0.0.1:5173` by default. Set `WEB_ORIGINS` explicitly when you need a tighter origin list.

## Demo Setup

For a graduation-project or presentation demo, use the explicit demo-safe runtime instead of relying on live providers:

1. In `apps/api/.env`, set `SERPAPI_RUNTIME_MODE=demo` and keep `AI_PROVIDER=stub`.
2. Seed the presentation dataset:

```powershell
cd apps/api
py -3.12 scripts/seed.py --migrate --demo-data --reset-demo-data
```

3. Start the API and frontend normally.

This gives you:

- one admin account plus manager and sales demo accounts
- pre-seeded search jobs, leads, scores, recommendations, outreach drafts, and activity
- visible map coordinates for presentation
- a reproducible fallback path where new searches use demo provider data unless live SerpAPI is explicitly enabled

See [`docs/demo-flow.md`](docs/demo-flow.md) for the presentation script, demo accounts, and reset commands.

## Real Visual QA

Use the seeded demo-safe runtime when you want browser screenshots from the real stack instead of the mock Playwright suite.

1. Start MariaDB.
2. In `apps/api/.env`, keep `SERPAPI_RUNTIME_MODE=demo` and `AI_PROVIDER=stub`.
3. Reset the demo dataset:

```powershell
cd apps/api
py -3.12 scripts/seed.py --migrate --demo-data --reset-demo-data
```

4. Start the API on `http://127.0.0.1:8000`.
5. Run the real visual suite:

```powershell
cd apps/web
npm run test:e2e:real
```

Artifacts:

- screenshots: `apps/web/test-artifacts/visual-qa/screenshots`
- Playwright HTML report: `apps/web/test-artifacts/visual-qa/playwright-report/index.html`
- markdown summary: `docs/visual-qa-report.md`

Important:

- `npm run test:e2e` is still the mock-backed Playwright path used for fast CI coverage.
- `npm run test:e2e:real` is the real-stack visual QA path and expects the backend and seeded MariaDB runtime to already be available.

## Deployment

### Container Images

- API image: `ghcr.io/yusufjojeh/prospectiq-api`
- Web image: `ghcr.io/yusufjojeh/prospectiq-web`

The web image supports two production modes:

- same-origin mode: set `WEB_PUBLIC_API_BASE_URL=` and let Nginx proxy `/api/*` to the API container
- split-origin mode: set `WEB_PUBLIC_API_BASE_URL=https://api.example.com`

### Docker Compose Deployment

```powershell
Copy-Item infra/deploy.env.example infra/deploy.env
# edit infra/deploy.env with real secrets and hostnames
docker compose --env-file infra/deploy.env -f infra/docker-compose.deploy.yml pull
docker compose --env-file infra/deploy.env -f infra/docker-compose.deploy.yml up -d
```

The deployment stack includes:

- MariaDB
- FastAPI API container
- Nginx-served React frontend container

## Quality Commands

### Backend

```powershell
cd apps/api
py -3.12 -m pytest -q
py -3.12 -m ruff check app tests migrations --config pyproject.toml
py -3.12 -m mypy app --config-file pyproject.toml
py -3.12 -m alembic upgrade head --sql > $env:TEMP\alembic.sql
```

### Frontend

```powershell
cd apps/web
npm run lint
npm run test:unit
npm run build
npm run test:e2e -- --workers=2
npm run test:e2e:real
```

## CI

GitHub Actions runs the same validation path from [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

- Backend: `ruff`, `mypy`, `pytest`, and `alembic upgrade head --sql`
- Frontend: `eslint`, `vitest`, `vite build`, and Playwright E2E
- Containers: API and web Docker image builds
- Deployment stack smoke: local image build plus `infra/docker-compose.deploy.yml` boot, seed, health, and login verification

## CD

GitHub Actions now includes two delivery workflows:

- `release-images.yml`: builds and publishes API and web images to GHCR on `main`, tags, or manual dispatch
- `deploy.yml`: deploys a chosen image tag to a remote Docker host over SSH using `infra/docker-compose.deploy.yml`, then verifies stack health and login bootstrap with `infra/scripts/verify_deploy_stack.sh`

Required GitHub Actions deploy secrets:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_PATH`
- `DEPLOY_ENV_FILE`
- `GHCR_DEPLOY_USERNAME`
- `GHCR_DEPLOY_TOKEN`

The frontend browser tests use the repo's mock API layer, so they do not require a live backend in CI. The backend suite uses isolated test databases and an offline Alembic render check instead of a live MariaDB service.
The deployment smoke job uses locally built images and a temporary deployment env so the image-based stack is validated before release.

## Reference Docs

- [`docs/implementation-reference.md`](docs/implementation-reference.md)
- [`docs/README.md`](docs/README.md)
- [`docs/architecture-review.md`](docs/architecture-review.md)
- [`docs/demo-flow.md`](docs/demo-flow.md)
- [`docs/go-live-checklist.md`](docs/go-live-checklist.md)
- [`docs/visual-qa-report.md`](docs/visual-qa-report.md)

## Local Verification Script

For a Windows-first smoke pass after dependencies are installed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_local_environment.ps1
```

This checks Docker availability, API import, database connectivity, Alembic upgrade, and the frontend production build.

## Local vs Production-Style Defaults

- `.env.example` is intentionally local-development friendly and boots cleanly in explicit demo runtime (`SERPAPI_RUNTIME_MODE=demo`, `AI_PROVIDER=stub`).
- For shared/staging/production environments, replace `JWT_SECRET`, `DEFAULT_ADMIN_PASSWORD`, and provider credentials with real secrets.
- Seed data and demo setup are explicit script-driven flows, not startup side effects.
- `infra/deploy.env.example` is the production-oriented template; fill it with real values before any remote deployment.

## MySQL/MariaDB Migration Recovery

MySQL/MariaDB DDL is non-transactional. If `alembic upgrade head` is interrupted, recover explicitly:

1. Stop API processes that may still hold old metadata.
2. Re-run `py -3.12 -m alembic upgrade head`.
3. If schema drift remains in local dev, reset only the local dev database, then rerun migration+seed:

```powershell
cd apps/api
py -3.12 -m alembic upgrade head
py -3.12 scripts/seed.py
```

Treat non-transactional DDL as an operational constraint, not a suppressible warning.
CREATE DATABASE IF NOT EXISTS prospectiq CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'prospectiq'@'127.0.0.1' IDENTIFIED BY 'prospectiq';
GRANT ALL PRIVILEGES ON prospectiq.* TO 'prospectiq'@'127.0.0.1';
FLUSH PRIVILEGES;