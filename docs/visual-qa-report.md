# Visual QA Report

## Run Context

- Date: `2026-04-05`
- Runtime mode: `SERPAPI_RUNTIME_MODE=demo`, `AI_PROVIDER=stub`
- Backend: real FastAPI API on `http://127.0.0.1:8000`
- Frontend: real Vite app on `http://localhost:5173`
- Database: local MariaDB with demo reset via `py -3.12 scripts/seed.py --migrate --demo-data --reset-demo-data`
- Playwright command: `npm run test:e2e:real`
- Result: `7/7` tests passed

## Test Files

- `apps/web/tests/e2e-real/auth.visual.spec.ts`
- `apps/web/tests/e2e-real/dashboard.visual.spec.ts`
- `apps/web/tests/e2e-real/searches.visual.spec.ts`
- `apps/web/tests/e2e-real/leads.visual.spec.ts`
- `apps/web/tests/e2e-real/lead-detail.visual.spec.ts`
- `apps/web/tests/e2e-real/admin.visual.spec.ts`

## Screenshot Paths

Root folder:

- `apps/web/test-artifacts/visual-qa/screenshots`

Key grouped captures:

- Login:
  `login/full-page.png`
  `login/validation-error.png`
  `login/invalid-credentials.png`
  `login/success-transition.png`
  `login/unauthorized-redirect.png`
- Dashboard:
  `dashboard/loading.png`
  `dashboard/full-page.png`
  `dashboard/top-summary.png`
- Searches:
  `searches/loading.png`
  `searches/full-page.png`
  `searches/search-form.png`
  `searches/validation-error.png`
  `searches/search-success.png`
  `searches/completed-job-card.png`
  `searches/completed-job-detail.png`
- Leads:
  `leads/loading.png`
  `leads/full-page.png`
  `leads/list-default.png`
  `leads/list-filtered.png`
  `leads/list-sorted.png`
  `leads/list-empty.png`
  `leads/detail-full-page.png`
  `leads/detail-overview.png`
  `leads/detail-score.png`
  `leads/detail-evidence.png`
  `leads/detail-recommendation.png`
  `leads/detail-outreach.png`
  `leads/export-before.png`
  `leads/export-after.png`
- Map:
  `map/map-full.png`
  `map/map-marker-popup.png`
- Admin:
  `admin/loading.png`
  `admin/full-page.png`
  `admin/system-health.png`
  `admin/provider-settings.png`
  `admin/scoring-config.png`
  `admin/prompt-templates.png`
  `admin/provider-save-success.png`

## Coverage Summary

- Login:
  initial load, inline validation, invalid credentials, successful transition, unauthorized redirect
- Dashboard:
  authenticated loading and loaded overview with cards and widgets
- Search page:
  loading, empty form, validation error, successful submission
- Search job status:
  completed card and completed detail view
- Leads list:
  default, filtered, sorted, no-results, export before/after
- Lead detail:
  full page, overview, score section, evidence section, recommendations, outreach
- Map:
  map visible and marker popup visible
- Admin:
  overview, system health, provider settings, scoring configuration, prompt templates, success feedback

## Reusable Test Infrastructure

- Real Playwright config:
  `apps/web/playwright.real.config.ts`
- Helpers:
  `apps/web/tests/e2e-real/helpers/auth.ts`
  `apps/web/tests/e2e-real/helpers/navigation.ts`
  `apps/web/tests/e2e-real/helpers/page.ts`
  `apps/web/tests/e2e-real/helpers/artifacts.ts`
  `apps/web/tests/e2e-real/helpers/env.ts`

## Issues Found And Fixed

- `apps/api/scripts/seed.py`
  Fixed demo reseed instability by preventing duplicate `website_domain` identities for the same seeded lead.
- `apps/web/src/features/settings/routes/settings-page.tsx`
  Fixed admin-page horizontal overflow by allowing grid cards and fields to shrink correctly.
- `apps/web/src/features/leads/routes/leads-page.tsx`
  Fixed lead workspace right-rail overflow with `min-w-0` shrink handling.
- `apps/web/src/features/leads/components/lead-map.tsx`
  Replaced animated selected-lead recentering with deterministic `setView(...)` for more stable visual runs.
- `apps/web/src/styles/globals.css`
  Hardened Leaflet clipping with `overflow: hidden`.

## Notes

- The suite uses real browser automation against the running app, not component-only tests.
- The suite prefers stable accessible selectors and uses seeded demo data for deterministic coverage.
- `admin/loading.png` is conditional because the admin page may load too quickly to expose the intermediate loading UI on every machine.
- The existing `npm run test:e2e` suite remains the mock-backed path; this report documents the real-stack visual suite only.
