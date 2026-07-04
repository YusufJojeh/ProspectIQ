import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Copy, FileText, Plus, Sparkles, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { appPaths } from "@/app/paths";
import { LeadScoreSpinner } from "@/components/brand/lead-score-spinner";
import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  addCampaignLeads,
  archiveCampaign,
  generateCampaignDrafts,
  generateCampaignSequence,
  getCampaign,
  removeCampaignLead,
} from "@/features/campaigns/api";
import { createCampaignDeals } from "@/features/crm/api";
import { listLeads } from "@/features/leads/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { scoreBandLabel } from "@/lib/i18n-labels";
import { bandTone, formatDate, formatScore } from "@/lib/presenters";
import type { CampaignLeadStatus, LeadResponse } from "@/types/api";

export function CampaignDetailPage() {
  const { campaignId = "" } = useParams();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [leadToAdd, setLeadToAdd] = useState("");
  useDocumentTitle(t("campaigns.detailTitle"));

  const campaignQuery = useQuery({
    queryKey: ["campaigns", campaignId],
    queryFn: () => getCampaign(campaignId),
    enabled: Boolean(campaignId),
  });
  const leadsQuery = useQuery({
    queryKey: ["leads", "campaign-add-options"],
    queryFn: () => listLeads({ page_size: 100, sort: "score_desc" }),
  });

  const invalidateCampaign = () => {
    void queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    void queryClient.invalidateQueries({ queryKey: ["campaigns", campaignId] });
    void queryClient.invalidateQueries({ queryKey: ["leads"] });
  };

  const addLeadMutation = useMutation({
    mutationFn: () => addCampaignLeads(campaignId, { lead_ids: [leadToAdd] }),
    onSuccess: () => {
      setLeadToAdd("");
      invalidateCampaign();
      toast.success(t("campaigns.leadAdded"));
    },
  });
  const removeLeadMutation = useMutation({
    mutationFn: (leadId: string) => removeCampaignLead(campaignId, leadId),
    onSuccess: () => {
      invalidateCampaign();
      toast.success(t("campaigns.leadRemoved"));
    },
  });
  const sequenceMutation = useMutation({
    mutationFn: () => generateCampaignSequence(campaignId),
    onSuccess: () => {
      invalidateCampaign();
      toast.success(t("campaigns.sequenceGenerated"));
    },
  });
  const draftsMutation = useMutation({
    mutationFn: () => generateCampaignDrafts(campaignId),
    onSuccess: (payload) => {
      invalidateCampaign();
      toast.success(t("campaigns.draftsGenerated", { count: payload.created_count }));
    },
  });
  const archiveMutation = useMutation({
    mutationFn: () => archiveCampaign(campaignId),
    onSuccess: invalidateCampaign,
  });
  const createDealsMutation = useMutation({
    mutationFn: () => createCampaignDeals(campaignId),
    onSuccess: (payload) => {
      void queryClient.invalidateQueries({ queryKey: ["crm"] });
      toast.success(
        t("crm.campaignDealsCreated", {
          created: payload.created_count,
          skipped: payload.skipped_count,
        }),
      );
    },
  });

  const leadOptions = useMemo(() => {
    const existing = new Set(campaignQuery.data?.leads.map((item) => item.lead.public_id) ?? []);
    return (leadsQuery.data?.items ?? []).filter((lead) => !existing.has(lead.public_id));
  }, [campaignQuery.data?.leads, leadsQuery.data?.items]);

  if (!campaignId) {
    return <Navigate replace to={appPaths.campaigns} />;
  }

  if (campaignQuery.isPending) {
    return (
      <div className="space-y-4 p-3 sm:p-4 lg:p-6">
        <Skeleton className="h-28 rounded-lg" />
        <Skeleton className="h-80 rounded-lg" />
      </div>
    );
  }

  if (campaignQuery.isError) {
    return (
      <EmptyState
        title={t("campaigns.notFoundTitle")}
        description={campaignQuery.error.message}
        action={
          <Button asChild>
            <Link to={appPaths.campaigns}>{t("campaigns.backToCampaigns")}</Link>
          </Button>
        }
      />
    );
  }

  const campaign = campaignQuery.data;

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow={t("campaigns.detailEyebrow")}
        title={campaign.name}
        description={campaign.description ?? t("campaigns.noDescription")}
        actions={
          <>
            <Button asChild variant="outline" className="bg-transparent">
              <Link to={appPaths.campaigns}>
                <ArrowLeft className="size-3.5" />
                {t("campaigns.backToCampaigns")}
              </Link>
            </Button>
            <Button
              variant="outline"
              className="bg-transparent"
              onClick={() => archiveMutation.mutate()}
              disabled={archiveMutation.isPending}
            >
              <Trash2 className="size-3.5" />
              {t("campaigns.archive")}
            </Button>
            <Button
              variant="outline"
              className="bg-transparent"
              onClick={() => createDealsMutation.mutate()}
              disabled={createDealsMutation.isPending || campaign.leads.length === 0}
            >
              <Plus className="size-3.5" />
              {t("crm.createDeals")}
            </Button>
          </>
        }
      />

      <section className="grid gap-3 sm:grid-cols-3">
        <Summary label={t("campaigns.status")} value={t(`campaigns.statuses.${campaign.status}`)} />
        <Summary label={t("campaigns.leads")} value={String(campaign.lead_count)} />
        <Summary label={t("campaigns.steps")} value={String(campaign.sequence_steps_count)} />
      </section>

      <Tabs defaultValue="leads" className="space-y-4">
        <TabsList>
          <TabsTrigger value="leads">{t("campaigns.leads")}</TabsTrigger>
          <TabsTrigger value="sequence">{t("campaigns.sequence")}</TabsTrigger>
          <TabsTrigger value="drafts">{t("campaigns.drafts")}</TabsTrigger>
          <TabsTrigger value="events">{t("campaigns.events")}</TabsTrigger>
        </TabsList>

        <TabsContent value="leads" className="space-y-4">
          <Card className="rounded-lg border-border bg-card/95">
            <CardHeader>
              <CardTitle>{t("campaigns.addLead")}</CardTitle>
              <CardDescription>{t("campaigns.addLeadDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 sm:flex-row">
              <Select value={leadToAdd} onValueChange={setLeadToAdd}>
                <SelectTrigger className="sm:max-w-md">
                  <SelectValue placeholder={t("campaigns.selectLead")} />
                </SelectTrigger>
                <SelectContent>
                  {leadOptions.map((lead) => (
                    <SelectItem key={lead.public_id} value={lead.public_id}>
                      {lead.company_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                onClick={() => addLeadMutation.mutate()}
                disabled={!leadToAdd || addLeadMutation.isPending}
              >
                <Plus className="size-3.5" />
                {t("campaigns.addLead")}
              </Button>
            </CardContent>
          </Card>

          {campaign.leads.length === 0 ? (
            <EmptyState
              title={t("campaigns.noLeadsTitle")}
              description={t("campaigns.noLeadsDescription")}
            />
          ) : (
            <div className="grid gap-3 xl:grid-cols-2">
              {campaign.leads.map((item) => (
                <CampaignLeadCard
                  key={item.lead.public_id}
                  lead={item.lead}
                  status={item.status}
                  onRemove={() => removeLeadMutation.mutate(item.lead.public_id)}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="sequence" className="space-y-4">
          <Button onClick={() => sequenceMutation.mutate()} disabled={sequenceMutation.isPending}>
            <Sparkles className="size-3.5" />
            {campaign.sequence_steps.length
              ? t("campaigns.regenerateSequence")
              : t("campaigns.generateSequence")}
          </Button>
          {campaign.sequence_steps.length === 0 ? (
            <EmptyState
              title={t("campaigns.noSequenceTitle")}
              description={t("campaigns.noSequenceDescription")}
            />
          ) : (
            <div className="grid gap-3">
              {campaign.sequence_steps.map((step) => (
                <Card key={step.public_id} className="rounded-lg border-border bg-card/95">
                  <CardHeader>
                    <div className="flex items-center justify-between gap-3">
                      <CardTitle className="text-base">
                        {t("campaigns.stepOrder", { order: step.step_order })}
                      </CardTitle>
                      <Badge tone="neutral">
                        {t(`campaigns.channels.${step.channel}`)} /{" "}
                        {t("campaigns.delayDays", { count: step.delay_days })}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm leading-6 text-muted-foreground">{step.template_text}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="drafts" className="space-y-4">
          <Button
            onClick={() => draftsMutation.mutate()}
            disabled={draftsMutation.isPending || campaign.leads.length === 0}
          >
            <FileText className="size-3.5" />
            {draftsMutation.isPending
              ? t("campaigns.generatingDrafts")
              : t("campaigns.generateDrafts")}
          </Button>
          {campaign.drafts.length === 0 ? (
            <EmptyState
              title={t("campaigns.noDraftsTitle")}
              description={t("campaigns.noDraftsDescription")}
            />
          ) : (
            <div className="grid gap-3 xl:grid-cols-2">
              {campaign.drafts.map((draft) => (
                <Card key={draft.public_id} className="rounded-lg border-border bg-card/95">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-3">
                      <CardTitle className="text-base">{draft.subject}</CardTitle>
                      <Badge tone={draft.outreach_status === "sent" ? "success" : "neutral"}>
                        {t(`leads.outreachStatus.${draft.outreach_status}`, {
                          defaultValue: draft.outreach_status,
                        })}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                      {draft.message}
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="bg-transparent"
                      onClick={() => {
                        void navigator.clipboard.writeText(`${draft.subject}\n\n${draft.message}`);
                        toast.success(t("outreach.copiedToast"));
                      }}
                    >
                      <Copy className="size-3.5" />
                      {t("outreach.copyAll")}
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="events" className="space-y-3">
          {campaign.events.length === 0 ? (
            <EmptyState
              title={t("campaigns.noEventsTitle")}
              description={t("campaigns.noEventsDescription")}
            />
          ) : (
            campaign.events.map((event) => (
              <div key={event.public_id} className="rounded-lg border border-border bg-card/95 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Badge tone="neutral">
                    {t(`campaigns.eventTypes.${event.event_type.replace(/\./g, "_")}`, {
                      defaultValue: event.event_type,
                    })}
                  </Badge>
                  <span className="text-xs text-muted-foreground">{formatDate(event.occurred_at)}</span>
                </div>
                {event.lead_id ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    {t("campaigns.eventLead", { id: event.lead_id })}
                  </p>
                ) : null}
              </div>
            ))
          )}
        </TabsContent>
      </Tabs>

      {archiveMutation.isSuccess ? (
        <QueryStateNotice
          tone="success"
          title={t("campaigns.archivedTitle")}
          description={t("campaigns.archivedDescription")}
        />
      ) : null}
    </div>
  );
}

function CampaignLeadCard({
  lead,
  status,
  onRemove,
}: {
  lead: LeadResponse;
  status: CampaignLeadStatus;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const score = lead.latest_final_priority_score ?? lead.latest_score ?? 0;
  return (
    <Card className="rounded-lg border-border bg-card/95">
      <CardContent className="flex items-start gap-4 p-4">
        <LeadScoreSpinner
          value={score}
          label={t("leadScoreSpinner.companyScore", {
            company: lead.company_name,
            score: Math.round(score),
          })}
        />
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Link to={appPaths.leadDetail(lead.public_id)} className="font-semibold hover:text-[oklch(var(--signal))]">
              {lead.company_name}
            </Link>
            <Badge tone={bandTone(lead.latest_band)}>{scoreBandLabel(t, lead.latest_band)}</Badge>
            <Badge tone="neutral">{t(`campaigns.leadStatuses.${status}`)}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {lead.category ?? t("leads.business")} / {lead.city ?? t("common.unknown")} / {formatScore(score)}
          </p>
          {lead.top_signal_type ? (
            <Badge tone="accent">
              {t(`leadDetail.signals.types.${lead.top_signal_type}`, {
                defaultValue: lead.top_signal_type.replace(/_/g, " "),
              })}
            </Badge>
          ) : null}
        </div>
        <Button
          size="icon"
          variant="outline"
          className="bg-transparent"
          onClick={onRemove}
          aria-label={t("campaigns.removeLead")}
        >
          <Trash2 className="size-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-card/95 p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-xl font-semibold">{value}</p>
    </div>
  );
}
