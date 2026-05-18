import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Compass, Copy, DatabaseZap, Play, SearchCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { appPaths } from "@/app/paths";
import { JobDetailDrawer } from "@/components/jobs/job-detail-drawer";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { createSearchJob } from "@/features/searches/api";
import { useInvalidateLeadsWhileDiscoveryActive } from "@/hooks/use-invalidate-leads-while-discovery-active";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { useSearchJobsQuery } from "@/hooks/use-search-jobs-query";
import { searchJobStatusLabel, websitePreferenceLabel } from "@/lib/i18n-labels";
import { formatDate, searchJobTone } from "@/lib/presenters";
import type { SearchJobResponse } from "@/types/api";

const searchSchema = z
  .object({
    business_type: z.string().min(2),
    city: z.string().min(2),
    region: z.string().optional(),
    radius_km: z.union([z.coerce.number().int().min(1).max(500), z.literal("")]).optional(),
    max_results: z.coerce.number().int().min(1).max(100),
    min_rating: z.union([z.coerce.number().min(0).max(5), z.literal("")]).optional(),
    max_rating: z.union([z.coerce.number().min(0).max(5), z.literal("")]).optional(),
    min_reviews: z.union([z.coerce.number().int().min(0), z.literal("")]).optional(),
    max_reviews: z.union([z.coerce.number().int().min(0), z.literal("")]).optional(),
    website_preference: z.enum(["any", "must_have", "must_be_missing"]).default("any"),
    keyword_filter: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    if (
      values.min_rating !== "" &&
      values.max_rating !== "" &&
      values.min_rating !== undefined &&
      values.max_rating !== undefined &&
      values.max_rating < values.min_rating
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["max_rating"],
        message: "Max rating must be greater than or equal to min rating.",
      });
    }

    if (
      values.min_reviews !== "" &&
      values.max_reviews !== "" &&
      values.min_reviews !== undefined &&
      values.max_reviews !== undefined &&
      values.max_reviews < values.min_reviews
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["max_reviews"],
        message: "Max reviews must be greater than or equal to min reviews.",
      });
    }
  });

type SearchValues = z.infer<typeof searchSchema>;

const defaultValues: SearchValues = {
  business_type: "",
  city: "",
  region: "",
  radius_km: "",
  max_results: 25,
  min_rating: "",
  max_rating: "",
  min_reviews: "",
  max_reviews: "",
  website_preference: "any",
  keyword_filter: "",
};

