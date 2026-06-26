import { useMemo, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Megaphone, Plus, Sparkles } from "lucide-react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { z } from "zod";
import { appPaths } from "@/app/paths";
import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { createCampaign, listCampaigns } from "@/features/campaigns/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { formatDate } from "@/lib/presenters";
import type { CampaignStatus } from "@/types/api";

const campaignSchema = z.object({
  name: z.string().trim().min(2).max(160),
  description: z.string().trim().max(2000).optional(),
});

type CampaignValues = z.infer<typeof campaignSchema>;

function statusTone(status: CampaignStatus) {
  if (status === "active" || status === "completed") return "success";
  if (status === "paused") return "warning";
  if (status === "archived") return "danger";
  return "neutral";
}

export function CampaignsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  useDocumentTitle(t("campaigns.title"));

  const form = useForm<CampaignValues>({
    resolver: zodResolver(campaignSchema),
    defaultValues: { name: "", description: "" },
  });

  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: listCampaigns,
  });

  const createMutation = useMutation({
    mutationFn: (values: CampaignValues) =>
      createCampaign({
        name: values.name,
        description: values.description?.trim() || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      form.reset();
      setOpen(false);
    },
  });

  const campaigns = useMemo(() => campaignsQuery.data?.items ?? [], [campaignsQuery.data]);

  if (campaignsQuery.isError) {
    return (
      <EmptyState
        title={t("campaigns.unavailableTitle")}
        description={campaignsQuery.error.message}
      />
    );
  }

  return (
    <div className="space-y-6 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow={t("campaigns.eyebrow")}
        title={t("campaigns.title")}
        description={t("campaigns.description")}
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="size-3.5" />
                {t("campaigns.create")}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t("campaigns.create")}</DialogTitle>
              </DialogHeader>
              <form
                className="space-y-4"
                onSubmit={form.handleSubmit((values) => createMutation.mutate(values))}
              >
                <div className="space-y-2">
                  <Label>{t("campaigns.name")}</Label>
                  <Input {...form.register("name")} />
                  {form.formState.errors.name ? (
                    <p className="text-sm text-destructive">
                      {form.formState.errors.name.message}
                    </p>
                  ) : null}
                </div>
                <div className="space-y-2">
                  <Label>{t("campaigns.descriptionLabel")}</Label>
                  <Textarea rows={3} {...form.register("description")} />
                </div>
                {createMutation.isError ? (
                  <p className="text-sm text-destructive">{createMutation.error.message}</p>
                ) : null}
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? t("common.saving") : t("campaigns.create")}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {campaignsQuery.isPending ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-40 rounded-lg" />
          ))}
        </div>
      ) : campaigns.length === 0 ? (
        <EmptyState
          title={t("campaigns.emptyTitle")}
          description={t("campaigns.emptyDescription")}
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus className="size-3.5" />
              {t("campaigns.create")}
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {campaigns.map((campaign) => (
            <Card key={campaign.public_id} className="rounded-lg border-border bg-card/95">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="truncate text-base">{campaign.name}</CardTitle>
                    <CardDescription className="mt-1 line-clamp-2">
                      {campaign.description || t("campaigns.noDescription")}
                    </CardDescription>
                  </div>
                  <Badge tone={statusTone(campaign.status)}>
                    {t(`campaigns.statuses.${campaign.status}`)}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-2">
                  <Metric label={t("campaigns.leads")} value={String(campaign.lead_count)} />
                  <Metric
                    label={t("campaigns.steps")}
                    value={String(campaign.sequence_steps_count)}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  {t("campaigns.createdAt", { date: formatDate(campaign.created_at) })}
                </p>
                <Button asChild className="w-full">
                  <Link to={appPaths.campaignDetail(campaign.public_id)}>
                    <Megaphone className="size-3.5" />
                    {t("campaigns.open")}
                  </Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {createMutation.isSuccess ? (
        <QueryStateNotice
          tone="success"
          title={t("campaigns.createdTitle")}
          description={t("campaigns.createdDescription")}
        />
      ) : null}

      <div className="rounded-lg border border-border bg-muted/20 p-4">
        <div className="flex items-start gap-3">
          <Sparkles className="mt-1 size-4 text-[oklch(var(--signal))]" />
          <p className="text-sm leading-6 text-muted-foreground">
            {t("campaigns.scopeNote")}
          </p>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold">{value}</p>
    </div>
  );
}
