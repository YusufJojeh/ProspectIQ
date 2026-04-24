import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Map, RefreshCw, Sparkles, Table2, LayoutGrid } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { LeadsCards } from "@/components/leads/leads-cards";
import { LeadsFiltersPanel } from "@/components/leads/filters-panel";
import { LeadsTable } from "@/components/leads/leads-table";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { generateLeadAnalysis } from "@/features/ai-analysis/api";
import { assignLead, downloadLeadsExport, getLead, listLeads, refreshLead, updateLeadStatus } from "@/features/leads/api";
import { generateLeadOutreach } from "@/features/outreach/api";
import { outreachDraftToMessagePreview } from "@/features/outreach/map-outreach-response";
import { listUsers } from "@/features/users/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { useSearchJobsQuery } from "@/hooks/use-search-jobs-query";
import { hasCoordinates } from "@/lib/maps";
import { bandTone, formatScore, statusTone, titleCaseLabel } from "@/lib/presenters";
import { LazyLeadMap } from "@/features/leads/components/lazy-lead-map";
import type {
  LeadAnalysisSnapshotResponse,
  LeadScoreBand,
  LeadSortOption,
  LeadStatus,
  OutreachMessageResult,
  OutreachTone,
} from "@/types/api";

type WorkspaceView = "table" | "cards" | "map";

