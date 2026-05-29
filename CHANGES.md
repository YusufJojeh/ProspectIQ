# CHANGES

## [Step 1B] SerpAPI multi-source enrichment — 2026-05-29

### Added
- `app/enrichers/base.py` — `EnrichmentPayload` dataclass + `BaseLeadEnricher` ABC. `safe_enrich()` wraps `enrich()` in try/except, logs a WARNING with enricher name + lead public_id on failure, and **always returns a valid (possibly empty) payload — never raises**.
- Three enrichers under `app/enrichers/` (all sync, match the synchronous orchestrator):
  - `google_maps_reviews.py` — SerpAPI `engine=google_maps_reviews`; extracts `rating`, `review_count`, and a `sentiment_ratio` (positive/neutral/negative) from review snippets. Skips (empty payload) when the lead has no resolvable place lookup.
  - `yelp.py` — SerpAPI `engine=yelp`; secondary discovery source. Matches Yelp businesses to the lead phone-first, then fuzzy name via `difflib.SequenceMatcher` (threshold 0.85); attaches `yelp_rating`, `yelp_review_count`, `yelp_url`. **New-lead creation from unmatched Yelp results is deferred** (enrichment-only this step).
  - `google_news.py` — reuses the existing `engines/google_news.py`; extracts `mention_count`, `latest_headline` (truncated 120 chars), `latest_date`, `news_present`.
- New engine modules `provider_serpapi/engines/google_maps_reviews.py` and `engines/yelp.py` (build/run/extract helpers following the existing engine pattern).
- `LeadDiscoveryOrchestrator._get_active_enrichers()` (registry keyed by `settings.enrichers`; returns `[]` when `SERPAPI_API_KEY` is missing/empty) and `_run_enrichment(db, lead_ids)` (sequential, merges payloads into `lead.enrichments` keyed by source). Wired into `run()` after web-presence validation and before scoring, with an `enriching` progress emit at 88%. Logs one WARNING and no-ops when no enrichers are active.
- `enrichments` JSON nullable column on `leads` (default NULL) — migration `0010_lead_enrichments.py`.
- Scoring signals: `ReviewScoreStrategy` (`review_score`, weight 0.15) = `min(rating/5,1)*0.6 + min(review_count/100,1)*0.4` (prefers google_maps_reviews over yelp); `NewsPresenceStrategy` (`news_presence`, weight 0.05) = 1.0 when news present. Both registered in `ScoringEngine`. New `NormalizedLeadFacts` fields `enriched_rating`, `enriched_review_count`, `news_present` populated by `EvidenceFactBuilder` from `lead.enrichments`.
- `ENRICHERS` config setting (`Settings.enrichers_raw` + `enrichers` property, comma-separated) + `.env.example` entry `ENRICHERS=google_maps_reviews,yelp,google_news`.
- Frontend `ScoringWeights` type + scoring-config form (`settings-page.tsx`): `review_score` and `news_presence` fields (schema, defaults, submit mapping, inputs).

### Changed
- `ScoringWeights` defaults redistributed so the total stays 1.0:

| key | old | new |
|---|---|---|
| local_trust | 0.25 | 0.20 |
| website_presence | 0.25 | 0.20 |
| search_visibility | 0.20 | 0.16 |
| opportunity | 0.20 | 0.16 |
| data_confidence | 0.10 | 0.08 |
| review_score | — | 0.15 |
| news_presence | — | 0.05 |

### Migration needed: yes
```
cd apps/api && alembic upgrade head
```

## [Step 4] Lead table polish — 2026-05-29

### Added
- Column visibility toggle (score, coverage, phone, website) — persisted in `localStorage` under `piq:leads_col_vis`; controlled via `useColumnVisibility` hook. Exposed in `LeadsTable` via a Columns3 dropdown (DropdownMenuCheckboxItem per column).
- Quick-filter bar (`QuickFilterBar` component): dual-thumb score range slider (0–100, powered by Radix UI Slider), "Has website" toggle (maps to API `has_website` param), "Has phone" toggle (client-side filter on returned leads to avoid schema change).
- Scoring breakdown bar chart on lead detail page: stacked total bar at top; Recharts horizontal BarChart (layout="vertical") with per-bar color coding (strong ≥60% / moderate 30–59% / weak <30%); custom tooltip shows reason text; legend.
- i18n keys: `leads.columns`, `leads.hasPhone`, `leadDetail.strengthStrong`, `leadDetail.strengthModerate`, `leadDetail.strengthWeak` in `en.json` + `ar.json`.