export function SearchesPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("searches.title"));
  const queryClient = useQueryClient();
  const [selectedJob, setSelectedJob] = useState<SearchJobResponse | null>(null);

  const form = useForm<SearchValues>({
    resolver: zodResolver(searchSchema),
    defaultValues,
  });

  const jobsQuery = useSearchJobsQuery();
  useInvalidateLeadsWhileDiscoveryActive(jobsQuery.data?.items);

  const createMutation = useMutation({
    mutationFn: (values: SearchValues) => createSearchJob(mapSearchValues(values)),
    onSuccess: (job) => {
      void queryClient.invalidateQueries({ queryKey: ["search-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      form.reset(defaultValues);
      setSelectedJob(job);
    },
  });

  const rerunMutation = useMutation({
    mutationFn: (job: SearchJobResponse) => createSearchJob(jobToRequest(job)),
    onSuccess: (job) => {
      void queryClient.invalidateQueries({ queryKey: ["search-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      setSelectedJob(job);
    },
  });

  const jobs = jobsQuery.data?.items ?? [];
  const activeJobs = jobs.filter((job) => job.status === "queued" || job.status === "running");
  const historyJobs = jobs.filter((job) => job.status !== "queued" && job.status !== "running");
  const queuedJobs = activeJobs.length;
  const completedJobs = jobs.filter((job) => job.status === "completed").length;
  const partialJobs = jobs.filter((job) => job.status === "partially_completed").length;
  const currentDiscoveryRuntime =
    createMutation.data?.discovery_runtime ?? jobsQuery.data?.items[0]?.discovery_runtime ?? null;

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow={t("searches.title")}
        title={t("searches.workspaceTitle")}
        description={t("searches.workspaceDescription")}
        actions={
          <Button asChild variant="outline" className="bg-transparent">
            <Link to={appPaths.leads}>{t("searches.openLeadsWorkspace")}</Link>
          </Button>
        }
      />

      {currentDiscoveryRuntime === "demo" ? (
        <QueryStateNotice
          tone="info"
          title={t("searches.demoRuntimeTitle")}
          description={t("searches.demoRuntimeDescription")}
        />
      ) : currentDiscoveryRuntime === "live" ? (
        <QueryStateNotice
          tone="success"
          title={t("searches.liveRuntimeTitle")}
          description={t("searches.liveRuntimeDescription")}
        />
      ) : currentDiscoveryRuntime === "blocked" ? (
        <QueryStateNotice
          tone="error"
          title={t("searches.blockedRuntimeTitle")}
          description={t("searches.blockedRuntimeDescription")}
        />
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label={t("searches.queuedOrRunning")} value={String(queuedJobs)} helper={t("searches.liveThroughput")} />
        <MetricCard label={t("searches.completedCleanly")} value={String(completedJobs)} helper={t("searches.finishedWithoutWarnings")} />
        <MetricCard label={t("searches.completedWithWarnings")} value={String(partialJobs)} helper={t("searches.partialProviderSuccess")} />
      </section>

      <section className="grid gap-4 2xl:grid-cols-[1.05fr_0.95fr]">
        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("searches.createNewJob")}</CardTitle>
            <CardDescription>
              {t("searches.createNewJobDescription")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={form.handleSubmit((values) => createMutation.mutate(values))}>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label={t("searches.businessType")} error={form.formState.errors.business_type?.message}>
                  <Input
                    data-testid="search-form-business-type"
                    placeholder="Dentist, lawyer, clinic, salon"
                    {...form.register("business_type")}
                  />
                </Field>
                <Field label={t("searches.city")} error={form.formState.errors.city?.message}>
                  <Input data-testid="search-form-city" placeholder="Istanbul" {...form.register("city")} />
                </Field>
                <Field label={t("searches.region")} error={form.formState.errors.region?.message}>
                  <Input placeholder="District, state, or broader geography" {...form.register("region")} />
                </Field>
                <Field label={t("searches.keywordFilter")} error={form.formState.errors.keyword_filter?.message}>
                  <Input placeholder="implant, emergency, cosmetic" {...form.register("keyword_filter")} />
                </Field>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <Field label={t("searches.radiusKm")} error={form.formState.errors.radius_km?.message}>
                  <Input type="number" min={1} max={500} {...form.register("radius_km")} />
                </Field>
                <Field label={t("searches.maxResults")} error={form.formState.errors.max_results?.message}>
                  <Input type="number" min={1} max={100} {...form.register("max_results")} />
                </Field>
                <Field label={t("searches.websitePreference")}>
                  <Select
                    value={form.watch("website_preference")}
                    onValueChange={(value) =>
                      form.setValue("website_preference", value as SearchValues["website_preference"], {
                        shouldDirty: true,
                        shouldValidate: true,
                      })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t("searches.selectWebsitePreference")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">{t("searches.websiteAny")}</SelectItem>
                      <SelectItem value="must_have">{t("searches.websiteRequired")}</SelectItem>
                      <SelectItem value="must_be_missing">{t("searches.websiteNone")}</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
              </div>

              <div className="grid gap-4 md:grid-cols-4">
                <Field label={t("searches.minRating")} error={form.formState.errors.min_rating?.message}>
                  <Input type="number" min={0} max={5} step="0.1" {...form.register("min_rating")} />
                </Field>
                <Field label={t("searches.maxRating")} error={form.formState.errors.max_rating?.message}>
                  <Input type="number" min={0} max={5} step="0.1" {...form.register("max_rating")} />
                </Field>
                <Field label={t("searches.minReviews")} error={form.formState.errors.min_reviews?.message}>
                  <Input type="number" min={0} {...form.register("min_reviews")} />
                </Field>
                <Field label={t("searches.maxReviews")} error={form.formState.errors.max_reviews?.message}>
                  <Input type="number" min={0} {...form.register("max_reviews")} />
                </Field>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button type="submit" disabled={createMutation.isPending}>
                  <Play className="size-3.5" />
                  {createMutation.isPending ? t("searches.submitting") : t("searches.queueDiscoveryJob")}
                </Button>
                <Button type="button" variant="outline" className="bg-transparent" onClick={() => form.reset(defaultValues)}>
                  {t("searches.resetForm")}
                </Button>
              </div>

              {createMutation.isSuccess ? (
                <QueryStateNotice
                  tone="success"
                  title={t("searches.discoveryQueuedTitle")}
                  description={t("searches.discoveryQueuedDescription")}
                />
              ) : null}
              {createMutation.isError ? (
                <QueryStateNotice
                  tone="error"
                  title={t("searches.queueErrorTitle")}
                  error={createMutation.error}
                />
              ) : null}
            </form>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>{t("searches.runGuidance")}</CardTitle>
              <CardDescription>{t("searches.runGuidanceDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <InsightCard
                icon={<SearchCheck className="mt-1 size-5 text-[oklch(var(--signal))]" />}
                title={t("searches.discoveryFlow")}
                description={t("searches.discoveryFlowDescription")}
              />
              <InsightCard
                icon={<DatabaseZap className="mt-1 size-5 text-[oklch(var(--signal))]" />}
                title={t("searches.storedOutputs")}
                description={t("searches.storedOutputsDescription")}
              />
              <InsightCard
                icon={<Compass className="mt-1 size-5 text-[oklch(var(--signal))]" />}
                title={t("searches.cloneAndRerun")}
                description={t("searches.cloneAndRerunDescription")}
              />
            </CardContent>
          </Card>

          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>{t("searches.selectedRun")}</CardTitle>
              <CardDescription>{t("searches.selectedRunDescription")}</CardDescription>
            </CardHeader>
            <CardContent>
              {selectedJob ? (
                <SearchJobPreview
                  job={selectedJob}
                  onOpen={() => setSelectedJob(selectedJob)}
                  onClone={() => cloneIntoForm(selectedJob, form.reset)}
                />
              ) : (
                <EmptyState
                  title={t("searches.noRunSelected")}
                  description={t("searches.noRunSelectedDescription")}
                />
              )}
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="grid gap-4 2xl:grid-cols-2">
        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("searches.activeJobs")}</CardTitle>
            <CardDescription>{t("searches.activeJobsDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {activeJobs.length === 0 ? (
              <EmptyState
                title={t("searches.noActiveJobs")}
                description={t("searches.noActiveJobsDescription")}
              />
            ) : (
              activeJobs.map((job) => (
                <SearchJobCard
                  key={job.public_id}
                  job={job}
                  onInspect={() => setSelectedJob(job)}
                  onClone={() => cloneIntoForm(job, form.reset)}
                  onRerun={() => rerunMutation.mutate(job)}
                  rerunning={rerunMutation.isPending && selectedJob?.public_id === job.public_id}
                />
              ))
            )}
          </CardContent>
        </Card>

        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("searches.runHistory")}</CardTitle>
            <CardDescription>{t("searches.runHistoryDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {historyJobs.length === 0 ? (
              <EmptyState
                title={t("searches.noCompletedRuns")}
                description={t("searches.noCompletedRunsDescription")}
              />
            ) : (
              historyJobs.map((job) => (
                <SearchJobCard
                  key={job.public_id}
                  job={job}
                  onInspect={() => setSelectedJob(job)}
                  onClone={() => cloneIntoForm(job, form.reset)}
                  onRerun={() => rerunMutation.mutate(job)}
                  rerunning={rerunMutation.isPending && selectedJob?.public_id === job.public_id}
                />
              ))
            )}
          </CardContent>
        </Card>
      </section>

      <JobDetailDrawer
        job={selectedJob}
        open={Boolean(selectedJob)}
        onClose={() => setSelectedJob(null)}
        onClone={(job) => cloneIntoForm(job, form.reset)}
        onRerun={(job) => rerunMutation.mutate(job)}
        rerunning={rerunMutation.isPending}
      />
    </div>
  );
}

function mapSearchValues(values: SearchValues) {
  return {
    business_type: values.business_type,
    city: values.city,
    region: values.region || undefined,
    radius_km: values.radius_km === "" ? undefined : values.radius_km,
    max_results: values.max_results,
    min_rating: values.min_rating === "" ? undefined : values.min_rating,
    max_rating: values.max_rating === "" ? undefined : values.max_rating,
    min_reviews: values.min_reviews === "" ? undefined : values.min_reviews,
    max_reviews: values.max_reviews === "" ? undefined : values.max_reviews,
    website_preference: values.website_preference,
    keyword_filter: values.keyword_filter?.trim() || undefined,
  };
}

function jobToRequest(job: SearchJobResponse) {
  return {
    business_type: job.business_type,
    city: job.city,
    region: job.region ?? undefined,
    radius_km: job.radius_km ?? undefined,
    max_results: job.max_results,
    min_rating: job.min_rating ?? undefined,
    max_rating: job.max_rating ?? undefined,
    min_reviews: job.min_reviews ?? undefined,
    max_reviews: job.max_reviews ?? undefined,
    website_preference: job.website_preference,
    keyword_filter: job.keyword_filter ?? undefined,
  };
}

function cloneIntoForm(job: SearchJobResponse, reset: (values: SearchValues) => void) {
  reset({
    business_type: job.business_type,
    city: job.city,
    region: job.region ?? "",
    radius_km: job.radius_km ?? "",
    max_results: job.max_results,
    min_rating: job.min_rating ?? "",
    max_rating: job.max_rating ?? "",
    min_reviews: job.min_reviews ?? "",
    max_reviews: job.max_reviews ?? "",
    website_preference: job.website_preference,
    keyword_filter: job.keyword_filter ?? "",
  });
}

function MetricCard({ label, value, helper }: { label: string; value: string; helper: string }) {
  return (
    <div className="rounded-[1.5rem] border border-border bg-card/95 p-5 shadow-[0_20px_60px_-44px_rgba(15,23,42,0.85)]">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-3 text-3xl font-semibold tracking-tight">{value}</p>
      <p className="mt-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">{helper}</p>
    </div>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">{label}</label>
      {children}
      {error ? <p className="text-sm text-[color:var(--danger)]">{error}</p> : null}
    </div>
  );
}

function InsightCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex gap-4 rounded-2xl border border-border bg-muted/20 p-4">
      {icon}
      <div>
        <p className="font-medium">{title}</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

function SearchJobPreview({
  job,
  onOpen,
  onClone,
}: {
  job: SearchJobResponse;
  onOpen: () => void;
  onClone: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="rounded-2xl border border-border bg-muted/20 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-medium">
            {job.business_type} / {job.city}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{formatDate(job.queued_at)}</p>
        </div>
        <Badge tone={searchJobTone(job.status)}>{searchJobStatusLabel(t, job.status)}</Badge>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" className="flex-1 sm:flex-none" onClick={onOpen}>
          {t("searches.inspectRun")}
        </Button>
        <Button size="sm" variant="outline" className="flex-1 bg-transparent sm:flex-none" onClick={onClone}>
          {t("searches.cloneToForm")}
        </Button>
      </div>
    </div>
  );
}

function SearchJobCard({
  job,
  onInspect,
  onClone,
  onRerun,
  rerunning,
}: {
  job: SearchJobResponse;
  onInspect: () => void;
  onClone: () => void;
  onRerun: () => void;
  rerunning?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="rounded-2xl border border-border bg-muted/20 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-medium">
            {job.business_type} / {job.city}
            {job.region ? `, ${job.region}` : ""}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("searches.jobCardSummary", {
              date: formatDate(job.queued_at),
              candidates: job.candidates_found,
              upserted: job.leads_upserted,
            })}
          </p>
        </div>
        <Badge tone={searchJobTone(job.status)}>{searchJobStatusLabel(t, job.status)}</Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Badge tone="neutral">
          {websitePreferenceLabel(t, job.website_preference)}
        </Badge>
        {job.keyword_filter ? <Badge tone="accent">{job.keyword_filter}</Badge> : null}
        {job.radius_km ? <Badge tone="neutral">{job.radius_km} km radius</Badge> : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" className="flex-1 sm:flex-none" onClick={onInspect}>
          {t("searches.inspect")}
        </Button>
        <Button size="sm" variant="outline" className="flex-1 bg-transparent sm:flex-none" onClick={onClone}>
          <Copy className="size-3.5" />
          {t("searches.clone")}
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="flex-1 bg-transparent sm:flex-none"
          onClick={onRerun}
          disabled={rerunning}
        >
          <Play className="size-3.5" />
          {rerunning ? t("searches.rerunning") : t("searches.rerun")}
        </Button>
        <Button size="sm" variant="outline" className="flex-1 bg-transparent sm:flex-none" asChild>
          <Link to={`${appPaths.leads}?search_job_id=${job.public_id}`}>{t("searches.viewLeads")}</Link>
        </Button>
      </div>
    </div>
  );
}
