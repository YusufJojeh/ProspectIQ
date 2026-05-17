import { Suspense, lazy, type ComponentType, type LazyExoticComponent, type ReactElement } from "react";
import { Navigate, Outlet, RouterProvider, createBrowserRouter, useParams } from "react-router-dom";
import { AppProviders } from "@/app/providers";
import { AppShell } from "@/app/layouts/app-shell";
import { appPaths } from "@/app/paths";
import { EmptyState } from "@/components/shared/empty-state";
import { RouteLoadingFallback } from "@/components/shared/route-loading-fallback";
import { useAuthSession } from "@/features/auth/session";
import { ForgotPasswordPage } from "@/features/auth/routes/forgot-password-page";
import { LoginPage } from "@/features/auth/routes/login-page";
import { SignUpPage } from "@/features/auth/routes/sign-up-page";
import i18n from "@/lib/i18n";

const HomePage = lazy(async () => {
  const module = await import("@/features/home/routes/home-page");
  return { default: module.HomePage };
});
const DashboardPage = lazy(async () => {
  const module = await import("@/features/dashboard/routes/dashboard-page");
  return { default: module.DashboardPage };
});
const SearchesPage = lazy(async () => {
  const module = await import("@/features/searches/routes/searches-page");
  return { default: module.SearchesPage };
});
const SearchJobDetailPage = lazy(async () => {
  const module = await import("@/features/searches/routes/search-job-detail-page");
  return { default: module.SearchJobDetailPage };
});
const LeadsPage = lazy(async () => {
  const module = await import("@/features/leads/routes/leads-page");
  return { default: module.LeadsPage };
});
const LeadDetailPage = lazy(async () => {
  const module = await import("@/features/lead-detail/routes/lead-detail-page");
  return { default: module.LeadDetailPage };
});
const SettingsPage = lazy(async () => {
  const module = await import("@/features/settings/routes/settings-page");
  return { default: module.SettingsPage };
});
const TeamPage = lazy(async () => {
  const module = await import("@/features/users/routes/team-page");
  return { default: module.TeamPage };
});
const BillingPage = lazy(async () => {
  const module = await import("@/features/billing/routes/billing-page");
  return { default: module.BillingPage };
});
const InvoicesPage = lazy(async () => {
  const module = await import("@/features/billing/routes/invoices-page");
  return { default: module.InvoicesPage };
});
const UsagePage = lazy(async () => {
  const module = await import("@/features/billing/routes/usage-page");
  return { default: module.UsagePage };
});
const AiAnalysisPage = lazy(async () => {
  const module = await import("@/features/ai-analysis/routes/ai-analysis-page");
  return { default: module.AiAnalysisPage };
});
const AssistantPage = lazy(async () => {
  const module = await import("@/features/assistant/routes/assistant-page");
  return { default: module.AssistantPage };
});
const AuditLogsPage = lazy(async () => {
  const module = await import("@/features/audit-logs/routes/audit-logs-page");
  return { default: module.AuditLogsPage };
});
const ExportsPage = lazy(async () => {
  const module = await import("@/features/exports/routes/exports-page");
  return { default: module.ExportsPage };
});
const OutreachPage = lazy(async () => {
  const module = await import("@/features/outreach/routes/outreach-page");
  return { default: module.OutreachPage };
});
const AdminPage = lazy(async () => {
  const module = await import("@/features/admin/routes/admin-page");
  return { default: module.AdminPage };
});

function PublicOnlyRoute({ children }: { children: ReactElement }) {
  const { isAuthenticated } = useAuthSession();

  if (isAuthenticated) {
    return <Navigate replace to={appPaths.dashboard} />;
  }

  return children;
}

