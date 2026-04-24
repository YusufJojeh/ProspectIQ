import { Database, Globe, MapPin, Search, ShieldCheck, Star } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatDate, titleCaseLabel } from "@/lib/presenters";
import type { LeadEvidenceItem } from "@/types/api";

const evidenceMeta: Record<string, { icon: React.ComponentType<{ className?: string }>; tone: "accent" | "success" | "warning" | "neutral" }> = {
  listing: { icon: MapPin, tone: "accent" },
  review: { icon: Star, tone: "warning" },
  web: { icon: Globe, tone: "success" },
  website: { icon: Globe, tone: "success" },
  search: { icon: Search, tone: "accent" },
};

export function LeadEvidenceTimeline({
  items,
  summary,
}: {
  items: LeadEvidenceItem[];
  summary: Array<{ label: string; count: number }>;
}) {
  return (
    <section className="rounded-2xl border border-border bg-card/95">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-4">
        <div>
          <h2 className="text-sm font-semibold">Evidence timeline</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Every normalized fact on this lead remains traceable to a provider fetch.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {summary.slice(0, 4).map((item) => (
            <Badge key={item.label} tone="neutral">
              {item.label} {item.count}
            </Badge>
          ))}
        </div>
      </header>

      <div className="space-y-3 p-4">
        {items.map((item) => {
          const meta = evidenceMeta[item.source_type] ?? { icon: Database, tone: "neutral" as const };
          const Icon = meta.icon;
          return (
            <article key={`${item.provider_fetch_public_id}-${item.created_at}`} className="rounded-xl border border-border bg-muted/20 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="rounded-xl border border-border bg-background p-2">
                    <Icon className="size-4 text-[oklch(var(--signal))]" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium">{titleCaseLabel(item.source_type.replace(/_/g, " "))}</p>
                      <Badge tone={meta.tone}>{Math.round(item.confidence * 100)}% confidence</Badge>
                      <Badge tone="neutral">{Math.round(item.completeness * 100)}% completeness</Badge>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {item.company_name} · {item.address ?? item.city ?? "No address captured"}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      <span>{item.request_mode}</span>
                      <span>{item.provider_status}</span>
                      <span>{formatDate(item.created_at)}</span>
                    </div>
                  </div>
                </div>
                <ShieldCheck className="size-4 text-[oklch(var(--evidence))]" />
              </div>

              <pre className="mt-4 overflow-x-auto rounded-xl border border-border bg-background/80 p-3 text-xs leading-6 text-muted-foreground">
                {JSON.stringify(item.facts, null, 2)}
              </pre>
            </article>
          );
        })}
      </div>
    </section>
  );
}
