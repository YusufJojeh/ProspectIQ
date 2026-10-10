# CHANGES

## [Copilot] Standalone Sales Copilot page - 2026-10-10

### Added
- `/app/copilot` (`features/copilot/routes/copilot-page.tsx`): the copilot used to live only inside lead detail, with no nav entry. It now has its own page, linked from the sidebar, the mobile nav and the command menu. A "Lead context" card lets you search for a lead and pick one, which stores it as `?leadId=` so the link can be shared, or clear it. With no lead picked, the copilot works in workspace mode.
- Workspace mode: `CopilotPanel` takes an optional `leadId`. Without one it shows workspace suggestions (services, case studies, objections, playbook) and skips the evidence-graph query.
- `runtime.tools_for_run`: a run with no lead is offered only RAG tools, minus `match_capabilities_to_lead`. The model is never handed lead read/write tools that would fail with "no lead bound".
- Tests:
  - `tests/test_agent_workspace_run_tools.py`
  - `tests/e2e/copilot-page.spec.ts` (workspace run sends no lead; picking a lead binds it; clearing a lead unbinds it)

### Known limitations
- The agent loop still runs inside `POST /agent/runs`, so the SSE stream replays the run's events after it finishes instead of showing progress live.

## [Search UX] Job progress SSE now runs on the shared EventBroker - 2026-10-08

### Changed
- `core/progress_bus.py` publishes through `agents.events.EventBroker` (in-memory or Redis, per `AGENT_EVENT_BROKER`) instead of a private one-queue-per-job dict. Many viewers can follow one job, one viewer disconnecting no longer unregisters the others, and Redis delivers across API workers.
- New `search_jobs/stream.py` is the single SSE body for `GET /api/v1/search-jobs/{id}/stream` and `GET /api/v2/stream/{id}`. It subscribes first, then sends the latest event as a snapshot (so a reconnecting client catches up), de-duplicates by seq, and emits `id:` per event. The `data:` payload is still `{stage, progress, message}`, so `useJobStream` is unchanged.
- `LeadDiscoveryOrchestrator._emit` now carries `workspace_id` (Redis channels are tenant-scoped).

### Added
- `tests/test_job_progress_stream.py`.

### Removed
- `/api/v2` (`search_jobs/router_v2.py`, its router registration and `tests/test_router_v2.py`) and the `apps/frontend` scaffold, its only consumer. `apps/web` never called v2, and CI, infra and docs did not reference `apps/frontend`. The v1 stream endpoint is now the only job-progress SSE; `useJobStream` is unaffected.

### Known limitations
- The snapshot is in-process. With the Redis broker, a client on a different worker than the one running the job gets live events only, plus the persisted terminal status.

## [Accessibility] Keyboard, focus and screen-reader pass over the new surfaces - 2026-09-20

### Added
- `hooks/use-return-focus.ts`: controlled Radix dialogs are opened from a state flag, not a `<Trigger>`, so Radix has no element to restore focus to on close. The hook records what opened the dialog and returns focus through `onCloseAutoFocus`. It falls back to the last activated control because touch pointers do not focus a button when tapped, which is why focus return failed only on the tablet and mobile projects.
- `tests/e2e/accessibility.spec.ts`: axe (`wcag2a/2aa/21a/21aa`, contrast excluded) over the Knowledge page, both of its dialogs, the archive alert dialog, and lead detail at idle, at `waiting_for_approval`, after a terminal phase and on a failed run; plus focus-trap, focus-return, keyboard-only approve/decline, an accessible-name sweep of icon-only buttons, a live-region budget, and assertions that Supported / Conflicting / Unverified and pending / applied / declined are stated in words.
- `@axe-core/playwright` (dev dependency only).

### Fixed
- The Copilot, Evidence Graph and Research History cards were unlabelled `<div>`s: they are now `role="region"` with `aria-labelledby` pointing at a heading, so the panels are reachable as landmarks.
- Unlabelled selects on lead detail (assignee, status, campaign, ICP profile, outreach tone) produced `button-name` violations; each trigger now carries an `aria-label`.
- Lead map markers are `role="button"` with no name (`aria-command-name`); each marker now carries the company name as its title.

### Known limitations
- Colour contrast is excluded from the axe run and is verified against the design tokens instead: the headless render differs from the real one in fonts and blend modes.
- The audit covers the new surfaces and lead detail. Older routes were not swept.

### Migration needed: no

## [Frontend + Integration] Sales Copilot, Evidence Graph, Research History, Sales Knowledge UI - 2026-09-19

### Added
- Copilot state machine (`features/copilot/agent-state.ts`, pure reducer; terminal phases sticky; events de-duplicated by `seq`; action status comes only from the server), fetch-based SSE client with `Last-Event-ID` resume, abortable exponential back-off and event batching, and `useAgentRun`. Sequential approvals re-sync the same run (no second run is created).
- Lead detail: Sales Copilot panel (activity, approvals with exact previews, final-answer hierarchy separating lead evidence from internal knowledge), Evidence Graph panel, Research History with depth choice and "What changed?".
- `/app/knowledge`: collections, documents (paste or plain-text upload), replace content, archive ("removed from answers"), ingestion outcome states (indexed / keyword-only / unchanged / failed), search tester with degraded-mode notice; en + ar strings; sidebar, mobile nav and command menu entries.
- Tests: reducer, SSE parser, file reader (Vitest); E2E `copilot.spec.ts` (pending is never shown as applied, decline, evidence/knowledge separation, server error) and `knowledge.spec.ts` (upload/search/replace/remove, refused files, member cannot pick restricted). The Playwright mock now models the research and knowledge endpoints and matches backend permissions (`leads:manage`).