function ProtectedShell() {
  const { isAuthenticated } = useAuthSession();

  if (!isAuthenticated) {
    return <Navigate replace to={appPaths.login} />;
  }

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

function RequireRole({ allowedRoles }: { allowedRoles: Array<"account_owner" | "admin" | "manager" | "member"> }) {
  const { isAuthenticated, user } = useAuthSession();

  if (!isAuthenticated) {
    return <Navigate replace to={appPaths.login} />;
  }

  if (!user || !allowedRoles.includes(user.role)) {
    return (
      <EmptyState
        title={i18n.t("routeLoading.accessRestrictedTitle")}
        description={i18n.t("routeLoading.accessRestrictedDescription")}
      />
    );
  }

  return <Outlet />;
}

function LegacyLeadDetailRedirect() {
  const { leadId } = useParams();

  if (!leadId) {
    return <Navigate replace to={appPaths.leads} />;
  }

  return <Navigate replace to={appPaths.leadDetail(leadId)} />;
}

function lazyPage(
  Page: LazyExoticComponent<ComponentType>,
  fallback?: { title?: string; description?: string; compact?: boolean },
): ReactElement {
  return (
    <Suspense
      fallback={
        <RouteLoadingFallback
          title={fallback?.title}
          description={fallback?.description}
          compact={fallback?.compact}
        />
      }
    >
      <Page />
    </Suspense>
  );
}

const router = createBrowserRouter([
  {
    path: appPaths.home,
    element: lazyPage(HomePage, {
      title: i18n.t("routeLoading.homeTitle"),
      description: i18n.t("routeLoading.homeDescription"),
    }),
  },
  {
    path: appPaths.login,
    element: (
      <PublicOnlyRoute>
        <LoginPage />
      </PublicOnlyRoute>
    ),
  },
  {
    path: appPaths.signUp,
    element: (
      <PublicOnlyRoute>
        <SignUpPage />
      </PublicOnlyRoute>
    ),
  },
  {
    path: appPaths.forgotPassword,
    element: (
      <PublicOnlyRoute>
        <ForgotPasswordPage />
      </PublicOnlyRoute>
    ),
  },
  {
    path: appPaths.dashboard,
    element: <ProtectedShell />,
    children: [
      {
        index: true,
        element: lazyPage(DashboardPage, {
          title: i18n.t("routeLoading.dashboardTitle"),
          description: i18n.t("routeLoading.dashboardDescription"),
          compact: true,
        }),
      },
      {
        path: "searches/jobs/:jobId",
        element: lazyPage(SearchJobDetailPage, {
          title: i18n.t("routeLoading.discoveryRunTitle"),
          description: i18n.t("routeLoading.discoveryRunDescription"),
        }),
      },
      {
        path: "searches",
        element: lazyPage(SearchesPage, {
          title: i18n.t("routeLoading.searchJobsTitle"),
          description: i18n.t("routeLoading.searchJobsDescription"),
          compact: true,
        }),
      },
      {
        path: "leads",
        element: lazyPage(LeadsPage, {
          title: i18n.t("routeLoading.leadWorkspaceTitle"),
          description: i18n.t("routeLoading.leadWorkspaceDescription"),
          compact: true,
        }),
      },
      {
        path: "leads/:leadId",
        element: lazyPage(LeadDetailPage, {
          title: i18n.t("routeLoading.leadDetailTitle"),
          description: i18n.t("routeLoading.leadDetailDescription"),
          compact: true,
        }),
      },
      {
        path: "ai-analysis",
        element: lazyPage(AiAnalysisPage, {
          title: i18n.t("routeLoading.aiAnalysisTitle"),
          description: i18n.t("routeLoading.aiAnalysisDescription"),
          compact: true,
        }),
      },
      {
        path: "assistant",
        element: lazyPage(AssistantPage, {
          title: i18n.t("routeLoading.assistantTitle"),
          description: i18n.t("routeLoading.assistantDescription"),
          compact: true,
        }),
      },
      {
        path: "outreach",
        element: lazyPage(OutreachPage, {
          title: i18n.t("routeLoading.outreachTitle"),
          description: i18n.t("routeLoading.outreachDescription"),
          compact: true,
        }),
      },
      {
        path: "exports",
        element: lazyPage(ExportsPage, {
          title: i18n.t("routeLoading.exportsTitle"),
          description: i18n.t("routeLoading.exportsDescription"),
          compact: true,
        }),
      },
      {
        path: "team",
        element: lazyPage(TeamPage, {
          title: i18n.t("routeLoading.teamTitle"),
          description: i18n.t("routeLoading.teamDescription"),
          compact: true,
        }),
      },
      {
        path: "billing",
        element: lazyPage(BillingPage, {
          title: i18n.t("routeLoading.billingTitle"),
          description: i18n.t("routeLoading.billingDescription"),
          compact: true,
        }),
      },
      {
        path: "invoices",
        element: lazyPage(InvoicesPage, {
          title: i18n.t("routeLoading.invoicesTitle"),
          description: i18n.t("routeLoading.invoicesDescription"),
          compact: true,
        }),
      },
      {
        path: "usage",
        element: lazyPage(UsagePage, {
          title: i18n.t("routeLoading.usageTitle"),
          description: i18n.t("routeLoading.usageDescription"),
          compact: true,
        }),
      },
      {
        element: <RequireRole allowedRoles={["account_owner", "admin"]} />,
        children: [
          {
            path: "admin",
            element: lazyPage(AdminPage, {
              title: i18n.t("routeLoading.adminTitle"),
              description: i18n.t("routeLoading.adminDescription"),
              compact: true,
            }),
          },
          {
            path: "settings",
            element: lazyPage(SettingsPage, {
              title: i18n.t("routeLoading.settingsTitle"),
              description: i18n.t("routeLoading.settingsDescription"),
              compact: true,
            }),
          },
          {
            path: "audit-logs",
            element: lazyPage(AuditLogsPage, {
              title: i18n.t("routeLoading.auditLogsTitle"),
              description: i18n.t("routeLoading.auditLogsDescription"),
              compact: true,
            }),
          },
        ],
      },
    ],
  },
  {
    path: "/searches",
    element: <Navigate replace to={appPaths.searches} />,
  },
  {
    path: "/leads",
    element: <Navigate replace to={appPaths.leads} />,
  },
  {
    path: "/leads/:leadId",
    element: <LegacyLeadDetailRedirect />,
  },
  {
    path: "/settings",
    element: <Navigate replace to={appPaths.settings} />,
  },
]);

export function AppRouterProvider() {
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
