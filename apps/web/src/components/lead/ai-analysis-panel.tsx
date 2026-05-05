import { AlertTriangle, CheckCircle2, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { MessageResponse } from "@/components/ai-elements/message";
import { formatDate } from "@/lib/presenters";
import type { LeadAnalysisSnapshotResponse } from "@/types/api";
import type { ApiError } from "@/lib/api-client";

export function LeadAiAnalysisPanel({
  snapshot,
  onGenerate,
  leadId,
  generating,
  error,
}: {
  snapshot: LeadAnalysisSnapshotResponse | null;
  onGenerate: () => void;
  leadId: string;
  generating?: boolean;
  error?: ApiError | Error | null;
}) {
  const { t } = useTranslation();
  return (
    <section className="rounded-2xl border border-border bg-card/95">
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-4">
        <div>
          <h2 className="text-sm font-semibold">{t("leadDetail.aiAnalysis")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("leadDetail.aiAnalysisDescription")}
          </p>
        </div>
        <Button data-testid="lead-analysis-generate" onClick={onGenerate} disabled={generating}>
          <Sparkles className="size-3.5" />
          {generating ? t("ai.generating") : snapshot ? t("outreach.regenerate") : t("common.generate")}
        </Button>
      </header>

      <div className="space-y-4 p-4">
        <div className="flex justify-end">
          <Button asChild size="sm" variant="outline" className="bg-transparent">
            <Link to={`${appPaths.assistant}?leadId=${leadId}`}>{t("leadDetail.askAssistant")}</Link>
          </Button>
        </div>
        {error ? <QueryStateNotice tone="error" title={t("leadDetail.analysisUnavailable")} error={error} /> : null}
        {snapshot ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="accent">{snapshot.ai_provider}</Badge>
              <Badge tone="neutral">{snapshot.model_name}</Badge>
              <Badge tone="success">{t("leadDetail.confidencePct", { pct: Math.round(snapshot.analysis.confidence * 100) })}</Badge>
              <Badge tone="neutral">{formatDate(snapshot.created_at)}</Badge>
            </div>

            <div className="rounded-xl border border-border bg-muted/20 p-4">
              <MessageResponse className="ai-markdown text-sm leading-7 text-muted-foreground">
                {snapshot.analysis.summary}
              </MessageResponse>
            </div>

            <InfoList
              title={t("leadDetail.analysisOpportunitiesTitle")}
              icon={<CheckCircle2 className="size-4 text-[oklch(var(--evidence))]" />}
              items={snapshot.analysis.opportunities}
            />
            <InfoList
              title={t("leadDetail.analysisWeaknessesTitle")}
              icon={<AlertTriangle className="size-4 text-[oklch(var(--caution))]" />}
              items={snapshot.analysis.weaknesses}
            />

            {snapshot.service_recommendations.length ? (
              <div className="rounded-xl border border-border bg-muted/20 p-4">
                <p className="text-sm font-medium">{t("leadDetail.recommendedServices")}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {snapshot.service_recommendations.map((item) => (
                    <Badge key={item.public_id} tone="accent">
                      {item.service_name}
                    </Badge>
                  ))}
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <QueryStateNotice
            tone="info"
            title={t("leadDetail.noAnalysisYet")}
            description={t("leadDetail.noAnalysisDescription")}
          />
        )}
      </div>
    </section>
  );
}

function InfoList({
  title,
  items,
  icon,
}: {
  title: string;
  items: string[];
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 p-4">
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-sm font-medium">{title}</p>
      </div>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-muted-foreground">
        {items.map((item) => (
          <li key={item}>
            <MessageResponse className="ai-markdown text-sm leading-6 text-muted-foreground">
              {item}
            </MessageResponse>
          </li>
        ))}
      </ul>
    </div>
  );
}
