# Architecture Review

## Current Assessment

LeadScope AI is a clean modular monolith with working backend, frontend, database migrations, CI, and end-to-end workflow coverage. The strongest architectural choices are:

- provider-specific acquisition and normalization logic is kept inside `apps/api/app/modules/provider_serpapi`
- deterministic scoring is isolated from AI generation
- raw provider payloads, normalized facts, lead truth, and AI snapshots are stored separately
- the React app is organized by feature areas instead of page-local data plumbing

## Hardening Changes in This Pass

### Backend

- extracted shared lead-intelligence assembly into `app/shared/services/lead_intelligence.py`
  - facts and score-context building are no longer duplicated across `leads` and `ai_analysis`
- tightened workspace-scoped lead lookups in `LeadsRepository`
  - `ai_analysis`, `outreach`, and `leads` now reuse repository methods instead of repeating workspace guards
- removed deprecated bootstrap-only code from `users/service.py`
- startup now logs allowed CORS origins and warns on unsafe local defaults such as placeholder secrets

### Frontend

- added a shared `QueryStateNotice` component for loading/error states
- removed stale seeded/demo copy from the login and admin flows
- tightened accessible labeling on key filters and forms
- made lead table rows keyboard-selectable and gave the shared map region an accessible label
- normalized user-facing product naming to `LeadScope AI`

## Strongest Parts of the Current Design

- deterministic lead scoring with persisted breakdowns and versioned configs
- evidence-first provider pipeline with auditability
- clear service/repository/router separation in the backend
- React feature modules with TanStack Query and typed API contracts
- CI reproduces the same validation path used locally

## Deferred Issues

- live deployment still depends on real secrets and a reachable target host
  - the repo now includes production Dockerfiles, GHCR publishing, deployment compose, and a deployment-stack smoke path in CI
  - the remaining deployment risk is operational handoff, not missing packaging
- frontend unit-test coverage is still thinner than backend coverage
  - Playwright covers the main workflow and Vitest now covers a minimal shared-state component, but isolated component-level coverage is still limited
- the frontend build still emits a Vite chunk-size warning
- the test/dev JWT secret warning remains intentional in test runs

## Migration Strategy

- existing historical Alembic revisions should now be treated as immutable
- any future schema corrections should be made with new forward-only revisions
- this pass did not require a schema change, so no migration file was added

## Final Status

Acceptable with warnings.

The application is strong enough for local delivery, grading, guided demos, and image-based deployment. The main remaining risks are operational secret/runtime hardening on the target host, a thinner frontend unit-test baseline, and the existing frontend bundle-size warning.
