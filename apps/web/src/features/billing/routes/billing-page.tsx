import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  cancelSubscription,
  changeSubscription,
  getSubscription,
  getUsageSummary,
  listInvoices,
  listPlans,
  renewSubscription,
  simulateInvoiceFailure,
} from "@/features/billing/api";
import { useAuthSession } from "@/features/auth/session";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { billingCycleLabel, billingStatusLabel } from "@/lib/i18n-labels";
import { formatDate } from "@/lib/presenters";

export function BillingPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("billing.title"));
  const queryClient = useQueryClient();
  const { user } = useAuthSession();
  const [billingCycle, setBillingCycle] = useState<"monthly" | "yearly">("monthly");
  const plansQuery = useQuery({ queryKey: ["billing-plans"], queryFn: listPlans });
  const subscriptionQuery = useQuery({ queryKey: ["billing-subscription"], queryFn: getSubscription });
  const invoicesQuery = useQuery({ queryKey: ["billing-invoices"], queryFn: listInvoices });
  const usageQuery = useQuery({ queryKey: ["billing-usage"], queryFn: getUsageSummary });
  const canManageBilling = user?.permissions?.includes("billing:manage") ?? false;

  const refreshBilling = () => {
    queryClient.invalidateQueries({ queryKey: ["billing-plans"] });
    queryClient.invalidateQueries({ queryKey: ["billing-subscription"] });
    queryClient.invalidateQueries({ queryKey: ["billing-invoices"] });
    queryClient.invalidateQueries({ queryKey: ["billing-usage"] });
  };

  const planMutation = useMutation({
    mutationFn: (planCode: string) => changeSubscription({ plan_code: planCode, billing_cycle: billingCycle }),
    onSuccess: refreshBilling,
  });
  const cancelMutation = useMutation({ mutationFn: cancelSubscription, onSuccess: refreshBilling });
  const renewMutation = useMutation({ mutationFn: renewSubscription, onSuccess: refreshBilling });
  const simulateFailureMutation = useMutation({
    mutationFn: (invoicePublicId: string) => simulateInvoiceFailure({ invoice_public_id: invoicePublicId }),
    onSuccess: refreshBilling,
  });

  if (plansQuery.isPending || subscriptionQuery.isPending || invoicesQuery.isPending || usageQuery.isPending) {
    return <QueryStateNotice tone="loading" title={t("billing.loadingTitle")} description={t("billing.loadingDescription")} />;
  }

  if (plansQuery.isError || subscriptionQuery.isError || invoicesQuery.isError || usageQuery.isError) {
    return <QueryStateNotice tone="error" title={t("billing.unavailableTitle")} description={t("billing.unavailableDescription")} />;
  }

  const currentPlan = subscriptionQuery.data.plan_code;
  const latestInvoice = invoicesQuery.data.items[0];
  const teamUsersMetric = usageQuery.data.items.find((item) => item.metric_key === "max_team_users");

  return (
    <div className="flex flex-col gap-6 p-4 lg:p-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("billing.subscription")}</CardTitle>
          <CardDescription>{t("billing.subscriptionDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
          <div className="rounded-xl border border-border bg-card/50 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-lg font-semibold">{subscriptionQuery.data.plan_name}</p>
              <Badge tone={subscriptionQuery.data.status === "past_due" ? "warning" : subscriptionQuery.data.status === "canceled" ? "neutral" : "success"}>
                {billingStatusLabel(t, subscriptionQuery.data.status)}
              </Badge>
            </div>
            <div className="mt-3 grid gap-1 text-sm text-muted-foreground">
              <p>{t("billing.billingCycle")}: {billingCycleLabel(t, subscriptionQuery.data.billing_cycle)}</p>
              <p>{t("billing.paymentMethod")}: {subscriptionQuery.data.simulated_payment_method}</p>
              <p>{t("billing.trialEnds")}: {formatDate(subscriptionQuery.data.trial_ends_at)}</p>
              <p>{t("billing.renews")}: {formatDate(subscriptionQuery.data.renews_at)}</p>
              <p>{t("billing.accessEnds")}: {formatDate(subscriptionQuery.data.ends_at)}</p>
              <p>{t("billing.canceledAt")}: {formatDate(subscriptionQuery.data.canceled_at)}</p>
            </div>
            {teamUsersMetric ? (
              <div className="mt-4 rounded-xl border border-border bg-background/70 p-3 text-sm text-muted-foreground">
                {t("billing.teamSeatsInUse")}: {teamUsersMetric.current_value} / {teamUsersMetric.limit_value ?? t("billing.unlimited")}
              </div>
            ) : null}
            {canManageBilling ? (
              <div className="mt-4 flex flex-col gap-3">
                <div className="flex flex-col gap-2">
                  <span className="text-sm font-medium">{t("billing.nextChangeCycle")}</span>
                  <Select value={billingCycle} onValueChange={(value) => setBillingCycle(value as "monthly" | "yearly")}>
                    <SelectTrigger className="max-w-56">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="monthly">{t("billing.monthly")}</SelectItem>
                      <SelectItem value="yearly">{t("billing.yearly")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={() => renewMutation.mutate()} disabled={renewMutation.isPending}>
                    {t("billing.renewSubscription")}
                  </Button>
                  <Button variant="outline" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}>
                    {t("billing.cancelSubscription")}
                  </Button>
                  {latestInvoice ? (
                    <Button
                      variant="outline"
                      onClick={() => simulateFailureMutation.mutate(latestInvoice.public_id)}
                      disabled={simulateFailureMutation.isPending}
                    >
                      {t("billing.simulatePaymentFailure")}
                    </Button>
                  ) : null}
                </div>
              </div>
            ) : (
              <QueryStateNotice tone="info" title={t("billing.ownerActionRequired")} description={t("billing.ownerActionDescription")} />
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {plansQuery.data.items.map((plan) => (
              <Card key={plan.code} className={plan.code === currentPlan ? "border-[oklch(var(--signal)/0.55)]" : undefined}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between gap-2">
                    <span>{plan.name}</span>
                    {plan.code === currentPlan ? <Badge tone="success">{t("billing.current")}</Badge> : null}
                  </CardTitle>
                  <CardDescription>
                    ${billingCycle === "yearly" ? plan.yearly_price : plan.monthly_price}/{billingCycle === "yearly" ? t("billing.year") : t("billing.month")} {t("billing.simulated")}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3 text-sm text-muted-foreground">
                  <div>{t("billing.searchesPerMonth")}: {plan.limits.searches_per_month}</div>
                  <div>{t("billing.exportsPerMonth")}: {plan.limits.exports_per_month}</div>
                  <div>{t("billing.aiRunsPerMonth")}: {plan.limits.ai_scoring_runs_per_month}</div>
                  <div>{t("billing.outreachPerMonth")}: {plan.limits.outreach_generations_per_month}</div>
                  <div>{t("billing.teamUsers")}: {plan.limits.max_team_users}</div>
                  {canManageBilling ? (
                    <Button
                      variant={plan.code === currentPlan ? "outline" : "default"}
                      disabled={planMutation.isPending || (plan.code === currentPlan && billingCycle === subscriptionQuery.data.billing_cycle)}
                      onClick={() => planMutation.mutate(plan.code)}
                    >
                      {plan.code === currentPlan && billingCycle === subscriptionQuery.data.billing_cycle ? t("billing.currentPlan") : t("billing.applyPlan")}
                    </Button>
                  ) : null}
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
