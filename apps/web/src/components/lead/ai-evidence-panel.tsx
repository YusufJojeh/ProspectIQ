import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ThumbsDown, ThumbsUp } from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";
import { titleCaseLabel } from "@/lib/presenters";
import type { AIFeedbackRating, LeadAiEvidenceResponse } from "@/types/api";

export function LeadAiEvidencePanel({
  evidence,
  loading,
  error,
  canGiveFeedback,
  onSubmitFeedback,
  submittingFeedback,
  feedbackSubmitted,
}: {
  evidence: LeadAiEvidenceResponse | null;
  loading: boolean;
  error: Error | null;
  canGiveFeedback: boolean;
  onSubmitFeedback: (rating: AIFeedbackRating, correction: string) => void;
  submittingFeedback: boolean;
  feedbackSubmitted: boolean;
}) {
  const { t } = useTranslation();
  const [rating, setRating] = useState<AIFeedbackRating | null>(null);
  const [correction, setCorrection] = useState("");
  const items = evidence?.items ?? [];

  return (
    <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
      <CardHeader>
        <CardTitle>{t("leadDetail.evidence.title")}</CardTitle>
        <CardDescription>{t("leadDetail.evidence.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <QueryStateNotice
            tone="loading"
            title={t("leadDetail.evidence.loadingTitle")}
            description={t("leadDetail.evidence.loadingDescription")}
          />
        ) : error ? (
          <QueryStateNotice
            tone="error"
            title={t("leadDetail.evidence.loadErrorTitle")}
            error={error}
          />
        ) : items.length === 0 ? (
          <EmptyState
            title={t("leadDetail.evidence.noneTitle")}
            description={t("leadDetail.evidence.noneDescription")}
          />
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <div
                key={item.public_id}
                className="rounded-xl border border-border bg-muted/20 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Badge tone="info" className="max-w-full">
                    <span className="truncate">
                      {titleCaseLabel(item.source_type)}
                    </span>
                  </Badge>
                  <Badge tone={confidenceTone(item.confidence)}>
                    {t("leadDetail.evidence.confidence", {
                      pct: Math.round(item.confidence * 100),
                    })}
                  </Badge>
                </div>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  {item.evidence_text}
                </p>
                {item.source_url ? (
                  <a
                    href={item.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 inline-block text-xs font-medium text-[oklch(var(--signal))] hover:underline"
                  >
                    {t("leadDetail.evidence.source")}
                  </a>
                ) : null}
              </div>
            ))}
          </div>
        )}

        {canGiveFeedback ? (
          <div className="space-y-3 rounded-xl border border-border bg-muted/10 p-4">
            <p className="text-sm font-medium">
              {t("leadDetail.evidence.feedbackPrompt")}
            </p>
            {feedbackSubmitted ? (
              <QueryStateNotice
                tone="success"
                title={t("leadDetail.evidence.feedbackThanksTitle")}
                description={t("leadDetail.evidence.feedbackThanksDescription")}
              />
            ) : (
              <>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant={rating === "useful" ? "default" : "outline"}
                    onClick={() => setRating("useful")}
                  >
                    <ThumbsUp className="size-3.5" />
                    {t("leadDetail.evidence.useful")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={rating === "not_useful" ? "default" : "outline"}
                    onClick={() => setRating("not_useful")}
                  >
                    <ThumbsDown className="size-3.5" />
                    {t("leadDetail.evidence.notUseful")}
                  </Button>
                </div>
                <Textarea
                  aria-label={t("leadDetail.evidence.correctionLabel")}
                  placeholder={t("leadDetail.evidence.correctionPlaceholder")}
                  value={correction}
                  onChange={(event) => setCorrection(event.target.value)}
                />
                <Button
                  type="button"
                  size="sm"
                  disabled={!rating || submittingFeedback}
                  onClick={() =>
                    rating && onSubmitFeedback(rating, correction.trim())
                  }
                >
                  {submittingFeedback
                    ? t("common.saving")
                    : t("leadDetail.evidence.submitFeedback")}
                </Button>
              </>
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function confidenceTone(confidence: number): BadgeTone {
  if (confidence >= 0.7) return "success";
  if (confidence >= 0.4) return "warning";
  return "neutral";
}
