import { type ReactNode, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Building2,
  CircleDollarSign,
  Database,
  ServerCog,
  Users,
} from "lucide-react";
import { Link, useLocation, useParams } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  disablePlatformUser,
  disablePlatformWorkspace,
  enablePlatformUser,
  enablePlatformWorkspace,
  getPlatformAiUsage,
  getPlatformFeatureHealth,
  getPlatformOverview,
  getPlatformProviders,
  getPlatformWorkspace,
  listPlatformInvoices,
  listPlatformPlans,
  listPlatformSearchJobs,
  listPlatformSubscriptions,
  listPlatformUsage,
  listPlatformUsers,
  listPlatformWorkspaces,
} from "@/features/platform-admin/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import type {
  AdminInvoiceResponse,
  AdminProviderFetchResponse,
  AdminSearchJobResponse,
  AdminSubscriptionResponse,
  AdminUsageCounterResponse,
  AdminUserSummaryResponse,
  AdminWorkspaceSummaryResponse,
  PlanResponse,
} from "@/types/api";

const ADMIN_NAV = [
  { label: "Overview", href: appPaths.admin },
  { label: "Workspaces", href: appPaths.adminWorkspaces },
  { label: "Users", href: appPaths.adminUsers },
  { label: "Billing", href: appPaths.adminBilling },
  { label: "Usage", href: appPaths.adminUsage },
  { label: "Providers", href: appPaths.adminProviders },
  { label: "Jobs", href: appPaths.adminJobs },
  { label: "AI", href: appPaths.adminAi },
] as const;

function formatNumber(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(
    value,
  );
}

