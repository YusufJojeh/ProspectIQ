import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { displayHost, safeHttpUrl } from "@/lib/safe-url";
import type { CanonicalFact, CanonicalFactStatus, EvidenceSource } from "@/types/research";

import { getLeadEvidenceGraph } from "../research-api";
import { formatPercent01, formatWhen, humanizeKey } from "../research-format";

const STATUS_TONE: Record<CanonicalFactStatus, "success" | "warning" | "neutral"> = {
  supported: "success",
  conflicting: "warning",
  unknown: "neutral",
};

export function EvidenceGraphPanel({ leadId }: { leadId: string }) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: ["lead", leadId, "evidence-graph"],
    queryFn: () => getLeadEvidenceGraph(leadId),
    enabled: Boolean(leadId),
  });
  const graph = query.data;
  const groups = (graph?.groups ?? []).filter((group) => group.facts.length > 0);

  return (
    <Card role="region" aria-labelledby="eg-title" className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle id="eg-title" role="heading" aria-level={2}>
            {t("evidenceGraph.title")}
          </CardTitle>
          {graph ? (
            <div className="flex flex-wrap gap-2">
              <Badge tone="neutral">
                {t("evidenceGraph.confidence", { value: formatPercent01(graph.evidence_confidence) })}
              </Badge>
              <Badge tone="neutral">
                {t("evidenceGraph.coverage", { value: formatPercent01(graph.research_coverage) })}
              </Badge>
            </div>
          ) : null}
        </div>
        <CardDescription>{t("evidenceGraph.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {query.isPending ? (
          <div className="space-y-3" aria-busy="true" aria-label={t("evidenceGraph.loading")}>
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : query.isError ? (
          <div className="space-y-3">
            <QueryStateNotice tone="error" title={t("evidenceGraph.title")} error={query.error} />
            <Button size="sm" variant="outline" className="bg-transparent" onClick={() => void query.refetch()}>
              {t("common.retry")}
            </Button>
          </div>
        ) : groups.length === 0 ? (
          <EmptyState title={t("evidenceGraph.emptyTitle")} description={t("evidenceGraph.emptyDescription")} />
        ) : (
          groups.map((group) => (
            <section key={group.group} aria-labelledby={`eg-${group.group}`}>
              <h3
                id={`eg-${group.group}`}
                className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
              >
                {t(`evidenceGraph.groups.${group.group}`, { defaultValue: humanizeKey(group.group) })}
              </h3>
              <ul className="mt-2 space-y-2">
                {group.facts.map((fact) => (
                  <FactRow key={`${fact.claim_type}:${fact.value}`} fact={fact} />
                ))}
              </ul>
            </section>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function FactRow({ fact }: { fact: CanonicalFact }) {
  const { t } = useTranslation();
  const conflicting = fact.status === "conflicting" || fact.contradicting_values.length > 0;
  const sourceCount = fact.sources.length;

  return (
    <li className="rounded-xl border border-border bg-muted/10">
      <details className="group">
        <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 p-3 [&::-webkit-details-marker]:hidden">
          <span className="text-xs text-muted-foreground">
            {t(`evidenceGraph.claims.${fact.claim_type}`, { defaultValue: humanizeKey(fact.claim_type) })}
          </span>
          <span className="min-w-0 flex-1 break-words text-sm font-medium">{fact.value}</span>
          <Badge tone={STATUS_TONE[fact.status]}>{t(`evidenceGraph.status.${fact.status}`)}</Badge>
          <span className="text-xs text-muted-foreground">
            {t("evidenceGraph.sourceCount", { count: sourceCount })}
          </span>
        </summary>
        <div className="space-y-3 border-t border-border p-3 text-sm">
          <dl className="grid grid-cols-3 gap-2 text-xs">
            <Metric label={t("evidenceGraph.metrics.confidence")} value={formatPercent01(fact.confidence)} />
            <Metric label={t("evidenceGraph.metrics.freshness")} value={formatPercent01(fact.freshness_score)} />
            <Metric label={t("evidenceGraph.metrics.quality")} value={formatPercent01(fact.source_quality)} />
          </dl>
          <SourceList sources={fact.sources} />
          {conflicting ? (
            <div className="rounded-lg border border-[oklch(var(--caution)/0.3)] bg-[oklch(var(--caution)/0.08)] p-2.5">
              <p className="text-xs font-medium">{t("evidenceGraph.conflictTitle")}</p>
              <ul className="mt-1.5 space-y-2">
                {fact.contradicting_values.map((other) => (
                  <li key={other.value}>
                    <p className="break-words text-sm">{other.value}</p>
                    <SourceList sources={other.sources} compact />
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </details>
    </li>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

function SourceList({ sources, compact = false }: { sources: EvidenceSource[]; compact?: boolean }) {
  const { t, i18n } = useTranslation();
  if (sources.length === 0) return null;
  return (
    <ul className={compact ? "mt-1 space-y-0.5" : "space-y-1.5"}>
      {sources.map((source, index) => {
        const href = safeHttpUrl(source.url);
        const host = displayHost(source.url);
        return (
          <li
            key={`${source.evidence_ref ?? source.provider}-${index}`}
            className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground"
          >
            <span className="font-medium text-foreground">
              {t(`evidenceGraph.providers.${source.provider}`, { defaultValue: humanizeKey(source.provider) })}
            </span>
            {href ? (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className="inline-flex items-center gap-1 underline-offset-2 hover:underline"
              >
                {host}
                <ExternalLink className="size-3" aria-hidden />
                <span className="sr-only">{t("evidenceGraph.opensNewTab")}</span>
              </a>
            ) : null}
            <span>{formatWhen(source.observed_at, i18n.language)}</span>
          </li>
        );
      })}
    </ul>
  );
}