### Fixed
- Backend: approving/rejecting agent actions was gated on the role name `admin`, so managers and members (who hold `leads:manage`) got 403. It now uses the permission.
- Backend: knowledge document listing, re-ingest and archive ignored visibility (any member could see or change a private or restricted document, and the service-catalog agent tool listed them); `restricted` documents could be created by roles that could never read them. Visibility is now enforced in one place (`knowledge/visibility.py`).
- Backend: agent actions returned an internal run id; they now return the public `run_id`.
- Contract drift: the re-ingest client sent no body although the API requires a full document body; `OutreachGenerateRequest` lacked `language`.
- Truthfulness: the outreach "Send" button only records a status and delivers nothing. It is now "Mark as sent" with a note, and the raw status string is localized.

### Known limitations
- Any workspace member may create, replace or archive workspace-visible knowledge; only visibility is enforced, there is no separate management permission.
- No endpoint returns a document's stored text, so "Replace content" requires the full new text.
- Capability matching is exposed only through the copilot's tools; there is no REST endpoint or dedicated UI.
- The lead-detail visual baseline was regenerated because the page now contains three new panels.

### Migration needed: no

## [Hardening] Production-verification gaps: grounded evidence refs, Redis SSE broker, RAG metrics - 2026-09-19

### Added
- `agents/grounding.py`: `evidence_refs` on a final answer are now backend-grounded (model-requested AND observed in this run's persisted `AgentToolCall` results AND owned by the run's workspace/lead). Fabricated refs are dropped, never fail the run, and emit `final_evidence_ref_dropped`. Reconstructable across pause/resume.
- `EventBroker` protocol with `InMemoryAgentEventBroker` and `RedisAgentEventBroker` (persist-then-publish, channel `{prefix}:{workspace}:{run}`, safe payload only, boot ping, scope check on delivery). Selected by `AGENT_EVENT_BROKER`; production refuses `inmemory` without `AGENT_EVENT_BROKER_SINGLE_WORKER=true` and `redis` without `REDIS_URL`. SSE supports `Last-Event-ID` (replay/live handoff without loss or duplication) and closes on `waiting_for_approval`. `redis>=5.0.0` declared in pyproject.
- Tests: `test_evidence_grounding.py`, `test_agent_redis_broker.py` (fake Redis only), `test_acceptance_change_monitoring.py` (section 49, transcript-driven model double, both branches), `test_agent_tool_validation.py`, `test_rag_retrieval_metrics.py` (+ `rag_golden_dataset.py`, `rag_metrics.py`), `scripts/rag_scale_benchmark.py`, `docs/RAG_RETRIEVAL_QUALITY.md`.
- `test_live_agent_smoke.py` rewritten (3 opt-in smokes) with a clear failure when the provider rejects the call.

### Fixed
- Tool-schema validation did not enforce `minItems`.
- Keyword retrieval lacked two-letter stopwords (`to`, `in`, `of`...): 50% of off-topic queries returned results; now 20%.
- Duplicate-tool-call guard now forgets READ signatures after a tool that persists new evidence, so a post-refresh re-read is allowed.

### Known limitations
- Redis broker proven against a fake Redis only; no real Redis server was run.
- Live smoke was executed and FAILED: the configured OpenAI key returned HTTP 401. Live-provider behaviour is unverified.
- The RAG candidate cap is recency-based: recall@5 is 0.20 at 1k chunks and 0.00 at 10k (see docs/RAG_RETRIEVAL_QUALITY.md). Not fixed here.

### Migration needed: no

## [Hardening] Phase E verification: schema-enforced tool arguments, backend-grounded final answers, main acceptance E2E - 2026-09-19

### Added
- `validate_arguments()` in `agents/tool_registry.py`: every model tool call is checked against the tool's registered `input_schema` (types, enum, required, `additionalProperties: false`, length/range bounds) at the single dispatch point in `AgentRuntime._handle_tool_call`. Invalid calls are recorded as `tool_failed` with a model-readable error and never reach a domain service or the action gate. Previously an invalid enum (e.g. `tone: "professional"`) raised an unhandled `ValueError` and a stray `query` on `search_web_tavily` was silently ignored.
- `AgentFinalAnswer.knowledge_refs`: Internal Sales Knowledge citations kept separate from `evidence_refs` (lead evidence).
- `AgentRuntime._ground_final_answer()`: backend-owned fields overwrite the model's claims on completion: `research_coverage` from the deterministic Evidence Graph, `knowledge_refs` filtered to documents in this run's `knowledge_selected` events, `completed_actions`/`pending_actions` from `AgentAction` rows.
- `tests/test_acceptance_sales_copilot.py`: section-48 E2E with a transcript-reading (unscripted) model double. It covers lead/ICP/evidence/Tavily/score/RAG/draft, a note + follow-up paused with nothing written, sequential approvals with retried-approval idempotency, two same-run resumes, one run, one note, one activity, a shared trace_id, and fabricated citations/actions discarded. Also covers invalid-argument rejection.

### Fixed
- `test_twelve_concurrent_runs_stay_independent`: the provider double kept its step counter on a per-call instance, so every call re-requested the same tool and the runtime (correctly) tripped the duplicate/consecutive-failure breaker. It now decides from the transcript.
- Eval tests that passed a `query` to parameterless `search_web_tavily` now call it with `{}`.