function formatMoney(value: number) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(value: string | null) {
  if (!value) return "N/A";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function SectionCard({
  title,
  children,
  actions,
}: {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <Card className="rounded-lg border-border bg-card/95">
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-base">{title}</CardTitle>
        {actions}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function AdminNav() {
  const location = useLocation();
  return (
    <div className="flex gap-2 overflow-x-auto border-b border-border px-3 py-2 sm:px-4 lg:px-6">
      {ADMIN_NAV.map((item) => {
        const active =
          location.pathname === item.href ||
          (item.href !== appPaths.admin &&
            location.pathname.startsWith(`${item.href}/`));
        return (
          <Button
            key={item.href}
            asChild
            size="sm"
            variant={active ? "default" : "outline"}
            className="h-8 shrink-0"
          >
            <Link to={item.href}>{item.label}</Link>
          </Button>
        );
      })}
    </div>
  );
}

function WorkspaceTable({
  items,
  onToggle,
  pendingId,
}: {
  items: AdminWorkspaceSummaryResponse[];
  onToggle: (workspace: AdminWorkspaceSummaryResponse) => void;
  pendingId: string | null;
}) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="No workspaces"
        description="Workspace rows appear after accounts are created."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead className="border-b border-border text-xs uppercase text-muted-foreground">
          <tr>
            <th className="py-2 pe-3">Name</th>
            <th className="py-2 pe-3">Slug</th>
            <th className="py-2 pe-3">Status</th>
            <th className="py-2 pe-3">Owner</th>
            <th className="py-2 pe-3">Users</th>
            <th className="py-2 pe-3">Leads</th>
            <th className="py-2 pe-3">Plan</th>
            <th className="py-2 pe-3">Created</th>
            <th className="py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((workspace) => (
            <tr key={workspace.public_id}>
              <td className="py-3 pe-3 font-medium">
                <Link
                  className="hover:underline"
                  to={appPaths.adminWorkspaceDetail(workspace.public_id)}
                >
                  {workspace.name}
                </Link>
              </td>
              <td className="py-3 pe-3 font-mono text-xs">{workspace.slug}</td>
              <td className="py-3 pe-3">
                <Badge tone={workspace.status === "active" ? "success" : "warning"}>
                  {workspace.status}
                </Badge>
              </td>
              <td className="py-3 pe-3">{workspace.owner_email ?? "N/A"}</td>
              <td className="py-3 pe-3">{workspace.users_count}</td>
              <td className="py-3 pe-3">{workspace.leads_count}</td>
              <td className="py-3 pe-3">
                {workspace.plan_code ?? "N/A"} /{" "}
                {workspace.subscription_status ?? "none"}
              </td>
              <td className="py-3 pe-3">{formatDate(workspace.created_at)}</td>
              <td className="py-3 text-right">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 bg-transparent"
                  disabled={pendingId === workspace.public_id}
                  onClick={() => onToggle(workspace)}
                >
                  {workspace.status === "active" ? "Disable" : "Enable"}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UsersTable({
  items,
  onToggle,
  pendingId,
}: {
  items: AdminUserSummaryResponse[];
  onToggle: (user: AdminUserSummaryResponse) => void;
  pendingId: string | null;
}) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="No users"
        description="User rows appear after workspaces add team members."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead className="border-b border-border text-xs uppercase text-muted-foreground">
          <tr>
            <th className="py-2 pe-3">Name</th>
            <th className="py-2 pe-3">Email</th>
            <th className="py-2 pe-3">Role</th>
            <th className="py-2 pe-3">Workspace</th>
            <th className="py-2 pe-3">Status</th>
            <th className="py-2 pe-3">Last login</th>
            <th className="py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((user) => (
            <tr key={user.public_id}>
              <td className="py-3 pe-3 font-medium">{user.full_name}</td>
              <td className="py-3 pe-3">{user.email}</td>
              <td className="py-3 pe-3 font-mono text-xs">{user.role}</td>
              <td className="py-3 pe-3">{user.workspace_name}</td>
              <td className="py-3 pe-3">
                <Badge tone={user.status === "active" ? "success" : "warning"}>
                  {user.status}
                </Badge>
              </td>
              <td className="py-3 pe-3">{formatDate(user.last_login_at)}</td>
              <td className="py-3 text-right">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 bg-transparent"
                  disabled={pendingId === user.public_id}
                  onClick={() => onToggle(user)}
                >
                  {user.status === "active" ? "Disable" : "Enable"}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BillingTables({
  plans,
  subscriptions,
  invoices,
}: {
  plans: PlanResponse[];
  subscriptions: AdminSubscriptionResponse[];
  invoices: AdminInvoiceResponse[];
}) {
  const paymentAttempts = invoices.flatMap((invoice) =>
    invoice.payment_attempts.map((attempt) => ({
      invoice,
      attempt,
    })),
  );
  const unpaidOrFailedInvoices = invoices.filter((invoice) =>
    ["open", "past_due", "failed"].includes(invoice.status),
  );

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <SectionCard title="Plans">
        <SimpleList
          items={plans.map((plan) => ({
            id: plan.code,
            title: plan.name,
            meta: `${formatMoney(plan.monthly_price)}/mo, ${formatMoney(
              plan.yearly_price,
            )}/yr`,
            value: plan.is_active ? "active" : "inactive",
          }))}
        />
      </SectionCard>
      <SectionCard title="Subscriptions">
        <SimpleList
          items={subscriptions.map((subscription) => ({
            id: subscription.public_id,
            title: subscription.workspace_name,
            meta: `${subscription.plan_name} / ${subscription.billing_cycle}`,
            value: subscription.status,
          }))}
        />
      </SectionCard>
      <SectionCard title="Invoices">
        <SimpleList
          items={invoices.map((invoice) => ({
            id: invoice.public_id,
            title: invoice.workspace_name,
            meta: `${formatMoney(invoice.amount)} ${invoice.currency} / ${
              invoice.payment_attempts.length
            } attempts`,
            value: invoice.status,
          }))}
        />
      </SectionCard>
      <SectionCard title="Payment attempts">
        <SimpleList
          items={paymentAttempts.map(({ invoice, attempt }) => ({
            id: attempt.public_id,
            title: invoice.workspace_name,
            meta: `${invoice.public_id} / ${formatDate(attempt.attempted_at)}${
              attempt.error_message ? ` / ${attempt.error_message}` : ""
            }`,
            value: attempt.simulated_result,
          }))}
        />
      </SectionCard>
      <SectionCard title="Unpaid or failed invoices">
        <SimpleList
          items={unpaidOrFailedInvoices.map((invoice) => ({
            id: invoice.public_id,
            title: invoice.workspace_name,
            meta: `${formatMoney(invoice.amount)} ${invoice.currency} due ${formatDate(
              invoice.due_at,
            )}`,
            value: invoice.status,
          }))}
        />
      </SectionCard>
    </div>
  );
}

function SimpleList({
  items,
}: {
  items: Array<{ id: string; title: string; meta: string; value: string }>;
}) {
  if (items.length === 0) {
    return <EmptyState title="No rows" description="No persisted records yet." />;
  }

  return (
    <div className="divide-y divide-border">
      {items.map((item) => (
        <div key={item.id} className="flex items-center justify-between gap-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{item.title}</p>
            <p className="truncate text-xs text-muted-foreground">{item.meta}</p>
          </div>
          <Badge tone="neutral">{item.value}</Badge>
        </div>
      ))}
    </div>
  );
}

function UsageList({ items }: { items: AdminUsageCounterResponse[] }) {
  return (
    <SimpleList
      items={items.map((item) => ({
        id: `${item.workspace_public_id}-${item.metric_key}-${item.period_end}`,
        title: `${item.workspace_name} / ${item.metric_key}`,
        meta: `${formatDate(item.period_start)} to ${formatDate(item.period_end)}`,
        value: formatNumber(item.current_value),
      }))}
    />
  );
}

function JobList({ items }: { items: AdminSearchJobResponse[] }) {
  return (
    <SimpleList
      items={items.map((job) => ({
        id: job.public_id,
        title: `${job.business_type} in ${job.city}`,
        meta: `${job.workspace_name} / ${formatDate(job.queued_at)}`,
        value: job.status,
      }))}
    />
  );
}

function ProviderFetchList({ items }: { items: AdminProviderFetchResponse[] }) {
  return (
    <SimpleList
      items={items.map((fetch) => ({
        id: fetch.public_id,
        title: `${fetch.provider} / ${fetch.engine}`,
        meta: `${fetch.workspace_name} / ${fetch.mode}${
          fetch.error_message ? ` / ${fetch.error_message}` : ""
        }`,
        value: fetch.status,
      }))}
    />
  );
}

export function PlatformAdminPage() {
  useDocumentTitle("Platform admin");
  const location = useLocation();
  const { workspaceId } = useParams();
  const queryClient = useQueryClient();
  const section = useMemo(() => {
    if (workspaceId) return "workspace-detail";
    if (location.pathname.startsWith(appPaths.adminWorkspaces)) return "workspaces";
    if (location.pathname.startsWith(appPaths.adminUsers)) return "users";
    if (location.pathname.startsWith(appPaths.adminBilling)) return "billing";
    if (location.pathname.startsWith(appPaths.adminUsage)) return "usage";
    if (location.pathname.startsWith(appPaths.adminProviders)) return "providers";
    if (location.pathname.startsWith(appPaths.adminJobs)) return "jobs";
    if (location.pathname.startsWith(appPaths.adminAi)) return "ai";
    return "overview";
  }, [location.pathname, workspaceId]);

  const overviewQuery = useQuery({
    queryKey: ["platform-admin", "overview"],
    queryFn: getPlatformOverview,
  });
  const workspacesQuery = useQuery({
    queryKey: ["platform-admin", "workspaces"],
    queryFn: listPlatformWorkspaces,
  });
  const usersQuery = useQuery({
    queryKey: ["platform-admin", "users"],
    queryFn: listPlatformUsers,
  });
  const plansQuery = useQuery({
    queryKey: ["platform-admin", "plans"],
    queryFn: listPlatformPlans,
  });
  const subscriptionsQuery = useQuery({
    queryKey: ["platform-admin", "subscriptions"],
    queryFn: listPlatformSubscriptions,
  });
  const invoicesQuery = useQuery({
    queryKey: ["platform-admin", "invoices"],
    queryFn: listPlatformInvoices,
  });
  const usageQuery = useQuery({
    queryKey: ["platform-admin", "usage"],
    queryFn: listPlatformUsage,
  });
  const providersQuery = useQuery({
    queryKey: ["platform-admin", "providers"],
    queryFn: getPlatformProviders,
  });
  const jobsQuery = useQuery({
    queryKey: ["platform-admin", "jobs"],
    queryFn: listPlatformSearchJobs,
  });
  const aiUsageQuery = useQuery({
    queryKey: ["platform-admin", "ai-usage"],
    queryFn: getPlatformAiUsage,
  });
  const featureHealthQuery = useQuery({
    queryKey: ["platform-admin", "feature-health"],
    queryFn: getPlatformFeatureHealth,
  });
  const workspaceDetailQuery = useQuery({
    queryKey: ["platform-admin", "workspace", workspaceId],
    queryFn: () => getPlatformWorkspace(workspaceId ?? ""),
    enabled: Boolean(workspaceId),
  });

  const workspaceMutation = useMutation({
    mutationFn: (workspace: AdminWorkspaceSummaryResponse) =>
      workspace.status === "active"
        ? disablePlatformWorkspace(workspace.public_id)
        : enablePlatformWorkspace(workspace.public_id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["platform-admin"] });
    },
  });

  const userMutation = useMutation({
    mutationFn: (user: AdminUserSummaryResponse) =>
      user.status === "active"
        ? disablePlatformUser(user.public_id)
        : enablePlatformUser(user.public_id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["platform-admin"] });
    },
  });

  if (overviewQuery.isError) {
    return (
      <EmptyState
        title="Platform admin unavailable"
        description="The current account is not authorized or the admin API could not be reached."
      />
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="SaaS admin"
        title="Platform administration"
        description="Workspaces, users, billing, providers, jobs, AI usage, and feature health across the platform."
      />
      <AdminNav />
      <div className="space-y-4 p-3 sm:p-4 lg:p-6">
        {overviewQuery.isPending ? (
          <QueryStateNotice
            tone="loading"
            title="Loading platform metrics"
            description="Fetching live platform aggregates."
          />
        ) : (
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <KpiCard
              label="Workspaces"
              value={formatNumber(overviewQuery.data.total_workspaces)}
              helper={`${overviewQuery.data.active_workspaces} active`}
              tone="signal"
              icon={Building2}
            />
            <KpiCard
              label="Users"
              value={formatNumber(overviewQuery.data.total_users)}
              helper={`${overviewQuery.data.active_users} active`}
              tone="evidence"
              icon={Users}
            />
            <KpiCard
              label="Leads"
              value={formatNumber(overviewQuery.data.total_leads)}
              helper="Persisted across all workspaces"
              tone="signal"
              icon={Database}
            />
            <KpiCard
              label="Search jobs"
              value={formatNumber(overviewQuery.data.total_search_jobs)}
              helper="Persisted discovery runs"
              tone="evidence"
              icon={Activity}
            />
            <KpiCard
              label="AI analyses"
              value={formatNumber(overviewQuery.data.total_ai_analyses)}
              helper={`${overviewQuery.data.total_evidence_rows} evidence rows`}
              tone="evidence"
              icon={Activity}
            />
            <KpiCard
              label="Signals"
              value={formatNumber(overviewQuery.data.total_signals)}
              helper="Detected lead signals"
              tone="signal"
              icon={Activity}
            />
            <KpiCard
              label="ICP profiles"
              value={formatNumber(overviewQuery.data.total_icp_profiles)}
              helper="Stored workspace profiles"
              tone="signal"
              icon={Database}
            />
            <KpiCard
              label="MRR"
              value={formatMoney(overviewQuery.data.monthly_recurring_revenue)}
              helper={`${overviewQuery.data.unpaid_invoices_count} unpaid invoices`}
              tone="evidence"
              icon={CircleDollarSign}
            />
            <KpiCard
              label="Failed jobs"
              value={formatNumber(overviewQuery.data.failed_search_jobs)}
              helper="Search jobs requiring attention"
              tone={
                overviewQuery.data.failed_search_jobs > 0 ? "caution" : "evidence"
              }
              icon={Activity}
            />
            <KpiCard
              label="Provider errors"
              value={formatNumber(overviewQuery.data.provider_error_count)}
              helper="Stored provider fetch failures"
              tone={overviewQuery.data.provider_error_count > 0 ? "risk" : "signal"}
              icon={ServerCog}
            />
          </section>
        )}

        {section === "overview" ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <SectionCard title="Usage by metric">
              <SimpleList
                items={(overviewQuery.data?.usage_by_metric ?? []).map((item) => ({
                  id: item.metric_key,
                  title: item.metric_key,
                  meta: "All workspaces",
                  value: formatNumber(item.current_value),
                }))}
              />
            </SectionCard>
            <SectionCard title="Feature health">
              <SimpleList
                items={[
                  {
                    id: "icp",
                    title: "ICP profiles",
                    meta: "Stored fit profiles",
                    value: formatNumber(
                      featureHealthQuery.data?.icp_profiles_count ?? 0,
                    ),
                  },
                  {
                    id: "signals",
                    title: "Lead signals",
                    meta: "Detected buying/data signals",
                    value: formatNumber(
                      featureHealthQuery.data?.lead_signals_count ?? 0,
                    ),
                  },
                  {
                    id: "evidence",
                    title: "AI evidence",
                    meta: "Evidence rows attached to analyses",
                    value: formatNumber(
                      featureHealthQuery.data?.ai_evidence_count ?? 0,
                    ),
                  },
                ]}
              />
            </SectionCard>
          </div>
        ) : null}

        {section === "workspaces" ? (
          <SectionCard title="Workspaces">
            {workspacesQuery.isPending ? (
              <QueryStateNotice
                tone="loading"
                title="Loading workspaces"
                description="Fetching platform workspace rows."
              />
            ) : workspacesQuery.isError ? (
              <EmptyState
                title="Workspaces unavailable"
                description="The workspace list could not be loaded."
              />
            ) : (
              <WorkspaceTable
                items={workspacesQuery.data.items}
                onToggle={(workspace) => workspaceMutation.mutate(workspace)}
                pendingId={
                  workspaceMutation.isPending
                    ? (workspaceMutation.variables?.public_id ?? null)
                    : null
                }
              />
            )}
          </SectionCard>
        ) : null}

        {section === "workspace-detail" && workspaceId ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-semibold">
                {workspaceDetailQuery.data?.workspace.name ?? "Workspace detail"}
              </h2>
              <Button asChild size="sm" variant="outline" className="bg-transparent">
                <Link to={appPaths.adminWorkspaces}>Back to workspaces</Link>
              </Button>
            </div>
            {workspaceDetailQuery.isPending ? (
              <QueryStateNotice
                tone="loading"
                title="Loading workspace"
                description="Fetching workspace detail."
              />
            ) : workspaceDetailQuery.data ? (
              <div className="grid gap-4 xl:grid-cols-2">
                <SectionCard title="Profile and feature summary">
                  <SimpleList
                    items={[
                      {
                        id: "status",
                        title: "Status",
                        meta: workspaceDetailQuery.data.workspace.slug,
                        value: workspaceDetailQuery.data.workspace.status,
                      },
                      {
                        id: "owner",
                        title: "Owner",
                        meta:
                          workspaceDetailQuery.data.owner?.email ??
                          "No workspace owner assigned",
                        value:
                          workspaceDetailQuery.data.owner?.status ?? "unassigned",
                      },
                      {
                        id: "users",
                        title: "Users",
                        meta: "Team members",
                        value: formatNumber(workspaceDetailQuery.data.users_count),
                      },
                      {
                        id: "leads",
                        title: "Leads",
                        meta: "Stored records",
                        value: formatNumber(workspaceDetailQuery.data.leads_count),
                      },
                      {
                        id: "searches",
                        title: "Searches",
                        meta: "Discovery jobs",
                        value: formatNumber(
                          workspaceDetailQuery.data.searches_count,
                        ),
                      },
                      {
                        id: "ai",
                        title: "AI analyses",
                        meta: "Lead snapshots",
                        value: formatNumber(
                          workspaceDetailQuery.data.ai_analyses_count,
                        ),
                      },
                      {
                        id: "icp",
                        title: "ICP profiles",
                        meta: "Workspace fit profiles",
                        value: formatNumber(
                          workspaceDetailQuery.data.icp_profiles_count,
                        ),
                      },
                      {
                        id: "signals",
                        title: "Lead signals",
                        meta: "Detected workspace signals",
                        value: formatNumber(workspaceDetailQuery.data.signals_count),
                      },
                      {
                        id: "scores",
                        title: "Scoring 2.0",
                        meta: `${workspaceDetailQuery.data.scoring_versions_count} versions`,
                        value: formatNumber(
                          workspaceDetailQuery.data.lead_scores_count,
                        ),
                      },
                      {
                        id: "evidence",
                        title: "AI evidence",
                        meta: `${workspaceDetailQuery.data.ai_feedback_count} feedback rows`,
                        value: formatNumber(
                          workspaceDetailQuery.data.ai_evidence_count,
                        ),
                      },
                    ]}
                  />
                </SectionCard>
                <SectionCard title="Users">
                  <SimpleList
                    items={workspaceDetailQuery.data.users.map((user) => ({
                      id: user.public_id,
                      title: user.full_name,
                      meta: `${user.email} / ${user.role}`,
                      value: user.status,
                    }))}
                  />
                </SectionCard>
                <SectionCard title="Subscription">
                  <SimpleList
                    items={
                      workspaceDetailQuery.data.subscription
                        ? [
                            {
                              id: workspaceDetailQuery.data.subscription.public_id,
                              title:
                                workspaceDetailQuery.data.subscription.plan_name,
                              meta: `${workspaceDetailQuery.data.subscription.billing_cycle} / ${workspaceDetailQuery.data.subscription.workspace_name}`,
                              value:
                                workspaceDetailQuery.data.subscription.status,
                            },
                          ]
                        : []
                    }
                  />
                </SectionCard>
                <SectionCard title="Invoices">
                  <SimpleList
                    items={workspaceDetailQuery.data.invoices.map((invoice) => ({
                      id: invoice.public_id,
                      title: `${formatMoney(invoice.amount)} ${invoice.currency}`,
                      meta: `${invoice.items.length} items / ${invoice.payment_attempts.length} payment attempts`,
                      value: invoice.status,
                    }))}
                  />
                </SectionCard>
                <SectionCard title="Usage">
                  <UsageList items={workspaceDetailQuery.data.usage_counters} />
                </SectionCard>
                <SectionCard title="Recent search jobs">
                  <JobList items={workspaceDetailQuery.data.recent_jobs} />
                </SectionCard>
                <SectionCard title="Recent provider errors">
                  <ProviderFetchList
                    items={workspaceDetailQuery.data.recent_provider_errors}
                  />
                </SectionCard>
                <SectionCard title="Recent audit logs">
                  <SimpleList
                    items={workspaceDetailQuery.data.recent_audit_logs.map(
                      (log) => ({
                        id: log.public_id,
                        title: log.event_name,
                        meta: `${formatDate(log.created_at)} / ${log.details}`,
                        value: log.actor_user_public_id ?? "system",
                      }),
                    )}
                  />
                </SectionCard>
              </div>
            ) : (
              <EmptyState
                title="Workspace unavailable"
                description="The workspace could not be loaded."
              />
            )}
          </div>
        ) : null}

        {section === "users" ? (
          <SectionCard title="Users">
            <UsersTable
              items={usersQuery.data?.items ?? []}
              onToggle={(user) => userMutation.mutate(user)}
              pendingId={
                userMutation.isPending
                  ? (userMutation.variables?.public_id ?? null)
                  : null
              }
            />
          </SectionCard>
        ) : null}

        {section === "billing" ? (
          <BillingTables
            plans={plansQuery.data?.items ?? []}
            subscriptions={subscriptionsQuery.data?.items ?? []}
            invoices={invoicesQuery.data?.items ?? []}
          />
        ) : null}

        {section === "usage" ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <SectionCard title="Usage counters">
              <UsageList items={usageQuery.data?.items ?? []} />
            </SectionCard>
            <SectionCard title="Quota overrides">
              <SimpleList
                items={[
                  {
                    id: "quota-override",
                    title: usageQuery.data?.quota_override_supported
                      ? "Quota override supported"
                      : "Quota override TODO",
                    meta:
                      usageQuery.data?.quota_override_todo ??
                      "Checking usage override support.",
                    value: usageQuery.data?.quota_override_supported ? "yes" : "todo",
                  },
                ]}
              />
            </SectionCard>
          </div>
        ) : null}

        {section === "providers" ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <SectionCard title="Provider health">
              <SimpleList
                items={[
                  {
                    id: "success",
                    title: "Successful fetches",
                    meta: "Stored provider_fetches with ok status",
                    value: formatNumber(providersQuery.data?.success_count ?? 0),
                  },
                  {
                    id: "failures",
                    title: "Failed fetches",
                    meta: "Errors or non-ok statuses",
                    value: formatNumber(providersQuery.data?.failure_count ?? 0),
                  },
                ]}
              />
            </SectionCard>
            <SectionCard title="Provider settings">
              <SimpleList
                items={(providersQuery.data?.settings ?? []).map((setting) => ({
                  id: setting.workspace_public_id,
                  title: setting.workspace_name,
                  meta: `${setting.google_domain} / hl=${setting.hl} / gl=${setting.gl}`,
                  value: `enrich ${setting.enrich_top_n}`,
                }))}
              />
            </SectionCard>
            <SectionCard title="Recent provider fetches">
              <ProviderFetchList items={providersQuery.data?.recent_fetches ?? []} />
            </SectionCard>
            <SectionCard title="Recent provider errors">
              <ProviderFetchList items={providersQuery.data?.recent_errors ?? []} />
            </SectionCard>
          </div>
        ) : null}

        {section === "jobs" ? (
          <SectionCard title="Search jobs">
            <JobList items={jobsQuery.data?.items ?? []} />
          </SectionCard>
        ) : null}

        {section === "ai" ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <SectionCard title="AI usage">
              <SimpleList
                items={[
                  {
                    id: "analyses",
                    title: "Analyses",
                    meta: "Stored AI analysis snapshots",
                    value: formatNumber(aiUsageQuery.data?.analyses_count ?? 0),
                  },
                  {
                    id: "evidence",
                    title: "Evidence rows",
                    meta: "Rows used by AI analysis",
                    value: formatNumber(aiUsageQuery.data?.evidence_rows_count ?? 0),
                  },
                  ...(aiUsageQuery.data?.feedback_counts ?? []).map((feedback) => ({
                    id: `feedback-${feedback.rating}`,
                    title: `Feedback: ${feedback.rating}`,
                    meta: "Stored operator feedback",
                    value: formatNumber(feedback.count),
                  })),
                ]}
              />
            </SectionCard>
            <SectionCard title="Latest AI feedback">
              <SimpleList
                items={(aiUsageQuery.data?.latest_feedback ?? []).map((feedback) => ({
                  id: feedback.public_id,
                  title: feedback.rating,
                  meta:
                    feedback.correction_text ??
                    `Workspace ${feedback.workspace_public_id}`,
                  value: formatDate(feedback.created_at),
                }))}
              />
            </SectionCard>
            <SectionCard title="Risky or low-confidence analyses">
              <SimpleList
                items={(aiUsageQuery.data?.flagged_analyses ?? []).map(
                  (analysis) => ({
                    id: analysis.public_id,
                    title: analysis.lead_name,
                    meta: `${analysis.workspace_name} / ${
                      analysis.risks_or_uncertainties.join("; ") ||
                      "Low model confidence"
                    }`,
                    value: `${Math.round(analysis.confidence * 100)}%`,
                  }),
                )}
              />
            </SectionCard>
            <SectionCard title="Top signals">
              <SimpleList
                items={(featureHealthQuery.data?.top_signal_types ?? []).map(
                  (signal) => ({
                    id: signal.metric_key,
                    title: signal.metric_key,
                    meta: "Signal detections",
                    value: formatNumber(signal.current_value),
                  }),
                )}
              />
            </SectionCard>
            <SectionCard title="Failed jobs">
              <JobList items={featureHealthQuery.data?.failed_jobs ?? []} />
            </SectionCard>
            <SectionCard title="Scoring health">
              <SimpleList
                items={(featureHealthQuery.data?.priority_band_distribution ?? []).map(
                  (band) => ({
                    id: band.metric_key,
                    title: band.metric_key,
                    meta: "Latest stored lead scores",
                    value: formatNumber(band.current_value),
                  }),
                )}
              />
            </SectionCard>
          </div>
        ) : null}

        {overviewQuery.isFetching ||
        workspacesQuery.isFetching ||
        usersQuery.isFetching ? (
          <div className="text-xs text-muted-foreground">
            Refreshing platform data...
          </div>
        ) : null}
      </div>
    </div>
  );
}
