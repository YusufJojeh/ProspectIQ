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

### 1. Start MariaDB

```powershell
docker compose -f infra/docker-compose.yml up -d
```

### 2. Run the backend

```powershell
cd apps/api
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -e .[dev]
Copy-Item .env.example .env
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload
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
py -3.12 -m ruff check app tests --config pyproject.toml
py -3.12 -m mypy app --config-file pyproject.toml
```

### Frontend

```powershell
cd apps/web
npm run lint
npm run test:unit
npm run build
npm run test:e2e -- --workers=1
```

## CI

GitHub Actions runs the same validation path from [ci.yml](C:/Users/Yusuf/OneDrive/Desktop/ProspectIQ/.github/workflows/ci.yml):

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

- [implementation-reference.md](C:/Users/Yusuf/OneDrive/Desktop/ProspectIQ/docs/implementation-reference.md)
- [docs/README.md](C:/Users/Yusuf/OneDrive/Desktop/ProspectIQ/docs/README.md)
- [architecture-review.md](C:/Users/Yusuf/OneDrive/Desktop/ProspectIQ/docs/architecture-review.md)
- [go-live-checklist.md](C:/Users/Yusuf/OneDrive/Desktop/ProspectIQ/docs/go-live-checklist.md)

## Local vs Production-Style Defaults

- `.env.example` is intentionally local-development friendly. Do not reuse placeholder values such as `JWT_SECRET=<replace-me>` or `SERPAPI_API_KEY=<replace-me>` outside local development.
- Rotate `DEFAULT_ADMIN_PASSWORD` before any shared demo or deployed environment.
- Seed data and demo setup are explicit script-driven flows, not startup side effects.
- `infra/deploy.env.example` is the production-oriented template; fill it with real values before any remote deployment.
