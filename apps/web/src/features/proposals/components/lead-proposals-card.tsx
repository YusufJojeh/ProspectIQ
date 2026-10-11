import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ClipboardCheck } from "lucide-react";

import { appPaths } from "@/app/paths";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { listProposals, proposalKeys } from "../api";
import { appLeadAuditPath } from "../paths";
import { NewProposalButton } from "./new-proposal-button";
import { ProposalList } from "./proposal-list";

export function LeadProposalsCard({ leadId }: { leadId: string }) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: proposalKeys.list(leadId),
    queryFn: () => listProposals(leadId),
  });
  const copilotHref = `${appPaths.copilot}?leadId=${encodeURIComponent(leadId)}`;

  return (
    <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between sm:space-y-0">
        <div>
          <CardTitle>{t("proposals.leadCardTitle")}</CardTitle>
          <CardDescription>{t("proposals.leadCardDescription")}</CardDescription>
        </div>
        <div className="flex flex-wrap items-start gap-2">
          <Button asChild size="sm" variant="outline" className="bg-transparent">
            <Link to={appLeadAuditPath(leadId)}>
              <ClipboardCheck className="size-4" aria-hidden />
              {t("proposals.audit.open")}
            </Link>
          </Button>
          <NewProposalButton leadId={leadId} />
        </div>
      </CardHeader>
      <CardContent>
        {query.isError ? (
          <QueryStateNotice tone="error" title={t("proposals.loadError")} error={query.error} />
        ) : (
          <ProposalList
            items={query.data?.items ?? []}
            loading={query.isPending}
            showLead={false}
            emptyAction={
              <Button asChild size="sm" variant="outline" className="bg-transparent">
                <Link to={copilotHref}>{t("proposals.askCopilot")}</Link>
              </Button>
            }
          />
        )}
      </CardContent>
    </Card>
  );
}