### Quality gate
- `ruff check .`: clean · `mypy app/`: 0 errors (233 files) · `pytest`: 458 passed, 4 skipped (live smoke / live-provider tests, opt-in).

### Migration needed: no

## [Feature] Governed actions and external send boundary (Phase C) - 2026-09-18

### Added

- `app/modules/outreach/send_gateway.py`: the single boundary where an outreach message could leave the platform. Everything else the agent can do — a draft, a note, a stage change, a task — is reversible by a human afterwards; a sent message is not, so this module is deliberately the most restricted thing in the codebase.
- Three tools registered: `send_email`, `send_whatsapp`, `send_linkedin_message` — `tool_type=action`, `risk_level=high`, `requires_approval=True`, `external_io=True`, `cost_class=external`.
- **External sending is DISABLED by default** (`EXTERNAL_SEND_ENABLED=false`), and "disabled" means three independent refusals rather than one: (1) a new `ToolDefinition.feature_flag` makes `tools_for_profile` omit the tool, so the model is never told it exists; (2) `build_preview` calls `ExternalSendGateway.ensure_enabled()`, so a disabled send cannot even be proposed for approval — an approval queue full of actions that can never run is its own hazard; (3) `execute_action` re-checks independently, so flipping the flag off between approval and execution still refuses.
- **No delivery transport exists.** Even with the flag enabled, `ExternalSendGateway.send` logs the attempt for audit and returns `delivered=False, provider="none"`. Wiring a real ESP, the WhatsApp Business API or LinkedIn is separate, audited work with its own credentials, consent records, suppression lists and compliance review. A plausible-looking stub that silently swallowed messages would be worse than an explicit refusal, so the result states exactly what happened and `outreach_status` advances to `sent` only on a genuine delivery — otherwise every downstream reply-rate and follow-up decision that reads that column would be reading a lie.
- **Approved payload == executed payload.** The send payload carries the exact stored draft text, resolved from the database by public id; the model supplies an id, never a body, so a human approves text they can read rather than something re-typed at send time. The payload is hashed at proposal, and `AgentActionGate.approve` re-hashes the stored payload immediately before execution and raises on mismatch. The recipient is likewise taken from the approved payload, never re-derived from the lead record at send time — approved text going to an address nobody reviewed is the same failure by a different route.
- Send tools are scoped to the `sales_copilot` and `admin_assistant` profiles, but the copilot's `medium` risk ceiling excludes them in practice: the profile must name the tool, the tool must name the profile, the caller must hold `outreach.write`, and the risk ceiling must allow it. In the shipped configuration only `admin_assistant` can see them, and only when the flag is on.

### Tests

- `tests/test_external_send.py` (11): registration policy (type/risk/approval/flag), no tenancy parameter in any send schema and `additionalProperties: False`, invisibility to every profile while disabled, visibility only to `admin_assistant` when enabled, gateway refusal transmitting nothing, refusal at proposal time, refusal at execution time with a previously-approved payload (config changed between approval and execution), payload carrying the exact stored draft text, tamper-detection via `hash_payload` (including that key order alone does not change the hash), rejection of an outreach message belonging to another lead, and the honest result path — `delivered=False`, `provider=none`, draft status unchanged in the database.

### Notes

- Live sending is **disabled** and **undelivering** in this build. Nothing in this phase can transmit a message.

## [Feature] Sales Knowledge RAG (Phase B) - 2026-09-18

### Added

