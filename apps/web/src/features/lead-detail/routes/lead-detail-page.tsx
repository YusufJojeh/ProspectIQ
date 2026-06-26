import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { LeadActivityPanel } from "@/components/lead/activity-panel";
import { LeadAiAnalysisPanel } from "@/components/lead/ai-analysis-panel";
import { LeadAiEvidencePanel } from "@/components/lead/ai-evidence-panel";
import { LeadContactCard } from "@/components/lead/contact-card";
import { LeadEvidenceTimeline } from "@/components/lead/evidence-timeline";
import { LeadIcpMatchPanel } from "@/components/lead/icp-match-panel";
import { LeadHero } from "@/components/lead/lead-hero";
import { LeadOutreachPanel } from "@/components/lead/outreach-panel";
import { LeadScoreBreakdownCard } from "@/components/lead/score-breakdown";
import { LeadScoringV2Panel } from "@/components/lead/scoring-v2-panel";
import { LeadSignalsPanel } from "@/components/lead/signals-panel";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  generateLeadAnalysis,
  getLatestLeadAnalysis,
  getLeadAiEvidence,
  submitAnalysisFeedback,
} from "@/features/ai-analysis/api";
import { addCampaignLeads, listCampaigns } from "@/features/campaigns/api";
import { createLeadDeal, listCrmDeals } from "@/features/crm/api";
import {
  listIcpProfiles,
  recomputeIcpProfileMatch,
} from "@/features/icp/api";
import {
  addLeadNote,
  assignLead,
  getLead,
  getLeadEvidence,
  getLeadScoreBreakdown,
  getLeadSignals,
  listLeadActivity,
  recomputeLeadSignals,
  refreshLead,
  updateLeadStatus,
} from "@/features/leads/api";
import {
  buildBreakdownSummary,
  buildLeadHealth,
  mergeActivityTimeline,
} from "@/features/internal/design-adapters";
import {
  generateLeadOutreach,
  getLatestOutreach,
  updateOutreachDraft,
} from "@/features/outreach/api";
import { listUsers } from "@/features/users/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { resolveErrorMessage } from "@/lib/error-messages";
import { leadStatusLabel, scoreBandLabel } from "@/lib/i18n-labels";
import { hasCoordinates } from "@/lib/maps";
import { formatPercent, formatScore } from "@/lib/presenters";
import { LazyLeadMap } from "@/features/leads/components/lazy-lead-map";
import type {
  AIFeedbackRating,
  LeadIcpMatchResponse,
  LeadStatus,
  OutreachTone,
} from "@/types/api";
import { toast } from "sonner";