export function LeadsPage() {
  useDocumentTitle("Leads");
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const searchJobIdParam = searchParams.get("search_job_id");
  const searchJobId = searchJobIdParam && searchJobIdParam.length > 0 ? searchJobIdParam : "all";
  const [view, setView] = useState<WorkspaceView>("table");
  const [q, setQ] = useState("");
  const [city, setCity] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState<LeadStatus | "all">("all");
  const [band, setBand] = useState<LeadScoreBand | "all">("all");
  const [qualified, setQualified] = useState<"all" | "true" | "false">("all");
  const [hasWebsite, setHasWebsite] = useState<"all" | "true" | "false">("all");
  const [ownerUserId, setOwnerUserId] = useState<"all" | string>("all");
  const [sort, setSort] = useState<LeadSortOption>("score_desc");
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [page, setPage] = useState(1);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [outreachTone, setOutreachTone] = useState<OutreachTone>("consultative");
  const [analysisPreview, setAnalysisPreview] = useState<LeadAnalysisSnapshotResponse | null>(null);
  const [outreachPreview, setOutreachPreview] = useState<OutreachMessageResult | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const leadFilters = useMemo(
    () =>
      ({
        page,
        page_size: 50,
        q: q || undefined,
        city: city || undefined,
        category: category || undefined,
        status,
        band,
        min_score: parseOptionalNumber(minScore),
        max_score: parseOptionalNumber(maxScore),
        qualified: qualified === "all" ? "all" : qualified === "true",
        owner_user_id: ownerUserId,
        search_job_id: searchJobId,
        has_website: hasWebsite === "all" ? "all" : hasWebsite === "true",
        sort,
      }) as const,
    [band, category, city, hasWebsite, maxScore, minScore, ownerUserId, page, q, qualified, searchJobId, sort, status],
  );

  const jobsQuery = useSearchJobsQuery();
  const searchJobs = useMemo(() => jobsQuery.data?.items ?? [], [jobsQuery.data?.items]);
  const leadsQuery = useQuery({
    queryKey: ["leads", "workspace", leadFilters],
    queryFn: () => listLeads(leadFilters),
    placeholderData: (previous) => previous,
  });
  const usersQuery = useQuery({
    queryKey: ["users", "workspace"],
    queryFn: listUsers,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
  const selectedLeadQuery = useQuery({
    queryKey: ["lead", selectedLeadId, "workspace-panel"],
    queryFn: () => getLead(selectedLeadId ?? ""),
    enabled: Boolean(selectedLeadId),
  });

  const leads = useMemo(() => leadsQuery.data?.items ?? [], [leadsQuery.data?.items]);
  const totalLeads = leadsQuery.data?.pagination.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalLeads / 50));
  const selectedLead = selectedLeadQuery.data ?? leads.find((lead) => lead.public_id === selectedLeadId) ?? null;
  const mappableLeads = leads.filter(hasCoordinates);
  const activeFilterCount = [
    q,
    city,
    category,
    status !== "all" ? status : "",
    band !== "all" ? band : "",
    qualified !== "all" ? qualified : "",
    hasWebsite !== "all" ? hasWebsite : "",
    ownerUserId !== "all" ? ownerUserId : "",
    searchJobId !== "all" ? searchJobId : "",
    minScore,
    maxScore,
  ].filter(Boolean).length;

  useEffect(() => {
    setPage(1);
  }, [q, city, category, status, band, qualified, hasWebsite, ownerUserId, searchJobId, sort, minScore, maxScore]);

  useEffect(() => {
    if (leads.length === 0) {
      setSelectedLeadId(null);
      setSelectedIds(new Set());
      return;
    }

    if (!selectedLeadId || !leads.some((lead) => lead.public_id === selectedLeadId)) {
      setSelectedLeadId(leads[0].public_id);
    }
  }, [leads, selectedLeadId]);

  useEffect(() => {
    setAnalysisPreview(null);
    setOutreachPreview(null);
    setActionSuccess(null);
  }, [selectedLeadId]);

  const invalidateLeadQueries = () => {
    void queryClient.invalidateQueries({ queryKey: ["leads"] });
    void queryClient.invalidateQueries({ queryKey: ["lead"] });
  };

  const statusMutation = useMutation({
    mutationFn: ({ leadId, nextStatus }: { leadId: string; nextStatus: LeadStatus }) => updateLeadStatus(leadId, nextStatus),
    onSuccess: (_payload, variables) => {
      invalidateLeadQueries();
      setActionSuccess(`Lead marked ${titleCaseLabel(variables.nextStatus)}.`);
    },
  });
  const assignMutation = useMutation({
    mutationFn: ({ leadId, assigneeId }: { leadId: string; assigneeId: string | null }) => assignLead(leadId, assigneeId),
    onSuccess: (_payload, variables) => {
      invalidateLeadQueries();
      setActionSuccess(variables.assigneeId ? "Lead owner updated." : "Lead owner cleared.");
    },
  });
  const analysisMutation = useMutation({
    mutationFn: (leadId: string) => generateLeadAnalysis(leadId),
    onSuccess: (payload, leadId) => {
      setAnalysisPreview(payload);
      void queryClient.invalidateQueries({ queryKey: ["lead", leadId, "analysis"] });
      setActionSuccess("Assistive analysis generated.");
    },
  });
  const outreachMutation = useMutation({
    mutationFn: (leadId: string) => generateLeadOutreach(leadId, { tone: outreachTone }),
    onSuccess: (payload, leadId) => {
      setOutreachPreview(outreachDraftToMessagePreview(payload));
      void queryClient.invalidateQueries({ queryKey: ["lead", leadId, "outreach"] });
      setActionSuccess("Outreach draft generated.");
    },
  });
  const refreshMutation = useMutation({
    mutationFn: (leadId: string) => refreshLead(leadId),
    onSuccess: (payload) => {
      invalidateLeadQueries();
      setSelectedLeadId(payload.public_id);
      setAnalysisPreview(null);
      setOutreachPreview(null);
      setActionSuccess("Lead refresh completed.");
    },
  });
  const exportMutation = useMutation({
    mutationFn: (leadIds?: string[]) =>
      leadIds && leadIds.length > 0 ? downloadLeadsExport({ lead_ids: leadIds }) : downloadLeadsExport(leadFilters),
  });

  if (leadsQuery.isError || jobsQuery.isError || usersQuery.isError) {
    return (
      <EmptyState
        title="Lead data is unavailable"
        description="Make sure the API is running and that the current session token is valid."
      />
    );
  }

  if (!leadsQuery.data || jobsQuery.isPending || usersQuery.isPending) {
    return (
      <QueryStateNotice
        tone="loading"
        title="Loading qualification workspace"
        description="Fetching leads, owners, and search-job filters from the API."
      />
    );
  }

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow="Leads"
        title="Evidence-first qualification workspace"
        description="The imported leads explorer is now active on the real route with a live filter rail, table or cards view, map mode, selection, and API-backed quick actions."
        actions={
          <>
            <Button
              variant="outline"
              className="bg-transparent"
              onClick={() => exportMutation.mutate(selectedIds.size ? Array.from(selectedIds) : undefined)}
              disabled={exportMutation.isPending}
            >
              <Download className="size-3.5" />
              {exportMutation.isPending ? "Exporting..." : selectedIds.size ? `Export ${selectedIds.size}` : "Export CSV"}
            </Button>
            {selectedLead ? (
              <Button asChild>
                <Link to={appPaths.leadDetail(selectedLead.public_id)}>Open lead detail</Link>
              </Button>
            ) : null}
          </>
        }
      />

      {exportMutation.isSuccess ? (
        <QueryStateNotice
          tone="success"
          title="Export started"
          description="The CSV download has been prepared from the current filters or selected leads."
        />
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <MetricCard label="Filtered leads" value={String(totalLeads)} helper="Current backend result set" />
        <MetricCard label="Mappable on page" value={String(mappableLeads.length)} helper="Visible markers in map mode" />
        <MetricCard label="Selected leads" value={String(selectedIds.size)} helper="Bulk export ready" />
      </section>

      <section className="grid gap-4 2xl:grid-cols-[320px_minmax(0,1fr)]">
        <LeadsFiltersPanel activeCount={activeFilterCount} onReset={resetFilters}>
          <FilterField label="Search">
            <Input value={q} onChange={(event) => setQ(event.target.value)} placeholder="Company, city, or domain" />
          </FilterField>
          <FilterField label="City">
            <Input value={city} onChange={(event) => setCity(event.target.value)} placeholder="Filter by city" />
          </FilterField>
          <FilterField label="Category">
            <Input value={category} onChange={(event) => setCategory(event.target.value)} placeholder="Filter by category" />
          </FilterField>
          <FilterField label="Search job">
            <Select
              value={searchJobId}
              onValueChange={(value) =>
                setSearchParams(
                  (prev) => {
                    const next = new URLSearchParams(prev);
                    if (value === "all") next.delete("search_job_id");
                    else next.set("search_job_id", value);
                    return next;
                  },
                  { replace: true },
                )
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="All search jobs" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All search jobs</SelectItem>
                {searchJobs.map((job) => (
                  <SelectItem key={job.public_id} value={job.public_id}>
                    {job.business_type} / {job.city}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label="Status">
            <Select value={status} onValueChange={(value) => setStatus(value as LeadStatus | "all")}>
              <SelectTrigger>
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="new">New</SelectItem>
                <SelectItem value="reviewed">Reviewed</SelectItem>
                <SelectItem value="qualified">Qualified</SelectItem>
                <SelectItem value="contacted">Contacted</SelectItem>
                <SelectItem value="interested">Interested</SelectItem>
                <SelectItem value="won">Won</SelectItem>
                <SelectItem value="lost">Lost</SelectItem>
                <SelectItem value="archived">Archived</SelectItem>
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label="Score band">
            <Select value={band} onValueChange={(value) => setBand(value as LeadScoreBand | "all")}>
              <SelectTrigger>
                <SelectValue placeholder="All score bands" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All score bands</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="not_qualified">Not qualified</SelectItem>
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label="Qualification">
            <Select value={qualified} onValueChange={(value) => setQualified(value as "all" | "true" | "false")}>
              <SelectTrigger>
                <SelectValue placeholder="Any qualification" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Any qualification</SelectItem>
                <SelectItem value="true">Qualified only</SelectItem>
                <SelectItem value="false">Needs qualification</SelectItem>
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label="Website">
            <Select value={hasWebsite} onValueChange={(value) => setHasWebsite(value as "all" | "true" | "false")}>
              <SelectTrigger>
                <SelectValue placeholder="Any website state" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Any website state</SelectItem>
                <SelectItem value="true">Has website</SelectItem>
                <SelectItem value="false">Missing website</SelectItem>
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label="Owner">
            <Select value={ownerUserId} onValueChange={setOwnerUserId}>
              <SelectTrigger>
                <SelectValue placeholder="Any owner" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Any owner</SelectItem>
                {(usersQuery.data?.items ?? []).map((user) => (
                  <SelectItem key={user.public_id} value={user.public_id}>
                    {user.full_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label="Sort">
            <Select value={sort} onValueChange={(value) => setSort(value as LeadSortOption)}>
              <SelectTrigger>
                <SelectValue placeholder="Sort" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="score_desc">Highest score</SelectItem>
                <SelectItem value="newest">Newest</SelectItem>
                <SelectItem value="reviews_desc">Most reviews</SelectItem>
                <SelectItem value="rating_desc">Best rating</SelectItem>
              </SelectContent>
            </Select>
          </FilterField>
          <div className="grid grid-cols-2 gap-3">
            <FilterField label="Min score">
              <Input type="number" value={minScore} onChange={(event) => setMinScore(event.target.value)} />
            </FilterField>
            <FilterField label="Max score">
              <Input type="number" value={maxScore} onChange={(event) => setMaxScore(event.target.value)} />
            </FilterField>
          </div>
        </LeadsFiltersPanel>

        <div className="space-y-4">
          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>Live workspace</CardTitle>
                  <CardDescription>
                    Imported table, cards, and map modes are now all backed by the active lead query and selection state.
                  </CardDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  <ViewButton active={view === "table"} onClick={() => setView("table")} icon={<Table2 className="size-3.5" />}>
                    Table
                  </ViewButton>
                  <ViewButton active={view === "cards"} onClick={() => setView("cards")} icon={<LayoutGrid className="size-3.5" />}>
                    Cards
                  </ViewButton>
                  <ViewButton active={view === "map"} onClick={() => setView("map")} icon={<Map className="size-3.5" />}>
                    Map
                  </ViewButton>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral">{totalLeads} matching leads</Badge>
                <Badge tone="accent">{selectedIds.size} selected</Badge>
                {selectedLead ? <Badge tone={bandTone(selectedLead.latest_band)}>{selectedLead.company_name}</Badge> : null}
              </div>

              {leads.length === 0 ? (
                <EmptyState
                  title="No leads match the current filters"
                  description="Adjust the filters or queue another discovery job to expand the current lead pool."
                />
              ) : view === "table" ? (
                <LeadsTable
                  leads={leads}
                  selectedLeadId={selectedLeadId}
                  selectedIds={selectedIds}
                  onSelectLead={setSelectedLeadId}
                  onToggleSelect={toggleSelected}
                />
              ) : view === "cards" ? (
                <LeadsCards leads={leads} selectedIds={selectedIds} onToggleSelect={toggleSelected} />
              ) : mappableLeads.length === 0 ? (
                <EmptyState
                  title="No map coordinates available"
                  description="When provider evidence includes location data, matching leads will appear here."
                />
              ) : (
                <div className="h-[520px] overflow-hidden rounded-2xl border border-border">
                  <LazyLeadMap className="h-full" leads={mappableLeads} selectedLeadId={selectedLeadId} onSelect={setSelectedLeadId} />
                </div>
              )}

              {totalLeads > 0 ? (
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
                  <p className="text-sm text-muted-foreground">
                    Showing {(page - 1) * 50 + 1} - {Math.min(page * 50, totalLeads)} of {totalLeads} leads
                  </p>
                  <div className="flex w-full gap-2 sm:w-auto">
                    <Button variant="outline" className="bg-transparent" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
                      Previous
                    </Button>
                    <Button variant="outline" className="bg-transparent" disabled={page >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>
                      Next
                    </Button>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>Selected lead workspace</CardTitle>
              <CardDescription>
                The imported quick-action area is now tied to the current API-backed lead record and owner list.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedLeadId && selectedLeadQuery.isPending ? (
                <QueryStateNotice
                  tone="loading"
                  title="Refreshing selected lead"
                  description="Loading the latest record for quick actions and preview panels."
                />
              ) : null}

              {actionSuccess ? <QueryStateNotice tone="success" title="Action completed" description={actionSuccess} /> : null}

              {!selectedLead ? (
                <EmptyState
                  title="No lead selected"
                  description="Pick a lead from the workspace to review score signals and trigger quick actions."
                />
              ) : (
                <>
                  <div>
                    <p className="text-lg font-semibold">{selectedLead.company_name}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {selectedLead.city ?? "Unknown city"} · {selectedLead.website_domain ?? "No website found"}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Badge tone={bandTone(selectedLead.latest_band)}>{selectedLead.latest_band ? titleCaseLabel(selectedLead.latest_band) : "Unscored"}</Badge>
                    <Badge tone={statusTone(selectedLead.status)}>{titleCaseLabel(selectedLead.status)}</Badge>
                    <Badge tone={selectedLead.latest_qualified ? "success" : "warning"}>
                      {selectedLead.latest_qualified ? "Qualified" : "Needs review"}
                    </Badge>
                    <Badge tone="neutral">{formatScore(selectedLead.latest_score)}</Badge>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <SignalCard label="Rating" value={selectedLead.rating ? String(selectedLead.rating) : "N/A"} />
                    <SignalCard label="Reviews" value={String(selectedLead.review_count)} />
                  </div>

                  <div className="space-y-2">
                    <Label>Assign owner</Label>
                    <Select
                      value={selectedLead.assigned_to_user_public_id ?? "unassigned"}
                      disabled={assignMutation.isPending}
                      onValueChange={(value) =>
                        assignMutation.mutate({
                          leadId: selectedLead.public_id,
                          assigneeId: value === "unassigned" ? null : value,
                        })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Unassigned" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="unassigned">Unassigned</SelectItem>
                        {(usersQuery.data?.items ?? []).map((user) => (
                          <SelectItem key={user.public_id} value={user.public_id}>
                            {user.full_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid gap-2 sm:grid-cols-3">
                    <Button variant="outline" className="bg-transparent" onClick={() => statusMutation.mutate({ leadId: selectedLead.public_id, nextStatus: "reviewed" })}>
                      Mark reviewed
                    </Button>
                    <Button variant="outline" className="bg-transparent" onClick={() => statusMutation.mutate({ leadId: selectedLead.public_id, nextStatus: "qualified" })}>
                      Mark qualified
                    </Button>
                    <Button variant="outline" className="bg-transparent" onClick={() => statusMutation.mutate({ leadId: selectedLead.public_id, nextStatus: "contacted" })}>
                      Mark contacted
                    </Button>
                  </div>

                  <div className="grid gap-2 sm:grid-cols-3">
                    <Button variant="outline" className="bg-transparent" onClick={() => refreshMutation.mutate(selectedLead.public_id)} disabled={refreshMutation.isPending}>
                      <RefreshCw className="size-3.5" />
                      {refreshMutation.isPending ? "Refreshing..." : "Refresh"}
                    </Button>
                    <Button variant="outline" className="bg-transparent" onClick={() => analysisMutation.mutate(selectedLead.public_id)} disabled={analysisMutation.isPending}>
                      <Sparkles className="size-3.5" />
                      {analysisMutation.isPending ? "Generating..." : "Generate analysis"}
                    </Button>
                    <Button onClick={() => outreachMutation.mutate(selectedLead.public_id)} disabled={outreachMutation.isPending}>
                      {outreachMutation.isPending ? "Drafting..." : "Draft outreach"}
                    </Button>
                  </div>

                  <div className="space-y-2">
                    <Label>Outreach tone</Label>
                    <Select value={outreachTone} onValueChange={(value) => setOutreachTone(value as OutreachTone)}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select tone" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="consultative">Consultative</SelectItem>
                        <SelectItem value="friendly">Friendly</SelectItem>
                        <SelectItem value="formal">Formal</SelectItem>
                        <SelectItem value="short_pitch">Short pitch</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {analysisPreview ? (
                    <div className="rounded-2xl border border-border bg-muted/20 p-4">
                      <p className="font-medium">Latest generated analysis</p>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{analysisPreview.analysis.summary}</p>
                    </div>
                  ) : null}
                  {outreachPreview ? (
                    <div className="rounded-2xl border border-border bg-muted/20 p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{outreachPreview.subject}</p>
                        <Badge tone="accent">{titleCaseLabel(outreachPreview.tone)}</Badge>
                      </div>
                      <p className="mt-2 whitespace-pre-line text-sm leading-6 text-muted-foreground">{outreachPreview.message}</p>
                    </div>
                  ) : null}

                  <Button asChild className="w-full">
                    <Link to={appPaths.leadDetail(selectedLead.public_id)}>Open full lead detail</Link>
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );

  function resetFilters() {
    setQ("");
    setCity("");
    setCategory("");
    setStatus("all");
    setBand("all");
    setQualified("all");
    setHasWebsite("all");
    setOwnerUserId("all");
    setSort("score_desc");
    setMinScore("");
    setMaxScore("");
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("search_job_id");
      return next;
    });
  }

  function toggleSelected(leadId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(leadId)) next.delete(leadId);
      else next.add(leadId);
      return next;
    });
  }
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

function FilterField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <Label tone="muted" className="text-xs font-semibold uppercase tracking-[0.16em]">
        {label}
      </Label>
      {children}
    </div>
  );
}

function ViewButton({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Button
      variant={active ? "default" : "outline"}
      className={active ? "flex-1 sm:flex-none" : "flex-1 bg-transparent sm:flex-none"}
      onClick={onClick}
    >
      {icon}
      {children}
    </Button>
  );
}

function SignalCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-xl font-semibold">{value}</p>
    </div>
  );
}

function parseOptionalNumber(value: string) {
  if (value.trim().length === 0) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}
