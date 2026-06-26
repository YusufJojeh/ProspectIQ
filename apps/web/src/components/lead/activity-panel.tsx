import { MessageSquareText, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { formatDate } from "@/lib/presenters";
import type { ApiError } from "@/lib/api-client";

export function LeadActivityPanel({
  items,
  noteDraft,
  onNoteChange,
  onSaveNote,
  saving,
  error,
}: {
  items: Array<{
    id: string;
    source: string;
    createdAt: string;
    title: string;
    detail: string;
    actor: string;
  }>;
  noteDraft: string;
  onNoteChange: (value: string) => void;
  onSaveNote: () => void;
  saving?: boolean;
  error?: ApiError | Error | null;
}) {
  const { t } = useTranslation();
  return (
    <section className="rounded-2xl border border-border bg-card/95">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-4">
        <div>
          <h2 className="text-sm font-semibold">
            {t("leadDetail.activityTimeline")}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("leadDetail.activityTimelineDescription")}
          </p>
        </div>
        <Badge tone="neutral">
          {t("leadDetail.activityEvents", { count: items.length })}
        </Badge>
      </header>

      <div className="space-y-4 p-4">
        <div className="rounded-xl border border-border bg-muted/20 p-4">
          <p className="text-sm font-medium">{t("leads.addNote")}</p>
          <Textarea
            value={noteDraft}
            onChange={(event) => onNoteChange(event.target.value)}
            className="mt-3 min-h-[110px]"
            placeholder={t("leadDetail.notePlaceholder")}
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              onClick={onSaveNote}
              disabled={saving || noteDraft.trim().length === 0}
            >
              <MessageSquareText className="size-3.5" />
              {saving ? t("common.loading") : t("leadDetail.saveNote")}
            </Button>
            {error ? (
              <QueryStateNotice
                tone="error"
                title={t("leadDetail.saveNoteError")}
                error={error}
              />
            ) : null}
          </div>
        </div>

        <div className="space-y-3">
          {items.map((item) => (
            <article
              key={item.id}
              className="rounded-xl border border-border bg-muted/20 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="rounded-xl border border-border bg-background p-2">
                    <ShieldCheck className="size-4 text-[oklch(var(--signal))]" />
                  </div>
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium">{item.title}</p>
                      <Badge
                        tone={item.source === "audit" ? "warning" : "accent"}
                      >
                        {item.source}
                      </Badge>
                    </div>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">
                      {item.detail}
                    </p>
                  </div>
                </div>
                <div className="text-end text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  <p>{item.actor}</p>
                  <p className="mt-1">{formatDate(item.createdAt)}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
