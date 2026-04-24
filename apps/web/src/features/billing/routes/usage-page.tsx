import { useQuery } from "@tanstack/react-query";
import { getUsageSummary } from "@/features/billing/api";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useDocumentTitle } from "@/hooks/use-document-title";

export function UsagePage() {
  useDocumentTitle("Usage");
  const usageQuery = useQuery({ queryKey: ["billing-usage"], queryFn: getUsageSummary });

  if (usageQuery.isPending) {
    return <QueryStateNotice tone="loading" title="Loading usage" description="Fetching plan limits and current workspace usage." />;
  }

  if (usageQuery.isError) {
    return <QueryStateNotice tone="error" title="Usage unavailable" description={usageQuery.error.message} />;
  }

  return (
    <div className="flex flex-col gap-6 p-4 lg:p-6">
      <Card>
        <CardHeader>
          <CardTitle>Usage and plan limits</CardTitle>
          <CardDescription>Usage is scoped to the current workspace and enforced before protected operations run.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {usageQuery.data.items.map((item) => {
            const percentage = item.limit_value ? Math.min(100, Math.round((item.current_value / item.limit_value) * 100)) : 0;
            return (
              <div key={item.metric_key} className="rounded-xl border border-border bg-card/50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">{item.metric_key.replace(/_/g, " ")}</p>
                  <p className="text-sm text-muted-foreground">
                    {item.current_value} / {item.limit_value ?? "unlimited"}
                  </p>
                </div>
                <Progress className="mt-3" value={percentage} />
                <p className="mt-3 text-sm text-muted-foreground">
                  Current period: {item.period_start} to {item.period_end}
                </p>
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
