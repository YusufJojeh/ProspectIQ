import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Globe2, MapPinned, Radar, Rows3, ShieldCheck, Sparkles } from "lucide-react";
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
  useDocumentTitle("Overview");

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
        title="Workspace data could not load"
        description="Make sure the API is running, the database is migrated, and the current session token is valid."
      />
    );
  }

  if (leadsQuery.isPending || jobsQuery.isPending) {
    return (
      <QueryStateNotice
        tone="loading"
        title="Loading workspace snapshot"
        description="Fetching live lead coverage, score bands, and job throughput from the API."
      />
    );
  }

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow="Dashboard"
        title="Operational lead intelligence desk"
        description="The imported dashboard composition is now driving the live workspace with real discovery throughput, score distribution, and evidence-backed lead readiness."
        actions={
          <>
            <Button variant="outline" className="bg-transparent" asChild>
              <Link to={appPaths.leads}>Review leads</Link>
            </Button>
            <Button asChild>
              <Link to={appPaths.searches}>
                Launch search
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </>
        }
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <KpiCard
          label="Total leads"
          value={String(leads.length)}
          helper="Persisted workspace records available for review."
          delta={`${qualified} qualified`}
          icon={Rows3}
        />
        <KpiCard
          label="High band"
          value={String(highBand)}
          helper="Highest-scoring leads across the current workspace."
          tone="evidence"
          delta={`${Math.round((highBand / Math.max(leads.length, 1)) * 100)}% mix`}
          icon={ShieldCheck}
        />
        <KpiCard
          label="Qualified"
          value={String(qualified)}
          helper="Leads already meeting current qualification criteria."
          tone="signal"
          delta={`${withWebsite} with websites`}
          icon={Radar}
        />
        <KpiCard
          label="Website coverage"
          value={String(withWebsite)}
          helper="Stored domain evidence ready for outbound preparation."
          tone="caution"
          delta={`${mappable} mappable`}
          icon={Globe2}
        />
        <KpiCard
          label="Active jobs"
          value={String(activeJobs.length)}
          helper="Queued or running discovery jobs refreshing live data."
          tone={activeJobs.length ? "signal" : "risk"}
          delta={activeJobs.length ? "Auto-refresh enabled" : "Idle"}
          icon={MapPinned}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>Discovery throughput</CardTitle>
            <CardDescription>
              Search jobs are aggregated into the imported area-chart treatment using the persisted FastAPI job records.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <JobThroughputChart data={throughputData} />
          </CardContent>
        </Card>

        <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>Lead score distribution</CardTitle>
            <CardDescription>
              Score bands are derived from live lead scores instead of the archive&apos;s mock distribution.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScoreDistributionChart data={scoreDistribution} />
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>Priority lead queue</CardTitle>
            <CardDescription>
              The highest-scoring leads now use the imported card language while staying attached to the current lead detail routes.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {topLeads.length === 0 ? (
              <EmptyState
                title="No leads yet"
                description="Launch a search job to populate the workspace and unlock the internal product views."
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
                        {lead.category ?? "Business"} · {lead.city ?? "Unknown city"}
                      </p>
                    </div>
                    <Badge tone={bandTone(lead.latest_band)}>
                      {lead.latest_band ? titleCaseLabel(lead.latest_band) : "Unscored"}
                    </Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge tone="neutral">{formatScore(lead.latest_score)}</Badge>
                    <Badge tone={lead.latest_qualified ? "success" : "warning"}>
                      {lead.latest_qualified ? "Qualified" : "Needs review"}
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
              <CardTitle>Region and operations</CardTitle>
              <CardDescription>
                The city widget from the imported design now runs on the actual lead geography in the database.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {cityCoverage.length === 0 ? (
                <EmptyState
                  title="No city coverage yet"
                  description="City-level operations metrics appear once leads are stored in the workspace."
                />
              ) : (
                cityCoverage.map((item) => (
                  <div
                    key={item.city}
                    className="flex items-center justify-between rounded-2xl border border-border bg-muted/20 px-4 py-3"
                  >
                    <div>
                      <p className="font-medium">{item.city}</p>
                      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Stored leads</p>
                    </div>
                    <Badge tone="accent">{item.count}</Badge>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>AI and audit activity</CardTitle>
              <CardDescription>
                Imported sidebar panels are backed by current route destinations instead of static demo content.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-2xl border border-border bg-muted/20 p-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Sparkles className="size-4 text-[oklch(var(--signal))]" />
                  AI workspace readiness
                </div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {highBand > 0
                    ? `${highBand} high-band leads are ready for deeper analysis and outreach draft generation.`
                    : "No high-band leads yet. The AI workspace will populate as new discovery jobs produce stronger evidence."}
                </p>
                <Button className="mt-3" variant="outline" asChild>
                  <Link to={appPaths.aiAnalysis}>Open AI analysis</Link>
                </Button>
              </div>

              {activeJobs.length === 0 ? (
                <QueryStateNotice
                  tone="info"
                  title="No active discovery runs"
                  description="Queue a new search job to refresh throughput, evidence, and lead scores."
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
