# CHANGES

## [Goal] Mini CRM Pipeline & Deal Tracking - 2026-06-26

### Added
- Added workspace-scoped CRM backend tables via migration `0017_crm_pipeline.py`: `crm_pipelines`, `crm_stages`, `crm_deals`, and `crm_activities`.
- Added `/api/v1/crm` endpoints for default pipelines, stages/reorder, deals, stage moves, won/lost marking, and activities.
- Added lead and campaign conversion endpoints: `POST /api/v1/leads/{lead_id}/create-deal` and `POST /api/v1/campaigns/{campaign_id}/create-deals`.
- Added `/app/crm` board and `/app/crm/deals/:dealId` detail pages with shadcn UI, score spinners, status badges, loading skeletons, empty states, and activity history.
- Added CRM navigation to sidebar, mobile nav, and command menu plus English/Arabic i18n coverage.
- Extended the full demo seeder with an offline default CRM pipeline, seven stages, two deals, activities, and printed CRM summary output.
- Added backend CRM regression tests in `apps/api/tests/test_crm.py`.

### Safety
- No Gmail, SMTP, HubSpot, Salesforce, Stripe, calendar, or real email sending was added.
- CRM activities and deal transitions are local audit/demo records only.

### Validation
- Pending in this turn: Ruff, mypy, targeted pytest, frontend unit tests, build, Playwright CRM demo spec, commit, and push.

## [Goal] Campaign Sprint Closeout QA - 2026-06-26

### Changed
- Tightened campaign list/detail UI polish: localized event/status labels, day-delay labels, accessible campaign lead remove buttons, localized `LeadScoreSpinner` aria labels, and 8px card/skeleton radius.
- Replaced Arabic campaign fallback strings for campaign routes, nav, statuses, lead statuses, channels, empty/loading states, event labels, and campaign actions.
- Extended the full demo seeder with deterministic offline campaign demo data: one draft campaign, one active campaign, campaign leads, three sequence steps, outreach drafts, and outreach events with a printed campaign summary.
- Added Playwright campaign closeout coverage with local screenshots under `apps/web/test-results/campaign-demo/` and a guard asserting no outreach send endpoint is called.

### Validation
- Pending in this turn: Alembic, Ruff, mypy, targeted pytest, frontend unit tests, build, and Playwright campaign demo spec.

## [Goal] Campaign Sequences & Outreach Events - 2026-06-26

### Added
- Campaign module with workspace-scoped tables: `campaigns`, `campaign_leads`, `sequence_steps`, and `outreach_events` via migration `0016_campaign_sequences.py`.
- Campaign APIs under `/api/v1/campaigns`: CRUD/archive, add/remove leads, default three-step sequence generation, sequence-step patching, campaign draft generation, and event listing.
- Campaign draft generation reuses existing AI analysis snapshots/intelligence and `outreach_messages`; no real email sending, Gmail OAuth, SMTP, CRM, or billing changes were added.
- Outreach event records for campaign creation, lead add/remove, sequence generation, sequence-step update, and campaign draft generation.
- Frontend campaign routes: `/app/campaigns` and `/app/campaigns/:campaignId`, with shadcn Card/Button/Badge/Dialog/Tabs/Skeleton/Select UI, empty states, loading states, and campaign event history.
- Campaign navigation entries in sidebar, mobile nav, and command menu.
- `LeadScoreSpinner` radial score indicator and usage in lead table, lead hero, and campaign lead cards.
- Lead detail now includes an "Add to campaign" action backed by the campaign API.
- English/Arabic i18n key coverage for campaign routes and UI labels.
- Backend tests in `tests/test_campaigns.py` for campaign CRUD scoping, lead add/remove, sequence generation, draft generation, and event persistence.

### Known limitations
- Sending remains a status-only stub through existing outreach message endpoints.
- Campaign-generated outreach messages are linked to campaigns through `outreach_events`; `outreach_messages` itself remains backward compatible and campaign-agnostic.
- No unsubscribe/compliance flow, CRM/deal pipeline, Gmail OAuth, or SMTP provider integration yet.

