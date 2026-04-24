import { AlertTriangle, CheckCircle2, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { formatDate } from "@/lib/presenters";
import type { LeadAnalysisSnapshotResponse } from "@/types/api";

export function LeadAiAnalysisPanel({
  snapshot,
  onGenerate,
  generating,
  error,
}: {
  snapshot: LeadAnalysisSnapshotResponse | null;
  onGenerate: () => void;
  generating?: boolean;
  error?: string | null;
}) {
  return (
    <section className="rounded-2xl border border-border bg-card/95">
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-4">
        <div>
          <h2 className="text-sm font-semibold">AI analysis</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Assistive recommendations grounded in stored lead evidence.
          </p>
        </div>
        <Button data-testid="lead-analysis-generate" onClick={onGenerate} disabled={generating}>
          <Sparkles className="size-3.5" />
          {generating ? "Generating..." : snapshot ? "Regenerate" : "Generate"}
        </Button>
      </header>

      <div className="space-y-4 p-4">
        {error ? <QueryStateNotice tone="error" title="Analysis unavailable" description={error} /> : null}
        {snapshot ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="accent">{snapshot.ai_provider}</Badge>
              <Badge tone="neutral">{snapshot.model_name}</Badge>
              <Badge tone="success">{Math.round(snapshot.analysis.confidence * 100)}% confidence</Badge>
              <Badge tone="neutral">{formatDate(snapshot.created_at)}</Badge>
            </div>

            <div className="rounded-xl border border-border bg-muted/20 p-4">
              <p className="text-sm leading-7 text-muted-foreground">{snapshot.analysis.summary}</p>
            </div>

            <InfoList
              title="Why the model recommends this lead"
              icon={<CheckCircle2 className="size-4 text-[oklch(var(--evidence))]" />}
              items={snapshot.analysis.opportunities}
            />
            <InfoList
              title="Risks and missing signals"
              icon={<AlertTriangle className="size-4 text-[oklch(var(--caution))]" />}
              items={snapshot.analysis.weaknesses}
            />

            {snapshot.service_recommendations.length ? (
              <div className="rounded-xl border border-border bg-muted/20 p-4">
                <p className="text-sm font-medium">Recommended services</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {snapshot.service_recommendations.map((item) => (
                    <Badge key={item.public_id} tone="accent">
                      {item.service_name}
                    </Badge>
                  ))}
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <QueryStateNotice
            tone="info"
            title="No analysis snapshot yet"
            description="Generate an evidence-grounded summary to populate this workspace."
          />
        )}
      </div>
    </section>
  );
}

function InfoList({
  title,
  items,
  icon,
}: {
  title: string;
  items: string[];
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 p-4">
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-sm font-medium">{title}</p>
      </div>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-muted-foreground">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
