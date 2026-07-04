import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { scoreBandLabel } from "@/lib/i18n-labels";
import { bandTone, formatScore } from "@/lib/presenters";
import type { LeadResponse, LeadScoreBreakdownResponse } from "@/types/api";

export function LeadScoringV2Panel({
  lead,
  breakdown,
}: {
  lead: LeadResponse;
  breakdown: LeadScoreBreakdownResponse | null;
}) {
  const { t } = useTranslation();
  const metrics = [
    {
      key: "fit",
      label: t("leadDetail.scoringV2.fitScore"),
      value: breakdown?.fit_score ?? lead.latest_fit_score,
    },
    {
      key: "need",
      label: t("leadDetail.scoringV2.needScore"),
      value: breakdown?.need_score ?? lead.latest_need_score,
    },
    {
      key: "urgency",
      label: t("leadDetail.scoringV2.urgencyScore"),
      value: breakdown?.urgency_score ?? lead.latest_urgency_score,
    },
    {
      key: "reachability",
      label: t("leadDetail.scoringV2.reachabilityScore"),
      value:
        breakdown?.reachability_score ?? lead.latest_reachability_score,
    },
    {
      key: "final",
      label: t("leadDetail.scoringV2.finalPriorityScore"),
      value:
        breakdown?.final_priority_score ??
        lead.latest_final_priority_score ??
        lead.latest_score,
    },
  ];
  const band = breakdown?.band ?? lead.latest_band;

  return (
    <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>{t("leadDetail.scoringV2.title")}</CardTitle>
            <CardDescription>
              {t("leadDetail.scoringV2.description")}
            </CardDescription>
          </div>
          <Badge tone={bandTone(band)}>{scoreBandLabel(t, band)}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {metrics.map((metric) => (
          <ScoreMetricRow
            key={metric.key}
            label={metric.label}
            value={metric.value}
          />
        ))}
      </CardContent>
    </Card>
  );
}

function ScoreMetricRow({
  label,
  value,
}: {
  label: string;
  value: number | null | undefined;
}) {
  const score = value ?? 0;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium">{label}</span>
        <span className="font-mono text-sm tabular-nums">
          {formatScore(value)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-[oklch(var(--signal))]"
          style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
        />
      </div>
    </div>
  );
}
