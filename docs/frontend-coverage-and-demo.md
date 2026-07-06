# Frontend Coverage and Demo Notes

Date: 2026-07-07

## Coverage Matrix

| Backend feature | API route | Frontend surface | Sidebar | Role | Action |
| --- | --- | --- | --- | --- | --- |
| Auth | `/api/v1/auth/*` | Login/signup/public routes | No | Public | Covered |
| Users/team | `/api/v1/users/*` | Team | Yes | account owner/admin/member read-only | Covered |
| Workspaces/settings | `/api/v1/workspaces/*` | Settings, Workspace Admin | Yes | account owner/admin | Covered |
| Search jobs | `/api/v1/search-jobs/*` | Lead Discovery, Search Jobs, job detail | Yes | authenticated | Covered |
| Provider statuses | `/api/v1/search-jobs/*`, `/api/v1/admin/operations/health` | Search job detail, Provider Health | Yes | account owner/admin | Added |
| Leads/prospects | `/api/v1/leads/*` | Leads / Prospects, lead detail | Yes | authenticated | Covered |
| Evidence/sources | lead evidence APIs | Lead detail evidence panels | Via Leads | authenticated | Covered in lead detail |
| Scoring | scoring config and lead score APIs | Lead detail scoring, Workspace Admin scoring | Yes | authenticated/admin config | Covered |
| ICP profiles | ICP APIs/settings | Settings ICP tab, lead detail ICP match | Yes via Settings/Leads | account owner/admin | Covered |
| Campaigns | `/api/v1/campaigns/*` | Campaigns and campaign detail | Yes | authenticated | Covered |
| Outreach generation/send stub | `/api/v1/outreach/*` | Outreach and lead detail drafts | Yes | authenticated | Covered |
| CRM pipelines/deals | `/api/v1/crm/*` | CRM, deal detail | Yes | authenticated | Covered |
| Workspace admin | workspace admin APIs | Workspace Admin | Yes | account owner/admin | Covered |
| Platform admin | `/api/v1/admin/*` | Platform Admin | Yes | platform_admin only | Covered |
| Billing/usage/limits | billing/usage APIs | Billing, Invoices, Usage / Limits | Yes | account owner/admin/member read-only | Covered |
| Audit logs | audit APIs | Audit Logs | Yes | account owner/admin | Covered |
| Exports | export APIs | Exports | Yes | account owner/admin | Covered |

## Provider Behavior

- Demo engine list supports `tavily_web,serpapi_maps,serpapi_web,openai_web`.
- Aliases normalize to `tavily_web,google_maps_search,google_web,openai_web`.
- Search job detail shows stored provider status metadata only: provider, engine, mode, status, HTTP status, attempt, and timestamps.
- Provider Health shows Tavily, SerpAPI, and OpenAI readiness without API keys or raw payloads.
- Suspicious provider diagnostics are redacted in the UI before display.

## Demo Query

Use:

```text
Find GCC-based ERP or CRM software companies in Saudi Arabia, UAE, Qatar, or Kuwait that serve real estate, sales, or business operations teams and show evidence of lead management, sales automation, CRM implementation, or business automation needs.
```

Expected result: Tavily participates in the normal search job, SerpAPI 429 is recorded as `rate_limited`, OpenAI web discovery may add candidates, leads are scored, evidence is persisted, and final status is `completed` or `partially_completed`.
