import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Microscope } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { errorKeyFor } from "@/features/copilot/use-agent-run";
import type { ResearchHistoryChange, ResearchHistoryItem } from "@/types/research";

import { getLeadResearchHistory, runLeadResearch, type ResearchDepth } from "../research-api";
import { formatPercent01, formatWhen, humanizeKey, scoreDelta } from "../research-format";

const PAGE_SIZE = 5;
const DEPTHS: readonly ResearchDepth[] = ["quick", "standard", "deep"];

export function ResearchHistoryPanel({ leadId, canRun }: { leadId: string; canRun: boolean }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [depth, setDepth] = useState<ResearchDepth>("standard");

  const history = useInfiniteQuery({
    queryKey: ["lead", leadId, "research-history"],
    queryFn: ({ pageParam }) => getLeadResearchHistory(leadId, pageParam, PAGE_SIZE),
    initialPageParam: 1,
    getNextPageParam: (last) => {
      const { page, per_page, total } = last.pagination;
      return page * per_page < total ? page + 1 : undefined;
    },
    enabled: Boolean(leadId),
  });

  const research = useMutation({
    mutationFn: () => runLeadResearch(leadId, depth),
    onSuccess: () => {
      // Evidence, history, score and activity all derive from the new run.
      void queryClient.invalidateQueries({ queryKey: ["lead", leadId] });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  const items = history.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card role="region" aria-labelledby="rh-title" className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
      <CardHeader>
        <CardTitle id="rh-title" role="heading" aria-level={2}>
          {t("researchHistory.title")}
        </CardTitle>
        <CardDescription>{t("researchHistory.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {canRun ? (
          <form
            className="space-y-3 rounded-xl border border-border bg-muted/10 p-3"
            onSubmit={(event) => {
              event.preventDefault();
              research.mutate();
            }}
          >
            <fieldset disabled={research.isPending} className="space-y-2">
              <legend className="text-sm font-medium">{t("researchHistory.depthLabel")}</legend>
              <RadioGroup
                value={depth}
                onValueChange={(value) => setDepth(value as ResearchDepth)}
                className="grid gap-2 sm:grid-cols-3"
              >
                {DEPTHS.map((option) => (
                  <Label
                    key={option}
                    htmlFor={`depth-${option}`}
                    className="flex cursor-pointer items-start gap-2 rounded-lg border border-border p-2.5 has-[[data-state=checked]]:border-[oklch(var(--signal))]"
                  >
                    <RadioGroupItem id={`depth-${option}`} value={option} className="mt-0.5" />
                    <span>
                      <span className="block text-sm font-medium">{t(`researchHistory.depth.${option}`)}</span>
                      <span className="block text-xs font-normal text-muted-foreground">
                        {t(`researchHistory.depthHint.${option}`)}
                      </span>
                    </span>
                  </Label>
                ))}
              </RadioGroup>
            </fieldset>
            <Button type="submit" size="sm" disabled={research.isPending}>
              <Microscope className="size-3.5" aria-hidden />
              {research.isPending ? t("researchHistory.running") : t("researchHistory.run")}
            </Button>
            {research.isError ? (
              <p role="alert" className="text-sm text-destructive">
                {t(errorKeyFor(research.error))}
              </p>
            ) : null}
            {research.isSuccess ? (
              <p role="status" className="text-sm text-[oklch(var(--evidence))]">
                {t("researchHistory.completed", { count: research.data.contradictions_detected })}
              </p>
            ) : null}
          </form>
        ) : null}

        {history.isPending ? (
          <div className="space-y-2" aria-busy="true" aria-label={t("researchHistory.loading")}>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : history.isError ? (
          <div className="space-y-3">
            <QueryStateNotice tone="error" title={t("researchHistory.title")} error={history.error} />
            <Button size="sm" variant="outline" className="bg-transparent" onClick={() => void history.refetch()}>
              {t("common.retry")}
            </Button>
          </div>
        ) : items.length === 0 ? (
          <EmptyState title={t("researchHistory.emptyTitle")} description={t("researchHistory.emptyDescription")} />
        ) : (
          <>
            <ol className="space-y-3">
              {items.map((item) => (
                <RunRow key={item.run_id} item={item} />
              ))}
            </ol>
            {history.hasNextPage ? (
              <Button
                size="sm"
                variant="outline"
                className="bg-transparent"
                disabled={history.isFetchingNextPage}
                onClick={() => void history.fetchNextPage()}
              >
                {history.isFetchingNextPage ? t("common.loading") : t("researchHistory.loadMore")}
              </Button>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function RunRow({ item }: { item: ResearchHistoryItem }) {
  const { t, i18n } = useTranslation();
  const delta = scoreDelta(item.score_before, item.score_after);
  const failed = item.status !== "completed";

  return (
    <li className="rounded-xl border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{formatWhen(item.completed_at || item.started_at, i18n.language)}</span>
        <Badge tone="neutral">{t(`researchHistory.depth.${item.depth}`, { defaultValue: humanizeKey(item.depth) })}</Badge>
        {failed ? <Badge tone="danger">{t("researchHistory.statusFailed")}</Badge> : null}
        <span className="text-xs text-muted-foreground">
          {t("researchHistory.coverage", { value: formatPercent01(item.research_coverage) })}
        </span>
        {item.score_before !== null && item.score_after !== null ? (
          <span className="ms-auto inline-flex items-center gap-1 text-xs">
            {item.score_before}
            <ArrowRight className="size-3 rtl:rotate-180" aria-hidden />
            <strong>{item.score_after}</strong>
            {delta !== null && delta !== 0 ? (
              <Badge tone={delta > 0 ? "success" : "warning"}>{delta > 0 ? `+${delta}` : String(delta)}</Badge>
            ) : null}
          </span>
        ) : null}
      </div>

      <div className="mt-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("researchHistory.whatChanged")}
        </h4>
        {item.changes.length === 0 ? (
          <p className="mt-1.5 text-sm text-muted-foreground">{t("researchHistory.noChanges")}</p>
        ) : (
          <ul className="mt-1.5 space-y-2">
            {item.changes.map((change) => (
              <ChangeRow key={change.change_id ?? `${change.claim_type}-${change.change_type}`} change={change} />
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

function ChangeRow({ change }: { change: ResearchHistoryChange }) {
  const { t } = useTranslation();
  const label = t(`researchHistory.changeTypes.${change.change_type}`, {
    defaultValue: humanizeKey(change.change_type),
  });
  return (
    <li className="text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{label}</span>
        {change.significance >= 0.7 ? <Badge tone="warning">{t("researchHistory.significant")}</Badge> : null}
      </div>
      {change.before !== null || change.after !== null ? (
        <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-muted-foreground">
          <span className="break-words line-through decoration-muted-foreground/50">
            {change.before ?? t("researchHistory.none")}
          </span>
          <ArrowRight className="size-3 shrink-0 rtl:rotate-180" aria-hidden />
          <span className="break-words text-foreground">{change.after ?? t("researchHistory.none")}</span>
        </p>
      ) : null}
      {change.explanation ? <p className="mt-0.5 text-xs text-muted-foreground">{change.explanation}</p> : null}
    </li>
  );
}
