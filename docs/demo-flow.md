# Demo Flow

## Demo Accounts

- Super Admin equivalent: `admin@example.test` / `password`
- Manager: `manager@example.test` / `password`
- Team User: `user1@example.test` / `password`
- Workspace slug: `ws_default`

The current auth model is email-based and workspace-scoped. The seeded “Super Admin” demo account is the workspace `account_owner` role because the product does not currently define a separate global `super_admin` role.

## Preferred Local-Live Runtime

- Local-live project mode:
  Set `SERPAPI_RUNTIME_MODE=live`, `AI_PROVIDER=ollama`, and keep `OPENAI_API_KEY` configured as the fallback.
- Result:
  New search jobs use real SerpAPI calls, while AI features prefer Ollama and fall back to OpenAI only when Ollama is unavailable.

## Explicit Demo Runtime (No External Calls)

- Set `SERPAPI_RUNTIME_MODE=demo`
- Set `AI_PROVIDER=stub`
- Keep `DISCOVERY_MODE` explicit (recommended: `multi_engine_multi_query`) so discovery behavior remains deterministic and inspectable.

## Demo Reset Commands

From a normal local setup:

```powershell
cd apps/api
py -3.12 scripts/seed.py --migrate --demo-data
```

If you want a full infrastructure reset as well:

```powershell
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d
cd apps/api
py -3.12 scripts/seed.py --migrate --demo-data
```

## Presentation Flow

1. Login
   Use `ws_default` with the admin account.

2. Show the dashboard
   Point out that recent jobs, lead counts, and pipeline state are already populated.

3. Create a search
   Open Search Jobs, create a scoped search, and explain:
   - `SERPAPI_RUNTIME_MODE=live` keeps the project behavior aligned with real provider-backed discovery
   - if Ollama is unavailable, the AI layer falls back to OpenAI instead of switching discovery into demo mode

4. Inspect results
   Open the existing completed and partially completed jobs to show both healthy runs and operational failure visibility.

5. Open the lead workspace
   Use `Marmara Smile Clinic` first because it has strong evidence, a map marker, a score, recommendations, and an edited outreach draft.

6. Show the map
   Highlight that seeded leads include valid coordinates so markers and popups are immediately visible.

7. Open lead detail
   Walk through:
   - normalized lead facts
   - score band and qualification state
   - evidence timeline
   - notes and status history

8. Show score breakdown
   Use `Marmara Smile Clinic` or `Ankara Motion Physio` to explain how the total score is composed from local trust, website presence, visibility, opportunity, and confidence.

9. Show recommendation and analysis
   Use the seeded AI analysis snapshot and service recommendations already attached to qualified leads.

10. Show outreach
   Display the seeded outreach draft and the manually edited version to demonstrate the "generate then refine" workflow.

11. Show admin configuration
   Open Settings/Admin and present:
   - provider settings
   - active scoring config plus an alternate version
   - prompt templates
   - operational health, including a seeded partial-failure example

12. Show export
   Export the current leads CSV to demonstrate that scores, recommendations, outreach, ownership, and status can leave the system in a presentation-friendly format.

## Suggested Lead Order

- `Marmara Smile Clinic`: best all-in-one showcase lead
- `Ankara Motion Physio`: strong lead already moved deeper in the pipeline
- `Moda Implant Studio`: medium-band lead with upside
- `Acibadem Oral Care`: missing-website opportunity example
