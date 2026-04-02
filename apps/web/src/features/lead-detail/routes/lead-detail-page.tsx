import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getLead, getLeadEvidence, getLeadScoreBreakdown } from "@/features/leads/api";
import { useDocumentTitle } from "@/hooks/use-document-title";

export function LeadDetailPage() {
  const { leadId = "" } = useParams();
  const leadQuery = useQuery({
    queryKey: ["lead", leadId],
    queryFn: () => getLead(leadId),
    enabled: Boolean(leadId),
  });
  useDocumentTitle(leadQuery.data?.company_name ?? "Lead Detail");
  const evidenceQuery = useQuery({
    queryKey: ["lead", leadId, "evidence"],
    queryFn: () => getLeadEvidence(leadId),
    enabled: Boolean(leadId),
  });
  const breakdownQuery = useQuery({
    queryKey: ["lead", leadId, "breakdown"],
    queryFn: () => getLeadScoreBreakdown(leadId),
    enabled: Boolean(leadId),
  });

  if (leadQuery.isError) {
    return (
      <EmptyState
        title="Lead detail is unavailable"
        description="The lead could not be loaded for the current workspace or session."
      />
    );
  }

  if (!leadQuery.data) {
    return <p className="text-sm text-[color:var(--muted)]">Loading lead details...</p>;
  }

  const lead = leadQuery.data;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Lead detail"
        title={lead.company_name}
        description="Foundation detail view for stored facts, evidence rows, and persisted score breakdowns."
        action={
          <Badge tone={lead.latest_band === "high" ? "warning" : "accent"}>
            {lead.latest_score ? `${Math.round(lead.latest_score)}/100` : "Unscored"}
          </Badge>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Stored facts</CardTitle>
            <CardDescription>Current lead fields represent the latest stored operational view.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-[color:var(--border)] p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">City</p>
                <p className="mt-2 font-semibold">{lead.city ?? "Unknown"}</p>
              </div>
              <div className="rounded-xl border border-[color:var(--border)] p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Website</p>
                <p className="mt-2 font-semibold">{lead.website_url ?? "Missing"}</p>
              </div>
              <div className="rounded-xl border border-[color:var(--border)] p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Reviews</p>
                <p className="mt-2 font-semibold">{lead.review_count}</p>
              </div>
              <div className="rounded-xl border border-[color:var(--border)] p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Rating</p>
                <p className="mt-2 font-semibold">{lead.rating ?? "N/A"}</p>
              </div>
            </div>

            {evidenceQuery.data?.items.length ? (
              <div className="space-y-3">
                {evidenceQuery.data.items.map((item) => (
                  <div
                    key={`${item.source_type}-${item.created_at}`}
                    className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4 text-sm text-[color:var(--muted)]"
                  >
                    <p className="font-semibold text-[color:var(--text)]">{item.source_type}</p>
                    <p className="mt-2">{item.address ?? item.city ?? "No address captured"}</p>
                    <p className="mt-1">
                      Confidence {item.confidence.toFixed(2)} | Completeness {item.completeness.toFixed(2)}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No evidence rows"
                description="Evidence will appear here once provider normalization is wired into the lead pipeline."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Latest score breakdown</CardTitle>
            <CardDescription>This panel reads persisted scoring data only.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {breakdownQuery.data ? (
              <div className="space-y-3 text-sm leading-6">
                <div className="rounded-xl border border-[color:var(--border)] p-4">
                  <p className="font-semibold">Version</p>
                  <p className="mt-2 text-[color:var(--muted)]">{breakdownQuery.data.scoring_version_id}</p>
                </div>
                {breakdownQuery.data.breakdown.map((item) => (
                  <div key={item.key} className="rounded-xl border border-[color:var(--border)] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold">{item.label}</p>
                      <Badge tone="neutral">{item.contribution.toFixed(1)}</Badge>
                    </div>
                    <p className="mt-2 text-[color:var(--muted)]">{item.reason}</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No score breakdown"
                description="Once deterministic scoring runs against normalized facts, its persisted breakdown will be shown here."
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
