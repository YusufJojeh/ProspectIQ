# Deployment Notes

Use `infra/deploy.env.example` as the production compose template. Real secrets belong only in the untracked deploy env file or the deployment platform secret store.

## Provider Runtime

- `SERPAPI_RUNTIME_MODE=live` with a real `SERPAPI_API_KEY` is required for production discovery.
- `TAVILY_RUNTIME_MODE=live` is optional. Add `tavily_web` to `DISCOVERY_ENGINE_LIST` only after a valid `TAVILY_API_KEY` is configured.
- Keep `TAVILY_LIVE_E2E=0` in production deploy envs. Live provider validation belongs in a manual run or a separate live-provider workflow.

## Frontend API Base

The web app must not hardcode localhost in production. Use one of:

- Same-origin: `WEB_PUBLIC_API_BASE_URL=` and proxy `/api/*` through Nginx.
- Split-origin: `WEB_PUBLIC_API_BASE_URL=https://api.example.com`.

## Push Readiness

Do not push unless default gates pass:

- Backend ruff, ruff format check, mypy, pytest, Alembic SQL render.
- Frontend lint, unit tests, build, default Playwright.
- Secret scan over tracked files.

Live Tavily tests are optional and must not block normal CI unless the live workflow intentionally opts in.
