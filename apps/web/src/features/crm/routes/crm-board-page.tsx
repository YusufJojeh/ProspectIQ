import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BriefcaseBusiness, CalendarClock, CircleDollarSign, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { appPaths } from "@/app/paths";
import { LeadScoreSpinner } from "@/components/brand/lead-score-spinner";
import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  createCrmDeal,
  listCrmDeals,
  listCrmPipelines,
  moveCrmDeal,
} from "@/features/crm/api";
import { listLeads } from "@/features/leads/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { scoreBandLabel } from "@/lib/i18n-labels";
import { bandTone, formatDate } from "@/lib/presenters";
import type { CrmDealResponse, CrmStageResponse, DealStatus } from "@/types/api";

type CreateDealForm = {
  leadId: string;
  title: string;
  valueAmount: string;
  stageId: string;
};

const initialForm: CreateDealForm = {
  leadId: "",
  title: "",
  valueAmount: "",
  stageId: "",
};

export function CrmBoardPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<DealStatus | "all">("open");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<CreateDealForm>(initialForm);
  useDocumentTitle(t("crm.title"));

  const pipelinesQuery = useQuery({
    queryKey: ["crm", "pipelines"],
    queryFn: listCrmPipelines,
  });
  const pipeline = pipelinesQuery.data?.items[0] ?? null;
  const dealsQuery = useQuery({
    queryKey: ["crm", "deals", pipeline?.public_id, status],
    queryFn: () =>
      listCrmDeals({
        pipeline_id: pipeline?.public_id,
        status: status === "all" ? undefined : status,
      }),
    enabled: Boolean(pipeline?.public_id),
  });
  const leadsQuery = useQuery({
    queryKey: ["leads", "crm-create-options"],
    queryFn: () => listLeads({ page_size: 100, sort: "score_desc" }),
  });

  const invalidateCrm = () => {
    void queryClient.invalidateQueries({ queryKey: ["crm"] });
  };

  const createDealMutation = useMutation({
    mutationFn: () =>
      createCrmDeal({
        lead_id: form.leadId,
        title: form.title.trim() || undefined,
        stage_id: form.stageId || undefined,
        value_amount: form.valueAmount.trim() ? Number(form.valueAmount) : undefined,
      }),
    onSuccess: () => {
      setDialogOpen(false);
      setForm(initialForm);
      invalidateCrm();
      toast.success(t("crm.dealCreated"));
    },
  });

  const moveMutation = useMutation({
    mutationFn: ({ dealId, stageId }: { dealId: string; stageId: string }) =>
      moveCrmDeal(dealId, stageId),
    onSuccess: () => {
      invalidateCrm();
      toast.success(t("crm.dealMoved"));
    },
  });

  const deals = useMemo(() => dealsQuery.data?.items ?? [], [dealsQuery.data]);
  const stageDeals = useMemo(() => groupDealsByStage(deals), [deals]);

  if (pipelinesQuery.isPending) {
    return (
      <div className="space-y-4 p-3 sm:p-4 lg:p-6">
        <Skeleton className="h-28 rounded-lg" />
        <div className="grid gap-3 xl:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <Skeleton key={item} className="h-96 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (pipelinesQuery.isError) {
    return (
      <EmptyState
        title={t("crm.unavailableTitle")}
        description={pipelinesQuery.error.message}
      />
    );
  }

  if (!pipeline) {
    return (
      <EmptyState
        title={t("crm.noPipelineTitle")}
        description={t("crm.noPipelineDescription")}
      />
    );
  }

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow={t("crm.eyebrow")}
        title={t("crm.title")}
        description={t("crm.description")}
        actions={
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="size-3.5" />
                {t("crm.createDeal")}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t("crm.createDeal")}</DialogTitle>
                <DialogDescription>{t("crm.createDealDescription")}</DialogDescription>
              </DialogHeader>
              <div className="grid gap-4">
                <div className="space-y-2">
                  <Label>{t("crm.lead")}</Label>
                  <Select
                    value={form.leadId}
                    onValueChange={(leadId) => setForm((current) => ({ ...current, leadId }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t("crm.selectLead")} />
                    </SelectTrigger>
                    <SelectContent>
                      {(leadsQuery.data?.items ?? []).map((lead) => (
                        <SelectItem key={lead.public_id} value={lead.public_id}>
                          {lead.company_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="deal-title">{t("crm.dealTitle")}</Label>
                  <Input
                    id="deal-title"
                    value={form.title}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, title: event.target.value }))
                    }
                    placeholder={t("crm.dealTitlePlaceholder")}
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="deal-value">{t("crm.value")}</Label>
                    <Input
                      id="deal-value"
                      type="number"
                      min="0"
                      value={form.valueAmount}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          valueAmount: event.target.value,
                        }))
                      }
                      placeholder="12000"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t("crm.stage")}</Label>
                    <Select
                      value={form.stageId}
                      onValueChange={(stageId) =>
                        setForm((current) => ({ ...current, stageId }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={t("crm.defaultStage")} />
                      </SelectTrigger>
                      <SelectContent>
                        {pipeline.stages
                          .filter((stage) => stage.stage_type === "open")
                          .map((stage) => (
                            <SelectItem key={stage.public_id} value={stage.public_id}>
                              {stage.name}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  className="bg-transparent"
                  onClick={() => setDialogOpen(false)}
                >
                  {t("common.cancel")}
                </Button>
                <Button
                  disabled={!form.leadId || createDealMutation.isPending}
                  onClick={() => createDealMutation.mutate()}
                >
                  {createDealMutation.isPending ? t("common.creating") : t("crm.createDeal")}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      <section className="grid gap-3 sm:grid-cols-3">
        <SummaryCard
          icon={BriefcaseBusiness}
          label={t("crm.openDeals")}
          value={String(deals.filter((deal) => deal.status === "open").length)}
        />
        <SummaryCard
          icon={CircleDollarSign}
          label={t("crm.pipelineValue")}
          value={formatCurrency(deals.reduce((sum, deal) => sum + (deal.value_amount ?? 0), 0))}
        />
        <SummaryCard
          icon={CalendarClock}
          label={t("crm.overdueActivities")}
          value={String(deals.reduce((sum, deal) => sum + deal.overdue_activity_count, 0))}
        />
      </section>

      <Tabs value={status} onValueChange={(value) => setStatus(value as DealStatus | "all")}>
        <TabsList>
          <TabsTrigger value="open">{t("crm.statuses.open")}</TabsTrigger>
          <TabsTrigger value="won">{t("crm.statuses.won")}</TabsTrigger>
          <TabsTrigger value="lost">{t("crm.statuses.lost")}</TabsTrigger>
          <TabsTrigger value="all">{t("common.all")}</TabsTrigger>
        </TabsList>
        <TabsContent value={status} className="mt-4">
          {dealsQuery.isPending ? (
            <div className="grid gap-3 xl:grid-cols-4">
              {pipeline.stages.slice(0, 4).map((stage) => (
                <Skeleton key={stage.public_id} className="h-96 rounded-lg" />
              ))}
            </div>
          ) : dealsQuery.isError ? (
            <QueryStateNotice
              tone="error"
              title={t("crm.dealsUnavailableTitle")}
              description={dealsQuery.error.message}
            />
          ) : deals.length === 0 ? (
            <EmptyState
              title={t("crm.emptyDealsTitle")}
              description={t("crm.emptyDealsDescription")}
            />
          ) : (
            <div className="grid gap-3 xl:grid-cols-4">
              {pipeline.stages.map((stage) => (
                <StageColumn
                  key={stage.public_id}
                  stage={stage}
                  deals={stageDeals.get(stage.public_id) ?? []}
                  stages={pipeline.stages}
                  moving={moveMutation.isPending}
                  onMove={(dealId, stageId) => moveMutation.mutate({ dealId, stageId })}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StageColumn({
  stage,
  deals,
  stages,
  moving,
  onMove,
}: {
  stage: CrmStageResponse;
  deals: CrmDealResponse[];
  stages: CrmStageResponse[];
  moving: boolean;
  onMove: (dealId: string, stageId: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <section className="min-h-[24rem] rounded-lg border border-border bg-muted/20 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">{stage.name}</h2>
          <p className="text-xs text-muted-foreground">
            {t("crm.stageSummary", {
              count: deals.length,
              probability: stage.probability,
            })}
          </p>
        </div>
        <Badge tone={stage.stage_type === "won" ? "success" : stage.stage_type === "lost" ? "danger" : "neutral"}>
          {t(`crm.stageTypes.${stage.stage_type}`)}
        </Badge>
      </div>
      <Separator className="my-3" />
      {deals.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-background/60 p-4 text-sm text-muted-foreground">
          {t("crm.noDealsInStage")}
        </div>
      ) : (
        <div className="space-y-3">
          {deals.map((deal) => (
            <DealCard
              key={deal.public_id}
              deal={deal}
              stages={stages}
              moving={moving}
              onMove={onMove}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function DealCard({
  deal,
  stages,
  moving,
  onMove,
}: {
  deal: CrmDealResponse;
  stages: CrmStageResponse[];
  moving: boolean;
  onMove: (dealId: string, stageId: string) => void;
}) {
  const { t } = useTranslation();
  const score = deal.lead.latest_final_priority_score ?? deal.lead.latest_score ?? 0;
  return (
    <Card className="rounded-lg border-border bg-card">
      <CardContent className="space-y-3 p-3">
        <div className="flex items-start gap-3">
          <LeadScoreSpinner
            value={score}
            size={44}
            label={t("leadScoreSpinner.companyScore", {
              company: deal.lead.company_name,
              score: Math.round(score),
            })}
          />
          <div className="min-w-0 flex-1">
            <Link
              to={appPaths.dealDetail(deal.public_id)}
              className="line-clamp-2 text-sm font-semibold hover:text-[oklch(var(--signal))]"
            >
              {deal.title}
            </Link>
            <p className="truncate text-xs text-muted-foreground">{deal.lead.company_name}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge tone={bandTone(deal.lead.latest_band)}>
            {scoreBandLabel(t, deal.lead.latest_band)}
          </Badge>
          <Badge tone={deal.status === "won" ? "success" : deal.status === "lost" ? "danger" : "neutral"}>
            {t(`crm.statuses.${deal.status}`)}
          </Badge>
          {deal.campaign_name ? <Badge tone="accent">{deal.campaign_name}</Badge> : null}
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
          <span>{formatCurrency(deal.value_amount ?? 0)}</span>
          <span>{t("crm.probabilityValue", { value: deal.probability })}</span>
          <span className="col-span-2">
            {deal.next_follow_up_at
              ? t("crm.nextFollowUpValue", { date: formatDate(deal.next_follow_up_at) })
              : t("crm.noFollowUp")}
          </span>
        </div>
        <Select
          value={deal.stage_id}
          disabled={moving}
          onValueChange={(stageId) => onMove(deal.public_id, stageId)}
        >
          <SelectTrigger className="h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {stages.map((stage) => (
              <SelectItem key={stage.public_id} value={stage.public_id}>
                {stage.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </CardContent>
    </Card>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof BriefcaseBusiness;
  label: string;
  value: string;
}) {
  return (
    <Card className="rounded-lg border-border bg-card/95">
      <CardContent className="flex items-center gap-3 p-4">
        <div className="flex size-10 items-center justify-center rounded-md border border-border bg-muted/40">
          <Icon className="size-4 text-muted-foreground" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-xl font-semibold">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function groupDealsByStage(deals: CrmDealResponse[]) {
  const grouped = new Map<string, CrmDealResponse[]>();
  for (const deal of deals) {
    grouped.set(deal.stage_id, [...(grouped.get(deal.stage_id) ?? []), deal]);
  }
  return grouped;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}