- `app/modules/knowledge/`: a retrieval store for the agency's OWN sales knowledge — service catalogue, capabilities, case studies, portfolio, playbooks, objection handling, pricing guidance, proposal templates, past proposals, winning outreach. It answers "what can we credibly offer this prospect?", which is a different question from the lead research store's "what is true about the prospect?". Structured operational lead data (score, evidence, stage, CRM fields, research history) is deliberately NOT embedded here just because vectors exist; it is still read through deterministic tools.
- Data model via migration `0024_sales_knowledge_rag`: `KnowledgeCollection`, `KnowledgeDocument`, `KnowledgeDocumentVersion`, `KnowledgeChunk`, `KnowledgeIngestionRun`. Documents are versioned rather than overwritten, so a citation stays resolvable and a superseded revision can be retired atomically.
- **No pgvector.** The deployment database is MariaDB/MySQL, so embeddings are stored as JSON float arrays with their model, dimension and precomputed L2 norm, and cosine similarity is computed in Python over a candidate set the SQL has already restricted. This is a real limit and is documented in `retrieval.py`: on a very large corpus, recall is bounded by `knowledge_search_candidate_limit` (default 400).
- `app/modules/knowledge/retrieval.py`: hybrid retrieval — IDF-weighted keyword overlap plus vector cosine, combined at `knowledge_hybrid_vector_weight` (0.7). **Tenant, visibility, status and version filtering all happen inside the candidate query.** A foreign workspace's chunk, an archived document's chunk, a superseded version's chunk, or a document the caller may not see is never loaded into the process, so no later bug in the Python scoring can leak it. A chunk embedded by a different model is never compared against the query vector (incompatible vector spaces); it can still match on keywords.
- Precision guard `knowledge_min_vector_only_similarity` (0.35): a passage with zero lexical overlap must clear a much higher vector bar. Low-dimension/hashed embeddings have a spurious-similarity noise floor, and a confidently-cited irrelevant case study is worse for a salesperson than no result.
- `app/modules/knowledge/embeddings.py`: `EmbeddingRouter` over `OpenAIEmbeddingProvider` and a deterministic, dependency-free `LocalHashingEmbeddingProvider` (256-dim, blake2b hashed bag-of-words, sublinear term weighting). The local provider keeps the pipeline functional and the evals offline and reproducible; it is explicitly documented as lexical, not semantic — it cannot match "appointment scheduling" to "booking system" without word overlap. The embedding model always comes from settings, never from a caller or the agent.
- `app/modules/knowledge/chunking.py`: structure-first chunking (headings → paragraphs → sentences) with overlap. Every chunk carries and is embedded with its section heading, so a chunk boundary cannot orphan a claim from the case study or service it belongs to. Text is NFKC-normalized with control, zero-width and bidi-override characters stripped, so what a reviewer reads is what the model receives.
- `app/modules/knowledge/ingestion.py`: validate → sanitize → checksum → (skip if unchanged) → new version → chunk → embed → store inactive → activate atomically → mark ready. Unchanged re-ingestion is reported as `skipped_unchanged` rather than silently re-embedding. Chunks are written inactive and swapped in one transaction, so a failure mid-ingestion leaves the previous version serving rather than the document unsearchable; a document that already has a live version stays `ready` on failure.
- `app/modules/knowledge/api.py`: `/api/v1/knowledge/collections` (POST, GET), `/documents` (POST, GET), `/documents/{id}/reingest` (POST), `/documents/{id}` (DELETE — archive), `/search` (POST). Visibility is resolved from the authenticated user; there is no request field that lets a caller widen its own scope.
- Agent tool `search_sales_knowledge` (tool_type `rag`, risk `low`, requires `knowledge.read`). Its schema has exactly three fields — `query`, `collection_types` (closed enum), `limit`. There is no workspace, user, tenant, visibility or SQL field for an injected instruction to fill in; tenancy comes from the run and the acting user. Unknown `collection_types` values are dropped rather than trusted, so an invented filter can never widen scope. Results re-enter the model wrapped as untrusted `KNOWLEDGE_CONTEXT` via the existing `wrap_untrusted` path.
- Runtime RAG lifecycle events: `rag_search_started`, `rag_search_completed` (result/candidate counts, embedding model, degraded flag, duration) and `knowledge_selected` (which documents grounded the answer — ids, titles, types, sections, versions, scores; never the passage text, which is untrusted content and stays in the tool result). Bounded by the new `agent_max_rag_queries` budget (default 8) and counted in `AgentRun.rag_query_count`.
- Tests: `tests/test_knowledge_rag.py` (17 evals) — Recall@3 / Precision@1 / MRR on a labelled corpus with deliberately overlapping vocabulary, citation-resolves-to-the-containing-document, irrelevant-query-returns-nothing, empty store, collection-type filtering and invented-filter rejection, cross-workspace isolation (asserting `candidate_count == 0`, i.e. never a candidate rather than filtered afterwards), private-document isolation from a colleague, restricted-document role gate, archived-document exclusion, re-ingestion superseding a price (the current retainer figure is returned and the old one is absent), skipped unchanged re-ingestion, the single-active-version invariant, section preservation under chunking, duplicate-passage crowd-out, sanitizer stripping invisible/control characters, poisoned-document inertness, and the structural assertion that the RAG tool schema exposes no tenancy field.

### Notes

- Retrieval quality with the local hashing provider is lexical. Deployments that need true semantic recall configure `EMBEDDING_PROVIDER=openai`; the evals pin behaviour, not provider quality.

## [Feature] Agent Runtime hardening: live SSE, tool-registry policy, injection defence (Phase A) - 2026-09-18

### Added

