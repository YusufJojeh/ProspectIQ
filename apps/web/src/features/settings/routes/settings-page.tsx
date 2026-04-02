import { useQuery } from "@tanstack/react-query";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getActiveScoringConfig, getProviderSettings } from "@/features/settings/api";
import { useDocumentTitle } from "@/hooks/use-document-title";

export function SettingsPage() {
  useDocumentTitle("Admin");
  const scoringQuery = useQuery({
    queryKey: ["admin", "scoring", "active"],
    queryFn: getActiveScoringConfig,
  });
  const providerQuery = useQuery({
    queryKey: ["admin", "provider-settings"],
    queryFn: getProviderSettings,
  });

  if (scoringQuery.isError || providerQuery.isError) {
    return (
      <EmptyState
        title="Admin configuration is unavailable"
        description="Make sure the current user is an admin in the seeded workspace and that the API is running."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin"
        title="Operational configuration"
        description="Foundation view of the currently active provider and scoring configuration."
      />

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Scoring version</CardTitle>
            <CardDescription>Read-only baseline until audited admin mutation flows are added.</CardDescription>
          </CardHeader>
          <CardContent>
            {scoringQuery.data ? (
              <div className="space-y-4 text-sm">
                <div className="rounded-xl border border-[color:var(--border)] p-4">
                  <p className="font-semibold">Active version</p>
                  <p className="mt-2 text-[color:var(--muted)]">{scoringQuery.data.active_version.public_id}</p>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {Object.entries(scoringQuery.data.active_version.weights).map(([key, value]) => (
                    <div
                      key={key}
                      className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4"
                    >
                      <p className="font-semibold">{key}</p>
                      <p className="mt-2 text-[color:var(--muted)]">{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <EmptyState
                title="No active scoring config"
                description="Run the seed script to create the initial scoring configuration for the default workspace."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Provider settings</CardTitle>
            <CardDescription>Workspace-specific SerpAPI defaults are surfaced here.</CardDescription>
          </CardHeader>
          <CardContent>
            {providerQuery.data ? (
              <div className="grid gap-3 text-sm md:grid-cols-2">
                <div className="rounded-xl border border-[color:var(--border)] p-4">
                  <p className="font-semibold">Language</p>
                  <p className="mt-2 text-[color:var(--muted)]">{providerQuery.data.hl}</p>
                </div>
                <div className="rounded-xl border border-[color:var(--border)] p-4">
                  <p className="font-semibold">Region</p>
                  <p className="mt-2 text-[color:var(--muted)]">{providerQuery.data.gl}</p>
                </div>
                <div className="rounded-xl border border-[color:var(--border)] p-4">
                  <p className="font-semibold">Google domain</p>
                  <p className="mt-2 text-[color:var(--muted)]">{providerQuery.data.google_domain}</p>
                </div>
                <div className="rounded-xl border border-[color:var(--border)] p-4">
                  <p className="font-semibold">Enrichment top N</p>
                  <p className="mt-2 text-[color:var(--muted)]">{providerQuery.data.enrich_top_n}</p>
                </div>
              </div>
            ) : (
              <EmptyState
                title="No provider settings"
                description="Run the seed script to create the initial provider settings row for the default workspace."
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
