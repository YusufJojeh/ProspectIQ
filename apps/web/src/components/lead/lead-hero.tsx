import { ArrowLeft, MapPin, Phone, RefreshCw, Sparkles, UserPlus } from "lucide-react";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { AiPill, ConfidenceBadge } from "@/components/brand/badges";
import { ScoreRing } from "@/components/brand/score-ring";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { bandTone, formatScore, statusTone, titleCaseLabel } from "@/lib/presenters";
import type { LeadResponse } from "@/types/api";

export function LeadHero({
  lead,
  onRefresh,
  refreshing,
  onGenerateAnalysis,
  generatingAnalysis,
}: {
  lead: LeadResponse;
  onRefresh: () => void;
  refreshing?: boolean;
  onGenerateAnalysis: () => void;
  generatingAnalysis?: boolean;
}) {
  return (
    <section className="overflow-hidden rounded-[1.75rem] border border-border bg-card shadow-[0_30px_80px_-48px_rgba(15,23,42,0.25)]">
      <div className="flex flex-wrap items-center gap-2 border-b border-border/80 px-4 py-3 text-sm text-muted-foreground sm:px-5">
        <Link to={appPaths.leads} className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="size-3.5" />
          Leads
        </Link>
        <span>/</span>
        <span className="truncate text-foreground">{lead.company_name}</span>
        <span className="ml-auto font-mono text-[11px] uppercase tracking-[0.16em]">{lead.public_id.slice(0, 8)}</span>
      </div>

      <div className="grid gap-6 px-4 py-5 sm:px-5 sm:py-6 lg:grid-cols-[auto,1fr,auto] lg:items-start">
        <div className="flex items-center gap-4">
          <ScoreRing value={lead.latest_score ?? 0} size={96} stroke={8} />
          <div className="space-y-2">
            <Badge tone={bandTone(lead.latest_band)}>{lead.latest_band ? titleCaseLabel(lead.latest_band) : "Unscored"}</Badge>
            <ConfidenceBadge value={lead.data_confidence} />
            <AiPill>{lead.latest_qualified ? "Outreach ready" : "Evidence-first review"}</AiPill>
          </div>
        </div>

        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{lead.category ?? "Business"}</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl lg:text-4xl">{lead.company_name}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <MapPin className="size-3.5" />
              {lead.address ?? lead.city ?? "Location unavailable"}
            </span>
            {lead.phone ? (
              <span className="inline-flex items-center gap-1.5">
                <Phone className="size-3.5" />
                {lead.phone}
              </span>
            ) : null}
            {lead.website_url ? (
              <a href={lead.website_url} target="_blank" rel="noreferrer" className="hover:text-foreground">
                {lead.website_domain ?? lead.website_url}
              </a>
            ) : (
              <span>No website detected</span>
            )}
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <Badge tone={statusTone(lead.status)}>{titleCaseLabel(lead.status)}</Badge>
            <Badge tone={lead.latest_qualified ? "success" : "neutral"}>
              {lead.latest_qualified ? "Qualified" : "Needs review"}
            </Badge>
            <Badge tone="neutral">{formatScore(lead.latest_score)}</Badge>
            <Badge tone="neutral">{lead.review_count} reviews</Badge>
            {lead.rating ? <Badge tone="accent">{lead.rating.toFixed(1)} rating</Badge> : null}
          </div>
        </div>

        <div className="flex flex-wrap gap-2 lg:flex-col lg:items-end">
          <Button className="flex-1 sm:flex-none" onClick={onGenerateAnalysis} disabled={generatingAnalysis}>
            <Sparkles className="size-3.5" />
            {generatingAnalysis ? "Generating..." : "Generate analysis"}
          </Button>
          <Button
            variant="outline"
            className="flex-1 bg-transparent sm:flex-none"
            onClick={onRefresh}
            disabled={refreshing}
          >
            <RefreshCw className="size-3.5" />
            {refreshing ? "Refreshing..." : "Refresh lead"}
          </Button>
          <Button variant="outline" className="flex-1 bg-transparent sm:flex-none" asChild>
            <Link to={appPaths.outreach}>
              <UserPlus className="size-3.5" />
              Open outreach desk
            </Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
