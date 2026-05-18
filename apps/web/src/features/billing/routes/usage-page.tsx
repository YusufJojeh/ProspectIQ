import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { getUsageSummary } from "@/features/billing/api";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { usageMetricLabel } from "@/lib/i18n-labels";
import { formatDate } from "@/lib/presenters";

export function UsagePage() {
  const { t } = useTranslation();
  useDocumentTitle(t("billing.usageTitle"));
  const usageQuery = useQuery({ queryKey: ["billing-usage"], queryFn: getUsageSummary });

  if (usageQuery.isPending) {
    return <QueryStateNotice tone="loading" title={t("billing.loadingUsageTitle")} description={t("billing.loadingUsageDescription")} />;
  }

  if (usageQuery.isError) {
    return <QueryStateNotice tone="error" title={t("billing.usageUnavailable")} error={usageQuery.error} />;
  }

  return (
    <div className="flex flex-col gap-6 p-4 lg:p-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("billing.usageAndLimits")}</CardTitle>
          <CardDescription>{t("billing.usageAndLimitsDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {usageQuery.data.items.map((item) => {
            const percentage = item.limit_value ? Math.min(100, Math.round((item.current_value / item.limit_value) * 100)) : 0;
            return (
              <div key={item.metric_key} className="rounded-xl border border-border bg-card/50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">{usageMetricLabel(t, item.metric_key)}</p>
                  <p className="text-sm text-muted-foreground">
                    {item.current_value} / {item.limit_value ?? t("billing.unlimited")}
                  </p>
                </div>
                <Progress className="mt-3" value={percentage} />
                <p className="mt-3 text-sm text-muted-foreground">
                  {t("billing.currentPeriod")}: {formatDate(item.period_start)} {t("billing.to")} {formatDate(item.period_end)}
                </p>
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
