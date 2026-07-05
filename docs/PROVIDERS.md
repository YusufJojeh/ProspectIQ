# Provider Operations

LeadScope AI uses provider adapters behind the existing provider-fetch/evidence model.
Default tests use stubs and never call live providers.

## Tavily

Tavily uses the official `tavily-python` SDK. Do not configure a Tavily dashboard URL or raw HTTP endpoint in application code.

Required runtime knobs:

| Variable | Default | Notes |
| --- | --- | --- |
| `TAVILY_API_KEY` | empty | Required only for `TAVILY_RUNTIME_MODE=live`. Placeholder values are treated as unconfigured. |
| `TAVILY_RUNTIME_MODE` | auto | Use `stub` for deterministic local/CI behavior or `live` for real calls. |
| `TAVILY_LIVE_E2E` | `0` | Set to `1` only for the guarded live smoke test. |
| `TAVILY_MAX_RESULTS` | `5` | Search result cap passed to the SDK. |
| `TAVILY_SEARCH_DEPTH` | `basic` | Supported values: `basic`, `fast`, `advanced`. |
| `TAVILY_RATE_LIMIT_RPM` | `60` | Local token bucket rate before SDK calls. |
| `TAVILY_LIVE_MAX_CALLS` | `3` | Per-job Tavily discovery/extract cap and live-smoke result cap. |

## Agentic Usage

- Tavily Search can participate in discovery when `tavily_web` is present in `DISCOVERY_ENGINE_LIST`.
- Tavily Extract is selective: the orchestrator extracts only the top unique, non-directory URLs from Tavily Search results, never every result.
- Tavily Research is opt-in via `POST /api/v1/leads/{lead_id}/research`; it records a provider fetch and normalized fact but does not run automatically.
- Evidence is stored with title, URL, snippet/content, provider, timestamp, confidence, and curated raw metadata. The system does not fabricate evidence.

## Failure Handling

- A local token bucket throttles Tavily calls before they leave the process.
- `429` errors honor `retry-after` when the SDK exposes it.
- `401`, `403`, timeout, and `5xx` failures are persisted as provider fetch failures without exposing keys.
- Provider usage is workspace-scoped through `provider_fetches.workspace_id` and raw payload capture.

## SerpAPI

SerpAPI remains the primary local-business discovery provider. The Tavily engine is additive and does not remove SerpAPI, demo, or stub behavior.
