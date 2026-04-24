import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listInvoices, markInvoicePaid, simulateInvoiceFailure } from "@/features/billing/api";
import { useAuthSession } from "@/features/auth/session";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocumentTitle } from "@/hooks/use-document-title";

export function InvoicesPage() {
  useDocumentTitle("Invoices");
  const queryClient = useQueryClient();
  const { user } = useAuthSession();
  const invoicesQuery = useQuery({ queryKey: ["billing-invoices"], queryFn: listInvoices });
  const canManageBilling = user?.permissions?.includes("billing:manage") ?? false;

  const refreshInvoices = () => {
    queryClient.invalidateQueries({ queryKey: ["billing-invoices"] });
    queryClient.invalidateQueries({ queryKey: ["billing-subscription"] });
  };

  const markPaidMutation = useMutation({
    mutationFn: (invoicePublicId: string) => markInvoicePaid({ invoice_public_id: invoicePublicId }),
    onSuccess: refreshInvoices,
  });
  const failureMutation = useMutation({
    mutationFn: (invoicePublicId: string) => simulateInvoiceFailure({ invoice_public_id: invoicePublicId }),
    onSuccess: refreshInvoices,
  });

  if (invoicesQuery.isPending) {
    return <QueryStateNotice tone="loading" title="Loading invoices" description="Fetching simulated invoice history." />;
  }

  if (invoicesQuery.isError) {
    return <QueryStateNotice tone="error" title="Invoices unavailable" description={invoicesQuery.error.message} />;
  }

  return (
    <div className="flex flex-col gap-6 p-4 lg:p-6">
      <Card>
        <CardHeader>
          <CardTitle>Invoices</CardTitle>
          <CardDescription>Internal invoice and payment-attempt records used to simulate SaaS billing and collections.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {invoicesQuery.data.items.map((invoice) => (
            <div key={invoice.public_id} className="rounded-xl border border-border bg-card/50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{invoice.public_id}</p>
                    <Badge tone={invoice.status === "paid" ? "success" : invoice.status === "past_due" ? "warning" : "neutral"}>
                      {invoice.status}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    ${invoice.amount} {invoice.currency} | issued {invoice.issued_at}
                  </p>
                  <p className="text-sm text-muted-foreground">Due {invoice.due_at ?? "n/a"} | Paid {invoice.paid_at ?? "n/a"}</p>
                </div>
                {canManageBilling ? (
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" disabled={invoice.status === "paid" || markPaidMutation.isPending} onClick={() => markPaidMutation.mutate(invoice.public_id)}>
                      Mark success
                    </Button>
                    <Button variant="outline" disabled={failureMutation.isPending} onClick={() => failureMutation.mutate(invoice.public_id)}>
                      Mark failure
                    </Button>
                  </div>
                ) : null}
              </div>

              <div className="mt-3 grid gap-2">
                {invoice.items.map((item, index) => (
                  <div key={`${invoice.public_id}-${index}`} className="text-sm text-muted-foreground">
                    {item.description} | {item.quantity} x ${item.amount}
                  </div>
                ))}
              </div>

              <div className="mt-4 grid gap-2 rounded-xl border border-border bg-background/70 p-3">
                <p className="text-sm font-medium">Payment attempts</p>
                {invoice.payment_attempts.length ? (
                  invoice.payment_attempts.map((attempt) => (
                    <div key={attempt.public_id} className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
                      <span>
                        {attempt.public_id} | {attempt.status} | {attempt.simulated_result}
                      </span>
                      <span>{attempt.error_message ?? attempt.attempted_at}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No simulated payment attempts have been recorded yet.</p>
                )}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
