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

Validated against CI and the local-live profile:

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
Copy-Item .env.local-live.example .env
py -3.12 -m alembic upgrade head
py -3.12 scripts/seed.py
py -3.12 -m uvicorn app.main:app --reload
```

Backend URL: `http://localhost:8000`

### 3. Run the frontend

```powershell
cd apps/web
npm install
Copy-Item .env.local-live.example .env
npm run dev
```

Frontend URL: `http://localhost:5173`

For local development, the backend accepts both `http://localhost:5173` and `http://127.0.0.1:5173` by default. Set `WEB_ORIGINS` explicitly when you need a tighter origin list.

### Runtime Mode Profiles

The runtime is explicit and controlled by env vars. No implicit discovery demo fallback is used.

- **Discovery runtime gate**: `SERPAPI_RUNTIME_MODE`
  - `live`: use real SerpAPI (requires `SERPAPI_API_KEY`)
  - `demo`: explicit demo discovery mode
  - `stub`: deterministic test-only discovery mode
  - `blocked`: disables discovery
- **Discovery execution mode**: `DISCOVERY_MODE`
  - `single_path`
  - `multi_query_single_engine`
  - `multi_engine_multi_query`
- **Hard stop**: `DISCOVERY_KILL_SWITCH=true` forces `single_path`
- **AI runtime gate**: `AI_PROVIDER`
  - `ollama`, `openai`, `auto`, or `stub`
  - `stub` is explicit demo AI mode

Minimal local profiles:

1. **Local demo mode (no external providers)**
   - `SERPAPI_RUNTIME_MODE=demo`
   - `AI_PROVIDER=stub`
2. **Local live discovery + Ollama primary**
   - `SERPAPI_RUNTIME_MODE=live`
   - `SERPAPI_API_KEY=<real key>`
   - `AI_PROVIDER=ollama`
   - `OLLAMA_BASE_URL` + `OLLAMA_MODEL`
   - optional OpenAI fallback with `OPENAI_API_KEY`
3. **Local live discovery + OpenAI primary**
   - `SERPAPI_RUNTIME_MODE=live`
   - `SERPAPI_API_KEY=<real key>`
   - `AI_PROVIDER=openai`
   - `OPENAI_API_KEY`, optional `OPENAI_MODEL`, optional `OPENAI_BASE_URL` for compatible gateways
   - optional `OLLAMA_*` fallback

## Production Environment Setup

LeadScope AI enforces strict production configuration to ensure security and reliability. When deploying with `APP_ENV=production`, the following variables **must** be configured:

### Required Production Variables

- `JWT_SECRET`: A cryptographically random string of at least 32 characters (not the default placeholder)
- `DEFAULT_ADMIN_PASSWORD`: A strong password different from the default `ChangeMe123!` (minimum 12 characters)
- `WEB_ORIGINS`: Explicitly set to your production domain(s), e.g., `https://leadscope.example.com`
- `SERPAPI_RUNTIME_MODE=live` and `SERPAPI_API_KEY`: Real SerpAPI credentials
- `AI_PROVIDER`: One of `ollama`, `openai`, or `auto` for real AI runtime
- `OPENAI_API_KEY` when OpenAI is primary or fallback
- `OLLAMA_BASE_URL` + `OLLAMA_MODEL` when Ollama is primary or fallback
- Discovery controls (explicit): `DISCOVERY_MODE`, `DISCOVERY_MULTI_ENGINE_ENABLED`, `DISCOVERY_ENGINE_LIST`, and budget limits

### Automatic Validation

On startup with `APP_ENV=production`, the backend validates all the above. If any requirement is not met, the application will refuse to boot with a clear error message. This is by design to prevent accidental deployment with unsafe defaults.

### Example Production Environment

```powershell
APP_ENV=production
JWT_SECRET=<generate-with-openssl-rand-hex-or-similar>
DEFAULT_ADMIN_PASSWORD=<strong-random-password>
WEB_ORIGINS=https://leadscope.example.com,https://www.leadscope.example.com
SERPAPI_RUNTIME_MODE=live
SERPAPI_API_KEY=<real-serpapi-key>
DISCOVERY_MODE=multi_engine_multi_query
DISCOVERY_MULTI_ENGINE_ENABLED=true
DISCOVERY_ENGINE_LIST=google_maps_search,google_maps_place,google_web
AI_PROVIDER=openai
OPENAI_API_KEY=<real-openai-key>
OPENAI_BASE_URL=https://api.openai.com/v1
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
ENABLE_API_DOCS=false
```

For Docker deployment, see the [Deployment](#deployment) section below and use `infra/deploy.env.example` as a template.

## Testing & Quality Assurance

### Local API Tests

```powershell
cd apps/api
py -3.12 -m pytest -q
```

### Frontend E2E Tests (Mock-backed)

```powershell
cd apps/web
npm run test:e2e
```

Artifacts:

- Playwright HTML report: `apps/web/test-artifacts/playwright-report/index.html`

### Container Images

- API image: `ghcr.io/yusufjojeh/prospectiq-api`
- Web image: `ghcr.io/yusufjojeh/prospectiq-web`

The web image supports two production modes:

- same-origin mode: set `WEB_PUBLIC_API_BASE_URL=` and let Nginx proxy `/api/*` to the API container
- split-origin mode: set `WEB_PUBLIC_API_BASE_URL=https://api.example.com`

Frontend env surface:

- `VITE_API_BASE_URL` (dev/build-time base URL)
- `WEB_PUBLIC_API_BASE_URL` (container runtime override -> `window.__APP_CONFIG__.VITE_API_BASE_URL`)

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

For a one-command local-live bootstrap:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_local_live.ps1
```

For a local prod-like stack check:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_local_prod_like.ps1
```

This checks Docker availability, API import, database connectivity, Alembic upgrade, and the frontend production build.

## Local vs Production-Style Defaults

- `.env.local-live.example` is the primary local development profile: live SerpAPI, Ollama primary, OpenAI fallback.
- `.env.example` remains a generic template, but local development should prefer the explicit local-live profile.
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
