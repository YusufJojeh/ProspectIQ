import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ScrollText,
  Send,
  Sparkles,
  Copy,
  Check,
  Search,
  Loader2,
  ArrowRight,
  MessageSquare,
} from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { listLeads } from "@/features/leads/api";
import { generateLeadOutreach, getLatestOutreach } from "@/features/outreach/api";
import { appPaths } from "@/app/paths";
import { BandBadge, bandFromScore } from "@/components/brand/badges";
import { useDocumentTitle } from "@/hooks/use-document-title";
import type { LeadResponse, OutreachTone } from "@/types/api";

const TONES: { value: OutreachTone; label: string }[] = [
  { value: "formal", label: "Formal" },
  { value: "friendly", label: "Friendly" },
  { value: "consultative", label: "Consultative" },
  { value: "short_pitch", label: "Short Pitch" },
];

function OutreachCard({ lead }: { lead: LeadResponse }) {
  const [tone, setTone] = useState<OutreachTone>("consultative");
  const [copied, setCopied] = useState(false);
  const queryClient = useQueryClient();

  const latestQuery = useQuery({
    queryKey: ["outreach", lead.public_id],
    queryFn: () => getLatestOutreach(lead.public_id),
    staleTime: 60_000,
  });

  const generateMutation = useMutation({
    mutationFn: () => generateLeadOutreach(lead.public_id, { tone, regenerate: true }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["outreach", lead.public_id] });
    },
  });

  const displayDraft = generateMutation.data ?? latestQuery.data?.message ?? null;
  const band = bandFromScore(lead.latest_score ?? 0);

  async function copyToClipboard(text: string) {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <article className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 transition hover:border-[oklch(var(--signal)/0.3)]">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Link
              to={appPaths.leadDetail(lead.public_id)}
              className="truncate text-[14px] font-medium hover:text-[oklch(var(--signal))]"
            >
              {lead.company_name}
            </Link>
            <BandBadge band={band} />
          </div>
          <div className="mt-0.5 text-[12px] text-muted-foreground">
            {lead.category ?? "Business"} · {lead.city ?? "—"}
          </div>
        </div>
        <Link
          to={appPaths.leadDetail(lead.public_id)}
          className="shrink-0 text-[11px] text-muted-foreground hover:text-foreground"
        >
          <ArrowRight className="size-3.5" />
        </Link>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <Select value={tone} onValueChange={(v) => setTone(v as OutreachTone)}>
          <SelectTrigger className="h-8 w-full text-[12px] sm:w-[150px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TONES.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          size="sm"
          variant="outline"
          className="h-8 w-full bg-transparent text-[12px] sm:w-auto"
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
        >
          {generateMutation.isPending ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Sparkles className="size-3.5" />
          )}
          {displayDraft ? "Regenerate" : "Generate draft"}
        </Button>
      </div>

      {generateMutation.isError && (
        <p className="text-[11.5px] text-destructive">{generateMutation.error.message}</p>
      )}

      {displayDraft && (
        <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/20 p-3">
          <div className="flex items-center justify-between">
            <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
              Subject
            </div>
            <button
              onClick={() => void copyToClipboard(`${displayDraft.subject}\n\n${displayDraft.message}`)}
              className="flex items-center gap-1 text-[10.5px] text-muted-foreground transition hover:text-foreground"
            >
              {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
              {copied ? "Copied" : "Copy all"}
            </button>
          </div>
          <div className="text-[12.5px] font-medium">{displayDraft.subject}</div>
          <div className="mt-1 border-t border-border pt-2">
            <div className="mb-1 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
              Message
            </div>
            <p className="whitespace-pre-wrap text-[12px] leading-relaxed text-muted-foreground">
              {displayDraft.message}
            </p>
          </div>
          <div className="flex items-center gap-2 border-t border-border pt-2">
            <span className="inline-flex items-center gap-1 rounded-full border border-[oklch(var(--signal)/0.3)] bg-[oklch(var(--signal)/0.08)] px-2 py-0.5 font-mono text-[10px] uppercase text-[oklch(var(--signal))]">
              {displayDraft.tone}
            </span>
            <span className="text-[11px] text-muted-foreground">v{displayDraft.version_number}</span>
          </div>
        </div>
      )}

      {!displayDraft && !generateMutation.isPending && !latestQuery.isPending && (
        <div className="flex items-center gap-2 rounded-lg border border-dashed border-border bg-muted/10 px-3 py-4 text-[12px] text-muted-foreground">
          <MessageSquare className="size-4 shrink-0" />
          Select a tone and generate a draft to begin outreach.
        </div>
      )}
    </article>
  );
}

export function OutreachPage() {
  useDocumentTitle("Outreach");
  const [query, setQuery] = useState("");

  const leadsQuery = useQuery({
    queryKey: ["leads", "outreach"],
    queryFn: () => listLeads({ page_size: 50, sort: "score_desc" }),
  });

  const leads = useMemo(() => leadsQuery.data?.items ?? [], [leadsQuery.data]);

  const filtered = useMemo(() => {
    if (!query) return leads;
    const q = query.toLowerCase();
    return leads.filter(
      (l) =>
        l.company_name.toLowerCase().includes(q) ||
        (l.city ?? "").toLowerCase().includes(q) ||
        (l.category ?? "").toLowerCase().includes(q),
    );
  }, [leads, query]);

  if (leadsQuery.isPending) {
    return <QueryStateNotice tone="loading" title="Loading outreach workspace" description="Fetching leads…" />;
  }

  if (leadsQuery.isError) {
    return (
      <QueryStateNotice tone="error" title="Could not load leads" description={leadsQuery.error.message} />
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Outreach"
        title="AI-drafted outreach messages"
        description="Generate tone-matched outreach drafts for each lead. Drafts are based on real evidence signals — no hallucinations."
        actions={
          <Button size="sm" variant="outline" className="bg-transparent">
            <Send className="size-3.5" /> Batch generate
          </Button>
        }
      />

      <div className="grid gap-4 p-3 sm:p-4 lg:p-6">
        {/* Summary stats */}
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[
            { k: "Leads available", v: String(leads.length), sub: "for outreach drafting", tone: "evidence", icon: ScrollText },
            { k: "High-band leads", v: String(leads.filter((l) => l.latest_band === "high").length), sub: "priority outreach", tone: "signal", icon: Sparkles },
            { k: "Tone options", v: "4", sub: "formal · friendly · consultative · pitch", tone: "caution", icon: MessageSquare },
          ].map((s) => (
            <div key={s.k} className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-center gap-2 text-[11.5px] uppercase tracking-wider text-muted-foreground">
                <s.icon className="size-3.5" style={{ color: `oklch(var(--${s.tone}))` }} />
                {s.k}
              </div>
              <div className="mt-2 font-mono text-[24px] font-semibold tabular-nums">{s.v}</div>
              <div className="mt-0.5 text-[11.5px] text-muted-foreground">{s.sub}</div>
            </div>
          ))}
        </section>

        {/* Search */}
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by company, city, or category…"
            className="h-9 bg-card pl-9"
          />
        </div>

        {/* Lead cards grid */}
        <section className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {filtered.map((lead) => (
            <OutreachCard key={lead.public_id} lead={lead} />
          ))}
        </section>

        {filtered.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border bg-card/40 py-16 text-center">
            <ScrollText className="size-5 text-muted-foreground" />
            <div className="text-sm font-medium">No leads match your search</div>
            <div className="text-xs text-muted-foreground">Try widening the search terms.</div>
          </div>
        )}
      </div>
    </div>
  );
}
