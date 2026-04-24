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
      <EmptyState title="Access restricted" description="This area is limited to authorized workspace roles." />
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
      title: "Loading home page",
      description: "Preparing the public product overview.",
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
          title: "Loading dashboard",
          description: "Preparing summary cards, charts, and workspace signals.",
          compact: true,
        }),
      },
      {
        path: "searches/jobs/:jobId",
        element: lazyPage(SearchJobDetailPage, {
          title: "Loading discovery run",
          description: "Preparing job detail metrics and execution state.",
        }),
      },
      {
        path: "searches",
        element: lazyPage(SearchesPage, {
          title: "Loading search jobs",
          description: "Preparing search forms and job history.",
          compact: true,
        }),
      },
      {
        path: "leads",
        element: lazyPage(LeadsPage, {
          title: "Loading lead workspace",
          description: "Preparing filters, table, and map panels.",
          compact: true,
        }),
      },
      {
        path: "leads/:leadId",
        element: lazyPage(LeadDetailPage, {
          title: "Loading lead detail",
          description: "Preparing evidence, activity, and outreach panels.",
          compact: true,
        }),
      },
      {
        path: "ai-analysis",
        element: lazyPage(AiAnalysisPage, {
          title: "Loading AI analysis",
          description: "Fetching lead intelligence and recommendations.",
          compact: true,
        }),
      },
      {
        path: "outreach",
        element: lazyPage(OutreachPage, {
          title: "Loading outreach workspace",
          description: "Preparing AI-drafted outreach messages.",
          compact: true,
        }),
      },
      {
        path: "audit-logs",
        element: lazyPage(AuditLogsPage, {
          title: "Loading audit logs",
          description: "Fetching tamper-evident event history.",
          compact: true,
        }),
      },
      {
        path: "exports",
        element: lazyPage(ExportsPage, {
          title: "Loading exports",
          description: "Preparing lead export workspace.",
          compact: true,
        }),
      },
      {
        element: <RequireRole allowedRoles={["account_owner", "admin"]} />,
        children: [
          {
            path: "admin",
            element: lazyPage(AdminPage, {
              title: "Loading admin workspace",
              description: "Preparing scoring, providers, and health panels.",
              compact: true,
            }),
          },
          {
            path: "settings",
            element: lazyPage(SettingsPage, {
              title: "Loading settings",
              description: "Preparing operational configuration and audit views.",
              compact: true,
            }),
          },
          {
            path: "team",
            element: lazyPage(TeamPage, {
              title: "Loading team",
              description: "Preparing workspace team members and access controls.",
              compact: true,
            }),
          },
          {
            path: "billing",
            element: lazyPage(BillingPage, {
              title: "Loading billing",
              description: "Preparing subscription controls and simulated billing records.",
              compact: true,
            }),
          },
          {
            path: "invoices",
            element: lazyPage(InvoicesPage, {
              title: "Loading invoices",
              description: "Preparing invoice history and payment simulation actions.",
              compact: true,
            }),
          },
          {
            path: "usage",
            element: lazyPage(UsagePage, {
              title: "Loading usage",
              description: "Preparing current plan limits and usage counters.",
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
