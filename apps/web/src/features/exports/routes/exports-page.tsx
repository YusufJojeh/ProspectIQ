import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
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
import { listLeads, downloadLeadsExport, downloadLeadsExportJson } from "@/features/leads/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { leadStatusLabel, scoreBandLabel } from "@/lib/i18n-labels";
import { cn } from "@/lib/utils";
import type { LeadScoreBand, LeadStatus } from "@/types/api";

type BandFilter = LeadScoreBand | "all";
type StatusFilter = LeadStatus | "all";

export function ExportsPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("exports.title"));
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

  const exportJsonMutation = useMutation({
    mutationFn: () =>
      downloadLeadsExportJson({
        band: band === "all" ? undefined : band,
        status: status === "all" ? undefined : status,
      }),
  });

  const totalLeads = leadsQuery.data?.pagination.total ?? 0;

  return (
    <div className="max-w-full overflow-x-clip">
      <PageHeader
        eyebrow={t("exports.title")}
        title={t("exports.workspaceTitle")}
        description={t("exports.workspaceDescription")}
        actions={
          <div className="flex flex-wrap gap-2">
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
              {exportMutation.isPending ? t("exports.preparing") : t("exports.downloadCsv")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => exportJsonMutation.mutate()}
              disabled={exportJsonMutation.isPending || totalLeads === 0}
            >
              {exportJsonMutation.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <FileDown className="size-3.5" />
              )}
              {exportJsonMutation.isPending ? t("exports.preparing") : t("exports.downloadJson")}
            </Button>
          </div>
        }
      />

      <div className="grid min-w-0 gap-4 p-3 sm:p-4 lg:p-6">
        {/* Stats */}
        <section className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[
            {
              k: t("exports.totalLeads"),
              v: String(totalLeads),
              sub: t("exports.currentFilter"),
              icon: Database,
              tone: "evidence",
            },
            {
              k: t("exports.format"),
              v: "CSV",
              sub: t("exports.commaSeparated"),
              icon: FileDown,
              tone: "signal",
            },
            {
              k: t("exports.encoding"),
              v: "UTF-8",
              sub: t("exports.universalCompatibility"),
              icon: CheckCircle2,
              tone: "caution",
            },
          ].map((s) => (
            <div key={s.k} className="min-w-0 rounded-xl border border-border bg-card p-4">
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
        <section className="min-w-0 rounded-xl border border-border bg-card p-4">
          <div className="mb-3 flex items-center gap-2 text-[11.5px] font-medium uppercase tracking-wider text-muted-foreground">
            <Filter className="size-3.5" />
            {t("exports.filters")}
          </div>
          <div className="flex min-w-0 flex-wrap gap-3">
            <div className="flex min-w-0 flex-1 basis-40 flex-col gap-1">
              <label className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                {t("exports.filterBand")}
              </label>
              <Select value={band} onValueChange={(v) => setBand(v as BandFilter)}>
                <SelectTrigger className="h-9 w-full sm:w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("exports.allBands")}</SelectItem>
                  <SelectItem value="high">{t("leads.bandHigh")}</SelectItem>
                  <SelectItem value="medium">{t("leads.bandMedium")}</SelectItem>
                  <SelectItem value="low">{t("leads.bandLow")}</SelectItem>
                  <SelectItem value="not_qualified">{t("leads.bandNotQualified")}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex min-w-0 flex-1 basis-40 flex-col gap-1">
              <label className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                {t("exports.filterStatus")}
              </label>
              <Select value={status} onValueChange={(v) => setStatus(v as StatusFilter)}>
                <SelectTrigger className="h-9 w-full sm:w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("exports.allStatuses")}</SelectItem>
                  <SelectItem value="new">{t("leads.statusNew")}</SelectItem>
                  <SelectItem value="reviewed">{t("leads.statusReviewed")}</SelectItem>
                  <SelectItem value="contacted">{t("leads.statusContacted")}</SelectItem>
                  <SelectItem value="qualified">{t("leads.statusQualified")}</SelectItem>
                  <SelectItem value="interested">{t("leads.statusInterested")}</SelectItem>
                  <SelectItem value="won">{t("leads.statusWon")}</SelectItem>
                  <SelectItem value="lost">{t("leads.statusLost")}</SelectItem>
                  <SelectItem value="archived">{t("leads.statusArchived")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </section>

        {/* Preview */}
        <section className="min-w-0 overflow-hidden rounded-xl border border-border bg-card">
          <header className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2 text-[11.5px] font-medium text-muted-foreground">
              <Clock className="size-3.5" />
              {t("exports.previewFirstTen")}
            </div>
            <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
              {leadsQuery.isPending ? "..." : t("exports.totalCount", { count: totalLeads })}
            </span>
          </header>

          {leadsQuery.isPending && (
            <QueryStateNotice tone="loading" title={t("exports.loadingRowsTitle")} description={t("exports.loadingRowsDescription")} />
          )}
          {leadsQuery.isError && (
            <QueryStateNotice tone="error" title={t("exports.previewErrorTitle")} error={leadsQuery.error} />
          )}

          {leadsQuery.isSuccess && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-[12px]">
                <thead>
                  <tr className="border-b border-border bg-muted/20">
                    {[
                      t("leads.companyName"),
                      t("leads.category"),
                      t("leads.city"),
                      t("leads.score"),
                      t("leads.band"),
                      t("leads.status"),
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-2 text-start font-mono text-[10px] uppercase tracking-wider text-muted-foreground"
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
                          {scoreBandLabel(t, lead.latest_band)}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">{leadStatusLabel(t, lead.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {leadsQuery.data.items.length === 0 && (
                <div className="flex flex-col items-center gap-2 py-12 text-center">
                  <FileDown className="size-5 text-muted-foreground" />
                  <div className="text-sm font-medium">{t("exports.noFilteredLeads")}</div>
                  <div className="text-xs text-muted-foreground">{t("exports.adjustFilters")}</div>
                </div>
              )}
            </div>
          )}
        </section>

        {exportMutation.isSuccess && (
          <div className="flex items-center gap-2 rounded-xl border border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.08)] px-4 py-3 text-[12.5px] text-[oklch(var(--evidence))]">
            <CheckCircle2 className="size-4" />
            {t("exports.downloadSuccess")}
          </div>
        )}
      </div>
    </div>
  );
}