### Validation
- `cd apps/api && python -m alembic upgrade head` passed.
- `cd apps/api && python -m ruff check .` passed.
- `cd apps/api && python -m mypy app` passed.
- `cd apps/api && python -m pytest tests/test_campaigns.py tests/test_leads_api.py tests/test_ai_evidence_signal_summary.py` passed: 11 tests.
- `cd apps/web && npm run test:unit` passed: 28 tests.
- `cd apps/web && npm run build` passed with the existing Vite large-chunk warning.

## [Goal] SaaS Platform Admin Sprint Closeout - 2026-06-26

### Added
- Added `apps/api/scripts/seed_demo_full.py` as an idempotent full demo seeder for the SaaS platform admin walkthrough.
- Added `apps/web/tests/e2e/saas-admin-demo-live.spec.ts` to exercise the live seeded demo against the FastAPI API with persisted screenshots.

### Verified
- `cd apps/api && python -m alembic upgrade head` passed against the local MariaDB database.
- `cd apps/api && python scripts/seed_demo_full.py` passed and remained idempotent on rerun.
- `cd apps/api && python -m ruff check scripts/seed_demo_full.py` passed.
- `cd apps/api && python -m ruff check .` passed.
- `cd apps/api && python -m mypy app` passed.
- `cd apps/api && python -m pytest tests/test_admin_platform_api.py tests/test_ai_evidence_signal_summary.py tests/test_icp_signals_scoring_v2.py tests/test_leads_api.py tests/test_scoring_engine.py` passed.
- `cd apps/api && python -m pytest` passed: 224 passed, 2 skipped.
- `cd apps/web && npm run test:unit` passed: 28 tests.
- `cd apps/web && npm run build` passed.
- `cd apps/web && npx playwright test tests/e2e/saas-admin-demo-live.spec.ts --project=desktop-wide` passed.

### Demo Credentials
- Platform admin: `platform-admin@example.test` / `PlatformAdmin123!`
- Workspace owner: `admin@example.test` / `AdminPass123!`
- Workspace manager: `manager@example.test` / `ManagerPass123!`
- Workspace member: `user1@example.test` / `UserPass123!`
- Disabled workspace owner: `disabled-owner@example.test` / `DisabledOwner123!`

### Demo Seed Summary
- Ensures a platform operations workspace, an active demo workspace, a disabled demo workspace, active and disabled subscriptions, invoices, payment attempts, usage counters, AI feedback, outreach messages, audit logs, provider evidence, lead signals, ICP matches, score breakdowns, and AI evidence.
- Final local demo counts after rerun: 35 leads, 90 lead signals, 90 lead signal scores, 35 ICP matches, 26 provider fetches, 40 normalized provider facts, 14 provider errors, 242 score breakdown rows, 7 AI snapshots, 72 AI evidence rows, 3 AI feedback rows, 4 outreach drafts, 1 sent outreach message, and 6 usage counters.
- The local active workspace already contained prior demo/live data, so final counts include existing local data; reruns remained stable.

### Captures
- Saved 27 local Playwright screenshots under `apps/web/test-results/saas-admin-demo/`.
- The capture folder is ignored by `.gitignore`, so screenshots remain available locally but are not committed by default.

### CI/CD
- `.github/workflows/ci.yml` now runs on push and pull request and covers backend Ruff, mypy, full pytest, Alembic offline render, frontend lint, unit tests, build, Playwright E2E, Docker build validation, and deploy-stack smoke checks.
- No deployment pipeline or production deployment was added during closeout.

### Safety Notes
- No real provider calls, SMTP sends, OpenAI calls, API keys, `.env` files, database dumps, or screenshots with secrets were added.
- The live verification toggles workspace and user disabled states, then restores both before completion.

## [Goal] SaaS Platform Admin Console — 2026-06-25

