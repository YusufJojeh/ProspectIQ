import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Map, RefreshCw, Sparkles, Table2, LayoutGrid } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { LeadsCards } from "@/components/leads/leads-cards";
import { LeadsFiltersPanel } from "@/components/leads/filters-panel";
import { LeadsTable } from "@/components/leads/leads-table";
import { QuickFilterBar } from "@/components/leads/quick-filter-bar";
import { useColumnVisibility } from "@/hooks/use-column-visibility";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
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
import { leadStatusLabel, scoreBandLabel } from "@/lib/i18n-labels";
import { bandTone, formatScore, statusTone } from "@/lib/presenters";
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
  const { t } = useTranslation();
  useDocumentTitle(t("leads.title"));
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
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100]);
  const [hasPhone, setHasPhone] = useState(false);
  const [columnVisibility, toggleColumn] = useColumnVisibility();
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
        min_score: scoreRange[0] > 0 ? scoreRange[0] : parseOptionalNumber(minScore),
        max_score: scoreRange[1] < 100 ? scoreRange[1] : parseOptionalNumber(maxScore),
        qualified: qualified === "all" ? "all" : qualified === "true",
        owner_user_id: ownerUserId,
        search_job_id: searchJobId,
        has_website: hasWebsite === "all" ? "all" : hasWebsite === "true",
        sort,
      }) as const,
    [band, category, city, hasWebsite, maxScore, minScore, ownerUserId, page, q, qualified, scoreRange, searchJobId, sort, status],
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

  const allLeads = useMemo(() => leadsQuery.data?.items ?? [], [leadsQuery.data?.items]);
  const leads = useMemo(
    () => hasPhone ? allLeads.filter((l) => Boolean(l.phone)) : allLeads,
    [allLeads, hasPhone],
  );
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
  }, [q, city, category, status, band, qualified, hasWebsite, ownerUserId, searchJobId, sort, minScore, maxScore, scoreRange, hasPhone]);

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
      setActionSuccess(t("leads.leadMarkedStatus", { status: leadStatusLabel(t, variables.nextStatus) }));
    },
  });
  const assignMutation = useMutation({
    mutationFn: ({ leadId, assigneeId }: { leadId: string; assigneeId: string | null }) => assignLead(leadId, assigneeId),
    onSuccess: (_payload, variables) => {
      invalidateLeadQueries();
      setActionSuccess(variables.assigneeId ? t("leads.leadOwnerUpdated") : t("leads.leadOwnerCleared"));
    },
  });
  const analysisMutation = useMutation({
    mutationFn: (leadId: string) => generateLeadAnalysis(leadId),
    onSuccess: (payload, leadId) => {
      setAnalysisPreview(payload);
      void queryClient.invalidateQueries({ queryKey: ["lead", leadId, "analysis"] });
      setActionSuccess(t("leads.analysisGenerated"));
    },
  });
  const outreachMutation = useMutation({
    mutationFn: (leadId: string) => generateLeadOutreach(leadId, { tone: outreachTone }),
    onSuccess: (payload, leadId) => {
      setOutreachPreview(outreachDraftToMessagePreview(payload));
      void queryClient.invalidateQueries({ queryKey: ["lead", leadId, "outreach"] });
      setActionSuccess(t("leads.outreachGenerated"));
    },
  });
  const refreshMutation = useMutation({
    mutationFn: (leadId: string) => refreshLead(leadId),
    onSuccess: (payload) => {
      invalidateLeadQueries();
      setSelectedLeadId(payload.public_id);
      setAnalysisPreview(null);
      setOutreachPreview(null);
      setActionSuccess(t("leads.leadRefreshCompleted"));
    },
  });
  const exportMutation = useMutation({
    mutationFn: (leadIds?: string[]) =>
      leadIds && leadIds.length > 0 ? downloadLeadsExport({ lead_ids: leadIds }) : downloadLeadsExport(leadFilters),
  });

  if (leadsQuery.isError || jobsQuery.isError || usersQuery.isError) {
    return (
      <EmptyState
        title={t("leads.dataUnavailableTitle")}
        description={t("leads.dataUnavailableDescription")}
      />
    );
  }

  const isInitialLoading = !leadsQuery.data && leadsQuery.isPending;

  return (
    <div className="max-w-full space-y-6 overflow-x-clip p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow={t("leads.title")}
        title={t("leads.workspaceTitle")}
        description={t("leads.workspaceDescription")}
        actions={
          <>
            <Button
              variant="outline"
              className="bg-transparent"
              onClick={() => exportMutation.mutate(selectedIds.size ? Array.from(selectedIds) : undefined)}
              disabled={exportMutation.isPending}
            >
              <Download className="size-3.5" />
              {exportMutation.isPending
                ? t("leads.exportingCsv")
                : selectedIds.size
                  ? t("leads.exportSelected", { count: selectedIds.size })
                  : t("leads.exportCsv")}
            </Button>
            {selectedLead ? (
              <Button asChild>
                <Link to={appPaths.leadDetail(selectedLead.public_id)}>{t("leads.openLeadDetail")}</Link>
              </Button>
            ) : null}
          </>
        }
      />

      {exportMutation.isSuccess ? (
        <QueryStateNotice
          tone="success"
          title={t("leads.exportStartedTitle")}
          description={t("leads.exportStartedDescription")}
        />
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <MetricCard label={t("leads.filteredLeads")} value={String(totalLeads)} helper={t("leads.currentResultSet")} />
        <MetricCard label={t("leads.mappableOnPage")} value={String(mappableLeads.length)} helper={t("leads.visibleMarkers")} />
        <MetricCard label={t("leads.selectedLeads")} value={String(selectedIds.size)} helper={t("leads.bulkExportReady")} />
      </section>

      <section className="grid min-w-0 gap-4 2xl:grid-cols-[320px_minmax(0,1fr)]">
        <LeadsFiltersPanel activeCount={activeFilterCount} onReset={resetFilters}>
          <FilterField label={t("common.search")}>
            <Input value={q} onChange={(event) => setQ(event.target.value)} placeholder={t("leads.searchPlaceholder")} />
          </FilterField>
          <FilterField label={t("leads.city")}>
            <Input value={city} onChange={(event) => setCity(event.target.value)} placeholder={t("leads.cityPlaceholder")} />
          </FilterField>
          <FilterField label={t("leads.category")}>
            <Input value={category} onChange={(event) => setCategory(event.target.value)} placeholder={t("leads.categoryPlaceholder")} />
          </FilterField>
          <FilterField label={t("searches.jobDetails")}>
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
                <SelectValue placeholder={t("leads.allSearchJobs")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("leads.allSearchJobs")}</SelectItem>
                {searchJobs.map((job) => (
                  <SelectItem key={job.public_id} value={job.public_id}>
                    {job.business_type} / {job.city}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label={t("leads.status")}>
            <Select value={status} onValueChange={(value) => setStatus(value as LeadStatus | "all")}>
              <SelectTrigger>
                <SelectValue placeholder={t("exports.allStatuses")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("exports.allStatuses")}</SelectItem>
                <SelectItem value="new">{t("leads.statusNew")}</SelectItem>
                <SelectItem value="reviewed">{t("leads.statusReviewed")}</SelectItem>
                <SelectItem value="qualified">{t("leads.statusQualified")}</SelectItem>
                <SelectItem value="contacted">{t("leads.statusContacted")}</SelectItem>
                <SelectItem value="interested">{t("leads.statusInterested")}</SelectItem>
                <SelectItem value="won">{t("leads.statusWon")}</SelectItem>
                <SelectItem value="lost">{t("leads.statusLost")}</SelectItem>
                <SelectItem value="archived">{t("leads.statusArchived")}</SelectItem>
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label={t("leads.band")}>
            <Select value={band} onValueChange={(value) => setBand(value as LeadScoreBand | "all")}>
              <SelectTrigger>
                <SelectValue placeholder={t("leads.allScoreBands")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("leads.allScoreBands")}</SelectItem>
                <SelectItem value="high">{t("leads.bandHigh")}</SelectItem>
                <SelectItem value="medium">{t("leads.bandMedium")}</SelectItem>
                <SelectItem value="low">{t("leads.bandLow")}</SelectItem>
                <SelectItem value="not_qualified">{t("leads.bandNotQualified")}</SelectItem>
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label={t("leads.qualification")}>
            <Select value={qualified} onValueChange={(value) => setQualified(value as "all" | "true" | "false")}>
              <SelectTrigger>
                <SelectValue placeholder={t("leads.anyQualification")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("leads.anyQualification")}</SelectItem>
                <SelectItem value="true">{t("leads.qualifiedOnly")}</SelectItem>
                <SelectItem value="false">{t("leads.needsQualification")}</SelectItem>
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label={t("leads.website")}>
            <Select value={hasWebsite} onValueChange={(value) => setHasWebsite(value as "all" | "true" | "false")}>
              <SelectTrigger>
                <SelectValue placeholder={t("leads.anyWebsiteState")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("leads.anyWebsiteState")}</SelectItem>
                <SelectItem value="true">{t("leads.hasWebsite")}</SelectItem>
                <SelectItem value="false">{t("leads.missingWebsite")}</SelectItem>
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label={t("leads.owner")}>
            <Select value={ownerUserId} onValueChange={setOwnerUserId}>
              <SelectTrigger>
                <SelectValue placeholder={t("leads.anyOwner")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("leads.anyOwner")}</SelectItem>
                {(usersQuery.data?.items ?? []).map((user) => (
                  <SelectItem key={user.public_id} value={user.public_id}>
                    {user.full_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label={t("leads.sortBy")}>
            <Select value={sort} onValueChange={(value) => setSort(value as LeadSortOption)}>
              <SelectTrigger>
                <SelectValue placeholder="Sort" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="score_desc">{t("leads.highestScore")}</SelectItem>
                <SelectItem value="newest">{t("leads.newest")}</SelectItem>
                <SelectItem value="reviews_desc">{t("leads.mostReviews")}</SelectItem>
                <SelectItem value="rating_desc">{t("leads.bestRating")}</SelectItem>
              </SelectContent>
            </Select>
          </FilterField>
          <div className="grid grid-cols-2 gap-3">
            <FilterField label={t("leads.minScore")}>
              <Input type="number" value={minScore} onChange={(event) => setMinScore(event.target.value)} />
            </FilterField>
            <FilterField label={t("leads.maxScore")}>
              <Input type="number" value={maxScore} onChange={(event) => setMaxScore(event.target.value)} />
            </FilterField>
          </div>
        </LeadsFiltersPanel>

        <div className="min-w-0 space-y-4">
          <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>{t("leads.liveWorkspace")}</CardTitle>
                  <CardDescription>
                    {t("leads.liveWorkspaceDescription")}
                  </CardDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  <ViewButton active={view === "table"} onClick={() => setView("table")} icon={<Table2 className="size-3.5" />}>
                    {t("leads.table")}
                  </ViewButton>
                  <ViewButton active={view === "cards"} onClick={() => setView("cards")} icon={<LayoutGrid className="size-3.5" />}>
                    {t("leads.cards")}
                  </ViewButton>
                  <ViewButton active={view === "map"} onClick={() => setView("map")} icon={<Map className="size-3.5" />}>
                    {t("leads.map")}
                  </ViewButton>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral">{t("leads.matchingLeads", { count: totalLeads })}</Badge>
                <Badge tone="accent">{t("leads.selectedCount", { count: selectedIds.size })}</Badge>
                {selectedLead ? <Badge tone={bandTone(selectedLead.latest_band)}>{selectedLead.company_name}</Badge> : null}
              </div>

              {isInitialLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full rounded-xl" />
                  ))}
                </div>
              ) : leads.length === 0 ? (
                activeFilterCount === 0 ? (
                  <EmptyState
                    title={t("leads.noLeadsYetTitle")}
                    description={t("leads.noLeadsYetDescription")}
                    action={
                      <Button asChild>
                        <Link to={appPaths.searches}>{t("searches.createNewJob")}</Link>
                      </Button>
                    }
                  />
                ) : (
                  <EmptyState
                    title={t("leads.noFilteredLeadsTitle")}
                    description={t("leads.noFilteredLeadsDescription")}
                  />
                )
              ) : view === "table" ? (
                <div className="space-y-3">
                  <QuickFilterBar
                    scoreRange={scoreRange}
                    onScoreRangeChange={setScoreRange}
                    hasWebsite={hasWebsite}
                    onHasWebsiteChange={setHasWebsite}
                    hasPhone={hasPhone}
                    onHasPhoneChange={setHasPhone}
                  />
                  <LeadsTable
                    leads={leads}
                    selectedLeadId={selectedLeadId}
                    selectedIds={selectedIds}
                    onSelectLead={setSelectedLeadId}
                    onToggleSelect={toggleSelected}
                    visibility={columnVisibility}
                    onToggleColumn={toggleColumn}
                  />
                </div>
              ) : view === "cards" ? (
                <LeadsCards leads={leads} selectedIds={selectedIds} onToggleSelect={toggleSelected} />
              ) : mappableLeads.length === 0 ? (
                activeFilterCount === 0 ? (
                  <EmptyState
                    title={t("leads.noLeadsYetTitle")}
                    description={t("leads.noLeadsYetDescription")}
                    action={
                      <Button asChild>
                        <Link to={appPaths.searches}>{t("searches.createNewJob")}</Link>
                      </Button>
                    }
                  />
                ) : (
                  <EmptyState
                    title={t("leads.noMapCoordinatesTitle")}
                    description={t("leads.noMapCoordinatesDescription")}
                  />
                )
              ) : (
                <div className="h-[520px] overflow-hidden rounded-2xl border border-border">
                  <LazyLeadMap className="h-full" leads={mappableLeads} selectedLeadId={selectedLeadId} onSelect={setSelectedLeadId} />
                </div>
              )}

              {totalLeads > 0 ? (
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
                  <p className="text-sm text-muted-foreground">
                    {t("leads.paginationSummary", {
                      start: (page - 1) * 50 + 1,
                      end: Math.min(page * 50, totalLeads),
                      total: totalLeads,
                    })}
                  </p>
                  <div className="flex w-full gap-2 sm:w-auto">
                    <Button variant="outline" className="bg-transparent" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
                      {t("common.back")}
                    </Button>
                    <Button variant="outline" className="bg-transparent" disabled={page >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>
                      {t("common.next")}
                    </Button>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>{t("leads.selectedLeadWorkspace")}</CardTitle>
              <CardDescription>
                {t("leads.selectedLeadWorkspaceDescription")}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedLeadId && selectedLeadQuery.isPending ? (
                <QueryStateNotice
                  tone="loading"
                  title={t("leads.refreshingSelectedLeadTitle")}
                  description={t("leads.refreshingSelectedLeadDescription")}
                />
              ) : null}

              {actionSuccess ? <QueryStateNotice tone="success" title={t("leads.actionCompleted")} description={actionSuccess} /> : null}

              {!selectedLead ? (
                <EmptyState
                  title={t("leads.noLeadSelectedTitle")}
                  description={t("leads.noLeadSelectedDescription")}
                />
              ) : (
                <>
                  <div>
                    <p className="text-lg font-semibold">{selectedLead.company_name}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {selectedLead.city ?? t("dashboard.unknownCity")} · {selectedLead.website_domain ?? t("leads.noWebsite")}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Badge tone={bandTone(selectedLead.latest_band)}>{scoreBandLabel(t, selectedLead.latest_band)}</Badge>
                    <Badge tone={statusTone(selectedLead.status)}>{leadStatusLabel(t, selectedLead.status)}</Badge>
                    <Badge tone={selectedLead.latest_qualified ? "success" : "warning"}>
                      {selectedLead.latest_qualified ? t("leads.qualified") : t("leads.needsReview")}
                    </Badge>
                    <Badge tone="neutral">{formatScore(selectedLead.latest_score)}</Badge>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <SignalCard label={t("leads.rating")} value={selectedLead.rating ? String(selectedLead.rating) : t("common.notAvailable")} />
                    <SignalCard label={t("leads.reviews")} value={String(selectedLead.review_count)} />
                  </div>

                  <div className="space-y-2">
                    <Label>{t("leads.assignOwner")}</Label>
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
                        <SelectValue placeholder={t("leads.unassigned")} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="unassigned">{t("leads.unassigned")}</SelectItem>
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
                      {t("leads.markReviewed")}
                    </Button>
                    <Button variant="outline" className="bg-transparent" onClick={() => statusMutation.mutate({ leadId: selectedLead.public_id, nextStatus: "qualified" })}>
                      {t("leads.markQualified")}
                    </Button>
                    <Button variant="outline" className="bg-transparent" onClick={() => statusMutation.mutate({ leadId: selectedLead.public_id, nextStatus: "contacted" })}>
                      {t("leads.markContacted")}
                    </Button>
                  </div>

                  <div className="grid gap-2 sm:grid-cols-3">
                    <Button variant="outline" className="bg-transparent" onClick={() => refreshMutation.mutate(selectedLead.public_id)} disabled={refreshMutation.isPending}>
                      <RefreshCw className="size-3.5" />
                      {refreshMutation.isPending ? t("leads.refreshing") : t("common.refresh")}
                    </Button>
                    <Button variant="outline" className="bg-transparent" onClick={() => analysisMutation.mutate(selectedLead.public_id)} disabled={analysisMutation.isPending}>
                      <Sparkles className="size-3.5" />
                      {analysisMutation.isPending ? t("leads.generating") : t("leads.generateAnalysis")}
                    </Button>
                    <Button onClick={() => outreachMutation.mutate(selectedLead.public_id)} disabled={outreachMutation.isPending}>
                      {outreachMutation.isPending ? t("leads.drafting") : t("leads.draftOutreach")}
                    </Button>
                  </div>

                  <div className="space-y-2">
                    <Label>{t("leads.outreachTone")}</Label>
                    <Select value={outreachTone} onValueChange={(value) => setOutreachTone(value as OutreachTone)}>
                      <SelectTrigger>
                        <SelectValue placeholder={t("leads.selectTone")} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="consultative">{t("outreach.toneConsultative")}</SelectItem>
                        <SelectItem value="friendly">{t("outreach.toneFriendly")}</SelectItem>
                        <SelectItem value="formal">{t("outreach.toneFormal")}</SelectItem>
                        <SelectItem value="short_pitch">{t("outreach.toneShortPitch")}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {analysisPreview ? (
                    <div className="rounded-2xl border border-border bg-muted/20 p-4">
                      <p className="font-medium">{t("leads.latestGeneratedAnalysis")}</p>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{analysisPreview.analysis.summary}</p>
                    </div>
                  ) : null}
                  {outreachPreview ? (
                    <div className="rounded-2xl border border-border bg-muted/20 p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{outreachPreview.subject}</p>
                        <Badge tone="accent">{t(`outreach.tones.${outreachPreview.tone}`)}</Badge>
                      </div>
                      <p className="mt-2 whitespace-pre-line text-sm leading-6 text-muted-foreground">{outreachPreview.message}</p>
                    </div>
                  ) : null}

                  <Button asChild className="w-full">
                    <Link to={appPaths.leadDetail(selectedLead.public_id)}>{t("leads.openFullLeadDetail")}</Link>
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
    setScoreRange([0, 100]);
    setHasPhone(false);
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
