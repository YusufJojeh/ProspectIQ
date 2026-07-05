# QA Gates

Default QA must be deterministic and mock-backed.

## Backend

```powershell
cd apps/api
py -3.12 -m ruff check app tests migrations --config pyproject.toml
py -3.12 -m ruff format --check app tests migrations --config pyproject.toml
py -3.12 -m mypy app --config-file pyproject.toml
py -3.12 -m pytest -q
py -3.12 -m alembic upgrade head --sql
```

The live Tavily smoke is skipped unless both are set:

```powershell
$env:TAVILY_LIVE_E2E = "1"
$env:TAVILY_API_KEY = "<real key>"
py -3.12 -m pytest tests/test_tavily_live_smoke.py -q
```

## Frontend

```powershell
cd apps/web
npm run lint
npm run test:unit
npm run build
npm run test:e2e
```

Playwright screenshots and reports stay under ignored artifact directories. Do not commit ad hoc captures with real provider data or credentials.

## Secret Check

Before committing or pushing:

```powershell
git grep -n -I -E "sk-[A-Za-z0-9]|TAVILY_API_KEY=.+|SERPAPI_API_KEY=.+|OPENAI_API_KEY=.+" -- .
```

Only placeholder/example values should appear in tracked files.