export function LeadDetailPage() {
  const { leadId = "" } = useParams();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [statusDraft, setStatusDraft] = useState<LeadStatus>("new");
  const [statusNote, setStatusNote] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [outreachSubjectDraft, setOutreachSubjectDraft] = useState("");
  const [outreachMessageDraft, setOutreachMessageDraft] = useState("");
  const [outreachTone, setOutreachTone] =
    useState<OutreachTone>("consultative");
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [selectedIcpProfileId, setSelectedIcpProfileId] = useState("");
  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [lastIcpMatch, setLastIcpMatch] =
    useState<LeadIcpMatchResponse | null>(null);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  const leadQuery = useQuery({
    queryKey: ["lead", leadId],
    queryFn: () => getLead(leadId),
    enabled: Boolean(leadId),
  });
  const evidenceQuery = useQuery({
    queryKey: ["lead", leadId, "evidence"],
    queryFn: () => getLeadEvidence(leadId),
    enabled: Boolean(leadId),
  });
  const breakdownQuery = useQuery({
    queryKey: ["lead", leadId, "breakdown"],
    queryFn: () => getLeadScoreBreakdown(leadId),
    enabled: Boolean(leadId),
  });
  const signalsQuery = useQuery({
    queryKey: ["lead", leadId, "signals"],
    queryFn: () => getLeadSignals(leadId),
    enabled: Boolean(leadId),
  });
  const icpProfilesQuery = useQuery({
    queryKey: ["icp-profiles"],
    queryFn: listIcpProfiles,
  });
  const activityQuery = useQuery({
    queryKey: ["lead", leadId, "activity"],
    queryFn: () => listLeadActivity(leadId),
    enabled: Boolean(leadId),
  });
  const latestAnalysisQuery = useQuery({
    queryKey: ["lead", leadId, "analysis", "latest"],
    queryFn: () => getLatestLeadAnalysis(leadId),
    enabled: Boolean(leadId),
  });
  const latestOutreachQuery = useQuery({
    queryKey: ["lead", leadId, "outreach", "latest"],
    queryFn: () => getLatestOutreach(leadId),
    enabled: Boolean(leadId),
  });
  const aiEvidenceQuery = useQuery({
    queryKey: ["lead", leadId, "ai-evidence"],
    queryFn: () => getLeadAiEvidence(leadId),
    enabled: Boolean(leadId),
  });
  const usersQuery = useQuery({
    queryKey: ["users", "workspace"],
    queryFn: listUsers,
  });
  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: listCampaigns,
  });
  const crmDealsQuery = useQuery({
    queryKey: ["crm", "deals", "lead", leadId],
    queryFn: () => listCrmDeals({ lead_id: leadId, status: "open" }),
    enabled: Boolean(leadId),
  });

  useDocumentTitle(leadQuery.data?.company_name ?? "Lead Detail");

  useEffect(() => {
    if (leadQuery.data) {
      setStatusDraft(leadQuery.data.status);
    }
  }, [leadQuery.data]);

  // Reset lead-scoped local state when navigating between leads so a recompute
  // result or success banner from one lead never bleeds into another.
  useEffect(() => {
    setLastIcpMatch(null);
    setActionSuccess(null);
    setFeedbackSubmitted(false);
  }, [leadId]);

  useEffect(() => {
    const message = latestOutreachQuery.data?.message;
    setOutreachSubjectDraft(message?.subject ?? "");
    setOutreachMessageDraft(message?.message ?? "");
    setOutreachTone(message?.tone ?? "consultative");
  }, [latestOutreachQuery.data?.message]);

  useEffect(() => {
    const profiles = icpProfilesQuery.data?.items ?? [];
    if (!selectedIcpProfileId && profiles.length > 0) {
      setSelectedIcpProfileId(
        profiles.find((profile) => profile.is_active)?.public_id ??
          profiles[0].public_id,
      );
    }
  }, [icpProfilesQuery.data?.items, selectedIcpProfileId]);

  const refreshQueries = () => {
    void queryClient.invalidateQueries({ queryKey: ["lead", leadId] });
    void queryClient.invalidateQueries({ queryKey: ["leads"] });
    void queryClient.invalidateQueries({
      queryKey: ["lead", leadId, "evidence"],
    });
    void queryClient.invalidateQueries({
      queryKey: ["lead", leadId, "breakdown"],
    });
    void queryClient.invalidateQueries({
      queryKey: ["lead", leadId, "signals"],
    });
    void queryClient.invalidateQueries({
      queryKey: ["lead", leadId, "activity"],
    });
    void queryClient.invalidateQueries({
      queryKey: ["lead", leadId, "analysis", "latest"],
    });
    void queryClient.invalidateQueries({
      queryKey: ["lead", leadId, "outreach", "latest"],
    });
    void queryClient.invalidateQueries({
      queryKey: ["lead", leadId, "ai-evidence"],
    });
    void queryClient.invalidateQueries({ queryKey: ["campaigns"] });
  };

  const statusMutation = useMutation({
    mutationFn: (payload: { status: LeadStatus; note?: string }) =>
      updateLeadStatus(leadId, payload.status, payload.note),
    onSuccess: () => {
      refreshQueries();
      setStatusNote("");
      setActionSuccess(t("leadDetail.leadStatusUpdated"));
    },
  });
  const assignMutation = useMutation({
    mutationFn: (assigneeId: string | null) => assignLead(leadId, assigneeId),
    onSuccess: (_payload, assigneeId) => {
      refreshQueries();
      setActionSuccess(
        assigneeId
          ? t("leadDetail.leadOwnerUpdated")
          : t("leadDetail.leadOwnerCleared"),
      );
    },
  });
  const analysisMutation = useMutation({
    mutationFn: () => generateLeadAnalysis(leadId),
    onSuccess: () => {
      refreshQueries();
      setActionSuccess(t("leadDetail.analysisGenerated"));
    },
  });
  const outreachMutation = useMutation({
    mutationFn: (regenerate: boolean) =>
      generateLeadOutreach(leadId, { tone: outreachTone, regenerate }),
    onSuccess: () => {
      refreshQueries();
      setActionSuccess(t("leadDetail.outreachGenerated"));
    },
  });
  const refreshMutation = useMutation({
    mutationFn: () => refreshLead(leadId),
    onSuccess: () => {
      refreshQueries();
      setActionSuccess(t("leadDetail.leadRefreshed"));
    },
  });
  const noteMutation = useMutation({
    mutationFn: (note: string) => addLeadNote(leadId, note),
    onSuccess: () => {
      refreshQueries();
      setNoteDraft("");
      setActionSuccess(t("leadDetail.noteSaved"));
    },
  });
  const saveOutreachMutation = useMutation({
    mutationFn: (messageId: string) =>
      updateOutreachDraft(messageId, {
        subject: outreachSubjectDraft.trim(),
        message: outreachMessageDraft.trim(),
      }),
    onSuccess: () => {
      refreshQueries();
      setActionSuccess(t("leadDetail.outreachSaved"));
    },
  });
  const recomputeSignalsMutation = useMutation({
    mutationFn: () => recomputeLeadSignals(leadId),
    onSuccess: () => {
      refreshQueries();
      toast.success(t("leadDetail.signals.recomputeSuccess"));
    },
    onError: (error) => {
      toast.error(resolveErrorMessage(error, t));
    },
  });
  const recomputeIcpMatchMutation = useMutation({
    mutationFn: () =>
      recomputeIcpProfileMatch(selectedIcpProfileId, leadId),
    onSuccess: (match) => {
      setLastIcpMatch(match);
      refreshQueries();
      toast.success(t("leadDetail.icp.recomputeSuccess"));
    },
    onError: (error) => {
      toast.error(resolveErrorMessage(error, t));
    },
  });
  const feedbackMutation = useMutation({
    mutationFn: (payload: {
      snapshotId: string;
      rating: AIFeedbackRating;
      correction: string;
    }) =>
      submitAnalysisFeedback(payload.snapshotId, {
        rating: payload.rating,
        correction_text: payload.correction || null,
      }),
    onSuccess: () => {
      setFeedbackSubmitted(true);
      toast.success(t("leadDetail.evidence.feedbackThanksTitle"));
    },
    onError: (error) => {
      toast.error(resolveErrorMessage(error, t));
    },
  });
  const addToCampaignMutation = useMutation({
    mutationFn: () =>
      addCampaignLeads(selectedCampaignId, {
        lead_ids: [leadId],
      }),
    onSuccess: () => {
      refreshQueries();
      toast.success(t("campaigns.leadAdded"));
    },
    onError: (error) => {
      toast.error(resolveErrorMessage(error, t));
    },
  });
  const createDealMutation = useMutation({
    mutationFn: () => createLeadDeal(leadId),
    onSuccess: (deal) => {
      void queryClient.invalidateQueries({ queryKey: ["crm"] });
      toast.success(t("crm.dealCreated"));
      setActionSuccess(t("crm.leadDealCreated", { title: deal.title }));
    },
    onError: (error) => {
      toast.error(resolveErrorMessage(error, t));
    },
  });

  if (leadQuery.isError) {
    return (
      <EmptyState
        title={t("leadDetail.unavailableTitle")}
        description={resolveErrorMessage(leadQuery.error, t)}
      />
    );
  }

  if (leadQuery.isPending || !leadQuery.data) {
    return (
      <QueryStateNotice
        tone="loading"
        title={t("leadDetail.loadingLeadDetail")}
        description={t("leadDetail.loadingLeadDetailDescription")}
      />
    );
  }

  const lead = leadQuery.data;
  const breakdown = breakdownQuery.data ?? null;
  const evidenceItems = evidenceQuery.data?.items ?? [];
  const latestAnalysis = latestAnalysisQuery.data?.snapshot ?? null;
  const latestOutreach = latestOutreachQuery.data?.message ?? null;
  const outreachDraftChanged =
    latestOutreach !== null &&
    (outreachSubjectDraft !== latestOutreach.subject ||
      outreachMessageDraft !== latestOutreach.message);
  const healthSignals = buildLeadHealth(lead);
  const breakdownSummary = buildBreakdownSummary(breakdown);
  const activityItems = mergeActivityTimeline(activityQuery.data?.items ?? []);

  return (
    <div className="max-w-full space-y-6 overflow-x-clip p-3 sm:p-4 lg:p-6">
      <LeadHero
        lead={lead}
        onRefresh={() => refreshMutation.mutate()}
        refreshing={refreshMutation.isPending}
        onGenerateAnalysis={() => analysisMutation.mutate()}
        generatingAnalysis={analysisMutation.isPending}
      />

      {actionSuccess ? (
        <QueryStateNotice
          tone="success"
          title={t("leadDetail.actionCompleted")}
          description={actionSuccess}
        />
      ) : null}

      <section className="grid min-w-0 gap-4 2xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <div className="min-w-0 space-y-4">
          <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>{t("leadDetail.normalizedFacts")}</CardTitle>
              <CardDescription>
                {t("leadDetail.normalizedFactsDescription")}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <FactCard
                label={t("leadDetail.leadScore")}
                value={formatScore(lead.latest_score)}
              />
              <FactCard
                label={t("leads.band")}
                value={scoreBandLabel(t, lead.latest_band)}
              />
              <FactCard
                label={t("leads.reviews")}
                value={String(lead.review_count)}
              />
              <FactCard
                label={t("leads.rating")}
                value={
                  lead.rating ? String(lead.rating) : t("common.notAvailable")
                }
              />
              <FactCard
                label={t("leads.confidence")}
                value={formatPercent(lead.data_confidence)}
              />
              <FactCard
                label={t("leadDetail.completeness")}
                value={formatPercent(lead.data_completeness)}
              />
              <FactCard
                label={t("leads.qualified")}
                value={lead.latest_qualified ? t("common.yes") : t("common.no")}
              />
              <FactCard
                label={t("leads.website")}
                value={lead.website_domain ?? t("leads.missing")}
              />
            </CardContent>
          </Card>

          <LeadContactCard lead={lead} />

          <LeadIcpMatchPanel
            lead={lead}
            breakdown={breakdown}
            profiles={icpProfilesQuery.data?.items ?? []}
            profilesLoading={icpProfilesQuery.isPending}
            profilesError={icpProfilesQuery.isError ? icpProfilesQuery.error : null}
            selectedProfileId={selectedIcpProfileId}
            lastMatch={lastIcpMatch}
            recomputing={recomputeIcpMatchMutation.isPending}
            onProfileChange={setSelectedIcpProfileId}
            onRecompute={() => recomputeIcpMatchMutation.mutate()}
          />

          <LeadSignalsPanel
            signals={signalsQuery.data ?? null}
            loading={signalsQuery.isPending}
            error={signalsQuery.isError ? signalsQuery.error : null}
            recomputing={recomputeSignalsMutation.isPending}
            onRecompute={() => recomputeSignalsMutation.mutate()}
          />

          <LeadScoringV2Panel lead={lead} breakdown={breakdown} />

          <LeadScoreBreakdownCard
            totalScore={breakdown?.total_score ?? lead.latest_score ?? 0}
            qualified={breakdown?.qualified ?? Boolean(lead.latest_qualified)}
            scoringVersionId={breakdown?.scoring_version_id}
            items={breakdownSummary}
          />

          {evidenceQuery.isPending ? (
            <QueryStateNotice
              tone="loading"
              title={t("leadDetail.loadingEvidenceTitle")}
              description={t("leadDetail.loadingEvidenceDescription")}
            />
          ) : evidenceQuery.isError ? (
            <QueryStateNotice
              tone="error"
              title={t("leads.evidence")}
              error={evidenceQuery.error}
            />
          ) : evidenceItems.length > 0 ? (
            <LeadEvidenceTimeline items={evidenceItems} />
          ) : (
            <QueryStateNotice
              tone="info"
              title={t("leadDetail.noEvidenceRows")}
              description={t("leadDetail.noEvidenceRowsDescription")}
            />
          )}
        </div>

        <div className="min-w-0 space-y-4">
          <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle>{t("leadDetail.leadOperations")}</CardTitle>
              <CardDescription>
                {t("leadDetail.leadOperationsDescription")}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {healthSignals.map((item) => (
                  <div
                    key={item.label}
                    className={`rounded-2xl border p-4 shadow-sm ${getHealthToneClass(item.value)}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                        {t(`leadDetail.health.${item.label}.label`, {
                          defaultValue: item.label,
                        })}
                      </p>
                      <span className="rounded-full border border-current/20 bg-background/60 px-2 py-0.5 text-xs font-semibold">
                        {item.value}%
                      </span>
                    </div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-background/70">
                      <div
                        className="h-full rounded-full bg-current transition-all"
                        style={{ width: `${item.value}%` }}
                      />
                    </div>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      {t(
                        `leadDetail.health.${item.label}.${item.value > 0 ? "positive" : "negative"}`,
                        { defaultValue: item.helper },
                      )}
                    </p>
                  </div>
                ))}
              </div>

              <div className="h-[260px] overflow-hidden rounded-2xl border border-border">
                {hasCoordinates(lead) ? (
                  <LazyLeadMap
                    className="h-full"
                    leads={[lead]}
                    selectedLeadId={lead.public_id}
                  />
                ) : (
                  <EmptyState
                    className="h-full border-0"
                    title={t("leadDetail.noMapLocation")}
                    description={t("leadDetail.noMapLocationDescription")}
                  />
                )}
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                <div className="space-y-2">
                  <Label>{t("leads.assignee")}</Label>
                  <Select
                    value={lead.assigned_to_user_public_id ?? "unassigned"}
                    disabled={assignMutation.isPending}
                    onValueChange={(value) =>
                      assignMutation.mutate(
                        value === "unassigned" ? null : value,
                      )
                    }
                  >
                    <SelectTrigger className="h-11 rounded-xl bg-background/70 text-start">
                      <SelectValue placeholder={t("leads.unassigned")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="unassigned">
                        {t("leads.unassigned")}
                      </SelectItem>
                      {(usersQuery.data?.items ?? []).map((user) => (
                        <SelectItem key={user.public_id} value={user.public_id}>
                          {user.full_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>{t("leadDetail.nextStatus")}</Label>
                  <Select
                    value={statusDraft}
                    onValueChange={(value) =>
                      setStatusDraft(value as LeadStatus)
                    }
                  >
                    <SelectTrigger className="h-11 rounded-xl bg-background/70 text-start">
                      <SelectValue placeholder={t("leadDetail.selectStatus")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="new">
                        {leadStatusLabel(t, "new")}
                      </SelectItem>
                      <SelectItem value="reviewed">
                        {leadStatusLabel(t, "reviewed")}
                      </SelectItem>
                      <SelectItem value="qualified">
                        {leadStatusLabel(t, "qualified")}
                      </SelectItem>
                      <SelectItem value="contacted">
                        {leadStatusLabel(t, "contacted")}
                      </SelectItem>
                      <SelectItem value="interested">
                        {leadStatusLabel(t, "interested")}
                      </SelectItem>
                      <SelectItem value="won">
                        {leadStatusLabel(t, "won")}
                      </SelectItem>
                      <SelectItem value="lost">
                        {leadStatusLabel(t, "lost")}
                      </SelectItem>
                      <SelectItem value="archived">
                        {leadStatusLabel(t, "archived")}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>{t("campaigns.addToCampaign")}</Label>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Select
                    value={selectedCampaignId}
                    disabled={campaignsQuery.isPending}
                    onValueChange={setSelectedCampaignId}
                  >
                    <SelectTrigger className="h-11 rounded-xl bg-background/70 text-start">
                      <SelectValue placeholder={t("campaigns.selectCampaign")} />
                    </SelectTrigger>
                    <SelectContent>
                      {(campaignsQuery.data?.items ?? []).map((campaign) => (
                        <SelectItem key={campaign.public_id} value={campaign.public_id}>
                          {campaign.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    variant="outline"
                    className="bg-transparent"
                    onClick={() => addToCampaignMutation.mutate()}
                    disabled={!selectedCampaignId || addToCampaignMutation.isPending}
                  >
                    {addToCampaignMutation.isPending
                      ? t("common.saving")
                      : t("campaigns.addLead")}
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label>{t("crm.deal")}</Label>
                <div className="flex flex-col gap-2 sm:flex-row">
                  {crmDealsQuery.data?.items[0] ? (
                    <Button asChild variant="outline" className="bg-transparent">
                      <Link to={appPaths.dealDetail(crmDealsQuery.data.items[0].public_id)}>
                        {t("crm.viewOpenDeal")}
                      </Link>
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      className="bg-transparent"
                      onClick={() => createDealMutation.mutate()}
                      disabled={createDealMutation.isPending}
                    >
                      {createDealMutation.isPending
                        ? t("common.creating")
                        : t("crm.createDeal")}
                    </Button>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label>{t("leadDetail.statusNote")}</Label>
                <Textarea
                  value={statusNote}
                  onChange={(event) => setStatusNote(event.target.value)}
                  placeholder={t("leadDetail.statusNotePlaceholder")}
                />
              </div>

              <Button
                onClick={() =>
                  statusMutation.mutate({
                    status: statusDraft,
                    note: statusNote || undefined,
                  })
                }
                disabled={statusMutation.isPending}
              >
                {statusMutation.isPending
                  ? t("common.saving")
                  : t("leadDetail.saveStatusUpdate")}
              </Button>
            </CardContent>
          </Card>

          <LeadAiAnalysisPanel
            snapshot={latestAnalysis}
            onGenerate={() => analysisMutation.mutate()}
            leadId={leadId}
            generating={analysisMutation.isPending}
            error={
              latestAnalysisQuery.isError ? latestAnalysisQuery.error : null
            }
          />

          <LeadAiEvidencePanel
            evidence={aiEvidenceQuery.data ?? null}
            loading={aiEvidenceQuery.isPending}
            error={aiEvidenceQuery.isError ? aiEvidenceQuery.error : null}
            canGiveFeedback={latestAnalysis !== null}
            submittingFeedback={feedbackMutation.isPending}
            feedbackSubmitted={feedbackSubmitted}
            onSubmitFeedback={(rating, correction) => {
              if (!latestAnalysis) return;
              feedbackMutation.mutate({
                snapshotId: latestAnalysis.public_id,
                rating,
                correction,
              });
            }}
          />

          <LeadOutreachPanel
            draft={latestOutreach}
            tone={outreachTone}
            onToneChange={setOutreachTone}
            subject={outreachSubjectDraft}
            message={outreachMessageDraft}
            onSubjectChange={setOutreachSubjectDraft}
            onMessageChange={setOutreachMessageDraft}
            onGenerate={(regenerate) => outreachMutation.mutate(regenerate)}
            onSave={() =>
              latestOutreach &&
              saveOutreachMutation.mutate(latestOutreach.public_id)
            }
            generating={outreachMutation.isPending}
            saving={saveOutreachMutation.isPending}
            canSave={
              latestOutreach !== null &&
              outreachSubjectDraft.trim().length > 0 &&
              outreachMessageDraft.trim().length > 0 &&
              outreachDraftChanged
            }
            error={
              latestOutreachQuery.isError ? latestOutreachQuery.error : null
            }
          />
        </div>
      </section>

      <LeadActivityPanel
        items={activityItems}
        noteDraft={noteDraft}
        onNoteChange={setNoteDraft}
        onSaveNote={() => noteMutation.mutate(noteDraft.trim())}
        saving={noteMutation.isPending}
        error={noteMutation.isError ? noteMutation.error : null}
      />
    </div>
  );
}

function getHealthToneClass(value: number) {
  if (value >= 80) {
    return "border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.08)] text-[oklch(var(--evidence))]";
  }
  if (value >= 50) {
    return "border-[oklch(var(--warning)/0.3)] bg-[oklch(var(--warning)/0.08)] text-[oklch(var(--warning))]";
  }
  return "border-[oklch(var(--risk)/0.3)] bg-[oklch(var(--risk)/0.08)] text-[oklch(var(--risk))]";
}

function FactCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 font-semibold">{value}</p>
    </div>
  );
}
