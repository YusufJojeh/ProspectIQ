# ProspectIQ Implementation Reference

This repository applies the architecture described for the Smart Lead Finder for Agencies project.

## Core architecture

- Use a single backend application and a single frontend application.
- Keep domains isolated as modules inside a modular monolith.
- Treat provider evidence and normalized facts as the durable source of truth.
- Use AI only after facts are collected, normalized, and validated.

## Backend conventions

- `app/core`: runtime configuration, database wiring, middleware, security, and error handling.
- `app/shared`: DTOs, pagination primitives, response envelopes, shared enums, and utility helpers.
- `app/modules`: business modules such as auth, search jobs, leads, scoring, outreach, and admin.
- `app/workers`: orchestration and long-running job coordination.

Each module should prefer this shape:

```text
module_name/
├─ api.py
├─ schemas.py
├─ models.py
├─ service.py
├─ repository.py
├─ policies.py
├─ exceptions.py
└─ tests/
```

## Backend patterns

- Service Layer for business logic.
- Adapter Pattern for external providers and LLM integrations.
- Strategy Pattern for scoring rules.
- Orchestrator Pattern for lead discovery pipelines.
- Policy Pattern for authorization and access control.

## Frontend conventions

- `src/app`: router, providers, and app-level layouts.
- `src/components`: reusable UI primitives and shared building blocks.
- `src/features`: domain-owned screens, hooks, forms, and view-model mapping.
- `src/lib`: API client, query client, environment parsing, and shared helpers.
- `src/styles`: global style tokens and Tailwind entrypoint.

## UI direction

- Neutral surfaces with one restrained accent palette.
- Dense but readable tables, evidence cards, chips, and status badges.
- Light borders before heavy shadows.
- Rounded corners with `rounded-xl` as the default surface radius.
- Avoid flashy landing-page styling, oversized gradients, and playful visuals.

## Delivery constraints

- Version the API from the start under `/api/v1`.
- Keep database schema changes behind migrations.
- Preserve raw provider payloads and normalized facts separately.
- Attach every score to a scoring version.
- Validate all AI outputs with strict schemas.

