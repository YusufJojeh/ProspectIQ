import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  ScrollText,
  Download,
  Search,
  ShieldCheck,
  Database,
  User,
  Zap,
  Settings as SettingsIcon,
  FileDown,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { listAuditLogs } from "@/features/settings/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { formatDate } from "@/lib/presenters";
import { cn } from "@/lib/utils";
import type { AuditLogResponse } from "@/types/api";

function categoryOf(eventName: string, t: ReturnType<typeof useTranslation>["t"]) {
  if (eventName.includes("lead")) return { label: t("auditLogs.categories.lead"), icon: User, color: "oklch(var(--signal))" };
  if (eventName.includes("export")) return { label: t("auditLogs.categories.export"), icon: FileDown, color: "oklch(var(--caution))" };
  if (eventName.includes("job") || eventName.includes("provider"))
    return { label: t("auditLogs.categories.pipeline"), icon: Zap, color: "oklch(var(--signal))" };
  if (eventName.includes("user") || eventName.includes("api") || eventName.includes("workspace"))
    return { label: t("auditLogs.categories.security"), icon: ShieldCheck, color: "oklch(var(--evidence))" };
  if (eventName.includes("scoring")) return { label: t("auditLogs.categories.scoring"), icon: SettingsIcon, color: "oklch(var(--signal))" };
  if (eventName.includes("outreach")) return { label: t("auditLogs.categories.outreach"), icon: ScrollText, color: "oklch(var(--caution))" };
  return { label: t("auditLogs.categories.system"), icon: Database, color: "oklch(var(--muted-foreground))" };
}

export function AuditLogsPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("auditLogs.title"));
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const logsQuery = useQuery({
    queryKey: ["audit-logs"],
    queryFn: listAuditLogs,
  });

  const logs = useMemo(() => logsQuery.data?.items ?? [], [logsQuery.data]);

  const filtered = useMemo(() => {
    if (!query) return logs;
    const q = query.toLowerCase();
    return logs.filter(
      (e) =>
        e.event_name.toLowerCase().includes(q) ||
        e.details.toLowerCase().includes(q) ||
        (e.actor_user_public_id ?? "").toLowerCase().includes(q),
    );
  }, [logs, query]);

  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  if (logsQuery.isPending) {
    return <QueryStateNotice tone="loading" title={t("auditLogs.loadingTitle")} description={t("auditLogs.loadingDescription")} />;
  }

  if (logsQuery.isError) {
    return (
      <QueryStateNotice tone="error" title={t("auditLogs.loadErrorTitle")} error={logsQuery.error} />
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow={t("auditLogs.eyebrow")}
        title={t("auditLogs.headerTitle")}
        description={t("auditLogs.headerDescription")}
        actions={
          <Button variant="outline" size="sm" className="bg-transparent">
            <Download className="size-3.5" /> {t("auditLogs.exportWindow")}
          </Button>
        }
      />

      <div className="p-3 sm:p-4 lg:p-6">
        <section className="rounded-xl border border-border bg-card">
          <header className="flex flex-wrap items-center gap-2 border-b border-border p-3">
            <div className="relative w-full flex-1 md:w-auto">
              <Search className="pointer-events-none absolute start-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("auditLogs.searchPlaceholder")}
                className="h-9 bg-background ps-8"
              />
            </div>
            <span className="ms-auto font-mono text-[11px] tabular-nums text-muted-foreground">
              {t("auditLogs.eventsCount", { visible: filtered.length, total: logs.length })}
            </span>
          </header>

          <ul className="divide-y divide-border">
            {filtered.map((e: AuditLogResponse) => {
              const cat = categoryOf(e.event_name, t);
              const isOpen = expanded.has(e.public_id);
              return (
                <li key={e.public_id}>
                  <button
                    onClick={() => toggle(e.public_id)}
                    className="grid w-full grid-cols-[auto,1fr,auto] items-center gap-3 px-3 py-3 text-start transition-colors hover:bg-muted/30 sm:px-4"
                  >
                    <span
                      className="flex size-7 items-center justify-center rounded-md border border-border bg-muted/30"
                      style={{ color: cat.color }}
                    >
                      <cat.icon className="size-3.5" />
                    </span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center rounded-md border border-border bg-muted/30 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                          {cat.label}
                        </span>
                        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                          {formatDate(e.created_at)}
                        </span>
                        <span className="font-mono text-[11.5px] text-[oklch(var(--signal))]">{e.event_name}</span>
                      </div>
                      <div className="mt-0.5 truncate text-[12px] text-muted-foreground">{e.details}</div>
                    </div>
                    {isOpen ? (
                      <ChevronDown className="size-3.5 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="size-3.5 text-muted-foreground" />
                    )}
                  </button>
                  {isOpen && (
                    <div className="border-t border-border bg-muted/20 px-4 py-3">
                      <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-[12px] md:grid-cols-2">
                        {[
                          [t("auditLogs.eventId"), e.public_id],
                          [t("auditLogs.timestampUtc"), new Date(e.created_at).toISOString()],
                          [t("auditLogs.actor"), e.actor_user_public_id ?? t("common.system")],
                          [t("auditLogs.event"), e.event_name],
                          [t("auditLogs.details"), e.details],
                        ].map(([k, v]) => (
                          <div key={k as string} className="grid grid-cols-[100px,1fr] gap-2 sm:grid-cols-[140px,1fr]">
                            <dt className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                              {k}
                            </dt>
                            <dd className="font-mono text-[11.5px] text-foreground">{v}</dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>

          {filtered.length === 0 && (
            <div className={cn("flex flex-col items-center gap-2 py-12 text-center")}>
              <ScrollText className="size-5 text-muted-foreground" />
              <div className="text-sm font-medium">{t("auditLogs.noEventsTitle")}</div>
              <div className="text-xs text-muted-foreground">{t("auditLogs.noEventsDescription")}</div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
