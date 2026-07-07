# Live Multi-Provider Validation Flow

This document describes how to validate the full product with real providers
(Tavily, SerpAPI, OpenAI) running together in one discovery job. CI never uses
this flow; default tests remain on stubs.

## Runtime configuration

Set these in `apps/api/.env` (never commit this file):

| Variable | Live value | Notes |
| --- | --- | --- |
| `TAVILY_API_KEY` / `SERPAPI_API_KEY` / `OPENAI_API_KEY` | real keys | Placeholders are treated as unconfigured. |
| `TAVILY_RUNTIME_MODE` | `live` | |
| `SERPAPI_RUNTIME_MODE` | `live` | |
| `AI_PROVIDER` | `openai` | Prompt parsing, analysis, and outreach drafting use OpenAI. |
| `DISCOVERY_ENGINE_LIST` | `tavily_web,serpapi_maps,serpapi_web,openai_web` | Aliases normalize to `tavily_web,google_maps_search,google_web,openai_web`. |
| `TAVILY_RATE_LIMIT_RPM` | `30` | Local token bucket before SDK calls. |
| `TAVILY_LIVE_MAX_CALLS` | `3` | Per-job Tavily discovery/extract cap (used by the orchestrator in normal operation). |

SerpAPI has no client-side RPM knob; per-job call volume is bounded by
`DISCOVERY_MAX_CALLS_PER_JOB` and the circuit breaker.

## Engine name aliases

`Settings.enabled_discovery_engines` normalizes aliases so operator-facing
names map to internal adapters:

| Alias | Internal adapter |
| --- | --- |
| `serpapi_maps`, `serpapi_map`, `google_maps` | `google_maps_search` |
| `serpapi_web`, `serpapi_search` | `google_web` |
| `openai`, `openai_fallback` | `openai_web` |
| `tavily_web` | `tavily_web` |

## Expected behavior in a live job

1. The execution planner fans one query out across every enabled adapter
   (`multi_engine_multi_query` mode).
2. Tavily search + selective extract, SerpAPI maps/web, and OpenAI web
   discovery all record `provider_fetches` rows scoped to the workspace and
   search job.
3. Provider failures are isolated per adapter: a failure or 429 increments
   `provider_error_count` once per adapter and trips that adapter's circuit
   breaker without stopping the others. SerpAPI/Tavily 429s persist with
   status `rate_limited`.
4. Final status: all providers ok and leads scored → `completed`; some
   providers failed but leads persisted → `partially_completed`; no leads →
   `failed`.
5. Cross-provider duplicates collapse by place id, domain, phone, then
   name+city (`CrossSourceDeduper`).
6. Evidence rows preserve provider source types: `maps_search`, `maps_place`,
   `web_search` (SerpAPI), `tavily_search` (Tavily discovery), `tavily_web`
   (Tavily web-presence validation), `openai_web` (OpenAI discovery).
7. Logs redact keys (`api_key=[REDACTED]`, `TAVILY_API_KEY=[REDACTED]`).

## Manual validation walkthrough

1. Apply migrations and seed: `python -m alembic upgrade head`, then
   `python scripts/seed.py`.
2. Start the API (`uvicorn app.main:app --port 8000`) and web (`npm run dev`).
   Startup logs include a SerpAPI reachability probe.
3. Sign in and submit a natural-language search from the Search Jobs page
   ("Search with AI" → `POST /api/v1/search-jobs/from-prompt`).
4. Watch the job detail page: live progress via SSE, then a Provider status
   card per fetch (provider, engine/mode, status, HTTP code, attempt).
5. Verify leads appear with scores, bands, confidence, and an evidence
   timeline attributing each fact to its provider.
6. Provider Health (`/app/provider-health`, admin/account_owner only) shows
   per-provider configured/runtime state, discovery execution mode, 7-day
   failure count, and recent failures with safe messages only.
7. Outreach drafts (`POST /api/v1/outreach/leads/{lead_id}/generate`) and CRM
   deals (`POST /api/v1/crm/deals`) work against live-discovered leads.

## Guardrails

- Live tests remain opt-in (`TAVILY_LIVE_E2E=1` for the guarded smoke test);
  `pytest` defaults to stub runtimes via `APP_ENV`-based checks.
- Do not commit `.env`, database files, or raw provider payloads.
- Do not weaken `rate_limited`/`error` classification when touching provider
  clients; the admin operational-health endpoint and Provider Health UI rely
  on those statuses.
