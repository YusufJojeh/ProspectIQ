# Database Maintenance

This project includes a dry-run maintenance audit for database integrity and table growth checks.

Run from `apps/api`:

```powershell
py -3.12 scripts/db_maintenance.py
```

What the command checks:

- duplicate logical `usage_counters` rows for `(workspace_id, metric_key, period_start, period_end)`
- leads with more than one current `lead_source_records` row
- `lead_source_records.current_for_lead_id` marker drift
- row counts for growth-prone tables such as `provider_raw_payloads`, `provider_normalized_facts`, `ai_analysis_snapshots`, `chat_messages`, `audit_logs`, and `outreach_messages`

Default behavior:

- dry-run only
- no rows are deleted
- no schema changes are applied

Optional safe repair mode:

```powershell
py -3.12 scripts/db_maintenance.py --apply-current-marker-repair
```

This repair mode only normalizes `lead_source_records.current_for_lead_id`:

- current rows get `current_for_lead_id = lead_id`
- non-current rows get `current_for_lead_id = NULL`

It does not:

- merge duplicate `usage_counters`
- delete rows
- rewrite business data

If duplicate logical counters or multiple-current source records are reported, stop and inspect the data before applying schema migrations that enforce those invariants.

For a non-default connection string:

```powershell
py -3.12 scripts/db_maintenance.py --database-url "mysql+pymysql://user:pass@127.0.0.1:3306/prospectiq"
```

JSON output is available for automation:

```powershell
py -3.12 scripts/db_maintenance.py --json
```
