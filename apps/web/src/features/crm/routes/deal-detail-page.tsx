import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, CircleDollarSign, Plus, Trophy, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { appPaths } from "@/app/paths";
import { LeadScoreSpinner } from "@/components/brand/lead-score-spinner";
import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  completeCrmActivity,
  createCrmActivity,
  getCrmDeal,
  listCrmPipelines,
  markCrmDealLost,
  markCrmDealWon,
  moveCrmDeal,
  updateCrmDeal,
} from "@/features/crm/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { scoreBandLabel } from "@/lib/i18n-labels";
import { bandTone, formatDate } from "@/lib/presenters";
import type { ActivityType } from "@/types/api";

export function DealDetailPage() {
  const { dealId = "" } = useParams();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [activityType, setActivityType] = useState<ActivityType>("note");
  const [activityTitle, setActivityTitle] = useState("");
  const [lostReason, setLostReason] = useState("");
  useDocumentTitle(t("crm.detailTitle"));

  const dealQuery = useQuery({
    queryKey: ["crm", "deals", dealId],
    queryFn: () => getCrmDeal(dealId),
    enabled: Boolean(dealId),
  });
  const pipelinesQuery = useQuery({
    queryKey: ["crm", "pipelines"],
    queryFn: listCrmPipelines,
  });

  const invalidateDeal = () => {
    void queryClient.invalidateQueries({ queryKey: ["crm"] });
    void queryClient.invalidateQueries({ queryKey: ["crm", "deals", dealId] });
  };

  const moveMutation = useMutation({
    mutationFn: (stageId: string) => moveCrmDeal(dealId, stageId),
    onSuccess: () => {
      invalidateDeal();
      toast.success(t("crm.dealMoved"));
    },
  });
  const wonMutation = useMutation({
    mutationFn: () => markCrmDealWon(dealId),
    onSuccess: () => {
      invalidateDeal();
      toast.success(t("crm.dealWon"));
    },
  });
  const lostMutation = useMutation({
    mutationFn: () => markCrmDealLost(dealId, lostReason || undefined),
    onSuccess: () => {
      setLostReason("");
      invalidateDeal();
      toast.success(t("crm.dealLost"));
    },
  });
  const updateValueMutation = useMutation({
    mutationFn: (valueAmount: number | null) =>
      updateCrmDeal(dealId, { value_amount: valueAmount }),
    onSuccess: invalidateDeal,
  });
  const activityMutation = useMutation({
    mutationFn: () =>
      createCrmActivity(dealId, {
        activity_type: activityType,
        title: activityTitle.trim() || t(`crm.activityTypes.${activityType}`),
        note: note.trim() || null,
      }),
    onSuccess: () => {
      setActivityTitle("");
      setNote("");
      invalidateDeal();
      toast.success(t("crm.activityCreated"));
    },
  });
  const completeMutation = useMutation({
    mutationFn: (activityId: string) => completeCrmActivity(dealId, activityId),
    onSuccess: () => {
      invalidateDeal();
      toast.success(t("crm.activityCompleted"));
    },
  });

  if (!dealId) {
    return <Navigate replace to={appPaths.crm} />;
  }

  if (dealQuery.isPending) {
    return (
      <div className="space-y-4 p-3 sm:p-4 lg:p-6">
        <Skeleton className="h-28 rounded-lg" />
        <Skeleton className="h-96 rounded-lg" />
      </div>
    );
  }

  if (dealQuery.isError) {
    return (
      <EmptyState
        title={t("crm.dealNotFoundTitle")}
        description={dealQuery.error.message}
        action={
          <Button asChild>
            <Link to={appPaths.crm}>{t("crm.backToCrm")}</Link>
          </Button>
        }
      />
    );
  }

  const deal = dealQuery.data;
  const score = deal.lead.latest_final_priority_score ?? deal.lead.latest_score ?? 0;
  const pipeline = pipelinesQuery.data?.items.find((item) => item.public_id === deal.pipeline_id);

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow={t("crm.detailEyebrow")}
        title={deal.title}
        description={deal.lead.company_name}
        actions={
          <>
            <Button asChild variant="outline" className="bg-transparent">
              <Link to={appPaths.crm}>
                <ArrowLeft className="size-3.5" />
                {t("crm.backToCrm")}
              </Link>
            </Button>
            <Button onClick={() => wonMutation.mutate()} disabled={wonMutation.isPending}>
              <Trophy className="size-3.5" />
              {t("crm.markWon")}
            </Button>
          </>
        }
      />

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-4">
          <Card className="rounded-lg border-border bg-card/95">
            <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center">
              <LeadScoreSpinner
                value={score}
                label={t("leadScoreSpinner.companyScore", {
                  company: deal.lead.company_name,
                  score: Math.round(score),
                })}
              />
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap gap-2">
                  <Badge tone={bandTone(deal.lead.latest_band)}>
                    {scoreBandLabel(t, deal.lead.latest_band)}
                  </Badge>
                  <Badge tone={deal.status === "won" ? "success" : deal.status === "lost" ? "danger" : "neutral"}>
                    {t(`crm.statuses.${deal.status}`)}
                  </Badge>
                  {deal.campaign_name ? <Badge tone="accent">{deal.campaign_name}</Badge> : null}
                </div>
                <p className="text-sm text-muted-foreground">
                  {deal.lead.category ?? t("leads.business")} /{" "}
                  {deal.lead.city ?? t("common.unknown")}
                </p>
                {deal.lead.top_signal_evidence ? (
                  <p className="text-sm leading-6 text-muted-foreground">
                    {deal.lead.top_signal_evidence}
                  </p>
                ) : null}
              </div>
              <Button asChild variant="outline" className="bg-transparent">
                <Link to={appPaths.leadDetail(deal.lead.public_id)}>
                  {t("crm.openLead")}
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="rounded-lg border-border bg-card/95">
            <CardHeader>
              <CardTitle>{t("crm.activities")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-[12rem_minmax(0,1fr)]">
                <Select
                  value={activityType}
                  onValueChange={(value) => setActivityType(value as ActivityType)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(["note", "call", "meeting", "email", "follow_up"] as ActivityType[]).map(
                      (type) => (
                        <SelectItem key={type} value={type}>
                          {t(`crm.activityTypes.${type}`)}
                        </SelectItem>
                      ),
                    )}
                  </SelectContent>
                </Select>
                <Input
                  value={activityTitle}
                  onChange={(event) => setActivityTitle(event.target.value)}
                  placeholder={t("crm.activityTitlePlaceholder")}
                />
              </div>
              <Textarea
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder={t("crm.activityNotePlaceholder")}
              />
              <Button
                onClick={() => activityMutation.mutate()}
                disabled={activityMutation.isPending}
              >
                <Plus className="size-3.5" />
                {t("crm.addActivity")}
              </Button>
              <Separator />
              {deal.activities.length === 0 ? (
                <EmptyState
                  title={t("crm.noActivitiesTitle")}
                  description={t("crm.noActivitiesDescription")}
                />
              ) : (
                <div className="space-y-3">
                  {deal.activities.map((activity) => (
                    <div
                      key={activity.public_id}
                      className="rounded-lg border border-border bg-background/60 p-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge tone={activity.completed_at ? "success" : "neutral"}>
                              {t(`crm.activityTypes.${activity.activity_type}`)}
                            </Badge>
                            <span className="font-medium">{activity.title}</span>
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {activity.actor_full_name ?? t("common.system")} /{" "}
                            {formatDate(activity.created_at)}
                          </p>
                        </div>
                        {!activity.completed_at ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="bg-transparent"
                            onClick={() => completeMutation.mutate(activity.public_id)}
                            disabled={completeMutation.isPending}
                          >
                            <CheckCircle2 className="size-3.5" />
                            {t("crm.complete")}
                          </Button>
                        ) : null}
                      </div>
                      {activity.note ? (
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                          {activity.note}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-4">
          <Card className="rounded-lg border-border bg-card/95">
            <CardHeader>
              <CardTitle>{t("crm.dealControls")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>{t("crm.stage")}</Label>
                <Select
                  value={deal.stage_id}
                  disabled={moveMutation.isPending}
                  onValueChange={(stageId) => moveMutation.mutate(stageId)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(pipeline?.stages ?? []).map((stage) => (
                      <SelectItem key={stage.public_id} value={stage.public_id}>
                        {stage.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>{t("crm.value")}</Label>
                <Input
                  type="number"
                  min="0"
                  defaultValue={deal.value_amount ?? ""}
                  onBlur={(event) =>
                    updateValueMutation.mutate(
                      event.target.value ? Number(event.target.value) : null,
                    )
                  }
                />
              </div>
              <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
                <div className="flex items-center gap-2 font-medium">
                  <CircleDollarSign className="size-4" />
                  {formatCurrency(deal.value_amount ?? 0)}
                </div>
                <p className="mt-1 text-muted-foreground">
                  {t("crm.probabilityValue", { value: deal.probability })}
                </p>
                <p className="mt-1 text-muted-foreground">
                  {deal.next_follow_up_at
                    ? t("crm.nextFollowUpValue", { date: formatDate(deal.next_follow_up_at) })
                    : t("crm.noFollowUp")}
                </p>
              </div>
              <Separator />
              <div className="space-y-2">
                <Label>{t("crm.lostReason")}</Label>
                <Input
                  value={lostReason}
                  onChange={(event) => setLostReason(event.target.value)}
                  placeholder={t("crm.lostReasonPlaceholder")}
                />
                <Button
                  variant="outline"
                  className="w-full bg-transparent"
                  onClick={() => lostMutation.mutate()}
                  disabled={lostMutation.isPending}
                >
                  <XCircle className="size-3.5" />
                  {t("crm.markLost")}
                </Button>
              </div>
            </CardContent>
          </Card>
        </aside>
      </section>
    </div>
  );
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}
