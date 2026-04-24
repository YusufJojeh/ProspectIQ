# Go-Live Checklist

## Environment and Secrets

- set a real `JWT_SECRET` (32+ chars)
- set a rotated `DEFAULT_ADMIN_PASSWORD` (12+ chars)
- set provider credentials if running in live provider mode (`SERPAPI_RUNTIME_MODE=live`, non-empty `SERPAPI_API_KEY`)
- set explicit `WEB_ORIGINS` for the deployed frontend origin
- confirm `DATABASE_URL` targets the intended MySQL or MariaDB instance
- prepare a real `infra/deploy.env` from `infra/deploy.env.example`
- store GitHub deploy secrets for the remote host and GHCR pull access

## Database and Migrations

- run `alembic upgrade head`
- run `alembic upgrade head --sql` in CI or release verification
- confirm the release process never edits old migration files
- keep seed/demo flows explicit; do not seed data on API startup

## Backend Readiness

- `pytest -q`
- `ruff check app tests migrations --config pyproject.toml`
- `mypy app --config-file pyproject.toml`
- verify `/api/v1/health`
- verify `/api/v1/health/db`
- verify login with a non-placeholder admin credential

## Frontend Readiness

- `npm run lint`
- `npm run build`
- `npm run test:e2e -- --workers=2`
- confirm the app loads from both the configured local origin and the intended deployed origin
- review keyboard access for filters, lead selection, and admin forms

## Provider and AI Checks

- confirm SerpAPI credentials are present
- run one real search job and verify:
  - provider fetches are stored
  - raw payloads are stored
  - normalized facts are stored
  - deduplication behaves as expected
  - scores and breakdowns are persisted
- run one assistive analysis and one outreach draft generation

## Logging and Auditability

- confirm logs redact API keys, tokens, and password-like values
- confirm audit logs capture:
  - login
  - user creation
  - scoring activation
  - prompt activation
  - lead status updates
  - exports

## Delivery Pipeline

- confirm `CI` passes on the target branch
- confirm the deployment-stack smoke job passes
- confirm `Release Images` publishes fresh `prospectiq-api` and `prospectiq-web` images to GHCR
- confirm the `Deploy` workflow has the required secrets and a reachable Docker host
- confirm the deploy workflow can run `infra/scripts/verify_deploy_stack.sh` successfully on the target host
- verify rollback by redeploying a prior image tag through the manual deploy workflow

## Demo Separation

- keep demo credentials and demo datasets separate from production credentials
- make mock/demo provider mode explicit in instructions
- reset demo data via scripts, not by manual database edits

## Known Warnings

- local MariaDB startup still depends on Docker or an equivalent MySQL/MariaDB service being available
- a real remote deployment still requires GitHub environment secrets and host-level Docker access
