import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Globe2, MapPinned } from "lucide-react";
import { Link } from "react-router-dom";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { listLeads } from "@/features/leads/api";
import { LeadMap } from "@/features/leads/components/lead-map";
import { listSearchJobs } from "@/features/searches/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { bandTone, formatDate, formatScore, statusTone, titleCaseLabel } from "@/lib/presenters";

export function DashboardPage() {
  useDocumentTitle("Overview");

  const leadsQuery = useQuery({
    queryKey: ["leads", "overview"],
    queryFn: () => listLeads({ page_size: 100 }),
  });
  const jobsQuery = useQuery({
    queryKey: ["search-jobs", "overview"],
    queryFn: listSearchJobs,
  });

  const leads = leadsQuery.data?.items ?? [];
  const jobs = jobsQuery.data?.items ?? [];
  const qualified = leads.filter((lead) => lead.status === "qualified").length;
  const highBand = leads.filter((lead) => lead.latest_band === "high").length;
  const withWebsite = leads.filter((lead) => lead.has_website).length;
  const mappable = leads.filter((lead) => lead.lat !== null && lead.lng !== null).length;
  const runningJobs = jobs.filter((job) => job.status === "queued" || job.status === "running").length;
  const topLeads = [...leads].sort((a, b) => (b.latest_score ?? 0) - (a.latest_score ?? 0)).slice(0, 6);
  const cityBreakdown = Object.entries(
    leads.reduce<Record<string, number>>((accumulator, lead) => {
      const key = lead.city ?? "Unknown";
      accumulator[key] = (accumulator[key] ?? 0) + 1;
      return accumulator;
    }, {}),
  )
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

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
        description="Fetching lead coverage, score bands, and recent job activity from the API."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Overview"
        title="Lead desk snapshot"
        description="Monitor the current lead pool, recent provider runs, and the quality signals that shape qualification decisions."
        action={
          <Button asChild>
            <Link to="/searches">
              Launch search
              <ArrowRight className="ms-2 h-4 w-4" />
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {[
          ["Total leads", leads.length],
          ["High band leads", highBand],
          ["Qualified leads", qualified],
          ["Website coverage", withWebsite],
          ["Active jobs", runningJobs],
        ].map(([label, value]) => (
          <Card key={label}>
            <CardContent className="p-5">
              <p className="text-sm text-[color:var(--muted)]">{label}</p>
              <p className="mt-3 text-3xl font-extrabold">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Lead geography</CardTitle>
            <CardDescription>Map markers reflect persisted lead coordinates from provider evidence and current score coverage.</CardDescription>
          </CardHeader>
          <CardContent className="h-[360px] p-3">
            {mappable === 0 ? (
              <EmptyState
                title="No mappable leads yet"
                description="Once provider normalization stores coordinates, the desk will center the current lead geography here."
                className="h-full"
              />
            ) : (
              <LeadMap className="h-full" leads={leads} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Coverage snapshot</CardTitle>
            <CardDescription>Operational counts derived from stored lead records and score bands.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                <MapPinned className="h-4 w-4 text-[color:var(--accent)]" />
                <p className="mt-3 text-sm text-[color:var(--muted)]">Mappable leads</p>
                <p className="mt-2 text-2xl font-extrabold">{mappable}</p>
              </div>
              <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                <Globe2 className="h-4 w-4 text-[color:var(--accent)]" />
                <p className="mt-3 text-sm text-[color:var(--muted)]">Web-ready leads</p>
                <p className="mt-2 text-2xl font-extrabold">{withWebsite}</p>
              </div>
            </div>
            <div className="space-y-3">
              {cityBreakdown.length === 0 ? (
                <p className="text-sm text-[color:var(--muted)]">City counts will appear once leads are available.</p>
              ) : (
                cityBreakdown.map(([city, count]) => (
                  <div key={city} className="flex items-center justify-between rounded-2xl border border-[color:var(--border)] px-4 py-3">
                    <div>
                      <p className="font-semibold">{city}</p>
                      <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Captured leads</p>
                    </div>
                    <Badge tone="accent">{count}</Badge>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <CardTitle>Priority leads</CardTitle>
            <CardDescription>Highest scoring leads in the current workspace, sorted from the latest persisted score.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {leads.length === 0 ? (
              <EmptyState
                title="No leads yet"
                description="Create a search job and let the provider pipeline populate normalized evidence and scores."
              />
            ) : (
              topLeads.map((lead) => (
                <div
                  key={lead.public_id}
                  className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-bold">{lead.company_name}</p>
                      <p className="text-sm text-[color:var(--muted)]">
                        {lead.city ?? "Unknown city"} · {lead.website_domain ?? "No website"}
                      </p>
                    </div>
                    <Badge tone={bandTone(lead.latest_band)}>
                      {lead.latest_band ? titleCaseLabel(lead.latest_band) : "Unscored"}
                    </Badge>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Badge tone={statusTone(lead.status)}>{titleCaseLabel(lead.status)}</Badge>
                    <Badge tone="neutral">{formatScore(lead.latest_score)}</Badge>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent discovery runs</CardTitle>
            <CardDescription>Search jobs queued through the API with background discovery and score persistence.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-[color:var(--muted)]">
            {jobs.length === 0 ? (
              <EmptyState
                title="No search jobs"
                description="Queue the first local discovery run to start collecting provider-backed lead evidence."
              />
            ) : (
              jobs.slice(0, 5).map((job) => (
                <div key={job.public_id} className="rounded-2xl border border-[color:var(--border)] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-[color:var(--text)]">
                        {job.business_type} in {job.city}
                        {job.region ? `, ${job.region}` : ""}
                      </p>
                      <p className="mt-1 text-xs uppercase tracking-[0.16em]">
                        Queued {formatDate(job.queued_at)}
                      </p>
                    </div>
                    <Badge tone={job.status === "completed" ? "warning" : "accent"}>
                      {titleCaseLabel(job.status)}
                    </Badge>
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl bg-[color:var(--surface-soft)] px-3 py-2">
                      <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">Candidates</p>
                      <p className="mt-1 font-semibold text-[color:var(--text)]">{job.candidates_found}</p>
                    </div>
                    <div className="rounded-xl bg-[color:var(--surface-soft)] px-3 py-2">
                      <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">Leads upserted</p>
                      <p className="mt-1 font-semibold text-[color:var(--text)]">{job.leads_upserted}</p>
                    </div>
                    <div className="rounded-xl bg-[color:var(--surface-soft)] px-3 py-2">
                      <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">Provider errors</p>
                      <p className="mt-1 font-semibold text-[color:var(--text)]">{job.provider_error_count}</p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
