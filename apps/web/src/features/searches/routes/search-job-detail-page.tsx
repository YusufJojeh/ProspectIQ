import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ListFilter, Radar, Rows3, ShieldAlert, TimerReset } from "lucide-react";
import { useTranslation } from "react-i18next";
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
import { discoveryRuntimeLabel, searchJobStatusLabel, websitePreferenceLabel } from "@/lib/i18n-labels";
import { formatDate, searchJobTone } from "@/lib/presenters";

const ACTIVE_JOB_STATUSES = new Set(["queued", "running"]);

export function SearchJobDetailPage() {
  const { t } = useTranslation();
  const { jobId = "" } = useParams();
  useDocumentTitle(t("searches.detailTitle"));

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
        title={t("searches.detailLoadingTitle")}
        description={t("searches.detailLoadingDescription")}
      />
    );
  }

  if (jobQuery.isError) {
    return (
      <EmptyState
        title={t("searches.jobNotFound")}
        description={jobQuery.error.message}
        action={
          <Button asChild>
            <Link to={appPaths.searches}>{t("searches.backToJobs")}</Link>
          </Button>
        }
      />
    );
  }

  const job = jobQuery.data;
  const runtimeLabel =
    job.discovery_runtime === "live"
      ? discoveryRuntimeLabel(t, "live")
      : job.discovery_runtime === "demo"
        ? discoveryRuntimeLabel(t, "demo")
        : job.discovery_runtime === "stub"
          ? discoveryRuntimeLabel(t, "stub")
          : discoveryRuntimeLabel(t, "blocked");

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow={t("searches.jobDetails")}
        title={t("searches.jobTitlePattern", { businessType: job.business_type, city: job.city })}
        description={t("searches.detailDescription")}
        actions={
          <>
            <Button asChild variant="outline" className="bg-transparent">
              <Link to={appPaths.searches}>
                <ArrowLeft className="size-3.5" />
                {t("searches.allJobs")}
              </Link>
            </Button>
            <Button asChild>
              <Link to={`${appPaths.leads}?search_job_id=${encodeURIComponent(job.public_id)}`}>
                <ListFilter className="size-3.5" />
                {t("searches.leadsFromRun")}
              </Link>
            </Button>
          </>
        }
      />

      <div className="flex flex-wrap gap-2">
        <Badge tone={searchJobTone(job.status)}>{searchJobStatusLabel(t, job.status)}</Badge>
        <Badge tone="neutral">{t("searches.jobId", { id: job.public_id })}</Badge>
        <Badge tone="neutral">{runtimeLabel}</Badge>
      </div>

      {job.status === "queued" || job.status === "running" ? (
        <QueryStateNotice
          tone="loading"
          title={t("searches.runInProgressTitle")}
          description={t("searches.runInProgressDescription")}
        />
      ) : job.status === "failed" ? (
        <QueryStateNotice
          tone="error"
          title={t("searches.runFailedTitle")}
          description={t("searches.runFailedDescription")}
        />
      ) : (
        <QueryStateNotice
          tone={job.status === "partially_completed" ? "info" : "success"}
          title={job.status === "partially_completed" ? t("searches.runCompletedWarningsTitle") : t("searches.runCompletedTitle")}
          description={
            job.status === "partially_completed"
              ? t("searches.runCompletedWarningsDescription")
              : t("searches.runCompletedDescription")
          }
        />
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label={t("searches.candidatesFound")} value={String(job.candidates_found)} helper={t("searches.rawProviderCandidates")} icon={Rows3} />
        <KpiCard label={t("searches.leadsUpserted")} value={String(job.leads_upserted)} helper={t("searches.persistedLeadRecords")} tone="evidence" icon={Radar} />
        <KpiCard label={t("searches.providerErrors")} value={String(job.provider_error_count)} helper={t("searches.fetchFailures")} tone={job.provider_error_count ? "risk" : "signal"} icon={ShieldAlert} />
        <KpiCard label={t("searches.enriched")} value={String(job.enriched_count)} helper={t("searches.expandedCandidates")} tone="caution" icon={TimerReset} />
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("searches.scope")}</CardTitle>
            <CardDescription>{t("searches.scopeDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <DetailRow label={t("searches.businessType")} value={job.business_type} />
            <DetailRow label={t("searches.city")} value={job.city} />
            <DetailRow label={t("searches.region")} value={job.region ?? "-"} />
            <DetailRow label={t("searches.radiusKm")} value={job.radius_km != null ? `${job.radius_km} km` : "-"} />
            <DetailRow label={t("searches.maxResults")} value={String(job.max_results)} />
            <DetailRow
              label={t("searches.websitePreference")}
              value={websitePreferenceLabel(t, job.website_preference)}
            />
            <DetailRow label={t("searches.keywordFilter")} value={job.keyword_filter ?? "-"} />
          </CardContent>
        </Card>

        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("searches.filtersThresholds")}</CardTitle>
            <CardDescription>{t("searches.filtersThresholdsDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <DetailRow label={t("searches.ratingRange")} value={`${job.min_rating ?? t("common.all")} - ${job.max_rating ?? t("common.all")}`} />
            <DetailRow label={t("searches.reviewRange")} value={`${job.min_reviews ?? t("common.all")} - ${job.max_reviews ?? t("common.all")}`} />
            <DetailRow label={t("searches.discoveryRuntime")} value={runtimeLabel} />
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-[1.5rem] border-border bg-card/95">
        <CardHeader>
          <CardTitle>{t("searches.executionTimeline")}</CardTitle>
          <CardDescription>{t("searches.executionTimelineDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <DetailRow label={t("searches.queued")} value={formatDate(job.queued_at)} />
          <DetailRow label={t("searches.started")} value={job.started_at ? formatDate(job.started_at) : "-"} />
          <DetailRow label={t("searches.finished")} value={job.finished_at ? formatDate(job.finished_at) : "-"} />
        </CardContent>
      </Card>

      <Card className="rounded-[1.5rem] border-border bg-card/95">
        <CardHeader>
          <CardTitle>{t("searches.operationalInterpretation")}</CardTitle>
          <CardDescription>{t("searches.operationalInterpretationDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 lg:grid-cols-3">
          <DetailRow
            label={t("searches.outcome")}
            value={
              job.status === "completed"
                ? t("searches.completedCleanly")
                : job.status === "partially_completed"
                  ? t("searches.completedWithWarnings")
                  : job.status === "failed"
                    ? t("searches.failedBeforePersistence")
                    : t("searches.stillProcessing")
            }
          />
          <DetailRow
            label={t("searches.leadYield")}
            value={job.leads_upserted > 0 ? t("searches.recordsPersisted", { count: job.leads_upserted }) : t("searches.noLeadRecordsYet")}
          />
          <DetailRow
            label={t("searches.nextAction")}
            value={job.leads_upserted > 0 ? t("searches.openFilteredLeads") : t("searches.monitorRunProgress")}
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
