# LeadScope AI Relational Schema

## Overview

The schema keeps three boundaries explicit:

1. Core lead truth lives in `leads` and related workflow tables.
2. Provider acquisition evidence stays split between raw payload capture and normalized facts.
3. AI outputs stay outside lead truth in snapshot, recommendation, and outreach tables.

## ERD-Style Summary

- `workspaces` owns tenant data such as `users`, `search_requests`, `search_jobs`, `leads`, `provider_fetches`, `provider_normalized_facts`, `scoring_config_versions`, `prompt_templates`, and `audit_logs`
- `roles` catalogs supported authorization roles and is referenced by `users.role`
- `search_requests` stores the immutable user-submitted lead search criteria, including radius, rating/review bounds, website preference, and keyword filters
- `search_jobs` stores operational execution status for a request run
- `leads` stores the current normalized lead profile used by the product
- `provider_fetches` stores outbound SerpAPI call metadata
- `provider_raw_payloads` stores raw provider response payloads
- `provider_normalized_facts` stores normalized evidence rows derived from provider payloads
- `lead_source_records` records which normalized fact currently has precedence for the lead
- `lead_scores` stores reproducible scores for a lead under a specific scoring config version
- `score_breakdowns` stores component-level reasons for each `lead_score`
- `scoring_config_versions` versions the scoring policy
- `workspace_scoring_active` selects the active scoring version per workspace
- `prompt_templates` versions analysis prompts
- `ai_analysis_snapshots` stores assistive AI output snapshots keyed by prompt/input hash
- `service_recommendations` stores structured recommended services derived from an analysis snapshot
- `outreach_messages` stores outreach drafts derived from an analysis snapshot
- `lead_status_history` stores lead stage changes over time
- `lead_notes` stores operator notes per lead
- `audit_logs` stores workspace-level action history
- `system_settings` stores global admin key/value settings

## Design Notes

- `lead_notes` is intentionally lead-specific instead of introducing a generic polymorphic `notes` table.
- `search_jobs` keeps a denormalized copy of request criteria even after adding `search_requests`.
  This preserves current operational queries while still introducing a canonical request entity.
- `users.role` remains a string in application code but now references the `roles.key` catalog through a foreign key.
  Supported keys are `admin`, `agency_manager`, and `sales_user`.
- `service_recommendations` is separated from both `ai_analysis_snapshots.output_json` and `outreach_messages`.
  That keeps recommendations queryable without relying on JSON blobs as the storage interface.

## Indexing Highlights

- Workspace and time filters:
  - `search_requests(workspace_id, created_at)`
  - `search_jobs(workspace_id, status, queued_at)`
  - `leads(workspace_id, status, updated_at)`
  - `audit_logs(workspace_id, created_at)`
- Lead workflow filters:
  - `leads(workspace_id, city)`
  - `lead_status_history(lead_id, changed_at)`
  - `lead_notes(lead_id, created_at)`
- Evidence and scoring retrieval:
  - `provider_fetches(workspace_id, engine, mode)`
  - `provider_normalized_facts(lead_id, source_type, created_at)`
  - `lead_scores(lead_id, scored_at)`
  - `score_breakdowns(lead_score_id, key)`
- AI and operator output retrieval:
  - `ai_analysis_snapshots(lead_id, created_at)`
  - `service_recommendations(lead_id, created_at)`
  - `outreach_messages(lead_id, created_at)`

## Intentionally Deferred

- CRM sync tables and export-job tracking
- Delivery/send-state tables beyond saved outreach drafts
- A full permissions matrix beyond the current role catalog
- A management UI over `system_settings`
