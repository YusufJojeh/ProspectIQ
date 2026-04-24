import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Compass, Copy, DatabaseZap, Play, SearchCheck } from "lucide-react";
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
import { formatDate, searchJobTone, titleCaseLabel } from "@/lib/presenters";
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
  useDocumentTitle("Search Jobs");
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
        eyebrow="Search jobs"
        title="Scoped discovery workspace"
        description="The imported job-management layout now runs on the live FastAPI search queue, including clone, rerun, history, and lead-routing actions."
        actions={
          <Button asChild variant="outline" className="bg-transparent">
            <Link to={appPaths.leads}>Open leads workspace</Link>
          </Button>
        }
      />

      {currentDiscoveryRuntime === "demo" ? (
        <QueryStateNotice
          tone="info"
          title="Discovery is using demo provider data"
          description="This workspace is currently returning structured demo results instead of live SerpAPI responses."
        />
      ) : currentDiscoveryRuntime === "serpapi" ? (
        <QueryStateNotice
          tone="success"
          title="Discovery is using live SerpAPI"
          description="New search jobs will call the live provider and persist real fetch traces."
        />
      ) : currentDiscoveryRuntime === "blocked" ? (
        <QueryStateNotice
          tone="error"
          title="Discovery is blocked"
          description="Real SerpAPI calls are required for this workspace and demo fallbacks are disabled or unavailable."
        />
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label="Queued or running" value={String(queuedJobs)} helper="Live discovery throughput" />
        <MetricCard label="Completed cleanly" value={String(completedJobs)} helper="Finished without warnings" />
        <MetricCard label="Completed with warnings" value={String(partialJobs)} helper="Partial provider success" />
      </section>

      <section className="grid gap-4 2xl:grid-cols-[1.05fr_0.95fr]">
        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>Create new job</CardTitle>
            <CardDescription>
              Imported discovery controls are now mapped to the real search job API contract and validation rules.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={form.handleSubmit((values) => createMutation.mutate(values))}>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Business type" error={form.formState.errors.business_type?.message}>
                  <Input
                    data-testid="search-form-business-type"
                    placeholder="Dentist, lawyer, clinic, salon"
                    {...form.register("business_type")}
                  />
                </Field>
                <Field label="City" error={form.formState.errors.city?.message}>
                  <Input data-testid="search-form-city" placeholder="Istanbul" {...form.register("city")} />
                </Field>
                <Field label="Region" error={form.formState.errors.region?.message}>
                  <Input placeholder="District, state, or broader geography" {...form.register("region")} />
                </Field>
                <Field label="Keyword filter" error={form.formState.errors.keyword_filter?.message}>
                  <Input placeholder="implant, emergency, cosmetic" {...form.register("keyword_filter")} />
                </Field>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <Field label="Radius (km)" error={form.formState.errors.radius_km?.message}>
                  <Input type="number" min={1} max={500} {...form.register("radius_km")} />
                </Field>
                <Field label="Max results" error={form.formState.errors.max_results?.message}>
                  <Input type="number" min={1} max={100} {...form.register("max_results")} />
                </Field>
                <Field label="Website preference">
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
                      <SelectValue placeholder="Select website preference" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">Any</SelectItem>
                      <SelectItem value="must_have">Must have website</SelectItem>
                      <SelectItem value="must_be_missing">Must be missing website</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
              </div>

              <div className="grid gap-4 md:grid-cols-4">
                <Field label="Min rating" error={form.formState.errors.min_rating?.message}>
                  <Input type="number" min={0} max={5} step="0.1" {...form.register("min_rating")} />
                </Field>
                <Field label="Max rating" error={form.formState.errors.max_rating?.message}>
                  <Input type="number" min={0} max={5} step="0.1" {...form.register("max_rating")} />
                </Field>
                <Field label="Min reviews" error={form.formState.errors.min_reviews?.message}>
                  <Input type="number" min={0} {...form.register("min_reviews")} />
                </Field>
                <Field label="Max reviews" error={form.formState.errors.max_reviews?.message}>
                  <Input type="number" min={0} {...form.register("max_reviews")} />
                </Field>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button type="submit" disabled={createMutation.isPending}>
                  <Play className="size-3.5" />
                  {createMutation.isPending ? "Submitting..." : "Queue discovery job"}
                </Button>
                <Button type="button" variant="outline" className="bg-transparent" onClick={() => form.reset(defaultValues)}>
                  Reset form
                </Button>
              </div>

              {createMutation.isSuccess ? (
                <QueryStateNotice
                  tone="success"
                  title="Discovery job queued"
                  description="The run was accepted and the search-job list has been refreshed."
                />
              ) : null}
              {createMutation.isError ? (
                <QueryStateNotice
                  tone="error"
                  title="Search job could not be queued"
                  description={createMutation.error.message}
                />
              ) : null}
            </form>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>Run guidance</CardTitle>
              <CardDescription>Use explicit qualification thresholds so result quality remains reproducible.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <InsightCard
                icon={<SearchCheck className="mt-1 size-5 text-[oklch(var(--signal))]" />}
                title="Discovery flow"
                description="Maps search discovers candidates, enrichment deepens selected records, and web validation confirms website presence."
              />
              <InsightCard
                icon={<DatabaseZap className="mt-1 size-5 text-[oklch(var(--signal))]" />}
                title="Stored outputs"
                description="Raw payloads, normalized facts, score breakdowns, and activity records remain persisted separately for traceability."
              />
              <InsightCard
                icon={<Compass className="mt-1 size-5 text-[oklch(var(--signal))]" />}
                title="Clone and rerun"
                description="Historical jobs can populate the live form or be resubmitted directly without introducing mock workflow state."
              />
            </CardContent>
          </Card>

          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>Selected run</CardTitle>
              <CardDescription>Use the drawer to inspect details, clone parameters, rerun, or jump into lead results.</CardDescription>
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
                  title="No run selected"
                  description="Select an active or historical job below to inspect the imported detail drawer."
                />
              )}
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="grid gap-4 2xl:grid-cols-2">
        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>Active jobs</CardTitle>
            <CardDescription>Queued and running search jobs with real execution status and action controls.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {activeJobs.length === 0 ? (
              <EmptyState
                title="No active jobs"
                description="Queued and running discovery jobs will appear here while the workspace refreshes in real time."
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
            <CardTitle>Run history</CardTitle>
            <CardDescription>Completed jobs remain actionable through the imported cards and detail drawer.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {historyJobs.length === 0 ? (
              <EmptyState
                title="No completed runs yet"
                description="Once jobs finish, their persisted throughput and warnings will appear in this history view."
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
  return (
    <div className="rounded-2xl border border-border bg-muted/20 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-medium">
            {job.business_type} / {job.city}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{formatDate(job.queued_at)}</p>
        </div>
        <Badge tone={searchJobTone(job.status)}>{titleCaseLabel(job.status)}</Badge>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" className="flex-1 sm:flex-none" onClick={onOpen}>
          Inspect run
        </Button>
        <Button size="sm" variant="outline" className="flex-1 bg-transparent sm:flex-none" onClick={onClone}>
          Clone to form
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
  return (
    <div className="rounded-2xl border border-border bg-muted/20 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-medium">
            {job.business_type} / {job.city}
            {job.region ? `, ${job.region}` : ""}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {formatDate(job.queued_at)} / {job.candidates_found} candidates / {job.leads_upserted} upserted
          </p>
        </div>
        <Badge tone={searchJobTone(job.status)}>{titleCaseLabel(job.status)}</Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Badge tone="neutral">
          {job.website_preference === "must_have"
            ? "Website required"
            : job.website_preference === "must_be_missing"
              ? "Website missing"
              : "Website any"}
        </Badge>
        {job.keyword_filter ? <Badge tone="accent">{job.keyword_filter}</Badge> : null}
        {job.radius_km ? <Badge tone="neutral">{job.radius_km} km radius</Badge> : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" className="flex-1 sm:flex-none" onClick={onInspect}>
          Inspect
        </Button>
        <Button size="sm" variant="outline" className="flex-1 bg-transparent sm:flex-none" onClick={onClone}>
          <Copy className="size-3.5" />
          Clone
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="flex-1 bg-transparent sm:flex-none"
          onClick={onRerun}
          disabled={rerunning}
        >
          <Play className="size-3.5" />
          {rerunning ? "Rerunning..." : "Rerun"}
        </Button>
        <Button size="sm" variant="outline" className="flex-1 bg-transparent sm:flex-none" asChild>
          <Link to={`${appPaths.leads}?search_job_id=${job.public_id}`}>View leads</Link>
        </Button>
      </div>
    </div>
  );
}
