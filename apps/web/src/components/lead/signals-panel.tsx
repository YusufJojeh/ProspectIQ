import { useTranslation } from "react-i18next";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatDate, titleCaseLabel } from "@/lib/presenters";
import type { LeadSignalsResponse } from "@/types/api";

export function LeadSignalsPanel({
  signals,
  loading,
  error,
  recomputing,
  onRecompute,
}: {
  signals: LeadSignalsResponse | null;
  loading: boolean;
  error: Error | null;
  recomputing: boolean;
  onRecompute: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>{t("leadDetail.signals.title")}</CardTitle>
            <CardDescription>
              {t("leadDetail.signals.description")}
            </CardDescription>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={onRecompute}
            disabled={recomputing}
          >
            {recomputing
              ? t("leadDetail.signals.recomputing")
              : t("leadDetail.signals.recompute")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <QueryStateNotice
            tone="loading"
            title={t("leadDetail.signals.loadingTitle")}
            description={t("leadDetail.signals.loadingDescription")}
          />
        ) : error ? (
          <QueryStateNotice
            tone="error"
            title={t("leadDetail.signals.loadErrorTitle")}
            error={error}
          />
        ) : (signals?.items ?? []).length === 0 ? (
          <EmptyState
            title={t("leadDetail.signals.noneTitle")}
            description={t("leadDetail.signals.noneDescription")}
          />
        ) : (
          signals?.items.map((signal) => (
            <div
              key={signal.public_id}
              className="rounded-xl border border-border bg-muted/20 p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Badge tone={signalTone(signal.signal_strength)}>
                  {t(`leadDetail.signals.types.${signal.signal_type}`, {
                    defaultValue: titleCaseLabel(signal.signal_type),
                  })}
                </Badge>
                <span className="font-mono text-xs text-muted-foreground">
                  {formatStrength(signal.signal_strength)}
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                {signal.evidence_text}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <span>{formatDate(signal.detected_at)}</span>
                {signal.source_url ? (
                  <a
                    href={signal.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-[oklch(var(--signal))] hover:underline"
                  >
                    {t("leadDetail.signals.source")}
                  </a>
                ) : null}
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function formatStrength(value: number) {
  const pct = value <= 1 ? value * 100 : value;
  return `${Math.round(pct)}%`;
}

function signalTone(value: number): BadgeTone {
  const pct = value <= 1 ? value * 100 : value;
  if (pct >= 70) return "success";
  if (pct >= 40) return "warning";
  return "neutral";
}
