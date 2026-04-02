import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Search, ShieldCheck, Workflow } from "lucide-react";
import { Link } from "react-router-dom";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { listLeads } from "@/features/leads/api";
import { listSearchJobs } from "@/features/searches/api";
import { useDocumentTitle } from "@/hooks/use-document-title";

export function DashboardPage() {
  useDocumentTitle("Overview");

  const leadsQuery = useQuery({
    queryKey: ["leads", "overview"],
    queryFn: listLeads,
  });
  const jobsQuery = useQuery({
    queryKey: ["search-jobs", "overview"],
    queryFn: listSearchJobs,
  });

  const leads = leadsQuery.data?.items ?? [];
  const jobs = jobsQuery.data?.items ?? [];
  const qualified = leads.filter((lead) => lead.status === "qualified").length;
  const highBand = leads.filter((lead) => lead.latest_band === "high").length;

  if (leadsQuery.isError || jobsQuery.isError) {
    return (
      <EmptyState
        title="Workspace data could not load"
        description="Make sure the API is running, the database is migrated, and the current session token is valid."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Overview"
        title="Lead desk snapshot"
        description="A compact view of the current repository foundation and the persisted data already available from the backend."
        action={
          <Link to="/searches">
            <Button>
              Launch search
              <ArrowRight className="ms-2 h-4 w-4" />
            </Button>
          </Link>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-[color:var(--muted)]">Search jobs</p>
            <p className="mt-3 text-3xl font-extrabold">{jobs.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-[color:var(--muted)]">High band leads</p>
            <p className="mt-3 text-3xl font-extrabold">{highBand}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-[color:var(--muted)]">Qualified leads</p>
            <p className="mt-3 text-3xl font-extrabold">{qualified}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Current system state</CardTitle>
            <CardDescription>This shell uses live API responses only. Empty states replace fabricated examples.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {leads.length === 0 ? (
              <EmptyState
                title="No leads yet"
                description="Create a search job after signing in. Leads will appear here when the discovery pipeline begins persisting normalized evidence."
              />
            ) : (
              leads.slice(0, 5).map((lead) => (
                <div
                  key={lead.public_id}
                  className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-bold">{lead.company_name}</p>
                      <p className="text-sm text-[color:var(--muted)]">{lead.city ?? "Unknown city"}</p>
                    </div>
                    <Badge tone={lead.latest_band === "high" ? "warning" : "accent"}>
                      {lead.latest_band ?? "unscored"}
                    </Badge>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Foundation boundaries</CardTitle>
            <CardDescription>The repository is wired to run locally without pretending unfinished phases already exist.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-[color:var(--muted)]">
            <div className="rounded-xl border border-[color:var(--border)] p-4">
              <div className="flex items-center gap-2 font-semibold text-[color:var(--text)]">
                <Search className="h-4 w-4 text-[color:var(--accent)]" />
                Search jobs are real records
              </div>
              <p className="mt-2">The backend now persists queued jobs without fake provider orchestration or fabricated leads.</p>
            </div>
            <div className="rounded-xl border border-[color:var(--border)] p-4">
              <div className="flex items-center gap-2 font-semibold text-[color:var(--text)]">
                <ShieldCheck className="h-4 w-4 text-[color:var(--accent)]" />
                Auth is workspace-aware
              </div>
              <p className="mt-2">Login requires the workspace public id, matching the backend contract and seed data.</p>
            </div>
            <div className="rounded-xl border border-[color:var(--border)] p-4">
              <div className="flex items-center gap-2 font-semibold text-[color:var(--text)]">
                <Workflow className="h-4 w-4 text-[color:var(--accent)]" />
                Unfinished flows are explicit
              </div>
              <p className="mt-2">AI analysis, outreach generation, and SerpAPI orchestration stay disabled until their production paths are implemented.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
