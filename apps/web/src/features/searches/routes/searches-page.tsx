import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Compass, DatabaseZap, SearchCheck } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { createSearchJob, listSearchJobs } from "@/features/searches/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { formatDate, titleCaseLabel } from "@/lib/presenters";

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

export function SearchesPage() {
  useDocumentTitle("Search Jobs");
  const queryClient = useQueryClient();
  const form = useForm<SearchValues>({
    resolver: zodResolver(searchSchema),
    defaultValues: {
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
    },
  });
  const jobsQuery = useQuery({
    queryKey: ["search-jobs", "list"],
    queryFn: listSearchJobs,
  });

  const mutation = useMutation({
    mutationFn: (values: SearchValues) =>
      createSearchJob({
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
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["search-jobs"] });
      form.reset({
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
      });
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Search jobs"
        title="Launch a scoped lead discovery run"
        description="Queue a city- and category-scoped run, then let the background pipeline discover, enrich, deduplicate, and score local leads."
      />

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <CardTitle>Create job</CardTitle>
            <CardDescription>
              Use explicit qualification thresholds so the resulting score remains reproducible.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-4"
              onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
            >
              <div className="space-y-2">
                <label className="text-sm font-semibold">Business type</label>
                <Input
                  placeholder="Dentist, lawyer, clinic, salon"
                  {...form.register("business_type")}
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-semibold">City</label>
                  <Input placeholder="Istanbul" {...form.register("city")} />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Region</label>
                  <Input
                    placeholder="District, state, or broader geography"
                    {...form.register("region")}
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Radius (km)</label>
                  <Input type="number" min={1} max={500} {...form.register("radius_km")} />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Max results</label>
                  <Input type="number" min={1} max={100} {...form.register("max_results")} />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Keyword filter</label>
                  <Input
                    placeholder="implant, emergency, cosmetic"
                    {...form.register("keyword_filter")}
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-4">
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Min rating</label>
                  <Input
                    type="number"
                    min={0}
                    max={5}
                    step="0.1"
                    {...form.register("min_rating")}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Max rating</label>
                  <Input
                    type="number"
                    min={0}
                    max={5}
                    step="0.1"
                    {...form.register("max_rating")}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Min reviews</label>
                  <Input type="number" min={0} {...form.register("min_reviews")} />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Max reviews</label>
                  <Input type="number" min={0} {...form.register("max_reviews")} />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold">Website preference</label>
                <select
                  className="flex h-11 w-full rounded-xl border border-[color:var(--border)] bg-white px-3 text-sm"
                  {...form.register("website_preference")}
                >
                  <option value="any">Any</option>
                  <option value="must_have">Must have website</option>
                  <option value="must_be_missing">Must be missing website</option>
                </select>
              </div>

              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Submitting..." : "Queue discovery job"}
              </Button>
              {mutation.error ? (
                <p className="text-sm text-red-600">{mutation.error.message}</p>
              ) : null}
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Run queue</CardTitle>
            <CardDescription>
              Live search jobs with persisted status, provider errors, and lead counts.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {jobsQuery.isError ? (
              <p className="text-sm text-red-600">{jobsQuery.error.message}</p>
            ) : jobsQuery.data?.items.length ? (
              <div className="space-y-3">
                {jobsQuery.data.items.map((job) => (
                  <div
                    key={job.public_id}
                    className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-bold">{job.business_type}</p>
                        <p className="text-sm text-[color:var(--muted)]">
                          {job.city}
                          {job.region ? `, ${job.region}` : ""}
                        </p>
                      </div>
                      <Badge tone={job.status === "completed" ? "warning" : "accent"}>
                        {titleCaseLabel(job.status)}
                      </Badge>
                    </div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-xl bg-white/70 px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">
                          Queued
                        </p>
                        <p className="mt-1 font-semibold text-[color:var(--text)]">
                          {formatDate(job.queued_at)}
                        </p>
                      </div>
                      <div className="rounded-xl bg-white/70 px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">
                          Thresholds
                        </p>
                        <p className="mt-1 font-semibold text-[color:var(--text)]">
                          {job.min_rating ?? "Any"}-{job.max_rating ?? "Any"} rating ·{" "}
                          {job.min_reviews ?? "Any"}-{job.max_reviews ?? "Any"} reviews
                        </p>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge tone="neutral">
                        {job.website_preference === "must_have"
                          ? "Website required"
                          : job.website_preference === "must_be_missing"
                            ? "Website missing"
                            : "Website any"}
                      </Badge>
                      {job.radius_km ? <Badge tone="neutral">{job.radius_km} km radius</Badge> : null}
                      {job.keyword_filter ? <Badge tone="accent">{job.keyword_filter}</Badge> : null}
                    </div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-3">
                      <div className="rounded-xl border border-[color:var(--border)] px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">
                          Candidates
                        </p>
                        <p className="mt-1 font-semibold">{job.candidates_found}</p>
                      </div>
                      <div className="rounded-xl border border-[color:var(--border)] px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">
                          Upserted
                        </p>
                        <p className="mt-1 font-semibold">{job.leads_upserted}</p>
                      </div>
                      <div className="rounded-xl border border-[color:var(--border)] px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">
                          Errors
                        </p>
                        <p className="mt-1 font-semibold">{job.provider_error_count}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No search jobs"
                description="Use the form to persist your first scoped discovery request."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <CardContent className="flex gap-4 p-5">
            <SearchCheck className="mt-1 h-5 w-5 text-[color:var(--accent)]" />
            <div>
              <p className="font-semibold">Discovery flow</p>
              <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">
                Google Maps search finds candidates, maps place enrichment deepens selected
                records, and Google search validates web presence.
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex gap-4 p-5">
            <DatabaseZap className="mt-1 h-5 w-5 text-[color:var(--accent)]" />
            <div>
              <p className="font-semibold">Stored outputs</p>
              <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">
                Raw payloads, normalized facts, identities, and score breakdowns are all
                persisted separately for auditability.
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex gap-4 p-5">
            <Compass className="mt-1 h-5 w-5 text-[color:var(--accent)]" />
            <div>
              <p className="font-semibold">Scope discipline</p>
              <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">
                Keep the city, category, and filter bounds explicit so you can compare runs and
                explain score outcomes later.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
