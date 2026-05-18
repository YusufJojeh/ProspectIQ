import { Database, FileDown, Play, RefreshCw, Users, X } from "lucide-react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { appPaths } from "@/app/paths";
import { StatusDot } from "@/components/brand/badges";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { searchJobStatusLabel, websitePreferenceLabel } from "@/lib/i18n-labels";
import { formatDate } from "@/lib/presenters";
import type { SearchJobResponse } from "@/types/api";

export function JobDetailDrawer({
  job,
  open,
  onClose,
  onRerun,
  onClone,
  rerunning,
}: {
  job: SearchJobResponse | null;
  open: boolean;
  onClose: () => void;
  onRerun: (job: SearchJobResponse) => void;
  onClone: (job: SearchJobResponse) => void;
  rerunning?: boolean;
}) {
  const { t } = useTranslation();

  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent side="right" className="flex w-full flex-col gap-0 p-0 sm:max-w-xl">
        {job ? (
          <>
            <SheetHeader className="border-b border-border p-5 text-start">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                <StatusDot status={job.status} />
                <span>{searchJobStatusLabel(t, job.status)}</span>
                <span className="font-mono">{job.public_id.slice(0, 8)}</span>
                <Button variant="ghost" size="icon" className="ms-auto size-7" onClick={onClose}>
                  <X className="size-4" />
                </Button>
              </div>
              <SheetTitle className="text-2xl tracking-tight">
                {t("searches.jobTitlePattern", { businessType: job.business_type, city: job.city })}
              </SheetTitle>
              <p className="text-sm text-muted-foreground">
                {job.region ? `${job.region} · ` : ""}
                {t("searches.queued")} {formatDate(job.queued_at)}
              </p>
            </SheetHeader>

            <div className="flex-1 space-y-6 overflow-y-auto p-5">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <StatTile label={t("searches.candidates")} value={String(job.candidates_found)} />
                <StatTile label={t("searches.upserted")} value={String(job.leads_upserted)} />
                <StatTile label={t("searches.errors")} value={String(job.provider_error_count)} />
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-medium">{t("searches.discoverySettings")}</h3>
                <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                  <MetaRow k={t("searches.websitePreference")} v={websitePreferenceLabel(t, job.website_preference)} />
                  <MetaRow k={t("searches.radius")} v={job.radius_km ? `${job.radius_km} km` : t("searches.workspaceDefault")} />
                  <MetaRow k={t("searches.ratingWindow")} v={`${job.min_rating ?? t("common.all")} - ${job.max_rating ?? t("common.all")}`} />
                  <MetaRow k={t("searches.reviewWindow")} v={`${job.min_reviews ?? t("common.all")} - ${job.max_reviews ?? t("common.all")}`} />
                  <MetaRow k={t("searches.keywordFilter")} v={job.keyword_filter ?? t("common.none")} />
                  <MetaRow k={t("searches.discoveryRuntime")} v={job.discovery_runtime} />
                </dl>
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-medium">{t("searches.operationalSummary")}</h3>
                <div className="space-y-2">
                  <StageRow label={t("searches.queued")} value={formatDate(job.queued_at)} />
                  <StageRow label={t("searches.started")} value={job.started_at ? formatDate(job.started_at) : t("searches.notStarted")} />
                  <StageRow label={t("searches.finished")} value={job.finished_at ? formatDate(job.finished_at) : t("searches.stillRunning")} />
                </div>
              </div>

              <div className="rounded-2xl border border-border bg-muted/20 p-4">
                <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  <Database className="size-3.5" />
                  {t("searches.realBackendData")}
                </div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {t("searches.drawerBackendDescription")}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 border-t border-border bg-background/80 p-4">
              <Button variant="outline" size="sm" className="flex-1 bg-transparent sm:flex-none" onClick={() => onClone(job)}>
                <RefreshCw className="size-3.5" />
                {t("searches.cloneIntoForm")}
              </Button>
              <Button size="sm" className="flex-1 sm:flex-none" onClick={() => onRerun(job)} disabled={rerunning}>
                <Play className="size-3.5" />
                {rerunning ? t("searches.rerunning") : t("searches.rerunJob")}
              </Button>
              <div className="flex w-full flex-wrap items-center gap-2 sm:ms-auto sm:w-auto">
                <Button variant="outline" size="sm" className="flex-1 bg-transparent sm:flex-none" asChild>
                  <Link to={appPaths.searchJobDetail(job.public_id)}>
                    <FileDown className="size-3.5" />
                    {t("searches.openFullRecord")}
                  </Link>
                </Button>
                <Button variant="outline" size="sm" className="flex-1 bg-transparent sm:flex-none" asChild>
                  <Link to={`${appPaths.leads}?search_job_id=${job.public_id}`}>
                    <Users className="size-3.5" />
                    {t("searches.viewLeads")}
                  </Link>
                </Button>
              </div>
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 p-3">
      <div className="font-mono text-lg font-semibold tabular-nums">{value}</div>
      <div className="mt-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
    </div>
  );
}

function MetaRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 p-3">
      <dt className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{k}</dt>
      <dd className="mt-1 text-sm text-foreground">{v}</dd>
    </div>
  );
}

function StageRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-muted/20 px-4 py-3">
      <span className="text-sm font-medium">{label}</span>
      <span className="font-mono text-xs text-muted-foreground">{value}</span>
    </div>
  );
}
