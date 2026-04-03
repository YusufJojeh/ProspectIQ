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
npm run build
npm run test:e2e -- --workers=1
```

## CI

GitHub Actions runs the same validation path from [ci.yml](C:/Users/Yusuf/OneDrive/Desktop/ProspectIQ/.github/workflows/ci.yml):

- Backend: `ruff`, `mypy`, `pytest`, and `alembic upgrade head --sql`
- Frontend: `eslint`, `vite build`, and Playwright E2E

The frontend browser tests use the repo's mock API layer, so they do not require a live backend in CI. The backend suite uses isolated test databases and an offline Alembic render check instead of a live MariaDB service.

## Reference Docs

- [implementation-reference.md](C:/Users/Yusuf/OneDrive/Desktop/ProspectIQ/docs/implementation-reference.md)
- [docs/README.md](C:/Users/Yusuf/OneDrive/Desktop/ProspectIQ/docs/README.md)
