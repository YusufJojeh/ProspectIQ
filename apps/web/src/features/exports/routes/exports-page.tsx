import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  FileDown,
  Download,
  CheckCircle2,
  Clock,
  Filter,
  Database,
  Loader2,
} from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { listLeads, downloadLeadsExport } from "@/features/leads/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn } from "@/lib/utils";
import type { LeadScoreBand, LeadStatus } from "@/types/api";

type BandFilter = LeadScoreBand | "all";
type StatusFilter = LeadStatus | "all";

export function ExportsPage() {
  useDocumentTitle("Exports");
  const [band, setBand] = useState<BandFilter>("all");
  const [status, setStatus] = useState<StatusFilter>("all");

  const leadsQuery = useQuery({
    queryKey: ["leads", "exports-preview", band, status],
    queryFn: () =>
      listLeads({
        page_size: 10,
        band: band === "all" ? undefined : band,
        status: status === "all" ? undefined : status,
      }),
  });

  const exportMutation = useMutation({
    mutationFn: () =>
      downloadLeadsExport({
        band: band === "all" ? undefined : band,
        status: status === "all" ? undefined : status,
      }),
  });

  const totalLeads = leadsQuery.data?.pagination.total ?? 0;

  return (
    <div>
      <PageHeader
        eyebrow="Exports"
        title="Download your lead workspace"
        description="Export filtered lead data to CSV for CRM import, compliance archiving, or offline review."
        actions={
          <Button
            size="sm"
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending || totalLeads === 0}
          >
            {exportMutation.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Download className="size-3.5" />
            )}
            {exportMutation.isPending ? "Preparing…" : "Export CSV"}
          </Button>
        }
      />

      <div className="grid gap-4 p-3 sm:p-4 lg:p-6">
        {/* Stats */}
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[
            {
              k: "Total leads",
              v: String(totalLeads),
              sub: "in current filter",
              icon: Database,
              tone: "evidence",
            },
            {
              k: "Format",
              v: "CSV",
              sub: "comma-separated values",
              icon: FileDown,
              tone: "signal",
            },
            {
              k: "Encoding",
              v: "UTF-8",
              sub: "universal compatibility",
              icon: CheckCircle2,
              tone: "caution",
            },
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

        {/* Filters */}
        <section className="rounded-xl border border-border bg-card p-4">
          <div className="mb-3 flex items-center gap-2 text-[11.5px] font-medium uppercase tracking-wider text-muted-foreground">
            <Filter className="size-3.5" />
            Export filters
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="flex flex-col gap-1">
              <label className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                Score band
              </label>
              <Select value={band} onValueChange={(v) => setBand(v as BandFilter)}>
                <SelectTrigger className="h-9 w-full sm:w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All bands</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="not_qualified">Not qualified</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-1">
              <label className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                Lead status
              </label>
              <Select value={status} onValueChange={(v) => setStatus(v as StatusFilter)}>
                <SelectTrigger className="h-9 w-full sm:w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="new">New</SelectItem>
                  <SelectItem value="contacted">Contacted</SelectItem>
                  <SelectItem value="qualified">Qualified</SelectItem>
                  <SelectItem value="disqualified">Disqualified</SelectItem>
                  <SelectItem value="converted">Converted</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </section>

        {/* Preview */}
        <section className="rounded-xl border border-border bg-card">
          <header className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2 text-[11.5px] font-medium text-muted-foreground">
              <Clock className="size-3.5" />
              Preview — first 10 leads
            </div>
            <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
              {leadsQuery.isPending ? "…" : `${totalLeads} total`}
            </span>
          </header>

          {leadsQuery.isPending && (
            <QueryStateNotice tone="loading" title="Loading preview" description="Fetching sample rows…" />
          )}
          {leadsQuery.isError && (
            <QueryStateNotice tone="error" title="Could not load preview" description={leadsQuery.error.message} />
          )}

          {leadsQuery.isSuccess && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-[12px]">
                <thead>
                  <tr className="border-b border-border bg-muted/20">
                    {["Company", "Category", "City", "Score", "Band", "Status"].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {leadsQuery.data.items.map((lead) => (
                    <tr key={lead.public_id} className="hover:bg-muted/10">
                      <td className="px-4 py-2.5 font-medium">{lead.company_name}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{lead.category ?? "—"}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{lead.city ?? "—"}</td>
                      <td className="px-4 py-2.5 font-mono tabular-nums">{lead.latest_score ?? "—"}</td>
                      <td className="px-4 py-2.5">
                        <span
                          className={cn(
                            "inline-flex items-center rounded-md border px-1.5 py-0.5 font-mono text-[10px] uppercase",
                            lead.latest_band === "high"
                              ? "border-[oklch(var(--signal)/0.3)] text-[oklch(var(--signal))]"
                              : lead.latest_band === "medium"
                                ? "border-[oklch(var(--caution)/0.3)] text-[oklch(var(--caution))]"
                                : "border-border text-muted-foreground",
                          )}
                        >
                          {lead.latest_band ?? "—"}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">{lead.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {leadsQuery.data.items.length === 0 && (
                <div className="flex flex-col items-center gap-2 py-12 text-center">
                  <FileDown className="size-5 text-muted-foreground" />
                  <div className="text-sm font-medium">No leads match your filters</div>
                  <div className="text-xs text-muted-foreground">Adjust the filters above to include more results.</div>
                </div>
              )}
            </div>
          )}
        </section>

        {exportMutation.isSuccess && (
          <div className="flex items-center gap-2 rounded-xl border border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.08)] px-4 py-3 text-[12.5px] text-[oklch(var(--evidence))]">
            <CheckCircle2 className="size-4" />
            Export downloaded successfully.
          </div>
        )}
      </div>
    </div>
  );
}
