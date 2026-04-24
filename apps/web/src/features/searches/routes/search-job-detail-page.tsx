import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ListFilter, Radar, Rows3, ShieldAlert, TimerReset } from "lucide-react";
import { Link, Navigate, useParams } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getSearchJob } from "@/features/searches/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { formatDate, searchJobTone, titleCaseLabel } from "@/lib/presenters";

const ACTIVE_JOB_STATUSES = new Set(["queued", "running"]);

export function SearchJobDetailPage() {
  const { jobId = "" } = useParams();
  useDocumentTitle("Discovery run");

  const jobQuery = useQuery({
    queryKey: ["search-jobs", "detail", jobId],
    queryFn: () => getSearchJob(jobId),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job) {
        return false;
      }
      return ACTIVE_JOB_STATUSES.has(job.status) ? 4_000 : false;
    },
  });

  if (!jobId) {
    return <Navigate replace to={appPaths.searches} />;
  }

  if (jobQuery.isPending) {
    return (
      <QueryStateNotice
        tone="loading"
        title="Loading discovery run"
        description="Fetching the latest persisted status and throughput metrics for this job."
      />
    );
  }

  if (jobQuery.isError) {
    return (
      <EmptyState
        title="Search job not found"
        description={jobQuery.error.message}
        action={
          <Button asChild>
            <Link to={appPaths.searches}>Back to search jobs</Link>
          </Button>
        }
      />
    );
  }

  const job = jobQuery.data;
  const runtimeLabel =
    job.discovery_runtime === "serpapi"
      ? "Live provider"
      : job.discovery_runtime === "demo"
        ? "Demo provider"
        : "Blocked runtime";

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow="Search job"
        title={`${job.business_type} in ${job.city}`}
        description="Live execution record from the discovery pipeline: search, enrichment, web validation, and score persistence."
        actions={
          <>
            <Button asChild variant="outline" className="bg-transparent">
              <Link to={appPaths.searches}>
                <ArrowLeft className="size-3.5" />
                All jobs
              </Link>
            </Button>
            <Button asChild>
              <Link to={`${appPaths.leads}?search_job_id=${encodeURIComponent(job.public_id)}`}>
                <ListFilter className="size-3.5" />
                Leads from this run
              </Link>
            </Button>
          </>
        }
      />

      <div className="flex flex-wrap gap-2">
        <Badge tone={searchJobTone(job.status)}>{titleCaseLabel(job.status)}</Badge>
        <Badge tone="neutral">Job ID {job.public_id}</Badge>
        <Badge tone="neutral">{runtimeLabel}</Badge>
      </div>

      {job.status === "queued" || job.status === "running" ? (
        <QueryStateNotice
          tone="loading"
          title="Discovery run in progress"
          description="This page refreshes automatically while the background pipeline is still working."
        />
      ) : job.status === "failed" ? (
        <QueryStateNotice
          tone="error"
          title="Discovery run failed"
          description="No leads were persisted for this run. Check provider configuration and recent operational health warnings."
        />
      ) : (
        <QueryStateNotice
          tone={job.status === "partially_completed" ? "info" : "success"}
          title={job.status === "partially_completed" ? "Discovery run completed with warnings" : "Discovery run completed"}
          description={
            job.status === "partially_completed"
              ? "Some provider calls failed, but usable leads were still persisted."
              : "The requested run finished and persisted its lead outputs."
          }
        />
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Candidates found" value={String(job.candidates_found)} helper="Raw provider candidates" icon={Rows3} />
        <KpiCard label="Leads upserted" value={String(job.leads_upserted)} helper="Persisted lead records" tone="evidence" icon={Radar} />
        <KpiCard label="Provider errors" value={String(job.provider_error_count)} helper="Fetch failures during run" tone={job.provider_error_count ? "risk" : "signal"} icon={ShieldAlert} />
        <KpiCard label="Enriched" value={String(job.enriched_count)} helper="Expanded candidate records" tone="caution" icon={TimerReset} />
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>Scope</CardTitle>
            <CardDescription>Immutable request parameters stored with the job.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <DetailRow label="Business type" value={job.business_type} />
            <DetailRow label="City" value={job.city} />
            <DetailRow label="Region" value={job.region ?? "-"} />
            <DetailRow label="Radius" value={job.radius_km != null ? `${job.radius_km} km` : "-"} />
            <DetailRow label="Max results" value={String(job.max_results)} />
            <DetailRow
              label="Website preference"
              value={
                job.website_preference === "must_have"
                  ? "Must have website"
                  : job.website_preference === "must_be_missing"
                    ? "Must be missing website"
                    : "Any"
              }
            />
            <DetailRow label="Keyword filter" value={job.keyword_filter ?? "-"} />
          </CardContent>
        </Card>

        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>Filters and thresholds</CardTitle>
            <CardDescription>Rating, reviews, and website constraints applied during discovery.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <DetailRow label="Rating range" value={`${job.min_rating ?? "Any"} - ${job.max_rating ?? "Any"}`} />
            <DetailRow label="Review range" value={`${job.min_reviews ?? "Any"} - ${job.max_reviews ?? "Any"}`} />
            <DetailRow label="Runtime" value={runtimeLabel} />
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-[1.5rem] border-border bg-card/95">
        <CardHeader>
          <CardTitle>Execution timeline</CardTitle>
          <CardDescription>Queued, started, and finished timestamps from the API.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <DetailRow label="Queued" value={formatDate(job.queued_at)} />
          <DetailRow label="Started" value={job.started_at ? formatDate(job.started_at) : "-"} />
          <DetailRow label="Finished" value={job.finished_at ? formatDate(job.finished_at) : "-"} />
        </CardContent>
      </Card>

      <Card className="rounded-[1.5rem] border-border bg-card/95">
        <CardHeader>
          <CardTitle>Operational interpretation</CardTitle>
          <CardDescription>Quick reading of how this run behaved in the workspace.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 lg:grid-cols-3">
          <DetailRow
            label="Outcome"
            value={
              job.status === "completed"
                ? "Completed cleanly"
                : job.status === "partially_completed"
                  ? "Completed with warnings"
                  : job.status === "failed"
                    ? "Failed before useful persistence"
                    : "Still processing"
            }
          />
          <DetailRow
            label="Lead yield"
            value={job.leads_upserted > 0 ? `${job.leads_upserted} records persisted` : "No lead records yet"}
          />
          <DetailRow
            label="Next action"
            value={job.leads_upserted > 0 ? "Open filtered leads workspace" : "Monitor run progress"}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-muted/20 px-4 py-3">
      <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
      <p className="mt-1 font-semibold text-foreground">{value}</p>
    </div>
  );
}
