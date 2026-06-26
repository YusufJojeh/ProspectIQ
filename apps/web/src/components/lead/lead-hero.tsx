import {
  ArrowLeft,
  Globe,
  MapPin,
  Phone,
  RefreshCw,
  Sparkles,
  Star,
  UserPlus,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { AiPill, ConfidenceBadge } from "@/components/brand/badges";
import { LeadScoreSpinner } from "@/components/brand/lead-score-spinner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { leadStatusLabel, scoreBandLabel } from "@/lib/i18n-labels";
import { bandTone, formatScore, statusTone } from "@/lib/presenters";
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
  const { t } = useTranslation();
  const score = lead.latest_score ?? 0;
  const websiteLabel = lead.website_domain ?? lead.website_url;

  return (
    <section className="overflow-hidden rounded-[1.5rem] border border-border bg-card shadow-[0_24px_70px_-48px_rgba(15,23,42,0.28)]">
      <div className="flex flex-wrap items-center gap-2 border-b border-border/70 bg-muted/15 px-4 py-2.5 text-sm text-muted-foreground sm:px-5">
        <Link
          to={appPaths.leads}
          className="inline-flex items-center gap-1 hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" />
          {t("leads.title")}
        </Link>
        <span>/</span>
        <span className="truncate text-foreground">{lead.company_name}</span>
        <span className="ms-auto font-mono text-[11px] uppercase tracking-[0.16em]">
          {lead.public_id.slice(0, 8)}
        </span>
      </div>

      <div className="grid gap-4 bg-gradient-to-br from-card via-card to-[oklch(var(--signal)/0.05)] px-4 py-4 sm:px-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-stretch">
        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={statusTone(lead.status)}>
                  {leadStatusLabel(t, lead.status)}
                </Badge>
                <Badge tone={lead.latest_qualified ? "success" : "warning"}>
                  {lead.latest_qualified
                    ? t("leads.qualified")
                    : t("leads.needsReview")}
                </Badge>
                <AiPill>
                  {lead.latest_qualified
                    ? t("leads.outreachReady")
                    : t("leads.evidenceFirstReview")}
                </AiPill>
              </div>

              <p className="mt-3 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                {lead.category ?? t("leads.business")}
              </p>
              <h1 className="mt-1 max-w-5xl text-2xl font-semibold tracking-tight sm:text-3xl">
                {lead.company_name}
              </h1>
            </div>
          </div>

          <div className="grid gap-2 text-sm text-muted-foreground md:grid-cols-3">
            <HeroFact icon={MapPin} value={lead.address ?? lead.city ?? t("leads.locationUnavailable")} />
            {lead.phone ? <HeroFact icon={Phone} value={lead.phone} /> : null}
            {lead.website_url ? (
              <a
                href={lead.website_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-w-0 items-center gap-2 rounded-xl border border-border bg-background/65 px-3 py-2 hover:border-[oklch(var(--signal)/0.35)] hover:text-foreground"
              >
                <Globe className="size-4 shrink-0 text-[oklch(var(--signal))]" />
                <span className="truncate">{websiteLabel}</span>
              </a>
            ) : (
              <HeroFact icon={Globe} value={t("leads.noWebsite")} />
            )}
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            <MetricPill
              label={t("leadDetail.leadScore")}
              value={formatScore(score)}
              toneClass="border-[oklch(var(--signal)/0.28)] bg-[oklch(var(--signal)/0.08)] text-[oklch(var(--signal))]"
            />
            <MetricPill
              label={t("leads.reviews")}
              value={String(lead.review_count)}
              toneClass="border-[oklch(var(--evidence)/0.28)] bg-[oklch(var(--evidence)/0.08)] text-[oklch(var(--evidence))]"
            />
            <MetricPill
              label={t("leads.rating")}
              value={lead.rating ? lead.rating.toFixed(1) : t("common.notAvailable")}
              icon={Star}
              toneClass="border-[oklch(var(--warning)/0.3)] bg-[oklch(var(--warning)/0.08)] text-[oklch(var(--warning))]"
            />
          </div>
        </div>

        <div className="flex flex-col gap-3 rounded-2xl border border-border bg-background/70 p-3 lg:w-[230px]">
          <div className="flex items-center justify-between gap-3">
            <LeadScoreSpinner
              value={score}
              size={72}
              stroke={7}
              label={t("leadScoreSpinner.companyScore", {
                company: lead.company_name,
                score: Math.round(score),
              })}
            />
            <div className="min-w-0 space-y-1 text-end">
              <p className="text-2xl font-semibold tabular-nums">
                {formatScore(score)}
              </p>
              <Badge tone={bandTone(lead.latest_band)}>
                {scoreBandLabel(t, lead.latest_band)}
              </Badge>
            </div>
          </div>
          <ConfidenceBadge value={lead.data_confidence} className="justify-center" />

          <div className="grid gap-2">
            <Button
              size="sm"
              onClick={onGenerateAnalysis}
              disabled={generatingAnalysis}
            >
              <Sparkles className="size-3.5" />
              {generatingAnalysis
                ? t("leads.generating")
                : t("leads.generateAnalysis")}
            </Button>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
              <Button
                size="sm"
                variant="outline"
                className="min-w-0 justify-center bg-transparent px-2 text-xs"
                onClick={onRefresh}
                disabled={refreshing}
              >
                <RefreshCw className="size-3.5 shrink-0" />
                <span className="truncate">
                  {refreshing ? t("leads.refreshing") : t("leads.refreshLead")}
                </span>
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="min-w-0 justify-center bg-transparent px-2 text-xs"
                asChild
              >
                <Link to={appPaths.outreach}>
                  <UserPlus className="size-3.5 shrink-0" />
                  <span className="truncate">{t("leads.openOutreachDesk")}</span>
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function HeroFact({
  icon: Icon,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  value: string;
}) {
  return (
    <span className="inline-flex min-w-0 items-center gap-2 rounded-xl border border-border bg-background/65 px-3 py-2">
      <Icon className="size-4 shrink-0 text-[oklch(var(--signal))]" />
      <span className="truncate">{value}</span>
    </span>
  );
}

function MetricPill({
  label,
  value,
  toneClass,
  icon: Icon,
}: {
  label: string;
  value: string;
  toneClass: string;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className={`rounded-xl border px-3 py-2 ${toneClass}`}>
      <p className="text-[10px] font-medium uppercase tracking-[0.16em] opacity-80">
        {label}
      </p>
      <p className="mt-1 inline-flex items-center gap-1.5 text-lg font-semibold text-foreground">
        {Icon ? <Icon className="size-4 text-current" /> : null}
        {value}
      </p>
    </div>
  );
}
