import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/shared/empty-state";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { ProposalSummary } from "@/types/proposals";

import { formatMoney } from "../money";
import { appProposalPath } from "../paths";
import { proposalStatusTone } from "../status";

export function ProposalList({
  items,
  loading,
  showLead,
  emptyAction,
}: {
  items: ProposalSummary[];
  loading: boolean;
  showLead: boolean;
  emptyAction?: ReactNode;
}) {
  const { t } = useTranslation();
  if (loading) {
    return (
      <div className="space-y-2" aria-busy="true">
        <Skeleton className="h-16 rounded-xl" />
        <Skeleton className="h-16 rounded-xl" />
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <EmptyState
        title={t("proposals.emptyTitle")}
        description={t("proposals.emptyDescription")}
        action={emptyAction}
      />
    );
  }
  return (
    <ul className="divide-y divide-border rounded-xl border border-border">
      {items.map((item) => (
        <li key={item.public_id}>
          <Link
            to={appProposalPath(item.public_id)}
            className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 transition-colors hover:bg-muted/40 focus-visible:bg-muted/40 focus-visible:outline-none"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{item.title || t("proposals.untitled")}</p>
              <p className="truncate text-xs text-muted-foreground">
                <span className="font-mono">{item.number}</span>
                {showLead ? ` · ${item.lead_company_name}` : null}
              </p>
            </div>
            <span className="font-mono text-sm tabular-nums">
              {item.total_minor > 0 ? formatMoney(item.currency, item.total_minor) : t("proposals.unpriced")}
            </span>
            <Badge tone={proposalStatusTone(item.status)}>{t(`proposals.status.${item.status}`)}</Badge>
            {item.status === "draft" && item.ready ? (
              <Badge tone="evidence">{t("proposals.complete")}</Badge>
            ) : null}
          </Link>
        </li>
      ))}
    </ul>
  );
}
