import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { appPaths } from "@/app/paths";
import { PageHeader } from "@/components/shell/page-header";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useDocumentTitle } from "@/hooks/use-document-title";
import type { ProposalStatus } from "@/types/proposals";

import { listProposals, proposalKeys } from "../api";
import { ProposalList } from "../components/proposal-list";

type Filter = "all" | ProposalStatus;
const FILTERS: Filter[] = ["all", "draft", "ready", "sent", "accepted", "declined"];

export function ProposalsPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("proposals.title"));
  const [filter, setFilter] = useState<Filter>("all");
  const query = useQuery({ queryKey: proposalKeys.list(null), queryFn: () => listProposals() });
  const items = useMemo(
    () => (query.data?.items ?? []).filter((item) => filter === "all" || item.status === filter),
    [query.data, filter],
  );

  return (
    <div>
      <PageHeader title={t("proposals.title")} description={t("proposals.description")} />
      <div className="mx-auto max-w-5xl space-y-4 px-3 py-4 sm:px-4 lg:px-6">
        <ToggleGroup
          type="single"
          value={filter}
          onValueChange={(value) => value && setFilter(value as Filter)}
          className="flex flex-wrap justify-start"
          aria-label={t("proposals.filterLabel")}
        >
          {FILTERS.map((value) => (
            <ToggleGroupItem key={value} value={value} size="sm">
              {value === "all" ? t("proposals.filterAll") : t(`proposals.status.${value}`)}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        {query.isError ? (
          <QueryStateNotice tone="error" title={t("proposals.loadError")} error={query.error} />
        ) : (
          <ProposalList
            items={items}
            loading={query.isPending}
            showLead
            emptyAction={
              <Button asChild size="sm" variant="outline" className="bg-transparent">
                <Link to={appPaths.leads}>{t("proposals.pickLead")}</Link>
              </Button>
            }
          />
        )}
      </div>
    </div>
  );
}
