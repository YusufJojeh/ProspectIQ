import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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

const searchSchema = z.object({
  business_type: z.string().min(2),
  city: z.string().min(2),
  region: z.string().optional(),
  max_results: z.coerce.number().int().min(1).max(100),
  min_rating: z.union([z.coerce.number().min(0).max(5), z.literal("")]).optional(),
  min_reviews: z.union([z.coerce.number().int().min(0), z.literal("")]).optional(),
  require_website: z.boolean().default(false),
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
      max_results: 25,
      min_rating: "",
      min_reviews: "",
      require_website: false,
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
        max_results: values.max_results,
        min_rating: values.min_rating === "" ? undefined : values.min_rating,
        min_reviews: values.min_reviews === "" ? undefined : values.min_reviews,
        require_website: values.require_website,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["search-jobs"] });
      form.reset({
        business_type: "",
        city: "",
        region: "",
        max_results: 25,
        min_rating: "",
        min_reviews: "",
        require_website: false,
      });
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Search jobs"
        title="Launch a scoped lead discovery run"
        description="Persist a real search request now. Provider orchestration is intentionally held for the next implementation phase."
      />

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <CardTitle>Create job</CardTitle>
            <CardDescription>Use explicit inputs so the later provider pipeline remains deterministic.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
              <div className="space-y-2">
                <label className="text-sm font-semibold">Business type</label>
                <Input placeholder="Dentist, lawyer, clinic, salon" {...form.register("business_type")} />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-semibold">City</label>
                  <Input placeholder="Istanbul" {...form.register("city")} />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Region</label>
                  <Input placeholder="Marmara" {...form.register("region")} />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Max results</label>
                  <Input type="number" min={1} max={100} {...form.register("max_results")} />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Min rating</label>
                  <Input type="number" min={0} max={5} step="0.1" {...form.register("min_rating")} />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Min reviews</label>
                  <Input type="number" min={0} {...form.register("min_reviews")} />
                </div>
              </div>

              <label className="flex items-center gap-3 rounded-xl border border-[color:var(--border)] bg-white px-3 py-2.5 text-sm">
                <input type="checkbox" {...form.register("require_website")} />
                Require website
              </label>

              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Submitting..." : "Queue search job"}
              </Button>
              {mutation.error ? <p className="text-sm text-red-600">{mutation.error.message}</p> : null}
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Queued jobs</CardTitle>
            <CardDescription>Jobs are stored now. Background discovery is not wired during the foundation phase.</CardDescription>
          </CardHeader>
          <CardContent>
            {jobsQuery.isError ? (
              <p className="text-sm text-red-600">{jobsQuery.error.message}</p>
            ) : jobsQuery.data?.items.length ? (
              <div className="space-y-3">
                {jobsQuery.data.items.map((job) => (
                  <div
                    key={job.public_id}
                    className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-bold">{job.business_type}</p>
                        <p className="text-sm text-[color:var(--muted)]">
                          {job.city}
                          {job.region ? `, ${job.region}` : ""}
                        </p>
                      </div>
                      <Badge tone="accent">{job.status}</Badge>
                    </div>
                    <p className="mt-3 text-sm text-[color:var(--muted)]">
                      Max results {job.max_results}, leads upserted {job.leads_upserted}, provider errors {job.provider_error_count}.
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No search jobs"
                description="Use the form to persist your first scoped search request."
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