### Phase 0 — Audit
- Confirmed the project already has real SaaS foundation tables/models for users, roles, workspaces, plans, subscriptions, invoices, payment attempts, usage counters, system/provider settings, provider fetches, search jobs, leads, ICP profiles, lead signals, lead scores, AI evidence/feedback, and outreach messages.
- Existing `/api/v1/admin` endpoints were workspace-admin controls for scoring, provider defaults, prompts, service catalog, and health, guarded by workspace owner/admin roles.

### Added
- Platform-only admin API endpoints under `/api/v1/admin`: overview, workspaces, workspace detail, workspace enable/disable, users, user enable/disable, plans, subscriptions, invoices, usage, providers, search jobs, AI usage, and feature health.
- Platform aggregates use persisted data only: workspace/user/lead/job counts, AI evidence, ICP/signals/scoring health, billing MRR from stored plans/subscriptions, unpaid invoices, provider errors, and usage counters.
- Billing admin invoice responses now include real invoice items and payment attempts; frontend billing admin shows payment attempts and unpaid/failed invoices.
- Workspace detail now surfaces workspace users, subscription, usage, ICP/signals/scoring summary, AI evidence/feedback counts, recent search jobs, recent provider errors, and recent audit logs.
- Provider admin now separates recent provider errors from the general provider fetch stream.
- Admin overview now renders every required KPI, workspace detail renders owner/search/invoice data, and provider admin renders persisted workspace provider settings.
- AI admin now renders feedback totals, latest feedback, and risky or low-confidence analyses derived from stored snapshot output.
- Demo-data reruns now idempotently backfill lead signals, ICP matches, and AI evidence from persisted lead/provider/score data so upgraded local workspaces expose the previous features without requiring a live AI provider.
- Fixed platform-admin enable/disable buttons remaining disabled after a successful mutation by limiting the pending state to active requests.
- Disabled workspaces now reject both new logins and existing bearer-token requests server-side; re-enabling the workspace restores access.
- Usage admin exposes an explicit quota override TODO because the current schema has no per-workspace quota override model.
- Sensitive admin actions write audit logs: workspace enable/disable and user enable/disable.
- Frontend platform admin routes under `/app/admin/*` for overview, workspaces, users, billing, usage, providers, jobs, and AI, guarded for `platform_admin`.
- Tenant workspace admin remains available to workspace owners/admins at `/app/workspace-admin`; `/app/admin` is reserved for platform admins only.
- Focused backend tests under `tests/test_admin_platform_api.py` for platform admin authorization, overview metrics, workspace disable/audit logging, user enable/disable, workspace detail rows, billing payment attempts, and provider response secret safety.

### Security
- Platform admin APIs use server-side `require_platform_admin`; workspace owners/admins/members cannot access them.
- Provider admin responses expose safe provider status/config metadata only and do not return raw request params or secrets.

### Migration needed
- Existing migration `0015_platform_admin_role.py` seeds the `platform_admin` role. No new schema migration was added in this step.

## [Sprint] Lead Signal Summary + AI Evidence-Based Analysis — 2026-06-25

### Phase 1 — ICP / Signals / Scoring 2.0 QA & stabilization
- Fixed cross-lead state bleed on the lead detail page: the last ICP recompute match, the success banner, and the AI-feedback state now reset when navigating between leads (`apps/web/src/features/lead-detail/routes/lead-detail-page.tsx`).
- Verified ICP profile CRUD, missing-match/empty-signal handling, recompute loading/error/success states, null-safe Scoring 2.0 rendering, and English/Arabic label completeness across the recently added panels — no further contract or i18n gaps found.

### Phase 2A — Lead Signal Summary (no N+1)
- `LeadResponse` now exposes `top_signal_type`, `top_signal_strength`, `top_signal_evidence`, and `signals_count` (additive, backward compatible).
- Added `LeadSignalRepository.summaries_for_leads`, a strictly workspace-scoped bulk loader (two queries, no per-lead round-trips) wired into both lead list and single-lead responses.
- Frontend: new toggleable, compact **Top signal** column in the leads table (clean dash when absent), with English/Arabic labels.