- `app/modules/agents/events.py`: the canonical agent event vocabulary and an in-process `AgentEventBroker`. Events are persisted first and published second, so a subscriber can never see an event that is not in the database. `sanitize_payload` drops forbidden keys (prompts, messages, reasoning/chain-of-thought, credentials, tokens) and truncates long values on the way IN, so an unsafe payload is never stored, not merely never rendered.
- **Known limitation, stated plainly:** the broker is in-process. This project has no Redis or other pub/sub, so live streaming works within a single API process; a multi-process deployment needs a shared broker behind the same `publish`/`subscribe`/`unsubscribe` seam. The replay path (`after_seq`) is durable and process-independent.
- `GET /api/v1/agent/runs/{run_id}/stream`: real SSE (`text/event-stream`). It subscribes BEFORE reading history so no event can fall between replay and live, de-duplicates by `seq`, resumes from `after_seq`, emits heartbeats every `agent_stream_heartbeat_seconds`, closes on a terminal event, and always unsubscribes in a `finally`. A slow client cannot block the agent loop: publishing uses `put_nowait` and drops on a full queue.
- Runtime now emits `model_started` / `model_completed` (provider, model, token counts, and the requested tool's NAME only — never the reasoning behind it), `tool_requested` before any budget check, `tool_started` immediately before execution, `tool_completed` / `tool_failed` with `duration_ms`, and `budget_exhausted` with `AgentRun.stop_reason`.
- `app/modules/agents/untrusted.py`: untrusted-content envelopes for research and RAG results, forged-marker stripping, a security preamble, and injection-marker detection recorded for observability ONLY — never used as a security decision. The module documents that the real boundary is structural: no tenancy parameter exists in any tool schema, writes require human approval, profiles gate tool availability, and scoring stays deterministic in the backend.
- `tool_registry.py` extended into a policy object: `tool_type` (read/research/rag/generative/write_proposal/action), `risk_level`, `requires_approval`, `resource_type`, `required_permissions`, `allowed_profiles`, `timeout_seconds`, `max_result_bytes`, `cost_class`, `external_io`. `tools_for_profile` requires three independent conditions — the profile names the tool, the tool names the profile, and the user holds every required permission — so a tool the caller is not entitled to is never described to the model at all.
- `AgentRun` columns via migration `0023_agent_profiles_and_cost`: `profile`, `prompt_key`, `prompt_version`, `stop_reason`, `rag_query_count`, `model_call_count`, `embedding_tokens`, `cost_micro_usd` (micro-USD integers, to avoid float drift in money).
- New setting `agent_runtime_mode` (`auto|openai|stub|blocked`) so provider-level tool-call behaviour can be exercised under test without the test environment silently forcing the stub.
- Tests: `tests/test_agent_streaming.py` (7), `tests/test_agent_provider_contract.py` (3, including a provider double that branches on the CONTENT of earlier tool results, proving the loop is model-directed and not a scripted workflow), `tests/test_agent_concurrency.py` (10, against file-backed SQLite so threads hold genuinely separate connections and contend for the same row), `tests/test_agent_authorization.py` (7), `tests/test_agent_injection.py` (9).


## [Feature] Operational Agent Runtime (model-directed multi-turn agent with human-in-the-loop write approval) - 2026-09-18

### Added

- `app/modules/agents/models.py`: `AgentRun`, `AgentMessage`, `AgentToolCall`, `AgentAction`, `AgentEvent`, via migration `0022_agent_runtime`. No hidden chain-of-thought is persisted — only tool calls, tool results, proposed/decided write actions, and lifecycle events.
- `app/modules/agents/tool_registry.py`: a single authoritative tool registry (15 read/research tools reusing `ResearchToolExecutor` and existing lead/outreach/CRM read paths; 8 write tools — `draft_outreach` auto-executes, the other 7 always pause for human approval) generating the OpenAI function-calling schema; no duplicate tool schemas exist elsewhere.
- `app/modules/agents/runtime.py`: `AgentRuntime`, the model-directed loop — each round persists the provider message history, asks the caller (native OpenAI tool-calling in production, a deterministic scripted stub in `agent_runtime=stub` for tests/demo) for the next step, and either executes a read/research tool immediately, creates a pending `AgentAction` and pauses the run for an approval-gated write, or completes with a server-validated structured final answer. Server-enforced bounds (`agent_max_steps=12`, `agent_max_tool_calls=16`, `agent_max_external_searches=6`, `agent_max_crawls=4`, `agent_max_write_proposals=5`, `agent_max_runtime_seconds=90`, `agent_max_tool_result_bytes=16384`, `agent_max_consecutive_tool_failures=3`) are checked before every tool call; duplicate tool calls with identical arguments are rejected; parallel tool execution stays disabled (only the first tool call per model turn is ever acted on).
- `app/modules/agents/action_gate.py`: `AgentActionGate`, the single place a pending `AgentAction` can become a real domain mutation — atomic claim via a conditional `UPDATE ... WHERE status='pending'`, payload-hash re-verification, workspace/lead re-verification at decision time, idempotent repeated approval, and expired/rejected actions cannot execute. Approval or rejection resumes the *same* `AgentRun` (`AgentRuntime.resume_after_action`), not a new run.
- `app/modules/agents/api.py`: 8 endpoints under `/api/v1/agent/...` — `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/events`, `POST /runs/{id}/cancel`, `GET /actions`, `GET /actions/{id}`, `POST /actions/{id}/approve`, `POST /actions/{id}/reject`.
- Documented domain-model gaps rather than inventing broken concepts: `Lead` has no `tags` column, so `update_lead_tags` writes into `Lead.enrichments["tags"]`; `CrmActivity.ActivityType` has no `TASK` value, so `create_lead_task` reuses `FOLLOW_UP` (documented in `tool_executor.py`).
- Known architectural limitation: `GET /runs/{id}/events` serves a replay of persisted events, not a live server push — this codebase has no pub/sub infrastructure for true streaming SSE.
- Tests: `tests/test_agent_runtime.py` and `tests/test_agent_actions_api.py` — full stub-runtime happy path (research → auto-drafted outreach → note proposal → pause → approve → resume → follow-up proposal → pause → approve → resume → completion), reject-causes-no-mutation, idempotent repeated approval, duplicate-tool-call detection, blocked-runtime fail-fast, and workspace-scoped authorization (a foreign workspace's user gets 404 on the run, the action, and an approve attempt).

## [Feature] Research History API and Business Intelligence Evidence - 2026-09-17

### Added

- `GET /api/v1/leads/{lead_id}/research-history`: authenticated, workspace-scoped, read-only history over durable research runs and their run-scoped change events, with newest-first `page`/`per_page` pagination. The response excludes provider payloads, provider settings, prompts, credentials, and model metadata and performs no research or LLM call.
- `app/modules/research/business_intelligence.py`: deterministic projections for `online_booking`, `branch_count`, `services`, `social_presence`, `contact_channels`, `has_ecommerce`, `has_whatsapp`, `review_sentiment`, `recurring_review_pain_points`, and `hiring_signal` from curated normalized provider facts and explicit crawl/search evidence.
- Evidence Graph `digital_maturity`: explicit 100-point formula based on official website (20), explicit mobile responsiveness (10), booking (15), ecommerce (15), WhatsApp (10), social profiles (up to 15), contact channels (up to 15), review volume (5), and structured services (5), capped at 100 and banded low below 40, medium from 40, and high from 70.
- Fact resolution now supports projected observations, case-insensitive merged service/contact collections, `supported`/`conflicting`/`unknown` status vocabulary, and full source records on contradicting values while retaining deterministic source-quality, freshness, and agreement scoring.
- Delta Intelligence classifications for capability, branch expansion, service/contact collection growth, hiring activity, and digital-maturity score movement; non-neutral significant changes continue through the existing deterministic rescore gate.
- Apify normalization retains only bounded, curated business evidence required by these projections; raw actor items remain confined to existing raw-payload persistence and are never returned by the history API.
- Focused tests cover tenant isolation, missing/empty history, pagination, newest-first ordering, run-scoped changes, no provider/LLM invocation, booking, branch disagreement, service deduplication, WhatsApp/contact channels, ecommerce, social presence, review sentiment/pain points, hiring, digital maturity, insufficient evidence, source quality/freshness, and new delta classifications.

## [Feature] Delta Intelligence (research-run diffing and change detection) - 2026-09-17

### Added

- `app/modules/research/models.py`: `ResearchRun` (one row per `research_lead` call), `ResearchFactSnapshot` (immutable per-claim-type canonical value captured at the end of a run), and `ResearchChangeEvent` (one row per meaningful, backend-decided change between two runs), via migration `0021_research_delta_intelligence`.
- `app/modules/research/delta.py`: `FactDiffEngine` — pure Python, deterministic diff of two `ResearchFactSnapshot` maps, dropping numeric noise below 2% of a claim's scale (rating/5.0, review_count/200) and classifying the rest into a fixed `event_type` vocabulary with a computed `significance` and `direction` (`improved`/`declined`/`neutral`); `ChangeExplainer` — runs strictly after `FactDiffEngine` has already decided a change occurred, and only ever produces the human-readable `explanation` string (via `OPENAI_API_KEY` when available, otherwise a deterministic templated sentence, exception-safe). **The LLM never decides whether a change occurred or how significant it is — only the backend does; the LLM only explains.**
- `app/modules/research/delta.py`: `DeltaIntelligenceService.process_completed_run`, wired into `LeadsService.research_lead` as the single shared call site for both `mode="planned"` and `mode="agentic"` research runs. Builds the current Evidence Graph, diffs it against the previous OK run, persists the new run/snapshot, and (for changes at/above `research_delta_min_significance`) persists `ResearchChangeEvent` rows and triggers `rescore_lead()` for non-neutral changes at/above `research_delta_rescore_significance`.
- `app/modules/scoring/rescore.py`: `rescore_lead()`, a job-independent extraction of `LeadDiscoveryOrchestrator._score_leads`'s scoring pipeline (evidence → signals → ICP match → facts → `ScoringEngine.evaluate` → persist) for exactly one already-known lead, usable outside a `SearchJob` context.
- New settings: `research_delta_min_significance` (0.15) and `research_delta_rescore_significance` (0.4), both deterministic backend thresholds.
- `docs/PROVIDERS.md`: Delta Intelligence section.
- Tests: `tests/test_delta_intelligence.py` (14 new tests) covering `FactDiffEngine` classification rules, `ChangeExplainer` template fallback and exception-safety, and `ResearchRepository` run/snapshot/event persistence round-trips.

## [Feature] Research Agent Loop, Tool Registry, and Evidence Graph - 2026-09-17

### Added

- `app/modules/research/tools.py`: `TOOL_DEFINITIONS`, a fixed registry of 10 research tools (`search_web_tavily`, `search_google_serpapi`, `crawl_company_site`, `crawl_reviews`, `get_existing_evidence`, `get_previous_research`, `get_lead_score_breakdown`, `get_icp_profile`, `resolve_company_domain`, `compare_evidence`) and `ResearchToolExecutor`. `crawl_company_site`/`crawl_reviews` take zero parameters — the crawl target is always resolved server-side from evidence already on file, so the LLM can never supply a URL or Apify Actor ID outside the existing allowlist layer.
- `app/modules/research/agent_loop.py`: `ResearchAgentLoop`, a bounded LLM tool-calling loop (`mode="agentic"`) as an alternative to `ResearchOrchestrator`'s fixed-step `mode="planned"` flow. Hard-bounded via new `research_agent_max_tool_calls` (8), `research_agent_max_external_searches` (5), `research_agent_max_crawls` (3), `research_agent_max_sources` (15), and `research_agent_max_runtime_seconds` (60) settings, enforced in the loop before each tool call. Reuses `OPENAI_API_KEY`; a `research_agent_runtime` property (`openai`/`stub`/`blocked`) mirrors the existing demo/live/stub/blocked runtime pattern.
- `app/modules/research/evidence_graph.py`: canonical Evidence Graph — `FactResolver` (per-claim canonical value plus explicit disagreeing values, not just a contradiction flag), `source_quality()` (a fixed weight table from official-site crawl 1.00 down to unrecognized source 0.35), and `EvidenceGraphBuilder`, which groups resolved facts and `LeadSignal` rows into Business Identity / Digital Presence / Reviews / Contactability / Pain / Opportunity / Growth groups and computes a deterministic `evidence_confidence` and `research_coverage` pair, distinct from the lead's Fit/Need/Urgency Opportunity Score.
- `GET /leads/{lead_id}/evidence-graph`: new, additive endpoint serving the Evidence Graph. Built from `ProviderNormalizedFact`'s existing flattened columns; the historical `facts_json` shape and the existing `/evidence` endpoint are unchanged.
- `POST /api/v1/leads/{lead_id}/research` now accepts `"mode": "planned"|"agentic"` (default `planned`) and returns `mode`/`tool_calls_made` in addition to the existing fields.
- `docs/PROVIDERS.md`: Research agent mode and Evidence Graph sections.
- Tests: `tests/test_evidence_graph.py`, `tests/test_research_tools.py`, `tests/test_research_agent_loop.py` (26 new tests), including a dedicated invariant test asserting no tool schema exposes a `url`/`actor` parameter other than `resolve_company_domain`'s pure-parsing `url`.

## [Feature] Multi-Source Research Pipeline (Tavily + SerpAPI + Apify) - 2026-09-17

### Added

- `app/modules/provider_apify`: new Apify provider adapter (client, live/demo services, normalizer) used as a deep-extraction/crawling layer, distinct from Tavily/SerpAPI search. Every call is enforced against a fixed Actor-key allowlist (`company_website_crawler`, `business_directory_crawler`, `social_public_profile_crawler`, `reviews_crawler`) resolved server-side to a real Actor ID — no caller, including an LLM tool call, can request an arbitrary Actor ID.
- `app/modules/research`: `ResearchPlanner` (depth-gated step planning for `quick`/`standard`/`deep`), `ResearchProviderRouter` (dispatches a step to the right provider's live/demo service), `ContradictionDetector` (flags disagreeing claims — phone/website_domain/category/address — across providers), and `ResearchOrchestrator` (ties them together, sequencing Tavily-discovers-site → Apify-crawls-site within one run).
- `provider_normalized_facts.freshness_score` and `.actor_run_id` columns, and a new `research_contradictions` table, via migration `0020_research_apify_evidence`.
- `POST /api/v1/leads/{lead_id}/research` now accepts an optional `{"depth": "quick"|"standard"|"deep"}` body and returns `providers_used` and `contradictions_detected` in addition to the existing fields.
- `docs/PROVIDERS.md`: Apify allowlist/env-var documentation and a research-depth explanation.

### Changed

- `LeadsService.research_lead` no longer calls Tavily directly; it delegates to `ResearchOrchestrator`, which decides per-request which of Tavily/SerpAPI/Apify to call based on `research_depth` and provider availability, instead of always calling every configured provider.
- Audit event for lead research renamed from `lead.tavily_research_requested` to `lead.research_requested` to reflect the multi-provider pipeline.

## [Live] Multi-Provider Validation Pass - 2026-07-07

### Added

- `docs/live-provider-validation.md`: operator walkthrough for running Tavily + SerpAPI + OpenAI together in one live discovery job, including engine alias table and guardrails.
- Provider Health entry in the mobile bottom navigation (admin/account_owner only) for parity with the desktop sidebar.

### Fixed

- Duplicate React keys on the search-job provider-status cards and Provider Health recent-failure rows when multiple fetches share a start timestamp (e.g. several `maps_place` enrichments in the same second).
- `test_settings_load_defaults` no longer depends on the developer's local `.env` contents (asserts pydantic defaults via `_env_file=None`).

### Validation

- Live end-to-end product run (`from-prompt` GCC ERP/CRM query): job completed with Tavily search+extract, SerpAPI maps/web + 5 place enrichments, and OpenAI web discovery all `ok`; 19 leads persisted with scores and mixed-provider evidence; outreach draft and CRM deal created against a live lead.
- Full gates: ruff check/format, mypy, pytest, `alembic upgrade head --sql`, eslint, tsc, vitest (28), `npm run build`, Playwright e2e, secret scan, `git diff --check`.

## [Feature] Multi-Provider Discovery and Frontend Coverage - 2026-07-07

### Added

- Wired `openai_web` into normal multi-provider discovery planning alongside `tavily_web`, `google_maps_search`, and `google_web`.
- Added operator-facing engine list aliases: `serpapi_maps`, `serpapi_web`, `openai`, and `openai_fallback`.
- Added provider status metadata to search job API responses and surfaced it on search job detail pages.
- Added a workspace Provider Health page with sidebar navigation, role guard, loading/error/empty states, and sanitized provider diagnostics.
- Added frontend coverage notes in `docs/frontend-coverage-and-demo.md`.

### Fixed

- Provider failures are isolated per discovery adapter so SerpAPI 429 is recorded as `rate_limited` without killing jobs when Tavily or OpenAI produce leads.
- OpenAI fallback evidence now uses the provider source label `openai_web`.
- Active scoring config regression coverage validates all active scoring weights sum to exactly `1.0`.

### Validation

- Initial frontend gates passed after each feature group: `npx tsc -b --pretty false` and `npm run build`.
- Focused backend discovery/scoring regression suite passed: 31 tests.

## [Fix] Scoring Weights and Fallback Discovery Completion - 2026-07-07

### Fixed

- Added migration `0019_repair_scoring_weight_totals.py` to repair persisted scoring configs whose weight totals are invalid, using the current canonical eight-dimension scoring weights.
- Added regression coverage for SerpAPI `rate_limited` discovery followed by OpenAI fallback, ensuring fallback leads still receive evidence and real scores and the search job finishes as `partially_completed`.
- Added tests for canonical scoring weight totals and valid custom scoring config preservation.

### Validation

- Passed: `ruff check app tests migrations`, `ruff format --check app tests migrations`, `mypy app`, `pytest -q` with MySQL default URL override, and `alembic upgrade head --sql` with MySQL dialect URL override.
- Local demo fallback search passed with SerpAPI `rate_limited`/429, OpenAI fallback `ok`/200, status `partially_completed`, one lead, one evidence row, and one score.

## [Hardening] Tavily Agentic Provider Polish - 2026-07-05

### Added

- Reworked Tavily integration around the official `tavily-python` SDK with Search, selective Extract, and opt-in Research support.
- Added local Tavily token-bucket rate limiting, `retry-after` handling for 429s, safe 401/403/timeout/5xx behavior, request fingerprinting, and workspace-scoped provider usage records.
- Added normalized Tavily discovery evidence with title, URL, snippet/content, provider, timestamp, confidence, and safe raw metadata; SerpAPI/stub paths remain intact.
- Added guarded live Tavily smoke coverage behind `TAVILY_LIVE_E2E=1` plus mock-backed provider/orchestrator/scoring/security regression tests.
- Added guarded Tavily SDK smoke execution to the separate live-provider workflow; default CI keeps Tavily disabled.
- Surfaced Tavily provider status in settings and refreshed provider/QA/deployment documentation.

### Validation

- Backend gates passed: `ruff check app tests migrations`, `ruff format --check app tests migrations`, `mypy app`, `pytest --basetemp ..\..\tmp\pytest-bt-full-0705b -q`, and `alembic upgrade head --sql`.
- Frontend gates passed: `npm run lint`, `npx tsc -b --pretty false`, `npm run test:unit`, `npm run build`, and `npm run test:e2e` (`126 passed`, `19 skipped`).
- Playwright documentation captures refreshed in `output/playwright/frontend-figures`.
- Tracked-file secret scan found no real Tavily/OpenAI/SerpAPI keys; only documented placeholders were present in examples and CI templates.

## [Hardening] Production Hardening Audit - 2026-07-05

### Fixed

- `apps/web/tests/e2e/saas-admin-demo-live.spec.ts`: added `test.skip(process.env.SAAS_ADMIN_DEMO_LIVE_E2E !== "1", ...)` guard so the spec is skipped in all default Playwright runs and CI. The spec was previously in the default `desktop-wide` project without any guard, which would cause CI failures whenever a real seeded backend is not running.

### Confirmed Passing (no changes needed)

- Backend: `ruff check` clean, `mypy` clean, `pytest -q` 191 passed / 2 skipped, `alembic upgrade head --sql` clean.
- Frontend: `eslint` clean, `tsc --noEmit` clean, `vitest run` 28 tests green, `vite build` clean.
- Playwright default run: 33 passed / 4 skipped (including the newly-gated `saas-admin-demo-live.spec.ts`).
- No real secrets found in any tracked file; CI uses placeholder keys only.
- All CORS, JWT, RBAC, workspace isolation, SSRF, and provider-key controls verified sound.

### Documentation

- `docs/architecture-review.md`: documented the E2E guard fix under Hardening Changes.
- `docs/visual-qa-report.md`: added Live E2E Environment Variables table describing `SAAS_ADMIN_DEMO_LIVE_E2E` and `PROSPECTIQ_LIVE_SEARCH_E2E` opt-in vars.
- `.gitignore`: added `*.docx`, `*.xlsx`, and `leads-*.png` patterns to exclude local document drafts and one-off screenshots.

## [Goal] Tavily Discovery Engine, Web-Search-Confidence Scoring, and Profession Persona - 2026-07-05

### Added
- New `provider_tavily` module (`client.py`, `engines/tavily_web.py`, `normalizers/tavily_web_normalizer.py`, `service.py`, `demo_service.py`) mirroring `provider_serpapi` conventions, gated by a `TAVILY_RUNTIME_MODE` runtime (live/demo/stub/blocked) that auto-resolves to `live` once `TAVILY_API_KEY` is configured.
- Tavily is wired as an opt-in `tavily_web` engine used during per-lead website/visibility validation (`LeadDiscoveryOrchestrator._validate_web_presence`), selectable via `DISCOVERY_ENGINE_LIST`. It is never production-required.
- New `WebSearchConfidenceStrategy` scoring strategy scoring Tavily-sourced evidence (answer presence, result relevance, result count); `ScoringWeights` rebalanced across all 8 strategies. Migration `0018_web_search_confidence_weight.py` backfills the new weight key for existing `scoring_config_versions` rows.
- Workspace profession/industry persona: a new `settings_json.profession` convention (no schema change — reuses the existing workspace settings API) that selects a profession-aware default service catalog in `ai_analysis` (real estate, recruiting, consulting, creative/freelance, B2B sales, digital marketing, or general), replacing the previously hardcoded SEO/marketing-only catalog. Exposed via a profession selector on the workspace settings page.

### Tests
- `apps/api/tests/test_tavily_provider.py`: client retry/backoff, param builder, normalizer, demo service persistence, runtime gating.
- `apps/api/tests/test_scoring_engine.py`: new strategy scoring, fact-builder Tavily evidence extraction, breakdown wiring.
- `apps/web/tests/e2e/settings-workspace-profile.spec.ts`: profession selector round-trip, scoring config form field presence.

### Validation
- Backend: `ruff check`, `mypy`, `pytest` (full suite), `alembic upgrade head --sql` all green.
- Frontend: `eslint`, `tsc --noEmit`, `vitest run` (28 tests), `vite build`, targeted Playwright spec all green.

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
