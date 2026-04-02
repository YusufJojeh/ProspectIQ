import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { listLeads } from "@/features/leads/api";
import { useDocumentTitle } from "@/hooks/use-document-title";

export function LeadsPage() {
  useDocumentTitle("Leads");
  const leadsQuery = useQuery({
    queryKey: ["leads", "table"],
    queryFn: listLeads,
  });

  if (leadsQuery.isError) {
    return (
      <EmptyState
        title="Lead data is unavailable"
        description="Make sure the API is running and that the current session token is valid."
      />
    );
  }

  if (!leadsQuery.data) {
    return (
      <p className="text-sm text-[color:var(--muted)]">Loading leads...</p>
    );
  }

  const leads = leadsQuery.data.items;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Leads"
        title="Persisted lead records"
        description="This table stays empty until the evidence pipeline starts writing normalized lead records."
      />

      <Card>
        <CardHeader>
          <CardTitle>Lead queue</CardTitle>
          <CardDescription>Live API data only. No generated sample rows are rendered here.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-hidden p-0">
          {leads.length === 0 ? (
            <div className="p-5">
              <EmptyState
                title="No leads available"
                description="Leads will appear here once search discovery and normalization are implemented."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-[color:var(--border)] text-left text-sm">
                <thead className="bg-[color:var(--surface-soft)] text-[color:var(--muted)]">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Company</th>
                    <th className="px-5 py-3 font-semibold">City</th>
                    <th className="px-5 py-3 font-semibold">Band</th>
                    <th className="px-5 py-3 font-semibold">Score</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                    <th className="px-5 py-3 font-semibold">Website</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[color:var(--border)]">
                  {leads.map((lead) => (
                    <tr key={lead.public_id} className="bg-white/70">
                      <td className="px-5 py-4">
                        <Link className="font-semibold hover:text-[color:var(--accent)]" to={`/leads/${lead.public_id}`}>
                          {lead.company_name}
                        </Link>
                      </td>
                      <td className="px-5 py-4 text-[color:var(--muted)]">{lead.city ?? "Unknown"}</td>
                      <td className="px-5 py-4">
                        <Badge tone={lead.latest_band === "high" ? "warning" : "accent"}>
                          {lead.latest_band ?? "unscored"}
                        </Badge>
                      </td>
                      <td className="px-5 py-4">{lead.latest_score ? Math.round(lead.latest_score) : "N/A"}</td>
                      <td className="px-5 py-4">
                        <Badge tone="neutral">{lead.status}</Badge>
                      </td>
                      <td className="px-5 py-4 text-[color:var(--muted)]">{lead.website_domain ?? "Missing"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