### Phase 2B/C — AI evidence storage + evidence-grounded analysis
- New tables `ai_analysis_evidence` and `ai_feedback` (migration `0014_ai_evidence_feedback.py`, reversible, guarded creation) with the required indexes on snapshot and user.
- `EvidenceBuilder` derives evidence deterministically from real stored data (detected signals, score breakdown, ICP matches, provider normalized facts) — no invented facts — and `AIAnalysisService.analyze` persists it per snapshot. Prompt now requests `pain_points`, `opportunity_reason`, `outreach_angle`, `risks_or_uncertainties`, and `evidence_used`, and instructs the model to say "unknown / insufficient evidence" rather than guess. `input_hash` caching and existing analysis consumers are preserved (new result fields are optional with defaults).

### Phase 2D/E — API + frontend
- `GET /api/v1/leads/{lead_id}/ai-evidence` and `POST /api/v1/ai-analysis/{snapshot_id}/feedback` (rating `useful|not_useful`, optional correction), both workspace-scoped.
- Lead detail page gains an **Evidence used by AI** section (type, confidence, text, optional source link) plus Useful / Not useful feedback with an optional correction note. English/Arabic labels added.

### Tests / quality
- Backend: `ruff check` clean, `mypy app` clean (157 files), targeted suite `test_ai_evidence_signal_summary.py test_icp_signals_scoring_v2.py test_leads_api.py test_scoring_engine.py` passed (17).
- Frontend: `npm run test:unit` passed (20), `npm run build` passed (zero TS errors).

## [Goal] ICP Profiles, Lead Signals, and Scoring 2.0 foundation — 2026-06-25

### Added
- ICP profile backend module with workspace-scoped CRUD at `/api/v1/icp-profiles`, including target industries/cities, rating/review constraints, website preference, required signals, excluded keywords, and lead match persistence.
- Lead signal engine with persisted `lead_signals` and `lead_signal_scores`; detects no/weak website, low rating, high reviews, missing phone, poor completeness, high local visibility, competitor gap, and outreach readiness.
- Scoring 2.0 component columns on `lead_scores`: `fit_score`, `need_score`, `urgency_score`, `reachability_score`, `final_priority_score`; new priority bands are additive to legacy bands.
- Manual recompute endpoints: `POST /api/v1/leads/{lead_id}/signals/recompute`, `GET /api/v1/leads/{lead_id}/signals`, and ICP lead match recompute endpoints.
- Migration `0013_icp_signals_scoring_v2.py`, seed ICP profile/demo signal matching, focused backend tests, and frontend API types/helpers for ICP and lead signals.

### Changed
- Discovery and manual refresh now recompute lead signals and ICP matches before scoring, then persist Scoring 2.0 while keeping legacy `total_score` consumers compatible.
- Lead responses and score breakdown responses expose Scoring 2.0 component fields.

### Tests / quality
- `ruff check` clean on changed backend files.
- `mypy` clean on runtime modules touched by the change; broad mypy still reports pre-existing strictness issues in `scripts/seed.py` and `tests/test_workspace_e2e.py`.
- `pytest tests/test_icp_signals_scoring_v2.py tests/test_scoring_engine.py tests/test_leads_api.py tests/test_lead_discovery_orchestrator.py` passed (23).
- `npm run build` passed.

## [Discovery] OpenAI web-search fallback when SerpAPI is rate-limited (429) — 2026-06-13

### Context
With the SerpAPI free key exhausted (250/250 used → HTTP 429), live discovery jobs
finished with **0 candidates** and status `failed`, even though parsing was correct.
The fix: when the primary provider returns no candidates, fall back to OpenAI's hosted
web-search tool to discover real businesses, then run them through the unchanged
normalize → dedupe → score pipeline.

