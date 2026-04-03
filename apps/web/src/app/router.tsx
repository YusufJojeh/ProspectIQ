import { Navigate, Outlet, RouterProvider, createBrowserRouter } from "react-router-dom";
import { AppProviders } from "@/app/providers";
import { AppShell } from "@/app/layouts/app-shell";
import { useAuthSession } from "@/features/auth/session";
import { LoginPage } from "@/features/auth/routes/login-page";
import { DashboardPage } from "@/features/dashboard/routes/dashboard-page";
import { LeadDetailPage } from "@/features/lead-detail/routes/lead-detail-page";
import { LeadsPage } from "@/features/leads/routes/leads-page";
import { SearchesPage } from "@/features/searches/routes/searches-page";
import { SettingsPage } from "@/features/settings/routes/settings-page";

function LoginRoute() {
  const { isAuthenticated } = useAuthSession();

  if (isAuthenticated) {
    return <Navigate replace to="/" />;
  }

  return <LoginPage />;
}

function ProtectedShell() {
  const { isAuthenticated } = useAuthSession();

  if (!isAuthenticated) {
    return <Navigate replace to="/login" />;
  }

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginRoute />,
  },
  {
    path: "/",
    element: <ProtectedShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "searches", element: <SearchesPage /> },
      { path: "leads", element: <LeadsPage /> },
      { path: "leads/:leadId", element: <LeadDetailPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);

export function AppRouterProvider() {
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