### Migration needed: no

## [Step 4] Outreach send stub & status tracking — 2026-05-29

### Added
- `outreach_status` column (`String(16)`, default `"draft"`) on `outreach_messages` table — migration `0009_outreach_status.py` (run: `cd apps/api && alembic upgrade head`).
- `POST /api/v1/outreach/messages/{id}/send` endpoint — auth-protected; sets `outreach_status = "sent"`, writes audit log entry `lead.outreach_sent`, returns `{ status: "queued" }`.
- `OutreachRepository.get_latest_outreach_statuses(db, lead_ids)` — single-query bulk lookup of latest outreach status per lead using a subquery on `MAX(id)`.
- `latest_outreach_status: str | None` field on `LeadResponse` (schema + service) — populated via bulk fetch in `list_leads`, `get_lead`, `queue_refresh`, `update_status`, `assign`.
- Sonner `<Toaster>` mounted in `AppProviders` (`richColors`, `position="bottom-right"`).
- Copy button in outreach card now fires `toast.success("Draft copied to clipboard.")`.
- Send button per outreach card — calls `/send` endpoint; toast on success/error; invalidates `outreach` + `leads` queries.
- Outreach status badge column in leads table — shows `draft` / `sent` / `replied` with tone-coded badges; dash when no outreach yet.
- i18n keys: `leads.outreach`, `leads.outreachStatus.{draft,sent,replied}`, `outreach.copiedToast`, `outreach.send`, `outreach.sentSuccess`, `outreach.sentError` in `en.json` + `ar.json`.

### Migration needed: yes
```
cd apps/api && alembic upgrade head
```

## [Step 3] Real-time job status — 2026-05-29

### Added
- `apps/api/app/core/progress_bus.py` — thread-safe in-process event bus (`register`, `unregister`, `emit`) using `threading.Queue` per job.
- `GET /api/v1/search-jobs/{job_id}/stream` SSE endpoint — auth-protected; streams `{ stage, progress, message }` events while a job runs; emits a single terminal event if job is already done.
- `LeadDiscoveryOrchestrator._emit()` method — calls injected `emit_fn` or falls back to global progress bus; emits at 5%, 40%, 65%, 80%, 95%, 100% of pipeline stages.
- `apps/web/src/hooks/use-job-stream.ts` — fetch-based SSE hook (supports `Authorization` header unlike native `EventSource`); exponential backoff reconnect on failure [1s, 2s, 4s]; exposes `reconnect()` and `canReconnect` flag; invalidates `search-jobs` and `leads` queries on `done` event.
- Live progress bar + stage label on `SearchJobDetailPage` for active jobs (replaces static loading notice).
- Live progress bar in `SearchJobCard` on searches page for active jobs.

### Changed
- `LeadDiscoveryOrchestrator.__init__` accepts optional `emit_fn: ProgressEmitFn | None` for testability.

### Migration needed: no

## [Step 2] Search UX Polish — 2026-05-29

### Added
- Loading skeletons on searches page active-jobs and run-history sections (replaces invisible gap during initial load).
- Loading skeleton on leads workspace table while initial data is fetching (replaces full-page `QueryStateNotice` takeover).
- First-run empty state on leads table and map view: when there are zero leads and no active filters, shows "No leads yet — Run a search to start discovering leads" with a CTA button to `/searches`.
- `leads.noLeadsYetTitle` and `leads.noLeadsYetDescription` i18n keys in `en.json` and `ar.json`.

### Changed
- Leads page: removed the full-page loading early-return; loading is now handled inline per-section so the page chrome (header, filters panel) stays visible during fetch.
- Map empty state now distinguishes first-run (zero leads, no filters) from no-coordinates (leads exist but lack coordinates).

### Migration needed: no
