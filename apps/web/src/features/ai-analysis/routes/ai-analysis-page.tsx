import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Sparkles,
  Zap,
  ShieldCheck,
  ArrowRight,
  Search,
  CheckCircle2,
  Clock,
  Target,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AiPill, AttentionPill, ConfidenceBadge, BandBadge, bandFromScore } from "@/components/brand/badges";
import { ScoreRing } from "@/components/brand/score-ring";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { listLeads } from "@/features/leads/api";
import { appPaths } from "@/app/paths";
import { cn } from "@/lib/utils";
import { useDocumentTitle } from "@/hooks/use-document-title";
import type { LeadResponse } from "@/types/api";

type Filter = "all" | "recommend" | "watch" | "attention";

function leadKind(lead: LeadResponse): Exclude<Filter, "all"> {
  const band = lead.latest_band;
  if (band === "high") return "recommend";
  if (band === "medium") return "watch";
  return "attention";
}

export function AiAnalysisPage() {
  useDocumentTitle("AI Analysis");
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const leadsQuery = useQuery({
    queryKey: ["leads", "ai-analysis"],
    queryFn: () => listLeads({ page_size: 100, sort: "score_desc" }),
  });

  const leads = useMemo(() => leadsQuery.data?.items ?? [], [leadsQuery.data]);

  const scored = useMemo(
    () =>
      leads
        .filter((l) => l.latest_score !== null)
        .map((l) => ({ lead: l, kind: leadKind(l) })),
    [leads],
  );

  const visible = scored.filter(({ lead, kind }) => {
    if (filter !== "all" && kind !== filter) return false;
    if (query && !lead.company_name.toLowerCase().includes(query.toLowerCase())) return false;
    return true;
  });

  const counts = {
    all: scored.length,
    recommend: scored.filter((s) => s.kind === "recommend").length,
    watch: scored.filter((s) => s.kind === "watch").length,
    attention: scored.filter((s) => s.kind === "attention").length,
  };

  const avgConfidence =
    leads.length > 0 ? leads.reduce((sum, l) => sum + l.data_confidence, 0) / leads.length : 0;

  if (leadsQuery.isPending) {
    return <QueryStateNotice tone="loading" title="Loading AI analysis" description="Fetching lead intelligence…" />;
  }

  if (leadsQuery.isError) {
    return (
      <QueryStateNotice tone="error" title="Could not load leads" description={leadsQuery.error.message} />
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="AI analysis"
        title="Evidence-grounded recommendations"
        description="Every recommendation cites the verified facts behind it. No hallucinated signals, no opaque scoring."
        actions={
          <Button size="sm">
            <Zap className="size-3.5" /> Run batch analysis
          </Button>
        }
      />

      <div className="grid gap-4 p-3 sm:p-4 lg:p-6">
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              k: "Leads analyzed",
              v: String(scored.length),
              sub: `${counts.recommend} recommended`,
              tone: "evidence",
              icon: Sparkles,
            },
            {
              k: "Avg. confidence",
              v: `${Math.round(avgConfidence * 100)}%`,
              sub: "across all leads",
              tone: "signal",
              icon: ShieldCheck,
            },
            {
              k: "Recommend outreach",
              v: String(counts.recommend),
              sub: "high-band qualified",
              tone: "signal",
              icon: Target,
            },
            {
              k: "Needs attention",
              v: String(counts.attention),
              sub: "low signal strength",
              tone: "caution",
              icon: AlertTriangle,
            },
          ].map((s) => (
            <div key={s.k} className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-center gap-2 text-[11.5px] uppercase tracking-wider text-muted-foreground">
                <s.icon className="size-3.5" style={{ color: `oklch(var(--${s.tone}))` }} />
                {s.k}
              </div>
              <div className="mt-2 font-mono text-[24px] font-semibold tabular-nums">{s.v}</div>
              <div className="mt-0.5 text-[11.5px] text-muted-foreground">{s.sub}</div>
            </div>
          ))}
        </section>

        <section className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card/50 p-2">
          {(
            [
              { id: "all", label: "All", count: counts.all },
              { id: "recommend", label: "Recommended", count: counts.recommend },
              { id: "watch", label: "Watch", count: counts.watch },
              { id: "attention", label: "Attention", count: counts.attention },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              onClick={() => setFilter(t.id)}
              className={cn(
                "flex h-8 items-center gap-1.5 rounded-md border px-3 text-[12px] transition",
                filter === t.id
                  ? "border-[oklch(var(--signal)/0.5)] bg-[oklch(var(--signal)/0.1)] text-foreground"
                  : "border-transparent text-muted-foreground hover:bg-muted/40 hover:text-foreground",
              )}
            >
              {t.label}
              <span className="font-mono text-[10.5px] tabular-nums text-muted-foreground">{t.count}</span>
            </button>
          ))}
          <div className="relative w-full md:ml-auto md:w-64">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search companies…"
              className="h-8 bg-background pl-8 text-[12.5px]"
            />
          </div>
        </section>

        <section className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {visible.map(({ lead, kind }) => {
            const score = lead.latest_score ?? 0;
            const band = bandFromScore(score);
            return (
              <article
                key={lead.public_id}
                className="group flex flex-col gap-3 rounded-xl border border-border bg-card p-4 transition hover:border-[oklch(var(--signal)/0.4)]"
              >
                <header className="flex items-start gap-3">
                  <ScoreRing value={score} size={56} stroke={5} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Link
                        to={appPaths.leadDetail(lead.public_id)}
                        className="truncate text-[14.5px] font-medium hover:text-[oklch(var(--signal))]"
                      >
                        {lead.company_name}
                      </Link>
                      <BandBadge band={band} />
                    </div>
                    <div className="mt-0.5 text-[12px] text-muted-foreground">
                      {lead.category ?? "Business"} · {lead.city ?? "—"}
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      {kind === "recommend" && <AiPill>Recommend outreach</AiPill>}
                      {kind === "watch" && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-[oklch(var(--caution)/0.35)] bg-[oklch(var(--caution)/0.08)] px-2 py-0.5 text-[11px] font-medium text-[oklch(var(--caution))]">
                          <Clock className="size-3" /> Watch — monitor signal
                        </span>
                      )}
                      {kind === "attention" && <AttentionPill>Needs review</AttentionPill>}
                      <ConfidenceBadge value={lead.data_confidence} />
                    </div>
                  </div>
                </header>

                <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                  <span className="font-medium text-foreground">{lead.company_name}</span>{" "}
                  {kind === "recommend" ? (
                    <>
                      shows strong operational maturity with {lead.review_count} reviews
                      {lead.rating ? ` at ${lead.rating} avg.` : "."} Confidence score of{" "}
                      <span className="text-foreground">{Math.round(lead.data_confidence * 100)}%</span>.
                    </>
                  ) : kind === "watch" ? (
                    <>
                      shows moderate signal. Data completeness at{" "}
                      <span className="text-foreground">{Math.round(lead.data_completeness * 100)}%</span>. Consider
                      an enrichment pass before outreach.
                    </>
                  ) : (
                    <>
                      has developing signal. Current evidence does not yet meet tier threshold — hold outreach until
                      next refresh.
                    </>
                  )}
                </p>

                <div className="grid grid-cols-3 gap-2 text-[11.5px]">
                  <div className="rounded-md border border-border bg-muted/20 p-2">
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Score</div>
                    <div className="mt-0.5 font-mono font-semibold tabular-nums">{score}</div>
                  </div>
                  <div className="rounded-md border border-border bg-muted/20 p-2">
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Reviews</div>
                    <div className="mt-0.5 font-mono font-semibold tabular-nums">{lead.review_count}</div>
                  </div>
                  <div className="rounded-md border border-border bg-muted/20 p-2">
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Confidence</div>
                    <div className="mt-0.5 font-mono font-semibold tabular-nums">
                      {Math.round(lead.data_confidence * 100)}%
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <CheckCircle2 className="size-3 text-[oklch(var(--evidence))]" />
                  {lead.category ?? "Business"} · {lead.city ?? "—"}{lead.has_website ? " · has website" : ""}
                </div>

                <div className="flex items-center gap-2 border-t border-border pt-3">
                  <Button size="sm" variant="outline" className="bg-transparent" asChild>
                    <Link to={appPaths.leadDetail(lead.public_id)}>
                      <TrendingUp className="size-3.5" /> Open lead
                    </Link>
                  </Button>
                </div>
              </article>
            );
          })}
        </section>

        {visible.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border bg-card/40 py-16 text-center">
            <Sparkles className="size-5 text-muted-foreground" />
            <div className="text-sm font-medium">No recommendations match your filters</div>
            <div className="text-xs text-muted-foreground">Try another segment or clear your search.</div>
          </div>
        )}

        {visible.length > 0 && (
          <div className="flex items-center justify-center gap-2 pt-2 text-[11.5px] text-muted-foreground">
            <span>
              Showing {visible.length} of {scored.length}
            </span>
            <ArrowRight className="size-3" />
          </div>
        )}
      </div>
    </div>
  );
}
