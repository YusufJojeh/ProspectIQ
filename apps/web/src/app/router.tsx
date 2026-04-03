import { Navigate, Outlet, RouterProvider, createBrowserRouter, useParams } from "react-router-dom";
import { AppProviders } from "@/app/providers";
import { AppShell } from "@/app/layouts/app-shell";
import { appPaths } from "@/app/paths";
import { useAuthSession } from "@/features/auth/session";
import { LoginPage } from "@/features/auth/routes/login-page";
import { DashboardPage } from "@/features/dashboard/routes/dashboard-page";
import { HomePage } from "@/features/home/routes/home-page";
import { LeadDetailPage } from "@/features/lead-detail/routes/lead-detail-page";
import { LeadsPage } from "@/features/leads/routes/leads-page";
import { SearchesPage } from "@/features/searches/routes/searches-page";
import { SettingsPage } from "@/features/settings/routes/settings-page";

function LoginRoute() {
  const { isAuthenticated } = useAuthSession();

  if (isAuthenticated) {
    return <Navigate replace to={appPaths.dashboard} />;
  }

  return <LoginPage />;
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

function LegacyLeadDetailRedirect() {
  const { leadId } = useParams();

  if (!leadId) {
    return <Navigate replace to={appPaths.leads} />;
  }

  return <Navigate replace to={appPaths.leadDetail(leadId)} />;
}

const router = createBrowserRouter([
  {
    path: appPaths.home,
    element: <HomePage />,
  },
  {
    path: appPaths.login,
    element: <LoginRoute />,
  },
  {
    path: appPaths.dashboard,
    element: <ProtectedShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "searches", element: <SearchesPage /> },
      { path: "leads", element: <LeadsPage /> },
      { path: "leads/:leadId", element: <LeadDetailPage /> },
      { path: "settings", element: <SettingsPage /> },
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
