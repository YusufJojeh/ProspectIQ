import { Badge } from "@/components/ui/badge";

export function LeadScoreBreakdownCard({
  totalScore,
  qualified,
  scoringVersionId,
  items,
}: {
  totalScore: number;
  qualified: boolean;
  scoringVersionId?: string | null;
  items: Array<{ key: string; label: string; contribution: number; reason: string; percent: number }>;
}) {
  return (
    <section className="rounded-2xl border border-border bg-card/95">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-4">
        <div>
          <h2 className="text-sm font-semibold">Score breakdown</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Deterministic model output from stored facts and scoring weights.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {scoringVersionId ? <Badge tone="neutral">{scoringVersionId}</Badge> : null}
          <Badge tone={qualified ? "success" : "warning"}>{qualified ? "Qualified" : "Below threshold"}</Badge>
          <Badge tone="accent">{totalScore}</Badge>
        </div>
      </header>

      <div className="space-y-3 p-4">
        {items.map((item) => (
          <div key={item.key} className="rounded-xl border border-border bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium">{item.label}</p>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{item.reason}</p>
              </div>
              <div className="text-right">
                <p className="font-mono text-base font-semibold tabular-nums">{item.contribution.toFixed(1)}</p>
                <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{item.percent}% impact</p>
              </div>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-background">
              <div className="h-full rounded-full bg-[oklch(var(--signal))]" style={{ width: `${item.percent}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
