import { MessageSquareText, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { formatDate } from "@/lib/presenters";

export function LeadActivityPanel({
  items,
  noteDraft,
  onNoteChange,
  onSaveNote,
  saving,
  error,
}: {
  items: Array<{ id: string; source: string; createdAt: string; title: string; detail: string; actor: string }>;
  noteDraft: string;
  onNoteChange: (value: string) => void;
  onSaveNote: () => void;
  saving?: boolean;
  error?: string | null;
}) {
  return (
    <section className="rounded-2xl border border-border bg-card/95">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-4">
        <div>
          <h2 className="text-sm font-semibold">Activity timeline</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Notes, workflow changes, and audit events stay on one operational timeline.
          </p>
        </div>
        <Badge tone="neutral">{items.length} events</Badge>
      </header>

      <div className="space-y-4 p-4">
        <div className="rounded-xl border border-border bg-muted/20 p-4">
          <p className="text-sm font-medium">Add note</p>
          <Textarea
            value={noteDraft}
            onChange={(event) => onNoteChange(event.target.value)}
            className="mt-3 min-h-[110px]"
            placeholder="Capture qualification context, handoff notes, or next-step detail."
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button onClick={onSaveNote} disabled={saving || noteDraft.trim().length === 0}>
              <MessageSquareText className="size-3.5" />
              {saving ? "Saving..." : "Save note"}
            </Button>
            {error ? <QueryStateNotice tone="error" title="Could not save note" description={error} /> : null}
          </div>
        </div>

        <div className="space-y-3">
          {items.map((item) => (
            <article key={item.id} className="rounded-xl border border-border bg-muted/20 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="rounded-xl border border-border bg-background p-2">
                    <ShieldCheck className="size-4 text-[oklch(var(--signal))]" />
                  </div>
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium">{item.title}</p>
                      <Badge tone={item.source === "audit" ? "warning" : "accent"}>{item.source}</Badge>
                    </div>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">{item.detail}</p>
                  </div>
                </div>
                <div className="text-right text-xs uppercase tracking-[0.16em] text-muted-foreground">
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