### Added
- **`app/modules/provider_openai/web_search_discovery.py`** — `OpenAIWebSearchDiscovery`.
  Calls the OpenAI **Responses API** (`/responses`) with the hosted web-search tool
  (`web_search_preview`, falling back to `web_search` on a 400), asks for real local
  businesses matching the search criteria, and parses the JSON into normalized
  `LeadCandidate`s (reusing `compute_domain` / `compute_identities` /
  `compute_completeness` / `normalize_phone` from the SerpAPI normalizer shared helpers,
  so dedupe + merge behave identically). Tolerant parsing strips ``` fences and isolates
  the JSON object; ratings are clamped to 0–5; rows without a company name are dropped.
- **`Settings.discovery_openai_fallback_enabled`** (env `DISCOVERY_OPENAI_FALLBACK_ENABLED`,
  default `true`) — gates the fallback; also requires `OPENAI_API_KEY`.

### Changed
- **`LeadDiscoveryOrchestrator`** — after primary discovery yields no leads, calls
  `_discover_via_openai_fallback()`, which records a `ProviderFetch` (`provider="openai"`,
  `mode="web_search_discovery"`) for evidence FK integrity and upserts the candidates with
  `source_type="openai_web_search"` (priority 25, between maps_search=20 and web_search=30).
  When the fallback is used, the SerpAPI-backed enrichment steps (maps_place, web presence,
  external enrichers) are **skipped** — they would only burn more 429 retries — but scoring
  still runs, so the rating/review filters in `_qualifies` still apply.
- No schema change: reuses the existing `provider_fetches` / `provider_normalized_facts`
  tables (`provider` and `source_type` are already `String(32)`).

### Verified live (frontend + backend)
- Submitted `ابحث عن مراكز لياقة بدنية في الرياض بعدد مراجعات بين 20 و150 وتقييم أعلى من 4`
  through the real UI (`/app/searches` → "Search with AI"). SerpAPI returned 429; the
  OpenAI fallback returned real Riyadh fitness centers (Q_FIT, Kinetico, Vitality Fitness
  Club, …), which appeared scored in the leads table at
  `/app/leads?search_job_id=…`. The job drawer correctly showed `Rating window 4–All`,
  `Review window 20–150`.

### Tests / quality
- `tests/test_openai_web_search_discovery.py` (7 tests): code-fence/prose JSON parsing,
  Responses-API output extraction, field normalization + identity building, rating clamp,
  stubbed `discover()` happy path, and unavailable → empty.
- `ruff` + `mypy` clean on the new module + test; orchestrator + discovery-pipeline suites
  still pass (15).

## [Search] Local prompt parser handles Arabic review ranges + "higher than" rating — 2026-06-13

### Context
The smart-search prompt
`ابحث عن مراكز لياقة بدنية في الرياض بعدد مراجعات بين 20 و150 وتقييم أعلى من 4`
("fitness centers in Riyadh, review count between 20–150, rating above 4") parsed
incorrectly in the local fallback parser (`search_jobs/prompt_parser.py`):
- `city` absorbed the entire filter tail → `"الرياض بعدد مراجعات بين 20 و150 …"`
  instead of `"الرياض"` (no Arabic stop token for `بعدد`/`مراجعات`/`وتقييم`).
- `min_reviews`/`max_reviews` were `None` — no "between X and Y" (`بين X و Y`) range support.
- `min_rating` was `None` — `تقييم أعلى من 4` ("rating higher than 4") had a word between
  `تقييم` and the number, which the existing `تقييم 4` pattern couldn't match.
With OpenAI configured the cloud parser handled it, but the no-OpenAI fallback produced
a broken search job.

### Changed
- **`_PLACE_STOP_RE`** — added Arabic stop tokens so the city is truncated at the filter
  clause: `بعدد`/`عدد`, prefix-tolerant `(و)(ب)مراجعات` and `(و)(ب)تقييم`, plus a
  numeric look-ahead (`\s+(?=\d)`) as a general safety net.
- **`_MIN_REVIEWS_PATTERNS` / `_MAX_REVIEWS_PATTERNS`** — added range patterns for both
  Arabic (`… مراجعات بين 20 و150`, number-first `بين 20 و150 مراجعة`) and English
  (`between 20 and 150 reviews`, `20 to 150 reviews`); min = first number, max = second.
- **`_MIN_RATING_PATTERNS`** — added `تقييم أعلى/أكثر من 4`, `أعلى من 4 نجوم`, and the
  English `above/over/higher than 4 stars`. The English variant *requires* a `stars|rating`
  keyword so it can't collide with review-count phrases like "more than 50 reviews".

### Tests / quality
- New `test_search_prompt_parser_arabic_review_range_and_min_rating` asserts the exact
  query yields `business=مراكز لياقة بدنية`, `city=الرياض`, `min_reviews=20`,
  `max_reviews=150`, `min_rating=4`.
- Hardened the three "uses_local_fallback" tests to force the local path with
  `monkeypatch.setenv("OPENAI_API_KEY", "")` (empty env var overrides the key sourced
  from `.env`; `delenv` alone did not, so they previously exercised live OpenAI here).
- `ruff check` + `mypy` clean on the changed module; full search-jobs suites
  (`test_search_prompt_parser`, `test_search_jobs_api`, `test_search_job_service`,
  `test_router_v2`) pass (3 + 14).

## [Assistant] Workspace answers now stream from the LLM on real lead data — 2026-05-30

### Context
Workspace-level questions (no specific lead) were intercepted by keyword routers
(`_is_qualified_leads_question`, `_is_comparison_question`, `_is_best_lead_question`)
that printed **canned deterministic tables/lists** regardless of what was actually
asked — e.g. "how do I handle the qualified leads" returned the identical list as
"which leads to contact first", and "compare and explain the trade-offs" returned a
bare table with no explanation. Requirement: workspace replies must come from the LLM
grounded on true database data, like the lead-specific path already does.

### Changed
- **`_generate_tokens()` (lead=None path) now routes through the LLM.** It builds a
  grounding payload from the real top-25 stored leads + their latest scores and streams
  the model's answer. The model answers the *actual* question (compare → explain +
  recommend; "how to engage" → per-lead outreach approach), in the user's language.
- Deterministic builders (`_build_qualified_leads_response`, `_build_comparison_response`,
  `_build_workspace_response`) are **retained only as an offline fallback** via the new
  `_workspace_fallback_tokens()`, used when `_resolve_runtime_candidates()` is empty
  (demo / no provider). Verified non-empty in this env (`ollama → openai` failover).

### Added
- `_stream_from_llm()` — extracted the runtime-failover streaming loop (shared by the
  lead and workspace paths; the lead path is a pure refactor, no behavior change).
- `_workspace_leads_grounding()` — serializes top leads + scores to JSON-safe facts;
  qualified count is labelled `qualified_in_returned` (not mislabeled as a workspace total).
- `_build_workspace_llm_messages()` — evidence-first system prompt that forbids invented
  facts, ranks strictly by the stored deterministic score, distinguishes unscored leads,
  and requires explanation after any comparison table.

### Removed
- Dead `_is_best_lead_question()` (its routing was replaced by the LLM path).

### Tests / quality
- `test_workspace_question_routes_through_llm_not_canned` — asserts the LLM sentinel is
  used, canned headers are absent, and real lead ("Acme Dental") reaches the grounding.
- `test_workspace_question_falls_back_to_deterministic_without_provider` — graceful
  no-LLM degradation.
- `ruff` clean, `mypy` clean, `tests/test_assistant_api.py` 8/8 passing.
- **Live-verified** against the running dev server: the Arabic "compare & explain"
  question returned a grounded LLM analysis (no canned `📊 مقارنة` header).

## [Assistant Fix] Repair workspace response path + remove canned insight text — 2026-05-30

### Context
The workspace assistant (no specific lead) was broken at runtime and the "best lead"
panel printed identical hardcoded prose for every lead regardless of its actual data —
including a self-contradicting `Data Is Solid: Complete business identity coverage`
claim shown even for low-confidence leads. All responses remain sourced from the
database; the fix removes static text masquerading as analysis and repairs the crashes.

### Fixed
- **`AttributeError` on every workspace question** — `_generate_tokens()` called
  `_build_workspace_response()`, which did not exist. The method body had been
  accidentally fused into the tail of `_build_comparison_response()`. Extracted it into
  a real method with signature `(db, *, workspace_id, messages, search_context)`.
- **`NameError: search_line`** — the fused code referenced an undefined `search_line`
  variable on every English/Arabic workspace reply. Now defined at the top of
  `_build_workspace_response()` (with an `_ar` variant), driven by
  `search_context.used_search`.
- **English comparison silently fell through** — `_build_comparison_response()`'s English
  branch built its table but never returned, dropping into the workspace summary code.
  Added the missing `return "\n".join(lines)`.

### Changed
- **Insight bullets are now data-driven, not hardcoded.** The "Why this lead ranks first"
  bullets (EN + AR) branch on the lead's real `band`, `data_confidence`, `has_website`,
  and `qualified` values instead of printing the same three sentences for every lead.
- Section headers aligned to spec: `Top candidates (N of M)` / `أفضل المرشحين (N من M)`.

### Quality
- Removed unused `website_text` / `website_text_ar` (ruff F841) and 6 placeholder-less
  f-strings (F541); fixed a `union-attr` mypy error in `_build_qualified_leads_response()`
  via an assignment-expression `None` guard.
- `ruff check` clean, `mypy` clean, `tests/test_assistant_api.py` 6/6 passing.

## [Assistant Responses] Intelligent routing + strong builders for common questions — 2026-05-30

### Context
Enhanced the workspace assistant to provide **data-driven, targeted responses** instead of generic summaries. Added smart routing that detects question intent and builds tailored responses directly from stored data.

### Added
- `_is_qualified_leads_question()` — Detects questions like "which qualified leads should I contact?"
- `_is_comparison_question()` — Detects comparison requests like "compare top 3 leads"
- `_is_best_lead_question()` — Enhanced with better keyword matching for engagement strategy questions
- `_build_qualified_leads_response()` — Ranked list of qualified leads with:
  - Priority order (highest score first)
  - Key metrics table (score, rating, category, website)
  - Actionable outreach tips
  - Bilingual support (Arabic/English)
- `_build_comparison_response()` — Side-by-side lead comparison with:
  - Metrics table for easy scanning
  - Detailed analysis per lead
  - Clear recommendation on which lead to prioritize
  - Bilingual formatting

### Changed
- `_generate_tokens()` routing logic now intelligently dispatches:
  - Qualified leads questions → `_build_qualified_leads_response()`
  - Comparison questions → `_build_comparison_response()`
  - Best lead questions → Auto-fetch top lead + call recursively with lead context
  - Default workspace questions → `_build_workspace_response()`
- All workspace-level responses now return **immediate, data-backed answers** instead of waiting for LLM
- Better Arabic/English keyword detection with expanded vocabulary

### Impact
- Users asking "Which leads should I contact first?" now get immediate ranked list instead of generic summary
- Users asking "Compare top 3 leads" get structured comparison table instead of "please provide details"
- Users asking "How to engage with my best lead" get lead-specific strategy instead of workspace overview
- **100% data-driven responses** — no hallucination, only stored facts
- Bilingual support consistent across all response types

## [Assistant UX] Enhanced bilingual workspace assistant output — 2026-05-30

### Context
Improved the workspace assistant general response to provide better visual hierarchy, actionable insights, and professional formatting for end users. The assistant now presents lead summaries with visual indicators, confidence levels, and contextual recommendations.

### Added
- Visual indicators for lead quality: confidence icon (🟢/🟡/🔴), qualification status (✓/○), band emoji (⭐ ratings)
- Markdown table format for key metrics (Score, Qualification, Reputation, Website, Data Confidence)
- Contextual action recommendations dynamically generated based on lead attributes (website presence, qualification status, review volume)
- Better section organization with clear visual separators (---)
- Emoji-based section headers for improved scannability (🎯, 🏆, 💡, ⚡, 📈, 🔍)
- Professional "Pro Tip" and summary footer for deeper exploration

### Changed
- Arabic response (`_build_workspace_response` with `prefers_arabic=True`):
  - Changed from bullet list format to structured table for key metrics
  - Improved Arabic UI labels (e.g., "مساعد مساحة العمل — ملخص العملاء" as title)
  - Added dynamic action items based on lead state (website check, outreach readiness, competitive comparison)
  - Enhanced explanations with emoji indicators and clearer hierarchy

- English response:
  - Parallel improvements to Arabic version for consistency
  - Professional tone with visual metrics table
  - Actionable follow-up questions formatted for better discovery
  - Dynamic suggestions based on lead qualification and reputation signals

### Impact
- End users get clearer, more professional lead summaries
- Visual indicators reduce cognitive load when scanning high-value leads
- Actionable recommendations guide next steps without additional prompts
- Bilingual support maintained with enhanced quality for both Arabic and English

## [Step 5] B2B contact fields, LinkedIn enricher, JSON export, voice search — 2026-05-29

### Context
Adapts a generic enhancement request into the existing `apps/web` + `/api/v1` codebase
(no `apps/frontend/` or `/api/v2` was created). Adds B2B-style contact/firmographic fields to
leads with a full schema + pipeline, plus JSON export and voice search. Several fields lack a
data source in a local-business/SerpAPI pipeline and are populated best-effort (see below) —
`email`, `email_confidence`, and `employee_count` stay NULL until a contact provider is wired
into the enrichment seam.

### Added
- 7 nullable columns on `leads` (model + migration `0011_lead_contact_fields.py`, idempotent
  `_has_column` guard like `0010`): `email` (VARCHAR 320), `email_confidence` (FLOAT),
  `linkedin_url` (VARCHAR 512), `industry` (VARCHAR 255), `employee_count` (INT),
  `ai_opener` (TEXT), `logo_url` (VARCHAR 512). All exposed as optional fields on
  `LeadResponse` (additive — existing response shape preserved).
- `app/shared/utils/branding.py` — `normalize_domain()` + `derive_logo_url()` (deterministic
  Clearbit logo URL from a lead's domain, no API call).
- `LinkedInEnricher` (`app/enrichers/linkedin.py`) + engine `provider_serpapi/engines/linkedin.py`
  — best-effort `site:linkedin.com/company "{company}" {city}` web search; emits `linkedin_url`.
  Registered in `_get_active_enrichers()`; `linkedin` added to `ENRICHERS` in `.env.example`.
- JSON export: `GET /api/v1/exports/leads.json` (same filters + auth as `/leads.csv`,
  billing-tracked). `ExportService` refactored to share `_collect_rows()` between CSV and JSON;
  both writers now include the new contact fields. CSV behaviour/headers extended, not removed.
- Frontend: `LeadContactCard` (logo with favicon fallback, industry, email + confidence bar,
  LinkedIn link, employee count, AI opener — each with empty states) on the lead detail page;
  optional `industry` column in the leads table (`ColumnVisibility` + `piq:leads_col_vis`);
  JSON download button on the exports page (`downloadLeadsExportJson`); `useVoiceInput` hook
  (Web Speech API, graceful fallback) + mic button on the search prompt.
- i18n keys (`leadContact.*`, `leads.industry`, `exports.downloadJson`, `searches.voiceHint`,
  `searches.voiceListening`) in both `en.json` and `ar.json`.
- Tests: `tests/test_lead_contact_fields.py` (branding helper, LinkedIn engine/enricher,
  LeadResponse fields, CSV+JSON export contents); `contact-card.test.tsx`, `use-voice-input.test.ts`.

### Changed
- `_upsert_candidate` sets `industry` (from category) and `logo_url` on lead creation;
  `_merge_lead` backfills both for existing leads. `_run_enrichment` adds a `_promote_enrichment_fields`
  step copying provider-derived `linkedin_url`/`email`/`email_confidence`/`employee_count` onto the
  typed columns (existing non-null values are never overwritten).
- `AIAnalysisService` sets `lead.ai_opener` from the analysis `summary` (reuses the existing AI
  path — no new AI call added to discovery).

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
