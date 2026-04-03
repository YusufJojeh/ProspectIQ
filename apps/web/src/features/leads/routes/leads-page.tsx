import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Download, RefreshCw, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  assignLead,
  analyzeLead,
  downloadLeadsExport,
  generateLeadOutreach,
  getLead,
  listLeads,
  refreshLead,
  updateLeadStatus,
} from "@/features/leads/api";
import { LeadMap } from "@/features/leads/components/lead-map";
import { listSearchJobs } from "@/features/searches/api";
import { listUsers } from "@/features/users/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { bandTone, formatScore, statusTone, titleCaseLabel } from "@/lib/presenters";
import type {
  LeadAnalysisResult,
  LeadScoreBand,
  LeadSortOption,
  LeadStatus,
  OutreachMessageResult,
  OutreachTone,
} from "@/types/api";

export function LeadsPage() {
  useDocumentTitle("Leads");
  const queryClient = useQueryClient();
  const [q, setQ] = useState("");
  const [city, setCity] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState<LeadStatus | "all">("all");
  const [band, setBand] = useState<LeadScoreBand | "all">("all");
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [qualified, setQualified] = useState<"all" | "true" | "false">("all");
  const [ownerUserId, setOwnerUserId] = useState<"all" | string>("all");
  const [hasWebsite, setHasWebsite] = useState<"all" | "true" | "false">("all");
  const [searchJobId, setSearchJobId] = useState<"all" | string>("all");
  const [sort, setSort] = useState<LeadSortOption>("score_desc");
  const [outreachTone, setOutreachTone] = useState<OutreachTone>("consultative");
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [analysisPreview, setAnalysisPreview] = useState<LeadAnalysisResult | null>(null);
  const [outreachPreview, setOutreachPreview] = useState<OutreachMessageResult | null>(null);

  const leadFilters = {
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
  } as const;

  const leadsQuery = useQuery({
    queryKey: ["leads", "table", leadFilters],
    queryFn: () => listLeads(leadFilters),
  });
  const jobsQuery = useQuery({
    queryKey: ["search-jobs", "filters"],
    queryFn: listSearchJobs,
  });
  const usersQuery = useQuery({
    queryKey: ["users", "workspace"],
    queryFn: listUsers,
  });
  const selectedLeadQuery = useQuery({
    queryKey: ["lead", selectedLeadId, "workspace-panel"],
    queryFn: () => getLead(selectedLeadId ?? ""),
    enabled: Boolean(selectedLeadId),
  });

  useEffect(() => {
    const leads = leadsQuery.data?.items ?? [];
    if (leads.length === 0) {
      setSelectedLeadId(null);
      return;
    }
    if (!selectedLeadId || !leads.some((lead) => lead.public_id === selectedLeadId)) {
      setSelectedLeadId(leads[0].public_id);
    }
  }, [leadsQuery.data?.items, selectedLeadId]);

  useEffect(() => {
    setAnalysisPreview(null);
    setOutreachPreview(null);
  }, [selectedLeadId]);

  const invalidateLeadQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["leads"] });
    queryClient.invalidateQueries({ queryKey: ["lead"] });
  };

  const statusMutation = useMutation({
    mutationFn: ({ leadId, nextStatus }: { leadId: string; nextStatus: LeadStatus }) =>
      updateLeadStatus(leadId, nextStatus),
    onSuccess: invalidateLeadQueries,
  });
  const assignMutation = useMutation({
    mutationFn: ({ leadId, assigneeId }: { leadId: string; assigneeId: string | null }) =>
      assignLead(leadId, assigneeId),
    onSuccess: invalidateLeadQueries,
  });
  const analysisMutation = useMutation({
    mutationFn: (leadId: string) => analyzeLead(leadId),
    onSuccess: (payload) => setAnalysisPreview(payload.analysis),
  });
  const outreachMutation = useMutation({
    mutationFn: (leadId: string) => generateLeadOutreach(leadId, { tone: outreachTone }),
    onSuccess: (payload) => setOutreachPreview(payload.message),
  });
  const refreshMutation = useMutation({
    mutationFn: (leadId: string) => refreshLead(leadId),
    onSuccess: (payload) => {
      invalidateLeadQueries();
      setSelectedLeadId(payload.public_id);
      setAnalysisPreview(null);
      setOutreachPreview(null);
    },
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
        description="Fetching leads, owner options, and search-job filters from the API."
      />
    );
  }

  const leads = leadsQuery.data.items;
  const selectedLead = selectedLeadQuery.data ?? leads.find((lead) => lead.public_id === selectedLeadId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Leads"
        title="Qualification workspace"
        description="Filter live leads, inspect score signals, navigate the current geography, and draft the next action from stored evidence."
        action={
          <Button
            variant="secondary"
            onClick={() => void downloadLeadsExport(leadFilters)}
          >
            <Download className="me-2 h-4 w-4" />
            Export CSV
          </Button>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Filters</CardTitle>
              <CardDescription>Table, map, and export all use the same backend query filters.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <Input aria-label="Search leads" placeholder="Search company, city, domain" value={q} onChange={(event) => setQ(event.target.value)} />
              <Input aria-label="Filter leads by city" placeholder="Filter by city" value={city} onChange={(event) => setCity(event.target.value)} />
              <Input aria-label="Filter leads by category" placeholder="Filter by category" value={category} onChange={(event) => setCategory(event.target.value)} />
              <Select aria-label="Filter leads by search job" value={searchJobId} onChange={(event) => setSearchJobId(event.target.value)}>
                <option value="all">All search jobs</option>
                {(jobsQuery.data?.items ?? []).map((job) => (
                  <option key={job.public_id} value={job.public_id}>
                    {job.business_type} / {job.city}
                  </option>
                ))}
              </Select>
              <Select aria-label="Filter leads by status" value={status} onChange={(event) => setStatus(event.target.value as LeadStatus | "all")}>
                <option value="all">All statuses</option>
                <option value="new">New</option>
                <option value="reviewed">Reviewed</option>
                <option value="qualified">Qualified</option>
                <option value="contacted">Contacted</option>
                <option value="interested">Interested</option>
                <option value="won">Won</option>
                <option value="lost">Lost</option>
                <option value="archived">Archived</option>
              </Select>
              <Select aria-label="Filter leads by score band" value={band} onChange={(event) => setBand(event.target.value as LeadScoreBand | "all")}>
                <option value="all">All score bands</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="not_qualified">Not qualified</option>
              </Select>
              <Select aria-label="Filter leads by qualification" value={qualified} onChange={(event) => setQualified(event.target.value as "all" | "true" | "false")}>
                <option value="all">Any qualification</option>
                <option value="true">Qualified only</option>
                <option value="false">Needs qualification</option>
              </Select>
              <Select aria-label="Filter leads by website state" value={hasWebsite} onChange={(event) => setHasWebsite(event.target.value as "all" | "true" | "false")}>
                <option value="all">Any website state</option>
                <option value="true">Has website</option>
                <option value="false">Missing website</option>
              </Select>
              <Select aria-label="Filter leads by owner" value={ownerUserId} onChange={(event) => setOwnerUserId(event.target.value)}>
                <option value="all">Any owner</option>
                {(usersQuery.data?.items ?? []).map((user) => (
                  <option key={user.public_id} value={user.public_id}>
                    {user.full_name}
                  </option>
                ))}
              </Select>
              <Input
                aria-label="Minimum lead score"
                type="number"
                min="0"
                max="100"
                placeholder="Min score"
                value={minScore}
                onChange={(event) => setMinScore(event.target.value)}
              />
              <Input
                aria-label="Maximum lead score"
                type="number"
                min="0"
                max="100"
                placeholder="Max score"
                value={maxScore}
                onChange={(event) => setMaxScore(event.target.value)}
              />
              <Select aria-label="Sort leads" value={sort} onChange={(event) => setSort(event.target.value as LeadSortOption)}>
                <option value="score_desc">Sort by score</option>
                <option value="reviews_desc">Sort by reviews</option>
                <option value="rating_desc">Sort by rating</option>
                <option value="newest">Sort by newest</option>
              </Select>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Lead queue</CardTitle>
              <CardDescription>Rows remain tied to live API data and persisted score bands.</CardDescription>
            </CardHeader>
            <CardContent className="overflow-hidden p-0">
              {leads.length === 0 ? (
                <div className="p-5">
                  <EmptyState
                    title="No leads match the current filters"
                    description="Adjust the filters or queue another discovery job to expand the current lead pool."
                  />
                </div>
              ) : (
                <div className="space-y-3 p-4">
                  <div className="space-y-3 md:hidden">
                    {leads.map((lead) => (
                      <button
                        key={lead.public_id}
                        className={
                          lead.public_id === selectedLeadId
                            ? "w-full rounded-[1.4rem] border border-[color:var(--accent)]/35 bg-[color:var(--accent-soft)]/60 p-4 text-left shadow-[0_18px_34px_-28px_rgba(15,118,110,0.55)]"
                            : "w-full rounded-[1.4rem] border border-[color:var(--border)] bg-white/72 p-4 text-left"
                        }
                        onClick={() => setSelectedLeadId(lead.public_id)}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <Link
                              className="text-base font-bold hover:text-[color:var(--accent)]"
                              to={appPaths.leadDetail(lead.public_id)}
                            >
                              {lead.company_name}
                            </Link>
                            <p className="mt-1 text-sm text-[color:var(--muted)]">{lead.city ?? "Unknown"}</p>
                          </div>
                          <Badge tone={bandTone(lead.latest_band)}>
                            {lead.latest_band ? titleCaseLabel(lead.latest_band) : "Unscored"}
                          </Badge>
                        </div>

                        <div className="mt-4 flex flex-wrap gap-2">
                          <Badge tone={statusTone(lead.status)}>{titleCaseLabel(lead.status)}</Badge>
                          <Badge tone={lead.latest_qualified ? "warning" : "neutral"}>
                            {lead.latest_qualified ? "Qualified" : "Review"}
                          </Badge>
                          <Badge tone="neutral">{formatScore(lead.latest_score)}</Badge>
                        </div>

                        <div className="mt-4 grid gap-3 sm:grid-cols-2">
                          <div>
                            <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Website</p>
                            <p className="mt-1 text-sm font-semibold">{lead.website_domain ?? "Missing"}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Reviews</p>
                            <p className="mt-1 text-sm font-semibold">{lead.review_count}</p>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>

                  <div className="hidden overflow-x-auto md:block">
                    <table className="min-w-full divide-y divide-[color:var(--border)] text-left text-sm">
                      <thead className="bg-[color:var(--surface-soft)] text-[color:var(--muted)]">
                        <tr>
                          <th className="px-5 py-3 font-semibold">Company</th>
                          <th className="px-5 py-3 font-semibold">City</th>
                          <th className="px-5 py-3 font-semibold">Band</th>
                          <th className="px-5 py-3 font-semibold">Score</th>
                          <th className="px-5 py-3 font-semibold">Qualified</th>
                          <th className="px-5 py-3 font-semibold">Status</th>
                          <th className="px-5 py-3 font-semibold">Website</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[color:var(--border)]">
                        {leads.map((lead) => (
                          <tr
                            key={lead.public_id}
                            className={
                              lead.public_id === selectedLeadId
                                ? "cursor-pointer bg-[color:var(--accent-soft)]/60 outline-none focus-visible:bg-[color:var(--accent-soft)]/75"
                                : "cursor-pointer bg-white/70 outline-none focus-visible:bg-[color:var(--surface-soft)]"
                            }
                            onClick={() => setSelectedLeadId(lead.public_id)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                setSelectedLeadId(lead.public_id);
                              }
                            }}
                            tabIndex={0}
                            role="button"
                            aria-pressed={lead.public_id === selectedLeadId}
                          >
                            <td className="px-5 py-4">
                              <Link
                                className="font-semibold hover:text-[color:var(--accent)]"
                                to={appPaths.leadDetail(lead.public_id)}
                              >
                                {lead.company_name}
                              </Link>
                            </td>
                            <td className="px-5 py-4 text-[color:var(--muted)]">{lead.city ?? "Unknown"}</td>
                            <td className="px-5 py-4">
                              <Badge tone={bandTone(lead.latest_band)}>
                                {lead.latest_band ? titleCaseLabel(lead.latest_band) : "Unscored"}
                              </Badge>
                            </td>
                            <td className="px-5 py-4">{formatScore(lead.latest_score)}</td>
                            <td className="px-5 py-4">
                              <Badge tone={lead.latest_qualified ? "warning" : "neutral"}>
                                {lead.latest_qualified ? "Qualified" : "Review"}
                              </Badge>
                            </td>
                            <td className="px-5 py-4">
                              <Badge tone={statusTone(lead.status)}>{titleCaseLabel(lead.status)}</Badge>
                            </td>
                            <td className="px-5 py-4 text-[color:var(--muted)]">
                              {lead.website_domain ?? "Missing"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Lead map</CardTitle>
              <CardDescription>Markers stay synchronized with the current filter set and selected lead.</CardDescription>
            </CardHeader>
            <CardContent className="h-[320px] p-3">
              {leads.filter((lead) => lead.lat !== null && lead.lng !== null).length === 0 ? (
                <EmptyState
                  title="No map coordinates available"
                  description="When provider evidence includes locations, matching leads will appear here."
                  className="h-full"
                />
              ) : (
                <LeadMap className="h-full" leads={leads} selectedLeadId={selectedLeadId} onSelect={setSelectedLeadId} />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Selected lead</CardTitle>
              <CardDescription>Use quick actions here, then open the full detail view for deeper evidence review.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!selectedLead ? (
                <p className="text-sm text-[color:var(--muted)]">Select a lead from the queue to inspect it.</p>
              ) : (
                <>
                  <div>
                    <p className="text-lg font-bold">{selectedLead.company_name}</p>
                    <p className="mt-1 text-sm text-[color:var(--muted)]">
                      {selectedLead.city ?? "Unknown city"} / {selectedLead.website_domain ?? "No website found"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={bandTone(selectedLead.latest_band)}>
                      {selectedLead.latest_band ? titleCaseLabel(selectedLead.latest_band) : "Unscored"}
                    </Badge>
                    <Badge tone={statusTone(selectedLead.status)}>{titleCaseLabel(selectedLead.status)}</Badge>
                    <Badge tone={selectedLead.latest_qualified ? "warning" : "neutral"}>
                      {selectedLead.latest_qualified ? "Qualified" : "Needs review"}
                    </Badge>
                    <Badge tone="neutral">{formatScore(selectedLead.latest_score)}</Badge>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                      <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Rating</p>
                      <p className="mt-2 text-xl font-extrabold">{selectedLead.rating ?? "N/A"}</p>
                    </div>
                    <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                      <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Reviews</p>
                      <p className="mt-2 text-xl font-extrabold">{selectedLead.review_count}</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Assign owner</label>
                    <Select
                      aria-label="Assign owner"
                      value={selectedLead.assigned_to_user_public_id ?? ""}
                      onChange={(event) =>
                        assignMutation.mutate({
                          leadId: selectedLead.public_id,
                          assigneeId: event.target.value || null,
                        })
                      }
                    >
                      <option value="">Unassigned</option>
                      {(usersQuery.data?.items ?? []).map((user) => (
                        <option key={user.public_id} value={user.public_id}>
                          {user.full_name}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <Button
                      variant="secondary"
                      onClick={() => statusMutation.mutate({ leadId: selectedLead.public_id, nextStatus: "reviewed" })}
                    >
                      Mark reviewed
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => statusMutation.mutate({ leadId: selectedLead.public_id, nextStatus: "qualified" })}
                    >
                      Mark qualified
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => statusMutation.mutate({ leadId: selectedLead.public_id, nextStatus: "contacted" })}
                    >
                      Mark contacted
                    </Button>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <Button
                      variant="secondary"
                      onClick={() => refreshMutation.mutate(selectedLead.public_id)}
                      disabled={refreshMutation.isPending}
                    >
                      <RefreshCw className="me-2 h-4 w-4" />
                      {refreshMutation.isPending ? "Refreshing..." : "Refresh lead"}
                    </Button>
                    <Button variant="secondary" onClick={() => analysisMutation.mutate(selectedLead.public_id)}>
                      <Sparkles className="me-2 h-4 w-4" />
                      Generate analysis
                    </Button>
                    <Button variant="secondary" onClick={() => outreachMutation.mutate(selectedLead.public_id)}>
                      Draft outreach
                    </Button>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Outreach tone</label>
                    <Select aria-label="Outreach tone" value={outreachTone} onChange={(event) => setOutreachTone(event.target.value as OutreachTone)}>
                      <option value="consultative">Consultative</option>
                      <option value="friendly">Friendly</option>
                      <option value="formal">Formal</option>
                      <option value="short_pitch">Short pitch</option>
                    </Select>
                  </div>
                  {analysisPreview ? (
                    <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                      <p className="font-semibold">Analysis summary</p>
                      <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">{analysisPreview.summary}</p>
                    </div>
                  ) : null}
                  {outreachPreview ? (
                    <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold">{outreachPreview.subject}</p>
                        <Badge tone="accent">{titleCaseLabel(outreachPreview.tone)}</Badge>
                      </div>
                      <p className="mt-2 whitespace-pre-line text-sm leading-6 text-[color:var(--muted)]">
                        {outreachPreview.message}
                      </p>
                    </div>
                  ) : null}
                  <Button asChild className="w-full justify-center">
                    <Link to={appPaths.leadDetail(selectedLead.public_id)}>
                      Open lead detail
                      <ArrowRight className="ms-2 h-4 w-4" />
                    </Link>
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
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
