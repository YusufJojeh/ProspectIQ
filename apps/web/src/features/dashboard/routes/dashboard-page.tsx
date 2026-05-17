import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Globe2, MapPinned, Radar, Rows3, ShieldCheck, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { JobThroughputChart, ScoreDistributionChart } from "@/components/dashboard/charts";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { listLeads } from "@/features/leads/api";
import { buildCityCoverage, buildJobThroughputSeries, buildScoreDistribution } from "@/features/internal/design-adapters";
import { useInvalidateLeadsWhileDiscoveryActive } from "@/hooks/use-invalidate-leads-while-discovery-active";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { useSearchJobsQuery } from "@/hooks/use-search-jobs-query";
import { hasCoordinates } from "@/lib/maps";
import { bandTone, formatDate, formatScore, searchJobTone, titleCaseLabel } from "@/lib/presenters";

export function DashboardPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("dashboard.title"));

  const jobsQuery = useSearchJobsQuery();
  const jobs = useMemo(() => jobsQuery.data?.items ?? [], [jobsQuery.data?.items]);
  const hasActiveDiscovery = useMemo(
    () => jobs.some((job) => job.status === "queued" || job.status === "running"),
    [jobs],
  );

  useInvalidateLeadsWhileDiscoveryActive(jobs);

  const leadsQuery = useQuery({
    queryKey: ["leads", "overview"],
    queryFn: () => listLeads({ page_size: 100, sort: "score_desc" }),
    refetchInterval: hasActiveDiscovery ? 5_000 : false,
  });

  const leads = useMemo(() => leadsQuery.data?.items ?? [], [leadsQuery.data?.items]);
  const highBand = leads.filter((lead) => lead.latest_band === "high").length;
  const qualified = leads.filter((lead) => lead.latest_qualified).length;
  const withWebsite = leads.filter((lead) => lead.has_website).length;
  const mappable = leads.filter(hasCoordinates).length;
  const activeJobs = jobs.filter((job) => job.status === "queued" || job.status === "running");
  const cityCoverage = buildCityCoverage(leads);
  const throughputData = buildJobThroughputSeries(jobs);
  const scoreDistribution = buildScoreDistribution(leads);
  const topLeads = leads.slice(0, 6);

  if (leadsQuery.isError || jobsQuery.isError) {
    return (
      <EmptyState
        title={t("dashboard.loadErrorTitle")}
        description={t("dashboard.loadErrorDescription")}
      />
    );
  }

  if (leadsQuery.isPending || jobsQuery.isPending) {
    return (
      <QueryStateNotice
        tone="loading"
        title={t("dashboard.loadingTitle")}
        description={t("dashboard.loadingDescription")}
      />
    );
  }

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow={t("dashboard.title")}
        title={t("dashboard.heroTitle")}
        description={t("dashboard.heroDescription")}
        actions={
          <>
            <Button variant="outline" className="bg-transparent" asChild>
              <Link to={appPaths.leads}>{t("dashboard.reviewLeads")}</Link>
            </Button>
            <Button asChild>
              <Link to={appPaths.searches}>
                {t("dashboard.launchSearch")}
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </>
        }
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <KpiCard
          label={t("dashboard.totalLeads")}
          value={String(leads.length)}
          helper={t("dashboard.totalLeadsHelper")}
          delta={t("dashboard.qualifiedCount", { count: qualified })}
          icon={Rows3}
        />
        <KpiCard
          label={t("dashboard.highBand")}
          value={String(highBand)}
          helper={t("dashboard.highBandHelper")}
          tone="evidence"
          delta={`${Math.round((highBand / Math.max(leads.length, 1)) * 100)}% mix`}
          icon={ShieldCheck}
        />
        <KpiCard
          label={t("dashboard.qualified")}
          value={String(qualified)}
          helper={t("dashboard.qualifiedHelper")}
          tone="signal"
          delta={`${withWebsite} with websites`}
          icon={Radar}
        />
        <KpiCard
          label={t("dashboard.websiteCoverage")}
          value={String(withWebsite)}
          helper={t("dashboard.websiteCoverageHelper")}
          tone="caution"
          delta={`${mappable} mappable`}
          icon={Globe2}
        />
        <KpiCard
          label={t("dashboard.activeJobs")}
          value={String(activeJobs.length)}
          helper={t("dashboard.activeJobsHelper")}
          tone={activeJobs.length ? "signal" : "risk"}
          delta={activeJobs.length ? t("dashboard.autoRefreshEnabled") : t("dashboard.idle")}
          icon={MapPinned}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("dashboard.discoveryThroughput")}</CardTitle>
            <CardDescription>{t("dashboard.discoveryThroughputDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            <JobThroughputChart data={throughputData} />
          </CardContent>
        </Card>

        <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("dashboard.leadScoreDistribution")}</CardTitle>
            <CardDescription>{t("dashboard.leadScoreDistributionDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            <ScoreDistributionChart data={scoreDistribution} />
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("dashboard.priorityLeadQueue")}</CardTitle>
            <CardDescription>{t("dashboard.priorityLeadQueueDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {topLeads.length === 0 ? (
              <EmptyState
                title="No leads yet"
                description={t("dashboard.noLeadsDescription")}
              />
            ) : (
              topLeads.map((lead) => (
                <Link
                  key={lead.public_id}
                  to={appPaths.leadDetail(lead.public_id)}
                  className="rounded-2xl border border-border bg-muted/20 p-4 transition hover:border-[oklch(var(--signal)/0.35)]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold">{lead.company_name}</p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {lead.category ?? t("dashboard.business")} · {lead.city ?? t("dashboard.unknownCity")}
                      </p>
                    </div>
                    <Badge tone={bandTone(lead.latest_band)}>
                      {lead.latest_band ? titleCaseLabel(lead.latest_band) : t("dashboard.unscored")}
                    </Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge tone="neutral">{formatScore(lead.latest_score)}</Badge>
                    <Badge tone={lead.latest_qualified ? "success" : "warning"}>
                      {lead.latest_qualified ? t("dashboard.qualified") : t("dashboard.needsReview")}
                    </Badge>
                    {lead.website_domain ? <Badge tone="accent">{lead.website_domain}</Badge> : null}
                  </div>
                </Link>
              ))
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>{t("dashboard.regionOperations")}</CardTitle>
              <CardDescription>{t("dashboard.regionOperationsDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {cityCoverage.length === 0 ? (
                <EmptyState
                  title="No city coverage yet"
                  description={t("dashboard.noCityCoverageDescription")}
                />
              ) : (
                cityCoverage.map((item) => (
                  <div
                    key={item.city}
                    className="flex items-center justify-between rounded-2xl border border-border bg-muted/20 px-4 py-3"
                  >
                    <div>
                      <p className="font-medium">{item.city}</p>
                      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                        {t("dashboard.storedLeads")}
                      </p>
                    </div>
                    <Badge tone="accent">{item.count}</Badge>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>{t("dashboard.aiAuditActivity")}</CardTitle>
              <CardDescription>{t("dashboard.aiAuditActivityDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-2xl border border-border bg-muted/20 p-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Sparkles className="size-4 text-[oklch(var(--signal))]" />
                  {t("dashboard.aiWorkspaceReadiness")}
                </div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {highBand > 0
                    ? t("dashboard.highBandReady", { count: highBand })
                    : t("dashboard.noHighBandReady")}
                </p>
                <Button className="mt-3" variant="outline" asChild>
                  <Link to={appPaths.aiAnalysis}>{t("dashboard.openAiAnalysis")}</Link>
                </Button>
              </div>

              {activeJobs.length === 0 ? (
                <QueryStateNotice
                  tone="info"
                  title={t("dashboard.noActiveDiscoveryRuns")}
                  description={t("dashboard.noActiveDiscoveryRunsDescription")}
                />
              ) : (
                activeJobs.slice(0, 3).map((job) => (
                  <div key={job.public_id} className="rounded-2xl border border-border bg-muted/20 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">
                          {job.business_type} · {job.city}
                        </p>
                        <p className="mt-1 text-sm text-muted-foreground">{formatDate(job.queued_at)}</p>
                      </div>
                      <Badge tone={searchJobTone(job.status)}>{titleCaseLabel(job.status)}</Badge>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
