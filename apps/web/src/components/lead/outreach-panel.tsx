import { Copy, Save, Send } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { formatDate, titleCaseLabel } from "@/lib/presenters";
import type { OutreachDraftResponse, OutreachTone } from "@/types/api";

export function LeadOutreachPanel({
  draft,
  tone,
  onToneChange,
  subject,
  message,
  onSubjectChange,
  onMessageChange,
  onGenerate,
  onSave,
  generating,
  saving,
  canSave,
  error,
}: {
  draft: OutreachDraftResponse | null;
  tone: OutreachTone;
  onToneChange: (value: OutreachTone) => void;
  subject: string;
  message: string;
  onSubjectChange: (value: string) => void;
  onMessageChange: (value: string) => void;
  onGenerate: (regenerate: boolean) => void;
  onSave: () => void;
  generating?: boolean;
  saving?: boolean;
  canSave: boolean;
  error?: string | null;
}) {
  return (
    <section className="rounded-2xl border border-border bg-card/95">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-4">
        <div>
          <h2 className="text-sm font-semibold">Outreach workspace</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Drafts are generated from the same normalized evidence and scoring context.
          </p>
        </div>
        {draft ? <Badge tone="accent">v{draft.version_number}</Badge> : null}
      </header>

      <div className="space-y-4 p-4">
        {error ? <QueryStateNotice tone="error" title="Outreach unavailable" description={error} /> : null}

        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto_auto]">
          <Select value={tone} onValueChange={(value) => onToneChange(value as OutreachTone)}>
            <SelectTrigger>
              <SelectValue placeholder="Select tone" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="consultative">Consultative</SelectItem>
              <SelectItem value="friendly">Friendly</SelectItem>
              <SelectItem value="formal">Formal</SelectItem>
              <SelectItem value="short_pitch">Short pitch</SelectItem>
            </SelectContent>
          </Select>
          <Button
            data-testid="lead-outreach-generate"
            variant="outline"
            className="bg-transparent"
            onClick={() => onGenerate(false)}
            disabled={generating}
          >
            <Send className="size-3.5" />
            {generating ? "Drafting..." : "Generate"}
          </Button>
          <Button onClick={() => onGenerate(true)} disabled={generating}>
            <Copy className="size-3.5" />
            Regenerate
          </Button>
        </div>

        {draft ? (
          <>
            <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
              <span>{formatDate(draft.updated_at)}</span>
              <span>{titleCaseLabel(draft.tone)}</span>
              <span>{draft.has_manual_edits ? "Edited draft" : "Generated draft"}</span>
            </div>
            <div className="space-y-2">
              <Input value={subject} onChange={(event) => onSubjectChange(event.target.value)} placeholder="Subject" />
              <Textarea value={message} onChange={(event) => onMessageChange(event.target.value)} className="min-h-[220px]" />
            </div>
            <Button data-testid="lead-outreach-save" onClick={onSave} disabled={!canSave || saving}>
              <Save className="size-3.5" />
              {saving ? "Saving..." : "Save edits"}
            </Button>
          </>
        ) : (
          <QueryStateNotice
            tone="info"
            title="No outreach draft yet"
            description="Generate a draft to start editing subject and message content."
          />
        )}
      </div>
    </section>
  );
}
