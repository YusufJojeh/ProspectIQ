import { useDeferredValue, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Search, X } from "lucide-react";

import { appPaths } from "@/app/paths";
import { PageHeader } from "@/components/shell/page-header";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { getLead, listLeads } from "@/features/leads/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import type { LeadResponse } from "@/types/api";

import { CopilotPanel } from "../components/copilot-panel";

const PICKER_PAGE_SIZE = 8;

export function CopilotPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("copilot.page.title"));
  const [searchParams, setSearchParams] = useSearchParams();
  const leadId = searchParams.get("leadId");

  const leadQuery = useQuery({
    queryKey: ["lead", leadId, "copilot-context"],
    queryFn: () => getLead(leadId ?? ""),
    enabled: leadId !== null,
  });

  function selectLead(next: LeadResponse | null) {
    const params = new URLSearchParams(searchParams);
    if (next) params.set("leadId", next.public_id);
    else params.delete("leadId");
    setSearchParams(params, { replace: true });
  }

  const lead = leadQuery.data ?? null;

  return (
    <div>
      <PageHeader title={t("copilot.page.title")} description={t("copilot.page.description")} />

      <div className="mx-auto grid max-w-6xl gap-6 px-3 py-4 sm:px-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)] lg:px-6">
        <div className="order-2 min-w-0 lg:order-1">
          {leadId !== null && leadQuery.isPending ? (
            <Skeleton className="h-64 rounded-[1.5rem]" />
          ) : (
            // Keyed so switching context always starts a clean run.
            <CopilotPanel
              key={lead?.public_id ?? "workspace"}
              leadId={lead?.public_id ?? null}
              leadName={lead?.company_name}
            />
          )}
        </div>

        <aside className="order-1 min-w-0 lg:order-2">
          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle role="heading" aria-level={2}>
                {t("copilot.page.contextTitle")}
              </CardTitle>
              <CardDescription>{t("copilot.page.contextDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {leadId !== null && leadQuery.isError ? (
                <QueryStateNotice
                  tone="error"
                  title={t("copilot.page.leadUnavailable")}
                  error={leadQuery.error}
                />
              ) : null}

              {lead ? (
                <SelectedLead lead={lead} onClear={() => selectLead(null)} />
              ) : (
                <p className="text-sm text-muted-foreground">{t("copilot.page.workspaceMode")}</p>
              )}

              <LeadPicker selectedId={lead?.public_id ?? null} onSelect={selectLead} />
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function SelectedLead({ lead, onClear }: { lead: LeadResponse; onClear: () => void }) {
  const { t } = useTranslation();
  const subtitle = [lead.category, lead.city].filter(Boolean).join(" · ");
  return (
    <div className="space-y-2 rounded-xl border border-border bg-muted/30 p-3">
      <div className="min-w-0">
        <p className="truncate font-medium">{lead.company_name}</p>
        {subtitle ? <p className="truncate text-xs text-muted-foreground">{subtitle}</p> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button asChild size="sm" variant="outline" className="bg-transparent">
          <Link to={appPaths.leadDetail(lead.public_id)}>
            <ExternalLink className="size-3.5" aria-hidden />
            {t("copilot.page.openLead")}
          </Link>
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onClear}>
          <X className="size-3.5" aria-hidden />
          {t("copilot.page.clearLead")}
        </Button>
      </div>
    </div>
  );
}

function LeadPicker({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (lead: LeadResponse) => void;
}) {
  const { t } = useTranslation();
  const [term, setTerm] = useState("");
  const query = useDeferredValue(term.trim());

  const leadsQuery = useQuery({
    queryKey: ["leads", "copilot-picker", query],
    queryFn: () => listLeads({ q: query || undefined, page_size: PICKER_PAGE_SIZE }),
  });
  const items = (leadsQuery.data?.items ?? []).filter((item) => item.public_id !== selectedId);

  return (
    <div className="space-y-2">
      <label htmlFor="copilot-lead-search" className="text-xs font-medium text-muted-foreground">
        {selectedId ? t("copilot.page.switchLead") : t("copilot.page.pickLead")}
      </label>
      <div className="relative">
        <Search
          className="pointer-events-none absolute start-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          id="copilot-lead-search"
          type="search"
          value={term}
          placeholder={t("copilot.page.searchPlaceholder")}
          className="ps-8"
          onChange={(event) => setTerm(event.target.value)}
        />
      </div>

      {leadsQuery.isPending ? (
        <div className="space-y-1.5" aria-busy="true">
          <Skeleton className="h-9 rounded-lg" />
          <Skeleton className="h-9 rounded-lg" />
          <Skeleton className="h-9 rounded-lg" />
        </div>
      ) : leadsQuery.isError ? (
        <QueryStateNotice tone="error" title={t("copilot.page.leadsUnavailable")} error={leadsQuery.error} />
      ) : items.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t("copilot.page.noLeads")}</p>
      ) : (
        <ul className="space-y-1" aria-label={t("copilot.page.leadResults")}>
          {items.map((item) => (
            <li key={item.public_id}>
              <button
                type="button"
                className="w-full rounded-lg px-2.5 py-2 text-start text-sm transition-colors hover:bg-muted focus-visible:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => onSelect(item)}
              >
                <span className="block truncate font-medium">{item.company_name}</span>
                {item.city ? (
                  <span className="block truncate text-xs text-muted-foreground">{item.city}</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
