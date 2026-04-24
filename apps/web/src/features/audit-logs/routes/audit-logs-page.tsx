import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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

function categoryOf(eventName: string) {
  if (eventName.includes("lead")) return { label: "Lead", icon: User, color: "oklch(var(--signal))" };
  if (eventName.includes("export")) return { label: "Export", icon: FileDown, color: "oklch(var(--caution))" };
  if (eventName.includes("job") || eventName.includes("provider"))
    return { label: "Pipeline", icon: Zap, color: "oklch(var(--signal))" };
  if (eventName.includes("user") || eventName.includes("api") || eventName.includes("workspace"))
    return { label: "Security", icon: ShieldCheck, color: "oklch(var(--evidence))" };
  if (eventName.includes("scoring")) return { label: "Scoring", icon: SettingsIcon, color: "oklch(var(--signal))" };
  if (eventName.includes("outreach")) return { label: "Outreach", icon: ScrollText, color: "oklch(var(--caution))" };
  return { label: "System", icon: Database, color: "oklch(var(--muted-foreground))" };
}

export function AuditLogsPage() {
  useDocumentTitle("Audit Logs");
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
    return <QueryStateNotice tone="loading" title="Loading audit logs" description="Fetching event history…" />;
  }

  if (logsQuery.isError) {
    return (
      <QueryStateNotice tone="error" title="Could not load audit logs" description={logsQuery.error.message} />
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Audit logs"
        title="Every change, every actor"
        description="Write-through, tamper-evident log of user and system actions. Exportable for compliance review."
        actions={
          <Button variant="outline" size="sm" className="bg-transparent">
            <Download className="size-3.5" /> Export window
          </Button>
        }
      />

      <div className="p-3 sm:p-4 lg:p-6">
        <section className="rounded-xl border border-border bg-card">
          <header className="flex flex-wrap items-center gap-2 border-b border-border p-3">
            <div className="relative w-full flex-1 md:w-auto">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search event, actor, details…"
                className="h-9 bg-background pl-8"
              />
            </div>
            <span className="ml-auto font-mono text-[11px] tabular-nums text-muted-foreground">
              {filtered.length} / {logs.length} events
            </span>
          </header>

          <ul className="divide-y divide-border">
            {filtered.map((e: AuditLogResponse) => {
              const cat = categoryOf(e.event_name);
              const isOpen = expanded.has(e.public_id);
              return (
                <li key={e.public_id}>
                  <button
                    onClick={() => toggle(e.public_id)}
                    className="grid w-full grid-cols-[auto,1fr,auto] items-center gap-3 px-3 py-3 text-left transition-colors hover:bg-muted/30 sm:px-4"
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
                          ["Event ID", e.public_id],
                          ["Timestamp (UTC)", new Date(e.created_at).toISOString()],
                          ["Actor", e.actor_user_public_id ?? "system"],
                          ["Event", e.event_name],
                          ["Details", e.details],
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
              <div className="text-sm font-medium">No events match your filters</div>
              <div className="text-xs text-muted-foreground">Try widening the search terms.</div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
