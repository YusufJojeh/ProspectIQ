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
In the research pipeline, SerpAPI is used only as Google-oriented search redundancy at `deep` depth, never as the sole research source.

## Apify

Apify is a deep-extraction/crawling layer, distinct from Tavily/SerpAPI search. It is only invoked when the research
planner has already identified a specific target (e.g. a lead's official website) and needs structured page extraction.

Callers — including any future LLM tool call — can never choose an arbitrary Apify Actor ID. They may only pass one
of a small allowlist of Actor keys; the backend resolves each key to a real Actor ID via `Settings.apify_actor_allowlist`.
This prevents indirect arbitrary remote code execution through Apify.

Allowlisted Actor keys (`app/modules/provider_apify/allowlist.py`):

| Key | Purpose |
| --- | --- |
| `company_website_crawler` | Crawl a lead's own official website. |
| `business_directory_crawler` | Crawl a business directory listing page. |
| `social_public_profile_crawler` | Crawl a public social profile page. |
| `reviews_crawler` | Crawl a public reviews page. |

Required runtime knobs:

| Variable | Default | Notes |
| --- | --- | --- |
| `APIFY_API_TOKEN` | empty | Required only for `APIFY_RUNTIME_MODE=live`. Placeholder values are treated as unconfigured. |
| `APIFY_RUNTIME_MODE` | auto | Use `stub` for deterministic local/CI behavior or `live` for real calls. |
| `APIFY_ACTOR_COMPANY_WEBSITE_CRAWLER` | `apify/website-content-crawler` | Real Actor ID (`owner/name`) behind the `company_website_crawler` key. |
| `APIFY_ACTOR_BUSINESS_DIRECTORY_CRAWLER` | empty | Real Actor ID behind the `business_directory_crawler` key. Unset disables that step. |
| `APIFY_ACTOR_SOCIAL_PUBLIC_PROFILE_CRAWLER` | empty | Real Actor ID behind the `social_public_profile_crawler` key. Unset disables that step. |
| `APIFY_ACTOR_REVIEWS_CRAWLER` | empty | Real Actor ID behind the `reviews_crawler` key. Unset disables that step. |
| `APIFY_MAX_DATASET_ITEMS` | `20` | Max dataset items fetched per run. |
| `APIFY_TIMEOUT_SECONDS` | `90` | Upper bound while polling a run for a terminal status. |

Every Apify call is a three-step REST sequence (start run → poll run status → fetch dataset items) so that the run's
`id` can be captured reliably as `actor_run_id` for provenance on each `ProviderNormalizedFact`.

## Research depth

`POST /api/v1/leads/{lead_id}/research` accepts an optional `{"depth": "quick" | "standard" | "deep"}` body
(default `quick`). Depth controls the provider-call budget the `ResearchPlanner` builds a plan from — research does
not call every provider for every lead:

| Depth | Providers | Behavior |
| --- | --- | --- |
| `quick` | Tavily only | Fast lead enrichment; one search step. |
| `standard` | Tavily, then Apify `company_website_crawler` if a website was found | Standard verification; crawls the lead's own site once Tavily (or existing evidence) identifies it. |
| `deep` | Tavily, SerpAPI, Apify (company site + reviews where configured) | Deep intelligence report; adds Google-oriented search redundancy and historical evidence. |

A provider step whose provider is unconfigured/blocked is dropped from the plan rather than failing the request. An
Apify `company_website_crawler` step is skipped at run time (not treated as a failure) when no website URL has been
discovered yet by the time that step is reached. After all steps run, `ContradictionDetector` compares claims
(`phone`, `website_domain`, `category`, `address`) across providers and persists any disagreement as a
`ResearchContradiction` row.

## Research agent mode ("agentic")

`POST /api/v1/leads/{lead_id}/research` also accepts `"mode": "planned" | "agentic"` (default `planned`).
`planned` is the fixed-step `ResearchOrchestrator` described above. `agentic` runs `ResearchAgentLoop`: an
LLM (reused from `OPENAI_API_KEY`, no separate credential) decides which of a fixed set of tools to call next,
one round trip at a time, until it says it has enough evidence or a hard bound is hit.

**Security invariant:** the LLM only ever names a tool by its fixed name from `app.modules.research.tools`. It
never receives a schema field for a URL or an Apify Actor ID — `crawl_company_site` and `crawl_reviews` take
zero parameters and always resolve their target server-side (the lead's already-discovered website, or its
already-discovered Google Place identity). `resolve_company_domain` is the only tool with a `url` parameter, and
it does pure string parsing (`urllib.parse`) with no network call. This is enforced structurally (there is no
parameter to smuggle a target through), not by prompting the model to behave.

**Hard bounds** (`app.core.config` `research_agent_max_*` settings, enforced in the loop before each tool call,
never inside the tool executor):

| Setting | Default | Meaning |
| --- | --- | --- |
| `research_agent_max_tool_calls` | 8 | Total tool calls per research run. |
| `research_agent_max_external_searches` | 5 | `search_web_tavily` + `search_google_serpapi` calls. |
| `research_agent_max_crawls` | 3 | `crawl_company_site` + `crawl_reviews` calls. |
| `research_agent_max_sources` | 15 | Normalized facts persisted from search/crawl tools. |
| `research_agent_max_runtime_seconds` | 60 | Wall-clock cap on the whole loop. |

`research_agent_runtime` mirrors the demo/live/stub/blocked pattern: `stub` during tests (a fixed scripted tool
sequence, no OpenAI call), `openai` when `OPENAI_API_KEY` is configured outside tests, `blocked` otherwise (the
`agentic` mode then returns an error result; `planned` mode is unaffected).

## Evidence Graph

`GET /leads/{lead_id}/evidence-graph` returns a canonical, cross-provider view of a lead's evidence — additive
to the existing `/evidence` endpoint and its `facts_json` shape, which are unchanged. `EvidenceGraphBuilder`
(`app.modules.research.evidence_graph`) computes it on the fly from `ProviderNormalizedFact`'s already-clean
flattened columns (phone, website, category, rating, etc.) plus `LeadSignal` rows, grouped into
`business_identity` / `digital_presence` / `reviews` / `contactability` / `pain_signals` / `opportunity_signals`
/ `growth_signals`.

For each claim type, `FactResolver` picks a canonical value (the value with the highest combined
source-quality × per-fact confidence weight) and lists any disagreeing values explicitly, rather than a boolean
"has a contradiction". Each canonical fact's `confidence` is deterministic, never LLM-generated:

```
confidence = best_source_quality × avg_freshness × cross_source_agreement × evidence_completeness
```

`source_quality()` is a fixed lookup table (official-site crawl 1.00 down to an unrecognized source type 0.35).
The graph's top-level `evidence_confidence` (average canonical-fact confidence) and `research_coverage`
(fraction of expected claim types with any evidence) are a separate signal from the lead's Fit/Need/Urgency
Opportunity Score — a lead can score highly on opportunity while still showing low confidence/coverage, which is
the signal that more research (a deeper `depth`, or `agentic` mode) would help.

## Delta Intelligence

Every successful `research_lead` call (both `planned` and `agentic` mode, wired through the single call site
`LeadsService.research_lead`) is immutably recorded, then compared against the lead's previous successful run:

```
Previous ResearchRun  ──┐
                        ├─▶ FactDiffEngine ─▶ ChangeCandidate(s) ─▶ ResearchChangeEvent
Current ResearchRun   ──┘         │                                        │
                                   └─▶ significant & non-neutral? ─▶ rescore_lead()
```

Three tables (`app.modules.research.models`), all append-only:

| Table | Purpose |
| --- | --- |
| `research_runs` | One row per `research_lead` call, whatever its outcome — the `created_at` ordering `FactDiffEngine` diffs against. |
| `research_fact_snapshots` | The canonical `(claim_type → value, confidence)` pairs captured from that run's Evidence Graph. Never updated after insert. |
| `research_change_events` | One row per meaningful, backend-decided change between two runs — `event_type`/`direction`/`significance` are deterministic; `explanation` is the only LLM-touched field. |

**Security/determinism invariant:** the LLM never decides *whether* a change occurred or *how significant* it
is. `FactDiffEngine` (`app.modules.research.delta`) is pure Python: it diffs two snapshot maps, drops noise below
a fixed threshold (numeric changes under 2% of the claim's scale, e.g. rating/5.0 or review_count/200), and
classifies the rest into a fixed `event_type` vocabulary with a deterministic `significance` score. `ChangeExplainer`
runs strictly after that decision and only ever fills in the human-readable `explanation` string — via
`OPENAI_API_KEY` when `research_agent_runtime == "openai"`, otherwise (or on any exception) a deterministic
templated sentence. A research run's success never depends on the explainer succeeding.

Two thresholds gate the pipeline (`app.core.config`):

| Setting | Default | Meaning |
| --- | --- | --- |
| `research_delta_min_significance` | 0.15 | Candidates below this are dropped as noise — no `ResearchChangeEvent` row is written. |
| `research_delta_rescore_significance` | 0.4 | A non-neutral candidate at/above this triggers an immediate `rescore_lead()` (via `app.modules.scoring.rescore`), independent of any `SearchJob`. |

`rescore_lead()` mirrors `LeadDiscoveryOrchestrator._score_leads` for exactly one already-known lead: it reloads
the lead's current evidence, recomputes signals and ICP match, rebuilds `NormalizedLeadFacts`, and persists a new
`LeadScore` — all outside a search-job context, using the workspace's already-active scoring config version.

A claim type present in a previous run but absent from the current one produces no event (the newer run's tools
simply didn't re-check it — that isn't evidence the fact became false). A brand-new claim type is recorded as a
low-significance `"evidence_added"`/mapped `event_type` with `direction: "neutral"`, since there is nothing to
compare it against yet.
